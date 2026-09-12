# -*- coding: utf-8 -*-
"""上传/创建/合并链路的 region 贯通回归守卫

覆盖：API Form → create_* 签名 → Track() 构造 → 5 处批量插入 → 详情/点/公开分享响应。
用 workdir 下的独立 SQLite（不触真实库、不跑 alembic）。
点级 region 是唯一带默认值的字段（漏传不报错、被默认值静默掩盖），故必须逐个生产者守卫。
"""
import asyncio
import io
import zipfile

import pytest
from fastapi import HTTPException, UploadFile

from app.api import live_recordings, overlay_templates, shared, tracks
from app.models.live_recording import LiveRecording
from app.models.overlay_template import OverlayTemplate
from app.models.user import User
from app.schemas.interpolation import InterpolationCreateRequest
from app.services.config_service import config_service
from app.services.interpolation_service import interpolation_service
from app.services.overlay_template_service import (
    OverlayTemplateService,
    resolve_contained_path,
    safe_font_basename,
)
from app.services.track_service import track_service
from conftest import _db_env, _gpx, _track_points


def _csv_gps_logger(hour=8):
    return (
        'time,lat,lon,elevation,speed,bearing\n'
        f'2026-09-01T{hour:02d}:00:00.000Z,-7.280,112.735,10,1.0,90\n'
        f'2026-09-01T{hour:02d}:00:10.000Z,-7.281,112.736,12,1.0,90\n'
    )


def _csv_project():
    return (
        'index,time_date,time_time,longitude_wgs84,latitude_wgs84\n'
        '0,2026/09/01,08:00:00,112.7350,-7.2800\n'
        '1,2026/09/01,08:00:10,112.7360,-7.2810\n'
    )


def _xlsx():
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(['index', 'time_date', 'time_time', 'longitude_wgs84', 'latitude_wgs84'])
    ws.append([0, '2026/09/01', '08:00:00', 112.7350, -7.2800])
    ws.append([1, '2026/09/01', '08:00:10', 112.7360, -7.2810])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _kml(hour=8):
    coords = ''.join(
        f'<when>2026-09-01T{hour:02d}:00:{i * 10:02d}Z</when>'
        f'<gx:coord>{112.735 + i * 0.001} {-7.280 - i * 0.001} {10 + i}</gx:coord>'
        for i in range(2)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2">'
        f'<Document><Placemark><gx:Track>{coords}</gx:Track></Placemark></Document></kml>'
    )


def _kmz():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('doc.kml', _kml())
    return buf.getvalue()


# 五个上传分支（此前只有 gpx 被测过：删掉 xlsx/kmz 分支的 region=region, 曾全绿）
_UPLOAD_CASES = [
    ('t.gpx', _gpx),
    ('t.csv', _csv_project),
    ('t.xlsx', _xlsx),
    ('t.kml', _kml),
    ('t.kmz', _kmz),
]


class TestServiceRegion:
    """create_* / merge_tracks 签名 → Track() → 批量插入"""

    def test_gpx(self, workdir):
        async def case():
            async with _db_env(workdir) as (db, user):
                track = await track_service.create_from_gpx(
                    db, user, 't.gpx', _gpx(), 't', region='id'
                )
                assert track.region == 'id'
                assert {p.region for p in await _track_points(db, track.id)} == {'id'}

        asyncio.run(case())

    def test_csv_gps_logger(self, workdir):
        async def case():
            async with _db_env(workdir) as (db, user):
                track = await track_service.create_from_csv(
                    db, user, 't.csv', _csv_gps_logger(), 't', region='id'
                )
                assert track.region == 'id'
                assert {p.region for p in await _track_points(db, track.id)} == {'id'}

        asyncio.run(case())

    def test_csv_project_format(self, workdir):
        async def case():
            async with _db_env(workdir) as (db, user):
                track = await track_service.create_from_csv(
                    db, user, 't.csv', _csv_project(), 't', region='id'
                )
                assert track.region == 'id'
                assert {p.region for p in await _track_points(db, track.id)} == {'id'}

        asyncio.run(case())

    def test_xlsx(self, workdir):
        async def case():
            async with _db_env(workdir) as (db, user):
                track = await track_service.create_from_xlsx(
                    db, user, 't.xlsx', _xlsx(), 't', region='id'
                )
                assert track.region == 'id'
                assert {p.region for p in await _track_points(db, track.id)} == {'id'}

        asyncio.run(case())

    def test_kml(self, workdir):
        async def case():
            async with _db_env(workdir) as (db, user):
                track = await track_service.create_from_kml(
                    db, user, 't.kml', _kml(), 't', region='id'
                )
                assert track.region == 'id'
                assert {p.region for p in await _track_points(db, track.id)} == {'id'}

        asyncio.run(case())

    def test_default_is_cn(self, workdir):
        """不传 region 的既有调用点（如 live_recording_service）不得被改变"""

        async def case():
            async with _db_env(workdir) as (db, user):
                track = await track_service.create_from_gpx(db, user, 't.gpx', _gpx(), 't')
                assert track.region == 'cn'
                assert {p.region for p in await _track_points(db, track.id)} == {'cn'}

        asyncio.run(case())

    def test_merge_keeps_per_point_region(self, workdir):
        """合并：产物 track.region 取首段源轨迹，点级 region 与 4 个 *_id 逐点复制

        每个点的 4 个 *_id 值唯一（轨号 + 点序 + 字段序号），断言按排序后的集合比较：
        既钉住「逐点复制」不串字段，也钉住同轨点位不取错，同时不规定同轨内点序。
        """

        async def case():
            async with _db_env(workdir) as (db, user):
                a = await track_service.create_from_gpx(db, user, 'a.gpx', _gpx(8), 'a', region='id')
                b = await track_service.create_from_gpx(db, user, 'b.gpx', _gpx(9), 'b', region='cn')

                # 合并前给两轨的点各赋互不相同的 *_id：值里编入「轨号 + 点序 + 字段序号」，
                # 使同轨两点的值也彼此不同 —— 任取错来源（如 province_id=p.city_id）、整体漏复制、
                # 或「点取错」（如把同轨第一个点的值复制给了第二个点）都会让下面的断言变红。
                # 这 4 个字段是 Task 10 collect_names 直读的字段，写错会静默污染多语 tooltip。
                id_fields = ('province_id', 'city_id', 'district_id', 'road_name_id')
                for track, prefix in ((a, 'A'), (b, 'B')):
                    for i, pt in enumerate(await _track_points(db, track.id), start=1):
                        for n, field in enumerate(id_fields, start=1):
                            setattr(pt, field, f'{prefix}{i}{n}')
                await db.commit()

                # 刻意倒转入参顺序：a 是较早轨迹但不是首参 → 取 track_ids[0] 的实现会红
                merged = await track_service.merge_tracks(db, user, [b.id, a.id], 'm')
                assert merged.region == 'id'  # 取 start_time 较早者，而非入参首个
                # 源点只有 *_id 列有值（中文/英文列全空）→ 合并产物的标志必须同导入路径的口径，
                # 否则前端 `!has_area_info && !has_road_info` 会直接清空区域树（用户可见且静默）
                assert merged.has_area_info is True
                assert merged.has_road_info is True
                points = await _track_points(db, merged.id)
                assert [p.region for p in points] == ['id', 'id', 'cn', 'cn']  # 逐点复制，非统一填充
                # 每个合并后的点必须带着它原来那个点的 4 个 *_id（merge 只复制这几列）。
                # 排序后比较：同轨两点谁先谁后由上面的 region 断言钉住，此处只负责「多点集合正确」，
                # 不引入「同轨内点序」这一脆弱前提；同轨两点值互不相同 → 点位错位必红。
                got = sorted(tuple(getattr(p, f) for f in id_fields) for p in points)
                assert got == sorted([
                    ('A11', 'A12', 'A13', 'A14'), ('A21', 'A22', 'A23', 'A24'),
                    ('B11', 'B12', 'B13', 'B14'), ('B21', 'B22', 'B23', 'B24'),
                ])

        asyncio.run(case())


class TestUploadEndpoint:
    """upload Form → create_* 调用透传 → TrackResponse"""

    @staticmethod
    def _file(filename, factory):
        data = factory()
        if isinstance(data, str):
            data = data.encode('utf-8')
        return UploadFile(filename=filename, file=io.BytesIO(data))

    @pytest.mark.parametrize(
        'filename,factory', _UPLOAD_CASES, ids=[c[1].__name__ for c in _UPLOAD_CASES]
    )
    def test_region_passthrough(self, workdir, filename, factory):
        """五个上传分支（gpx/csv/xlsx/kml/kmz）都要把 region 透传到 create_*"""

        async def case():
            async with _db_env(workdir) as (db, user):
                resp = await tracks.upload_track(
                    file=self._file(filename, factory), name='t', description=None,
                    original_crs='wgs84', convert_to=None, fill_geocoding=False,
                    region='id', current_user=user, db=db,
                )
                assert resp.region == 'id'
                assert {p.region for p in await _track_points(db, resp.id)} == {'id'}

        asyncio.run(case())

    def test_upload_without_region_form_defaults_to_cn(self, workdir):
        """请求真的不带 region 字段 → 钉住 `Form("cn")` 默认值

        `test_default_is_cn` 测的是 service 层形参默认值；Form 默认值若被改成 "id"，
        所有不传该字段的既有客户端上传都会被静默标成印尼。
        """

        async def case():
            async with _db_env(workdir) as (db, user):
                from app.core.config import settings
                from app.core.database import get_db
                from app.core.deps import get_current_user
                from app.main import app
                from httpx import ASGITransport, AsyncClient

                async def _override_db():
                    yield db

                app.dependency_overrides[get_db] = _override_db
                app.dependency_overrides[get_current_user] = lambda: user
                try:
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url='http://test'
                    ) as client:
                        resp = await client.post(
                            f"{settings.API_V1_PREFIX}/tracks/upload",
                            data={'name': 't', 'original_crs': 'wgs84'},  # 刻意不含 region
                            files={'file': ('t.gpx', _gpx().encode('utf-8'), 'application/gpx+xml')},
                        )
                finally:
                    # 只摘自己设的两个键：clear() 会连带摘掉其他用例的 override
                    app.dependency_overrides.pop(get_db, None)
                    app.dependency_overrides.pop(get_current_user, None)

                assert resp.status_code == 200, resp.text
                assert resp.json()['region'] == 'cn'
                assert {p.region for p in await _track_points(db, resp.json()['id'])} == {'cn'}

        asyncio.run(case())

    def test_invalid_region_rejected(self, workdir):
        async def case():
            async with _db_env(workdir) as (db, user):
                with pytest.raises(HTTPException) as exc:
                    await tracks.upload_track(
                        file=self._file('t.gpx', _gpx), name='t', description=None,
                        original_crs='wgs84', convert_to=None, fill_geocoding=False,
                        region='us', current_user=user, db=db,
                    )
                assert exc.value.status_code == 400

        asyncio.run(case())


class TestMultilingualFieldPassthrough:
    """4 个 *_id 字段的取值守卫（质量审 I1：此前只断言键在不在、不断言值从哪来）

    四个哨兵值必须互不相同，否则「传错来源」（如 province_id=p.city_id）照样绿。
    """

    def test_id_fields_value_source(self, workdir):
        async def case():
            async with _db_env(workdir) as (db, user):
                track = await track_service.create_from_gpx(
                    db, user, 't.gpx', _gpx(), 't', region='id'
                )
                pt = (await _track_points(db, track.id))[0]
                pt.province_id, pt.city_id, pt.district_id, pt.road_name_id = (
                    'PID', 'CID', 'DID', 'RID'
                )
                await db.commit()

                # 消费者 ①：GET /tracks/{id}/points
                points = await tracks.get_track_points(
                    track.id, crs='wgs84', current_user=user, db=db
                )
                p = points['points'][0]
                assert (p['province_id'], p['city_id'], p['district_id'], p['road_name_id']) == (
                    'PID', 'CID', 'DID', 'RID'
                )

                # 消费者 ②：公开分享页
                track.share_token = 'tok-id-fields'
                track.is_shared = True
                await db.commit()

                resp = await shared.get_shared_track('tok-id-fields', db=db)
                sp = resp.points[0]
                assert (sp.province_id, sp.city_id, sp.district_id, sp.road_name_id) == (
                    'PID', 'CID', 'DID', 'RID'
                )

        asyncio.run(case())


class TestSerializationRegion:
    """详情 / 点 / 公开分享 / unified 列表的响应字段"""

    def test_detail_and_points(self, workdir):
        async def case():
            async with _db_env(workdir) as (db, user):
                track = await track_service.create_from_gpx(
                    db, user, 't.gpx', _gpx(), 't', region='id'
                )
                detail = await tracks.get_track(track.id, current_user=user, db=db)
                assert detail.region == 'id'

                points = await tracks.get_track_points(track.id, crs='wgs84', current_user=user, db=db)
                assert {p['region'] for p in points['points']} == {'id'}

        asyncio.run(case())

    def test_public_poster_detail(self, workdir):
        """海报公开端点（手工构造 dict，与详情端点同类缺口）"""

        async def case():
            async with _db_env(workdir) as (db, user):
                track = await track_service.create_from_gpx(
                    db, user, 't.gpx', _gpx(), 't', region='id'
                )
                # 该端点直接返回手工 dict（response_model 仅在 FastAPI 线上生效）
                detail = await tracks.get_track_public(
                    track.id, current_user=user, db=db
                )
                assert detail['region'] == 'id'

        asyncio.run(case())

    def test_shared_page_points(self, workdir):
        async def case():
            async with _db_env(workdir) as (db, user):
                track = await track_service.create_from_gpx(
                    db, user, 't.gpx', _gpx(), 't', region='id'
                )
                track.share_token = 'tok-region'
                track.is_shared = True
                await db.commit()

                resp = await shared.get_shared_track('tok-region', db=db)
                assert {p.region for p in resp.points} == {'id'}

        asyncio.run(case())

    def test_unified_list(self, workdir):
        async def case():
            async with _db_env(workdir) as (db, user):
                track = await track_service.create_from_gpx(
                    db, user, 't.gpx', _gpx(), 't', region='id'
                )
                # 无关联轨迹的实时记录 → 虚拟项
                db.add(LiveRecording(user_id=user.id, token='vtok', name='rec', status='active'))
                await db.commit()

                items, _ = await track_service.get_unified_list(db, user.id)
                by_id = {i['id']: i for i in items}
                assert by_id[track.id]['region'] == 'id'
                assert by_id[-1]['region'] == 'cn'  # 虚拟实时项无轨迹，固定 'cn'

        asyncio.run(case())


class TestInterpolationRegion:
    """插值点 region 继承区段锚点（点级权威），不得落到模型默认 'cn'

    `interpolation_service._insert_interpolated_points` 构造 TrackPoint 时不传 region，
    点就落默认值 'cn'：印尼轨迹插值后，这些点会在区域树里以 region=cn 冒出一个
    「未知区域」根节点与 id 分组并列，导出 CSV 也会 cn/id 行混杂。
    """

    def test_inherits_anchor_region(self, workdir):
        """锚点优先于行级；锚点缺失才回退 tracks.region"""

        async def case():
            async with _db_env(workdir) as (db, user):
                # ① 常规：id 轨迹的插值点必须是 'id'（漏传 region 时这里是 'cn'）
                a = await track_service.create_from_gpx(db, user, 'a.gpx', _gpx(), 'a', region='id')

                # ② 锚点与行级不一致：编辑轨迹地区默认只改行级，勾选 sync_points_region
                #    才批量覆盖已有点级；故此处必须取锚点的 'cn'
                #    —— 用 tracks.region（'id'）顶替的实现在这里变红
                b = await track_service.create_from_gpx(db, user, 'b.gpx', _gpx(), 'b', region='id')
                (await _track_points(db, b.id))[0].region = 'cn'
                await db.commit()

                for track, expected in ((a, 'id'), (b, 'cn')):
                    await interpolation_service.create_interpolation(
                        db, track.id,
                        InterpolationCreateRequest(
                            start_point_index=0, end_point_index=1,
                            interpolation_interval_seconds=2,
                        ),
                        user.id,
                    )
                    interp = [p for p in await _track_points(db, track.id) if p.is_interpolated]
                    assert len(interp) == 5, f'10s 区段 / 2s 间隔应为 5 点，实际 {len(interp)}'
                    assert {p.region for p in interp} == {expected}

        asyncio.run(case())


class TestSecurityRegressions:
    """Focused guards for the security remediation patch."""

    def test_font_path_helpers_reject_traversal(self, workdir):
        with pytest.raises(HTTPException):
            safe_font_basename(r'..\..\.env')

        root = workdir / 'fonts'
        root.mkdir()
        assert resolve_contained_path(root, root / '..' / '..' / '.env') is None

    def test_public_font_endpoint_rejects_traversal(self, workdir):
        async def case():
            async with _db_env(workdir) as (db, _):
                with pytest.raises(HTTPException) as exc:
                    await overlay_templates.get_font_file(
                        r'admin_..\..\.env', db=db
                    )
                assert exc.value.status_code == 404

        asyncio.run(case())

    def test_public_track_requires_owner(self, workdir):
        async def case():
            async with _db_env(workdir) as (db, user):
                track = await track_service.create_from_gpx(
                    db, user, 't.gpx', _gpx(), 't'
                )
                other = User(
                    username='other',
                    email='other@example.com',
                    hashed_password='x',
                )
                db.add(other)
                await db.commit()
                await db.refresh(other)

                with pytest.raises(HTTPException) as exc:
                    await tracks.get_track_public(
                        track.id, current_user=other, db=db
                    )
                assert exc.value.status_code == 404

        asyncio.run(case())

    def test_interpolation_rejects_other_owner(self, workdir):
        async def case():
            async with _db_env(workdir) as (db, user):
                track = await track_service.create_from_gpx(
                    db, user, 't.gpx', _gpx(), 't'
                )
                other = User(
                    username='other',
                    email='other@example.com',
                    hashed_password='x',
                )
                db.add(other)
                await db.commit()
                await db.refresh(other)

                with pytest.raises(ValueError):
                    await interpolation_service.get_available_segments(
                        db, track.id, 3.0, other.id
                    )

        asyncio.run(case())

    def test_private_template_hidden_from_other_user(self, workdir):
        async def case():
            async with _db_env(workdir) as (db, user):
                other = User(
                    username='other',
                    email='other@example.com',
                    hashed_password='x',
                )
                db.add(other)
                await db.commit()
                await db.refresh(other)

                template = OverlayTemplate(
                    name='private',
                    description='',
                    config={},
                    user_id=user.id,
                    is_public=False,
                    is_system=False,
                )
                db.add(template)
                await db.commit()
                await db.refresh(template)

                service = OverlayTemplateService(db)
                assert await service.get_template(template.id, other.id) is None
                assert await service.get_template(template.id, user.id) is not None

        asyncio.run(case())

    def test_kmz_rejects_uncompressed_budget(self, workdir, monkeypatch):
        import zipfile
        from app.utils import archive_helper

        monkeypatch.setattr(archive_helper, "MAX_UNCOMPRESSED_BYTES", 10)

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("doc.kml", "<kml>" + ("x" * 1000) + "</kml>")
        buffer.seek(0)

        async def case():
            async with _db_env(workdir) as (db, user):
                with pytest.raises(HTTPException) as exc:
                    await tracks.upload_track(
                        file=UploadFile(filename="x.kmz", file=buffer),
                        name="x",
                        current_user=user,
                        db=db,
                    )
                assert exc.value.status_code == 400

        asyncio.run(case())

    def test_live_placeholder_redirect_encodes_token(self, workdir):
        async def case():
            async with _db_env(workdir) as (db, _):
                response = await live_recordings.log_track_point(
                    token='x";alert(1)//',
                    lat='%LAT',
                    db=db,
                )
                assert response.status_code == 307
                location = response.headers['location']
                assert '"' not in location
                assert '<' not in location
                assert '%22' in location

        asyncio.run(case())

    def test_invite_code_cannot_exceed_max_uses(self, workdir):
        async def case():
            async with _db_env(workdir) as (db, user):
                await config_service.create_invite_code(
                    db, 'once', 1, user.id
                )
                assert await config_service.use_invite_code(
                    db, 'once', user.id
                ) is True
                assert await config_service.use_invite_code(
                    db, 'once', user.id
                ) is False

        asyncio.run(case())
