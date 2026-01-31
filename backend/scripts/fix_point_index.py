"""
修复实时记录轨迹的 point_index 问题

问题：由于并发竞态条件，实时记录的所有点的 point_index 都是 0
解决方案：按 created_at 顺序重新分配 point_index
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from datetime import datetime
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from loguru import logger

from app.models.track import Track, TrackPoint
from app.core.config import settings


async def fix_track_point_index(db: AsyncSession, track_id: int) -> dict:
    """
    修复指定轨迹的 point_index

    Args:
        db: 数据库会话
        track_id: 轨迹 ID

    Returns:
        修复结果字典
    """
    # 获取所有点，按 time 排序（GPS 时间是轨迹的真正顺序）
    # 对于 time 为 NULL 的点，使用 created_at 作为后备
    points_result = await db.execute(
        select(TrackPoint)
        .where(
            and_(
                TrackPoint.track_id == track_id,
                TrackPoint.is_valid == True
            )
        )
        .order_by(TrackPoint.time.asc(), TrackPoint.created_at.asc())
    )
    points = points_result.scalars().all()

    if not points:
        return {
            "track_id": track_id,
            "status": "skipped",
            "message": "没有找到轨迹点"
        }

    # 检查是否需要修复
    needs_fix = False
    for i, point in enumerate(points):
        if point.point_index != i:
            needs_fix = True
            break

    if not needs_fix:
        logger.info(f"Track {track_id}: point_index 已正确，无需修复")
        return {
            "track_id": track_id,
            "status": "ok",
            "message": "point_index 已正确",
            "point_count": len(points)
        }

    # 重新分配 point_index
    logger.info(f"Track {track_id}: 开始修复 {len(points)} 个点的 point_index")
    updated_count = 0
    for i, point in enumerate(points):
        if point.point_index != i:
            point.point_index = i
            point.updated_at = datetime.now()
            updated_count += 1

    # 重新计算距离
    total_distance = 0.0
    total_duration = 0
    elevation_gain = 0.0
    elevation_loss = 0.0

    if len(points) >= 2:
        from app.services.spatial import PythonSpatialService
        spatial = PythonSpatialService()

        for i in range(1, len(points)):
            prev_point = points[i - 1]
            curr_point = points[i]

            # 计算距离
            if curr_point.latitude_wgs84 and curr_point.longitude_wgs84:
                distance = await spatial.distance(
                    prev_point.latitude_wgs84, prev_point.longitude_wgs84,
                    curr_point.latitude_wgs84, curr_point.longitude_wgs84
                )
                total_distance += distance

            # 计算爬升/下降
            if curr_point.elevation is not None and prev_point.elevation is not None:
                diff = curr_point.elevation - prev_point.elevation
                if diff > 0:
                    elevation_gain += diff
                else:
                    elevation_loss += abs(diff)

        # 计算时长
        first_point = points[0]
        last_point = points[-1]
        if first_point.time and last_point.time:
            total_duration = int((last_point.time - first_point.time).total_seconds())

    # 更新轨迹统计
    track_result = await db.execute(
        select(Track).where(
            and_(
                Track.id == track_id,
                Track.is_valid == True
            )
        )
    )
    track = track_result.scalar_one_or_none()
    if track:
        old_distance = track.distance
        track.distance = round(total_distance, 2)
        track.duration = total_duration
        track.elevation_gain = round(elevation_gain, 2)
        track.elevation_loss = round(elevation_loss, 2)

        logger.info(f"Track {track_id}: 距离从 {old_distance:.2f}m 更新为 {track.distance:.2f}m")

    await db.commit()

    logger.info(f"Track {track_id}: 已修复 {updated_count} 个点")

    return {
        "track_id": track_id,
        "status": "fixed",
        "point_count": len(points),
        "updated_count": updated_count,
        "old_distance": old_distance if track else None,
        "new_distance": track.distance if track else None,
    }


async def main():
    """主函数"""
    logger.info("开始修复实时记录轨迹的 point_index")

    # 创建数据库连接
    database_url = settings.DATABASE_URL
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # 获取所有实时记录轨迹
        tracks_result = await db.execute(
            select(Track).where(
                and_(
                    Track.is_live_recording == True,
                    Track.is_valid == True
                )
            )
        )
        live_tracks = tracks_result.scalars().all()

        logger.info(f"找到 {len(live_tracks)} 条实时记录轨迹")

        results = []
        for track in live_tracks:
            result = await fix_track_point_index(db, track.id)
            results.append(result)

        # 打印汇总
        logger.info("\n=== 修复结果汇总 ===")
        for r in results:
            if r["status"] == "fixed":
                logger.info(
                    f"Track {r['track_id']}: 修复了 {r['updated_count']}/{r['point_count']} 个点, "
                    f"距离: {r['old_distance']:.2f}m -> {r['new_distance']:.2f}m"
                )
            elif r["status"] == "ok":
                logger.info(f"Track {r['track_id']}: 已正确 ({r['point_count']} 个点)")
            else:
                logger.warning(f"Track {r['track_id']}: {r['message']}")

    await engine.dispose()
    logger.info("修复完成")


if __name__ == "__main__":
    asyncio.run(main())
