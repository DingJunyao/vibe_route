# backend/app/services/animation_export.py

import asyncio
import json
import time
import uuid
from datetime import timedelta
from typing import Callable, Optional
from loguru import logger
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas.animation import AnimationExportRequest, AnimationExportTask as AnimationExportTaskSchema
from ..models.animation_task import AnimationExportTask
from ..models.base import get_utc_now
from ..models.track import Track, TrackPoint


class ExportQueueLimitError(Exception):
    """用户排队任务数达到上限"""


class AnimationExportService:
    """动画导出（录屏）任务队列服务

    任务状态落库（animation_export_tasks），本类是进程内调度器：
    按管理员配置的并发数从 pending 队列按创建时间先后启动录制。
    适用于单进程 uvicorn 部署；若未来多副本部署，各副本会各自调度，
    需改造为 DB 行锁/租约或外部队列（见 agents/features.md）。
    """

    def __init__(self):
        # task_id -> asyncio.Task（运行中的录制协程）
        self._running: dict[str, asyncio.Task] = {}
        # 已请求取消的 task_id（协作式取消信号，兼容 Windows 线程循环路径）
        self._cancel_requested: set[str] = set()

    # ---------- 配置 ----------

    async def _int_config(self, key: str, default: int) -> int:
        from ..core.database import async_session_maker
        from .config_service import config_service

        try:
            async with async_session_maker() as db:
                value = await config_service.get_json(db, key, default)
            return int(value)
        except Exception:
            return default

    # ---------- 入队 ----------

    async def start_export(
        self,
        track_id: int,
        user_id: int,
        token: str,
        request: AnimationExportRequest,
        db: AsyncSession,
    ) -> AnimationExportTaskSchema:
        """校验并创建导出任务（pending），随后触发调度"""
        # 获取轨迹点
        result = await db.execute(
            select(TrackPoint)
            .where(TrackPoint.track_id == track_id)
            .order_by(TrackPoint.point_index)
        )
        points = result.scalars().all()

        if len(points) < 2:
            raise ValueError("轨迹点数量不足，至少需要2个点")

        # 计算轨迹时长（毫秒），时间缺失时兜底 60s
        duration_ms = 60000.0
        if points[0].time and points[-1].time:
            duration_ms = (points[-1].time - points[0].time).total_seconds() * 1000

        # 单用户排队上限
        max_queued = await self._int_config('animation_export_max_queued_per_user', 3)
        if max_queued > 0:
            count_result = await db.execute(
                select(func.count())
                .select_from(AnimationExportTask)
                .where(
                    AnimationExportTask.user_id == user_id,
                    AnimationExportTask.status == 'pending',
                    AnimationExportTask.is_valid == True,  # noqa: E712
                )
            )
            queued = count_result.scalar() or 0
            if queued >= max_queued:
                raise ExportQueueLimitError(
                    f"排队任务已达上限（{max_queued} 个），请等待完成或到录屏任务页取消未开始的任务"
                )

        task_id = str(uuid.uuid4())
        task = AnimationExportTask(
            id=task_id,
            track_id=track_id,
            user_id=user_id,
            status='pending',
            progress=0.0,
            # 排队后才启动，参数与页面登录 token 随任务落库，启动时读取
            params=json.dumps(
                {'duration_ms': duration_ms, 'request': request.model_dump()},
                ensure_ascii=False,
            ),
            auth_token=token,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(task)
        await db.commit()

        await self.dispatch()

        return AnimationExportTaskSchema(
            task_id=task_id,
            status='pending',
            progress=0.0,
            track_id=track_id,
        )

    # ---------- 调度 ----------

    async def dispatch(self) -> None:
        """按当前并发配置启动 pending 任务（入队/任务结束/取消/改配置后调用）"""
        from ..core.database import async_session_maker

        # 回收已结束的协程引用（异常路径兜底，正常路径在 finally 中清理）
        for tid in [tid for tid, t in self._running.items() if t.done()]:
            self._running.pop(tid, None)

        concurrency = await self._int_config('animation_export_max_concurrency', 1)
        slots = concurrency - len(self._running)
        if slots <= 0:
            return

        now = get_utc_now()
        started: list[str] = []
        async with async_session_maker() as db:
            result = await db.execute(
                select(AnimationExportTask.id)
                .where(
                    AnimationExportTask.status == 'pending',
                    AnimationExportTask.is_valid == True,  # noqa: E712
                )
                .order_by(AnimationExportTask.created_at.asc(), AnimationExportTask.id.asc())
                .limit(slots)
            )
            candidates = [row[0] for row in result.all()]
            for tid in candidates:
                # 条件更新抢占：已在此间隙被取消的任务不会启动
                claim = await db.execute(
                    update(AnimationExportTask)
                    .where(AnimationExportTask.id == tid, AnimationExportTask.status == 'pending')
                    .values(status='processing', started_at=now, updated_at=now)
                )
                await db.commit()
                if claim.rowcount == 1:
                    started.append(tid)

        for tid in started:
            self._running[tid] = asyncio.create_task(self._run_export(tid))

    async def _run_export(self, task_id: str) -> None:
        """执行单个录制任务（调度器启动的协程）"""
        from ..core.database import async_session_maker
        from ..utils.playwright_export import capture_animation_video

        try:
            async with async_session_maker() as db:
                task = await db.get(AnimationExportTask, task_id)
                if task is None or task.status != 'processing':
                    return
                track_id = task.track_id
                params = json.loads(task.params or '{}')
                token = task.auth_token or ''
                request = AnimationExportRequest(**(params.get('request') or {}))
                duration_ms = float(params.get('duration_ms') or 60000.0)
                # token 用完即清，减少 DB 中的凭据存留
                task.auth_token = None
                await db.commit()

            last_progress_write = 0.0

            async def progress_callback(p: float):
                """进度回调（节流：写入间隔 <3s 时跳过，避免并发任务下 SQLite 写锁竞争）"""
                nonlocal last_progress_write
                now = time.monotonic()
                if p < 100.0 and now - last_progress_write < 3.0:
                    return
                last_progress_write = now
                async with async_session_maker() as db:
                    task = await db.get(AnimationExportTask, task_id)
                    if task and task.status == 'processing':
                        task.progress = p
                        await db.commit()

            download_url = await capture_animation_video(
                track_id=track_id,
                duration_ms=duration_ms,
                token=token,
                request=request,
                progress_callback=progress_callback,
                task_id=task_id,
                cancel_check=lambda: task_id in self._cancel_requested,
            )

            async with async_session_maker() as db:
                task = await db.get(AnimationExportTask, task_id)
                if task and task.status == 'processing':
                    task.status = 'completed'
                    task.progress = 100.0
                    task.download_url = download_url
                    task.finished_at = get_utc_now()
                    await db.commit()

        except asyncio.CancelledError:
            # 用户取消路径：DELETE 已先把状态置为 cancelled，这里无需改写；
            # 服务关闭路径：状态仍是 processing，标记中断
            try:
                async with async_session_maker() as db:
                    task = await db.get(AnimationExportTask, task_id)
                    if task and task.status == 'processing':
                        task.status = 'failed'
                        task.error = '服务关闭，任务中断'
                        task.finished_at = get_utc_now()
                        await db.commit()
            except Exception:
                pass
            raise

        except Exception as e:
            logger.exception(f"Animation export failed for task {task_id}: {e}")
            try:
                async with async_session_maker() as db:
                    task = await db.get(AnimationExportTask, task_id)
                    # 状态已被取消时不得覆盖为 failed
                    if task and task.status == 'processing':
                        task.status = 'failed'
                        task.error = "导出失败"
                        task.finished_at = get_utc_now()
                        await db.commit()
            except Exception:
                pass

        finally:
            self._running.pop(task_id, None)
            self._cancel_requested.discard(task_id)
            # 释放并发槽位后立即排上下一个任务；关闭阶段循环可能已停，忽略报错
            try:
                asyncio.get_running_loop().create_task(self.dispatch())
            except RuntimeError:
                pass

    # ---------- 取消 ----------

    async def cancel_task(self, task_id: str) -> Optional[str]:
        """取消任务：pending 直接出队，processing 中断录制。返回取消后的状态。"""
        from ..core.database import async_session_maker

        async with async_session_maker() as db:
            task = await db.get(AnimationExportTask, task_id)
            if task is None or task.status not in ('pending', 'processing'):
                return task.status if task else None
            task.status = 'cancelled'
            task.error = '用户取消'
            task.finished_at = get_utc_now()
            await db.commit()

        if task_id in self._running:
            # 录制协程里的 DB 写入会复查状态，不会覆盖 cancelled
            self._cancel_requested.add(task_id)
            running = self._running[task_id]
            if not running.done():
                running.cancel()

        # 立即排上接下来的排队任务
        try:
            asyncio.get_running_loop().create_task(self.dispatch())
        except RuntimeError:
            pass
        return 'cancelled'

    async def cancel_all(self) -> None:
        """服务关闭时终止全部运行中的录制"""
        tasks = [t for t in self._running.values() if not t.done()]
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    # ---------- 重启恢复 ----------

    async def recover_on_startup(self) -> None:
        """启动时恢复队列：遗留 processing 标记中断，pending 重新入队"""
        from ..core.database import async_session_maker

        async with async_session_maker() as db:
            result = await db.execute(
                update(AnimationExportTask)
                .where(AnimationExportTask.status == 'processing')
                .values(
                    status='failed',
                    error='服务重启，任务中断',
                    finished_at=get_utc_now(),
                    updated_at=get_utc_now(),
                )
            )
            await db.commit()
            if result.rowcount:
                logger.info(f"Marked {result.rowcount} interrupted animation export tasks as failed")

        await self.dispatch()


animation_export_service = AnimationExportService()
