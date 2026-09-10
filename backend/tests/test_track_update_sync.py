# -*- coding: utf-8 -*-
"""编辑轨迹时同步点级 region（sync_points_region）测试。

背景：图标渲染的权威是点级 track_points.region，轨迹级 tracks.region 只是新点的默认值。
在无同步开关前，把一条点级全是 'cn' 的印尼轨迹改成 region='id' 不会产生任何盾牌。
"""
import asyncio

from app.models import Track, TrackPoint
from app.schemas.track import TrackUpdate
from app.services.track_service import track_service
from conftest import _db_env, _track_points


def _make_track(db, user, region='cn', n_points=3):
    track = Track(
        user_id=user.id, name='t', original_filename='t.gpx',
        original_crs='wgs84', region=region, created_by=user.id, updated_by=user.id,
    )
    db.add(track)
    return track


async def _seed(db, user, point_region='cn', n=3):
    track = _make_track(db, user)
    await db.commit()
    await db.refresh(track)
    db.add_all([
        TrackPoint(track_id=track.id, point_index=i,
                   latitude_wgs84=-7.28, longitude_wgs84=112.73,
                   region=point_region, created_by=user.id, updated_by=user.id)
        for i in range(n)
    ])
    await db.commit()
    return track


def test_sync_flips_all_points(workdir):
    """region='id' + sync=True → 全点点级 region 刷新（模拟 track 85 现状）"""

    async def _run():
        async with _db_env(workdir) as (db, user):
            track = await _seed(db, user, point_region='cn')
            await track_service.update(
                db, track, TrackUpdate(region='id', sync_points_region=True), user.id)
            assert track.region == 'id'
            assert {p.region for p in await _track_points(db, track.id)} == {'id'}

    asyncio.run(_run())


def test_no_sync_leaves_points_untouched(workdir):
    """不带 sync → 点级不动（轨迹级只是新点默认值）"""

    async def _run():
        async with _db_env(workdir) as (db, user):
            track = await _seed(db, user, point_region='cn')
            await track_service.update(db, track, TrackUpdate(region='id'), user.id)
            assert track.region == 'id'
            assert {p.region for p in await _track_points(db, track.id)} == {'cn'}

    asyncio.run(_run())


def test_sync_without_region_is_noop(workdir):
    """sync=True 但未给 region → 静默 no-op，不抛 AttributeError"""

    async def _run():
        async with _db_env(workdir) as (db, user):
            track = await _seed(db, user, point_region='cn')
            await track_service.update(
                db, track, TrackUpdate(name='改名', sync_points_region=True), user.id)
            assert track.name == '改名'
            assert track.region == 'cn'
            assert {p.region for p in await _track_points(db, track.id)} == {'cn'}

    asyncio.run(_run())


def test_rename_with_sync_false_does_not_touch_points(workdir):
    """改名不动点级（前端仅在 regionChanged 时才发 sync，双保险）"""

    async def _run():
        async with _db_env(workdir) as (db, user):
            track = await _seed(db, user, point_region='id')
            await track_service.update(db, track, TrackUpdate(name='改名'), user.id)
            assert {p.region for p in await _track_points(db, track.id)} == {'id'}

    asyncio.run(_run())


def test_sync_back_to_cn(workdir):
    """反向同步：id → cn 同样生效（点级权威，两个方向一致）"""

    async def _run():
        async with _db_env(workdir) as (db, user):
            track = await _seed(db, user, point_region='id')
            await track_service.update(
                db, track, TrackUpdate(region='cn', sync_points_region=True), user.id)
            assert {p.region for p in await _track_points(db, track.id)} == {'cn'}

    asyncio.run(_run())


def test_api_patch_accepts_sync_flag(workdir):
    """API 层：TrackUpdate 透传 sync_points_region（schema 校验 + 非 Track 列不落 setattr）"""

    async def _run():
        async with _db_env(workdir) as (db, user):
            track = await _seed(db, user, point_region='cn')
            update = TrackUpdate.model_validate(
                {'region': 'id', 'sync_points_region': True})
            await track_service.update(db, track, update, user.id)
            assert {p.region for p in await _track_points(db, track.id)} == {'id'}

    asyncio.run(_run())


def test_sync_rejects_unknown_region(workdir):
    """region 值域仍受 schema 约束"""
    import pytest
    with pytest.raises(ValueError):
        TrackUpdate.model_validate({'region': 'us', 'sync_points_region': True})
