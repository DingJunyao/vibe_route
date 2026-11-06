"""
邮件服务层

录屏任务完成/失败通知邮件：
- SMTP 配置存 configs 表 email_config（后台管理界面可改，host 为空 = 未配置）
- 总开关 email_notification_enabled（管理员），用户级开关 user_configs.notify_recording_*
- 模板存 email_templates 表（管理员可编辑，支持 {{variable}} 占位符）

发送走 fire-and-forget 协程（schedule_notify），任何失败只记日志，绝不影响导出流程。
"""
import asyncio
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Optional

import aiosmtplib
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.animation_task import AnimationExportTask
from app.models.email_template import EmailTemplate
from app.models.track import Track
from app.models.user import User
from app.models.user_config import UserConfig
from app.services.config_service import config_service


# 邮件模板默认内容（启动时种子化，管理员可在后台管理中编辑）
DEFAULT_TEMPLATES = {
    "recording_completed": {
        "subject": "【{{app_name}}】录屏任务已完成",
        "body": (
            "{{username}} 您好，\n"
            "\n"
            "您的录屏任务已完成。\n"
            "\n"
            "轨迹名称：{{track_name}}\n"
            "完成时间：{{finished_at}}\n"
            "下载地址：{{download_url}}\n"
            "\n"
            "本邮件为系统自动发送，请勿直接回复。"
        ),
        "is_html": False,
    },
    "recording_failed": {
        "subject": "【{{app_name}}】录屏任务失败",
        "body": (
            "{{username}} 您好，\n"
            "\n"
            "很遗憾，您的录屏任务执行失败。\n"
            "\n"
            "轨迹名称：{{track_name}}\n"
            "失败时间：{{finished_at}}\n"
            "失败原因：{{error}}\n"
            "\n"
            "您可以登录系统重新发起录屏任务。\n"
            "本邮件为系统自动发送，请勿直接回复。"
        ),
        "is_html": False,
    },
}


def render_template(text: str, context: dict) -> str:
    """替换 {{variable}} 占位符；未提供的变量保留原文，便于排查模板问题"""
    for key, value in context.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text


class EmailService:
    """邮件通知服务（模块级单例）"""

    def __init__(self):
        # 持有后台任务引用，防止被垃圾回收
        self._bg_tasks: set[asyncio.Task] = set()

    # ---------- SMTP ----------

    @staticmethod
    def is_smtp_configured(email_config: dict) -> bool:
        """SMTP 是否已配置（host 非空即视为已配置）"""
        return bool((email_config or {}).get("host", "").strip())

    async def send_email(
        self,
        email_config: dict,
        to_email: str,
        subject: str,
        body: str,
        is_html: bool = False,
    ) -> None:
        """
        通过 SMTP 发送一封邮件（读取传入的 email_config，不做开关判断）

        失败抛异常，由调用方决定如何处理。
        """
        from_email = (email_config.get("from_email") or email_config.get("username") or "").strip()
        if not from_email:
            from_email = (email_config.get("host") or "").split(".", 1)[0] or "vibe-route"

        message = MIMEText(body, "html" if is_html else "plain", "utf-8")
        message["Subject"] = subject
        message["From"] = formataddr((settings.APP_NAME, from_email))
        message["To"] = to_email

        await aiosmtplib.send(
            message,
            hostname=email_config["host"].strip(),
            port=int(email_config.get("port") or 465),
            username=(email_config.get("username") or "").strip() or None,
            password=email_config.get("password") or None,
            use_tls=bool(email_config.get("use_ssl")),
            start_tls=bool(email_config.get("starttls")) and not bool(email_config.get("use_ssl")),
            timeout=30,
        )

    # ---------- 通知 ----------

    async def notify_recording_result(
        self,
        user_id: int,
        task_id: str,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """
        录屏任务完成/失败通知（自持数据库会话，供后台协程直接调用）

        判定链：总开关 → 用户级开关 → 用户邮箱 → SMTP 配置 → 模板存在。
        任一不满足则跳过（记 info/warning 日志），SMTP 发送失败记 error 日志。
        """
        from app.core.database import async_session_maker

        async with async_session_maker() as db:
            try:
                await self._notify_with_session(db, user_id, task_id, success, error)
            except Exception as e:
                logger.error(f"发送录屏通知邮件失败 (task={task_id}, success={success}): {e}")

    async def _notify_with_session(
        self,
        db: AsyncSession,
        user_id: int,
        task_id: str,
        success: bool,
        error: Optional[str],
    ) -> None:
        # 1. 管理员总开关
        configs = await config_service.get_all_configs(db)
        if not configs.get("email_notification_enabled", False):
            logger.info(f"邮件通知总开关关闭，跳过发送 (task={task_id})")
            return
        email_config = configs.get("email_config") or {}
        if not self.is_smtp_configured(email_config):
            logger.warning("SMTP 未配置（email_config.host 为空），跳过发送")
            return

        # 2. 用户级开关与邮箱
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if user is None or not user.email:
            logger.warning(f"用户不存在或无邮箱，跳过发送 (user_id={user_id}, task={task_id})")
            return

        user_config_result = await db.execute(
            select(UserConfig).where(UserConfig.user_id == user_id, UserConfig.is_valid == True)  # noqa: E712
        )
        user_config = user_config_result.scalar_one_or_none()
        # 无用户配置行 = 两个开关都视为关闭
        if user_config is None:
            logger.info(f"用户未开启录屏邮件通知，跳过发送 (user_id={user_id}, task={task_id})")
            return
        want_notify = user_config.notify_recording_completed if success else user_config.notify_recording_failed
        if not want_notify:
            logger.info(f"用户未开启该类型邮件通知 (user_id={user_id}, task={task_id}, success={success})")
            return

        # 3. 任务与轨迹信息（用于模板上下文）
        task_result = await db.execute(select(AnimationExportTask).where(AnimationExportTask.id == task_id))
        task = task_result.scalar_one_or_none()
        track_name = ""
        if task is not None and task.track_id:
            track_result = await db.execute(select(Track).where(Track.id == task.track_id))
            track = track_result.scalar_one_or_none()
            if track is not None:
                track_name = track.name or ""
        finished_at = task.finished_at if task is not None else None
        finished_at_str = (
            finished_at.strftime("%Y-%m-%d %H:%M:%S") + " UTC"
            if finished_at
            else datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " UTC"
        )

        # 4. 模板
        template_key = "recording_completed" if success else "recording_failed"
        template_result = await db.execute(
            select(EmailTemplate).where(
                EmailTemplate.template_key == template_key,
                EmailTemplate.is_valid == True,  # noqa: E712
            )
        )
        template = template_result.scalar_one_or_none()
        if template is None:
            logger.warning(f"邮件模板不存在，跳过发送 (template_key={template_key})")
            return

        # 5. 渲染并发送
        download_url = f"{settings.FRONTEND_URL.rstrip('/')}/api/animation/export/{task_id}/download"
        context = {
            "app_name": settings.APP_NAME,
            "username": user.username,
            "track_name": track_name,
            "finished_at": finished_at_str,
            "error": error or ("导出失败" if not success else ""),
            "download_url": download_url,
        }
        subject = render_template(template.subject, context)
        body = render_template(template.body, context)

        await self.send_email(
            email_config=email_config,
            to_email=user.email,
            subject=subject,
            body=body,
            is_html=bool(template.is_html),
        )
        logger.info(f"录屏通知邮件已发送 (to={user.email}, template={template_key}, task={task_id})")

    def schedule_notify(
        self,
        user_id: int,
        task_id: str,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """
        以 fire-and-forget 方式调度通知（不阻塞导出流程，异常只记日志）

        必须在运行中的事件循环内调用；无事件循环（如启动恢复前）时静默跳过。
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning(f"无运行中的事件循环，跳过录屏通知调度 (task={task_id})")
            return
        bg_task = loop.create_task(self.notify_recording_result(user_id, task_id, success, error))
        self._bg_tasks.add(bg_task)
        bg_task.add_done_callback(self._bg_tasks.discard)

    # ---------- 模板初始化 ----------

    async def init_default_templates(self, db: AsyncSession, user_id: int = 1) -> None:
        """初始化默认邮件模板（已存在的 key 不覆盖，管理员编辑内容得以保留）"""
        for template_key, defaults in DEFAULT_TEMPLATES.items():
            # 存在性检查包含软删除墓碑（template_key 唯一索引仍被墓碑占用）
            result = await db.execute(
                select(EmailTemplate).where(
                    EmailTemplate.template_key == template_key,
                )
            )
            template = result.scalar_one_or_none()
            if template is not None:
                # 有效模板不覆盖，保留管理员编辑；墓碑复活以恢复模板可用
                if not template.is_valid:
                    template.is_valid = True
                    template.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                continue

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            template = EmailTemplate(
                template_key=template_key,
                subject=defaults["subject"],
                body=defaults["body"],
                is_html=defaults["is_html"],
                created_by=user_id,
                updated_by=user_id,
                created_at=now,
                updated_at=now,
                is_valid=True,
            )
            db.add(template)

        await db.commit()


email_service = EmailService()
