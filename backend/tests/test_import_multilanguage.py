# -*- coding: utf-8 -*-
"""CSV 导入：列名别名表 + 行级 region 的闭环守卫

导入路径此前没有任何用例覆盖，而它的全部失效模式都是静默的：
- 别名查不到 → 该字段不更新，不报错；
- point_data/insert_values 少一个键 → INSERT 省略该列 → 模型 default 生效，不报错；
- insert_values 写死 "region": region → 行级 region 被轨迹默认值整体覆盖，不报错。
故本文件是这次改动的唯一防线：用例 2 钉死第三条，用例 1 钉死前两条。

复用 tests/test_region_propagation.py 的 workdir fixture（本机 %TEMP%/pytest-of-* 不可访问）。
"""
import asyncio
import contextlib
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, TrackPoint, User
from app.services.track_service import track_service


# 与 Task 8 导出的 30 列一致
NEW_HEADERS = ("index,time_date,time_time,time_microsecond,elapsed_time,"
               "longitude_wgs84,latitude_wgs84,longitude_gcj02,latitude_gcj02,"
               "longitude_bd09,latitude_bd09,elevation,distance,course,speed,"
               "region,province_zh,province_id,province_en,city_zh,city_id,city_en,"
               "area_zh,area_id,area_en,road_num,road_name_zh,road_name_id,"
               "road_name_en,memo")
_COLUMNS = NEW_HEADERS.split(',')


@pytest.fixture
def workdir():
    """临时目录（不用 pytest tmp_path：本机 %TEMP%/pytest-of-* 残留不可访问）"""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@contextlib.asynccontextmanager
async def _db_env(workdir):
    """独立 SQLite + 一个用户；退出时 dispose（Windows 下否则临时目录无法清理）"""
    engine = create_async_engine(f"sqlite+aiosqlite:///{workdir / 'test.db'}")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            user = User(username='u', email='u@example.com', hashed_password='x')
            db.add(user)
            await db.commit()
            await db.refresh(user)
            yield db, user
    finally:
        await engine.dispose()


async def _track_points(db, track_id):
    result = await db.execute(
        select(TrackPoint).where(TrackPoint.track_id == track_id).order_by(TrackPoint.point_index)
    )
    return list(result.scalars().all())


def _gpx(hour=8):
    pts = ''.join(
        f'<trkpt lat="{-7.280 - i * 0.001}" lon="{112.735 + i * 0.001}">'
        f'<ele>{10 + i}</ele><time>2026-09-01T{hour:02d}:00:{i * 10:02d}Z</time></trkpt>'
        for i in range(2)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<gpx version="1.1" creator="t" xmlns="http://www.topografix.com/GPX/1/1">'
        f'<trk><name>t</name><trkseg>{pts}</trkseg></trk></gpx>'
    )


def _row(**kw):
    """按 30 列顺序拼一行（未给的列留空）"""
    return ','.join(str(kw.get(col, '')) for col in _COLUMNS)


def _new_format_csv(region0='id', region1='cn'):
    return (NEW_HEADERS + '\n'
            + _row(index=0, time_date='2026/09/01', time_time='08:00:00',
                    longitude_wgs84='112.735000', latitude_wgs84='-7.280000',
                    region=region0, province_zh='东爪哇省', province_id='JI', province_en='East Java',
                    city_zh='泗水市', city_id='SURABAYA', city_en='Surabaya',
                    area_zh='根腾区', area_id='GENTENG', area_en='Genteng',
                    road_num='R1', road_name_zh='街道一', road_name_id='Jalan Satu',
                    road_name_en='Road One', memo='备注一')
            + '\n'
            + _row(index=1, time_date='2026/09/01', time_time='08:00:10',
                    longitude_wgs84='112.736000', latitude_wgs84='-7.281000',
                    region=region1, province_zh='巴厘省', province_id='BA', province_en='Bali',
                    city_zh='登巴萨市', city_id='DENPASAR', city_en='Denpasar',
                    area_zh='西登巴萨区', area_id='DENBAR', area_en='West Denpasar',
                    road_num='R2', road_name_zh='街道二', road_name_id='Jalan Dua',
                    road_name_en='Road Two', memo='备注二'))


def _assert_full_fields(p0, p1):
    """逐字段核值：行政区划/道路 × 三语言

    两条写入路径（导入的 ORM 赋值 / 创建的批量 INSERT）共用本断言：
    批量 INSERT 少一个键就是 INSERT 省略该列 → 模型 default 生效，不报错。
    两行的值互不相同 → 取错行、串字段、漏列都会红。
    不含 memo：创建路径的 insert_values 至今不写 memo（既有缺口，非本次改动）。
    """
    assert (p0.province, p0.province_id, p0.province_en) == ('东爪哇省', 'JI', 'East Java')
    assert (p0.city, p0.city_id, p0.city_en) == ('泗水市', 'SURABAYA', 'Surabaya')
    assert (p0.district, p0.district_id, p0.district_en) == ('根腾区', 'GENTENG', 'Genteng')
    assert (p0.road_number, p0.road_name, p0.road_name_id, p0.road_name_en) == (
        'R1', '街道一', 'Jalan Satu', 'Road One')

    assert (p1.province, p1.province_id, p1.province_en) == ('巴厘省', 'BA', 'Bali')
    assert (p1.city, p1.city_id, p1.city_en) == ('登巴萨市', 'DENPASAR', 'Denpasar')
    assert (p1.district, p1.district_id, p1.district_en) == (
        '西登巴萨区', 'DENBAR', 'West Denpasar')
    assert (p1.road_number, p1.road_name, p1.road_name_id, p1.road_name_en) == (
        'R2', '街道二', 'Jalan Dua', 'Road Two')

    assert p0.province_en != p1.province_en  # 同行取错 → 也会红


async def _import(db, track_id, user_id, content: str, fmt='csv'):
    return await track_service.import_points_from_file(
        db, track_id, user_id, content.encode('utf-8'), file_format=fmt, match_mode='index'
    )


class TestNewFormatColumns:
    """新格式（语言后缀列）：30 列全量落库 + 行级 region"""

    def test_new_format_all_columns_applied(self, workdir):
        async def case():
            async with _db_env(workdir) as (db, user):
                track = await track_service.create_from_gpx(
                    db, user, 'a.gpx', _gpx(), 'a', region='cn'
                )
                await _import(db, track.id, user.id, _new_format_csv())

                p0, p1 = await _track_points(db, track.id)
                _assert_full_fields(p0, p1)
                assert (p0.memo, p1.memo) == ('备注一', '备注二')  # memo 只走导入路径
                assert p0.region == 'id'  # 行级 region，与轨迹默认 'cn' 不同
                assert p1.region == 'cn'

        asyncio.run(case())

    def test_id_only_columns_set_has_area_flag(self, workdir):
        """只填 *_id 列（无中文/英文列）也要置 has_area_info

        漏了 *_id 的重算分支时该标志静默为 False，前端就不显示行政区划。
        """

        async def case():
            async with _db_env(workdir) as (db, user):
                track = await track_service.create_from_gpx(
                    db, user, 'a.gpx', _gpx(), 'a', region='cn'
                )
                csv = (NEW_HEADERS + '\n'
                       + _row(index=0, time_date='2026/09/01', time_time='08:00:00',
                              longitude_wgs84='112.735000', latitude_wgs84='-7.280000',
                              region='cn', province_id='JI')
                       + '\n'
                       + _row(index=1, time_date='2026/09/01', time_time='08:00:10',
                              longitude_wgs84='112.736000', latitude_wgs84='-7.281000',
                              region='cn', road_name_id='Jalan Satu'))
                await _import(db, track.id, user.id, csv)

                await db.refresh(track)
                p0, p1 = await _track_points(db, track.id)
                assert p0.province_id == 'JI' and p0.province is None
                assert p1.road_name_id == 'Jalan Satu'
                assert track.has_area_info is True  # 只靠 province_id
                assert track.has_road_info is True  # 只靠 road_name_id

        asyncio.run(case())


class TestRowRegion:
    """行级 region 优先级与合法性"""

    def test_row_region_overrides_track_default(self, workdir):
        """轨迹 region='cn' + 文件 region 列写 'id' → 点 region 必须是 'id'

        两条路径都要钉住，它们各自的写入方式不同、失效都不报错：
        ① 导入路径（update_point_fields 直接改 ORM 对象）；
        ② 创建路径（_create_from_csv_project_format 的 insert_values，写死
           `"region": region` 时行级值被轨迹默认整体覆盖）。
        """

        async def case():
            async with _db_env(workdir) as (db, user):
                # ① 导入路径
                track = await track_service.create_from_gpx(
                    db, user, 'a.gpx', _gpx(), 'a', region='cn'
                )
                assert {p.region for p in await _track_points(db, track.id)} == {'cn'}

                await _import(db, track.id, user.id, _new_format_csv(region0='id', region1='id'))
                assert {p.region for p in await _track_points(db, track.id)} == {'id'}

                # ② 创建路径：轨迹参数 region='cn'，文件 region 列写 'id'
                created = await track_service.create_from_csv(
                    db, user, 'c.csv', _new_format_csv(region0='id', region1='id'), 'c', region='cn'
                )
                assert created.region == 'cn'  # 轨迹级仍是入参，只点级被文件覆盖
                c0, c1 = await _track_points(db, created.id)
                assert (c0.region, c1.region) == ('id', 'id')
                # 批量 INSERT 与导入的 ORM 赋值是两套写入方式，字段要各自钉一遍
                _assert_full_fields(c0, c1)

        asyncio.run(case())

    def test_empty_region_falls_back_to_track(self, workdir):
        """region 列存在但值为空 → 用轨迹自身 region；无 region 列（旧格式）→ 保持原值"""

        async def case():
            async with _db_env(workdir) as (db, user):
                # ① 列存在、值为空
                t_empty = await track_service.create_from_gpx(
                    db, user, 'a.gpx', _gpx(), 'a', region='id'
                )
                await _import(db, t_empty.id, user.id, _new_format_csv(region0='', region1=''))
                assert {p.region for p in await _track_points(db, t_empty.id)} == {'id'}

                # ② 旧格式无 region 列 → 完全不动点 region（已有 'cn' 保持 'cn'）
                t_legacy = await track_service.create_from_gpx(
                    db, user, 'b.gpx', _gpx(9), 'b', region='cn'
                )
                await _import(db, t_legacy.id, user.id,
                              'index,province,city,area,road_num,road_name\n'
                              '0,甲省,甲市,甲区,R1,路一\n'
                              '1,乙省,乙市,乙区,R2,路二\n')
                pts = await _track_points(db, t_legacy.id)
                assert {p.region for p in pts} == {'cn'}
                assert [p.province for p in pts] == ['甲省', '乙省']  # 其余字段照旧更新

        asyncio.run(case())

    def test_invalid_region_raises(self, workdir):
        async def case():
            async with _db_env(workdir) as (db, user):
                track = await track_service.create_from_gpx(
                    db, user, 'a.gpx', _gpx(), 'a', region='cn'
                )
                with pytest.raises(ValueError):
                    await _import(db, track.id, user.id, _new_format_csv(region0='sg', region1='cn'))

        asyncio.run(case())


class TestLegacyFormat:
    """旧版列名（无语言后缀）回归守卫"""

    def test_legacy_format_still_works(self, workdir):
        async def case():
            async with _db_env(workdir) as (db, user):
                track = await track_service.create_from_gpx(
                    db, user, 'a.gpx', _gpx(), 'a', region='id'
                )
                await _import(db, track.id, user.id,
                              'index,province,city,area,road_num,road_name,road_name_en,memo\n'
                              '0,甲省,甲市,甲区,R1,路一,Road One,m0\n'
                              '1,乙省,乙市,乙区,R2,路二,Road Two,m1\n')
                p0, p1 = await _track_points(db, track.id)
                assert (p0.province, p0.city, p0.district) == ('甲省', '甲市', '甲区')
                assert (p0.road_number, p0.road_name, p0.road_name_en, p0.memo) == (
                    'R1', '路一', 'Road One', 'm0')
                assert (p1.province, p1.city, p1.district) == ('乙省', '乙市', '乙区')
                assert (p1.road_name, p1.memo) == ('路二', 'm1')

        asyncio.run(case())


class TestRoundtrip:
    """Task 8 的导出列 ↔ Task 9 的别名表 必须互认"""

    def test_export_import_roundtrip(self, workdir):
        async def case():
            async with _db_env(workdir) as (db, user):
                src = await track_service.create_from_gpx(db, user, 's.gpx', _gpx(), 's', region='id')
                fields = ('province', 'city', 'district', 'province_en', 'city_en', 'district_en',
                          'province_id', 'city_id', 'district_id',
                          'road_number', 'road_name', 'road_name_en', 'road_name_id', 'memo')
                # 逐点赋互不相同的值（值里编入点序）→ 取错行/串字段都会红
                src_pts = await _track_points(db, src.id)
                for n, pt in enumerate(src_pts, start=1):
                    for f in fields:
                        setattr(pt, f, f'{f}-{n}')
                    pt.region = 'id'
                await db.commit()

                _, content = await track_service.export_points_to_csv(db, src.id, user.id)

                dst = await track_service.create_from_gpx(db, user, 'd.gpx', _gpx(9), 'd', region='cn')
                await track_service.import_points_from_file(
                    db, dst.id, user.id, content.encode('utf-8'),
                    file_format='csv', match_mode='index',
                )

                dst_pts = await _track_points(db, dst.id)
                assert len(dst_pts) == len(src_pts)
                for s, d in zip(src_pts, dst_pts):
                    assert tuple(getattr(d, f) for f in fields) == tuple(getattr(s, f) for f in fields)
                    assert d.region == 'id'  # 导出的点级 region 覆盖目标轨迹默认 'cn'

        asyncio.run(case())
