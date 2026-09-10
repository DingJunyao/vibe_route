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
    """逐字段核值：行政区划/道路 × 三语言 + memo

    两条写入路径（导入的 ORM 赋值 / 创建的批量 INSERT）共用本断言：
    批量 INSERT 少一个键就是 INSERT 省略该列 → 模型 default 生效，不报错。
    两行的值互不相同 → 取错行、串字段、漏列都会红。
    含 memo：创建路径此前不写 memo（导出写、创建丢），补上后两条路径都在这里钉住。
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

    assert (p0.memo, p1.memo) == ('备注一', '备注二')

    assert p0.province_en != p1.province_en  # 同行取错 → 也会红


def _new_format_xlsx(region0='id', region1='cn'):
    """把 _new_format_csv 的同一份内容写成 xlsx（值逐字段一致，只换载体）

    XLSX 导入走的是 row 为 tuple + headers.index 的取值分支，与 CSV 的 DictReader
    dict 分支是两套代码 —— CSV 全绿不能说明 XLSX 正确。
    """
    import csv as _csv
    from io import BytesIO, StringIO

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for row in _csv.reader(StringIO(_new_format_csv(region0, region1))):
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _bare_province_csv():
    """新列 province_zh 与旧列 province 并存：1-2 行 zh 为空、3 行两列都有值、4 行 zh 只有空白"""
    rows = []
    for i, (tm, lon, lat, zh, bare) in enumerate((
        ('08:00:00', '112.735000', '-7.280000', '', '旧省一'),
        ('08:00:10', '112.736000', '-7.281000', '', '旧省二'),
        ('08:00:20', '112.737000', '-7.282000', '新省', '旧省三'),
        ('08:00:30', '112.738000', '-7.283000', '   ', '旧省四'),
    )):
        rows.append(_row(index=i, time_date='2026/09/01', time_time=tm,
                         longitude_wgs84=lon, latitude_wgs84=lat, region='cn',
                         province_zh=zh)
                    + f',{bare}')
    return NEW_HEADERS + ',province\n' + '\n'.join(rows)


async def _import(db, track_id, user_id, content, fmt='csv'):
    if isinstance(content, str):
        content = content.encode('utf-8')
    return await track_service.import_points_from_file(
        db, track_id, user_id, content, file_format=fmt, match_mode='index'
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
                assert p0.region == 'id'  # 行级 region，与轨迹默认 'cn' 不同
                assert p1.region == 'cn'

        asyncio.run(case())

    def test_xlsx_import_all_columns_applied(self, workdir):
        """XLSX 导入：走 row 为 tuple + headers.index 的取值分支（与 CSV 的 dict 分支不同）

        get_val 的 XLSX 分支（headers.index(alias)）是本次重写的代码，而此前 tests/ 里
        file_format 只出现过 'csv' —— CSV 全绿不能说明这一支正确。
        顺带覆盖行级 region（两行取值不同）与 memo。
        """

        async def case():
            async with _db_env(workdir) as (db, user):
                track = await track_service.create_from_gpx(
                    db, user, 'a.gpx', _gpx(), 'a', region='cn'
                )
                await _import(db, track.id, user.id, _new_format_xlsx(), fmt='xlsx')

                p0, p1 = await _track_points(db, track.id)
                _assert_full_fields(p0, p1)
                assert (p0.region, p1.region) == ('id', 'cn')

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

    def test_create_path_id_only_sets_has_area_flag(self, workdir):
        """创建路径：只填 *_id 列（无中文/英文列）也要置 has_area_info / has_road_info

        与上面的 test_id_only_columns_set_has_area_flag **不是同一条路径**，不可互替：
        那条走导入（import_points_from_file 的重算分支），本条走创建
        （_create_from_csv_project_format 的检测段 + Track(...) 构造参数），
        两处各有一份 if，删掉一份不会让另一条的用例变红。
        """

        async def case():
            async with _db_env(workdir) as (db, user):
                csv = (NEW_HEADERS + '\n'
                       + _row(index=0, time_date='2026/09/01', time_time='08:00:00',
                              longitude_wgs84='112.735000', latitude_wgs84='-7.280000',
                              region='cn', province_id='JI')
                       + '\n'
                       + _row(index=1, time_date='2026/09/01', time_time='08:00:10',
                              longitude_wgs84='112.736000', latitude_wgs84='-7.281000',
                              region='cn', road_name_id='Jalan Satu'))
                created = await track_service.create_from_csv(
                    db, user, 'c.csv', csv, 'c', region='cn'
                )

                c0, c1 = await _track_points(db, created.id)
                assert c0.province_id == 'JI' and c0.province is None
                assert c1.road_name_id == 'Jalan Satu'
                assert created.has_area_info is True  # 只靠 province_id
                assert created.has_road_info is True  # 只靠 road_name_id

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

                # ② 创建路径：轨迹参数 region='cn'，文件 region 列写 'id' / 'cn'
                created = await track_service.create_from_csv(
                    db, user, 'c.csv', _new_format_csv(region0='id', region1='cn'), 'c', region='cn'
                )
                assert created.region == 'cn'  # 轨迹级仍是入参，只点级被文件覆盖
                c0, c1 = await _track_points(db, created.id)
                # 两行取值不同：漏掉行级解析、整体写死 region 的做法都会红
                assert (c0.region, c1.region) == ('id', 'cn')
                # 批量 INSERT 与导入的 ORM 赋值是两套写入方式，字段要各自钉一遍
                _assert_full_fields(c0, c1)

        asyncio.run(case())

    def test_empty_region_falls_back_to_track(self, workdir):
        """region 列存在但值为空 → 用轨迹自身 region；无 region 列（旧格式）→ 保持原值"""

        async def case():
            async with _db_env(workdir) as (db, user):
                # ① 列存在、值为空 → 落回轨迹 region。
                # 点值 'id' 与轨迹值 'cn' 刻意不同：期望值若等于点原值，
                # 「整段没动点 region」这种错误也会绿。
                t_empty = await track_service.create_from_gpx(
                    db, user, 'a.gpx', _gpx(), 'a', region='cn'
                )
                for pt in await _track_points(db, t_empty.id):
                    pt.region = 'id'
                await db.commit()
                await _import(db, t_empty.id, user.id, _new_format_csv(region0='', region1=''))
                assert {p.region for p in await _track_points(db, t_empty.id)} == {'cn'}

                # ② 旧格式无 region 列 → 完全不动点 region。
                # 点值 'id' 与轨迹值 'cn' 刻意不同：期望值若等于轨迹默认值，
                # 「删掉 has_key('region') 守卫、一律写 track.region」这种错误也会绿。
                t_legacy = await track_service.create_from_gpx(
                    db, user, 'b.gpx', _gpx(9), 'b', region='cn'
                )
                for pt in await _track_points(db, t_legacy.id):
                    pt.region = 'id'
                await db.commit()

                await _import(db, t_legacy.id, user.id,
                              'index,province,city,area,road_num,road_name\n'
                              '0,甲省,甲市,甲区,R1,路一\n'
                              '1,乙省,乙市,乙区,R2,路二\n')
                pts = await _track_points(db, t_legacy.id)
                assert {p.region for p in pts} == {'id'}  # 保持原值，未被轨迹 region 覆盖
                assert [p.province for p in pts] == ['甲省', '乙省']  # 其余字段照旧更新

        asyncio.run(case())

    def test_invalid_region_raises(self, workdir):
        async def case():
            async with _db_env(workdir) as (db, user):
                track = await track_service.create_from_gpx(
                    db, user, 'a.gpx', _gpx(), 'a', region='cn'
                )
                with pytest.raises(ValueError, match='无效的地区值'):
                    await _import(db, track.id, user.id, _new_format_csv(region0='sg', region1='cn'))

        asyncio.run(case())

    def test_create_path_invalid_region_raises(self, workdir):
        """创建路径的 region 校验（_create_from_csv_project_format 的 row_region 分支）

        与上面的 test_invalid_region_raises **不是同一条路径**，不可互替：那条走导入
        （import_points_from_file），本条走创建（create_from_csv）。删掉创建路径那两行
        raise 不会让导入路径的用例变红，反之亦然。
        """

        async def case():
            async with _db_env(workdir) as (db, user):
                with pytest.raises(ValueError, match='无效的地区值'):
                    await track_service.create_from_csv(
                        db, user, 'c.csv', _new_format_csv(region0='sg', region1='cn'),
                        'c', region='cn',
                    )

        asyncio.run(case())

    def test_create_path_takes_first_nonempty_alias(self, workdir):
        """新列 province_zh 与旧列 province 并存时，创建路径取「第一个非空」的值

        F1 的防线，三条断言各钉一半：
        - 前两行 zh 列为空 → 落回旧列（若 `_row_aliased` 被写成「取第一个存在的列」，
          照抄导入路径的 get_val，这里只会得到 None）；
        - 第三行两列都有值 → 新列优先（若别名表里 'province' 项漏了 'province_zh'，
          即创建路径没真的读这张表，这里会拿到 '旧省三'）；
        - 第四行 zh 列**只有空白** → 同样视为「无值」落回旧列。这一条钉的是
          `_row_aliased` 的「先 strip 再判空」：旧写法 `(a or b or '').strip() or None`
          按**原始**真值短路（'   ' 为真），会得到 None —— 即两种写法在这一格上
          给出不同结果，别在「恢复等价」时把它静默改回去。
        同一份文件走导入路径得到 None —— 两条路径的语义差异（建点 vs 覆盖）在此钉住，
        以免日后被「统一一下」悄悄改掉。
        """

        async def case():
            async with _db_env(workdir) as (db, user):
                csv = _bare_province_csv()

                # 创建路径：取第一个非空的别名列 → 落回旧列 province
                created = await track_service.create_from_csv(
                    db, user, 'c.csv', csv, 'c', region='cn'
                )
                c0, c1, c2, c3 = await _track_points(db, created.id)
                assert (c0.province, c1.province) == ('旧省一', '旧省二')
                assert c2.province == '新省'  # 两列都有值 → 新列优先
                assert c3.province == '旧省四'  # zh 只有空白 → 视为无值，落回旧列

                # 导入路径：列存在即覆盖（空值也算值）→ province 被清空
                # （本轨迹只有 2 点，第三行 index=2 无对应点，不影响本断言）
                track = await track_service.create_from_gpx(
                    db, user, 'a.gpx', _gpx(), 'a', region='cn'
                )
                # 建点时 province 本就是 None → 「覆盖为空」与「整段没动」不可区分，
                # 先设哨兵值，使断言能分辨这两种情形
                for pt in await _track_points(db, track.id):
                    pt.province = '哨兵'
                await db.commit()
                await _import(db, track.id, user.id, csv)
                assert [p.province for p in await _track_points(db, track.id)] == [None, None]

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
