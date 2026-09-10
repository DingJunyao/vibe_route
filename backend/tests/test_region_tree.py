# -*- coding: utf-8 -*-
"""区域树：region 分组 + 节点多语言 names + 显示回退链

为什么必须有：本 Task 的两类缺陷都躲得过冒烟验证——
(a) 节点 names 取错层级（市/区节点填了省名）：冒烟只看「首节点是否含 region/names 键」，键在就过；
(b) 合并两入口时若等价性不成立：冒烟要有「能被两个入口同时读到的轨迹」才暴露。
故此处直接钉死每层 names 的取值来源与两入口的结构一致性。

用例 1-4、6 直接构造内存 TrackPoint 喂 `_build_region_tree`
（`spatial_service.distance` 的两个实现都是纯 Haversine、不查库，故不必建轨迹入库）；
用例 5 走两个公共入口，必须入库，故用 conftest 的 workdir + _db_env。
"""
import asyncio
from datetime import datetime

from app.models import TrackPoint
from app.services.track_service import track_service
from conftest import _db_env, _gpx, _track_points


def _pt(i, t_hour=8, **kw):
    """构造一个**不入库**的 TrackPoint：只给用例用到的字段"""
    return TrackPoint(
        track_id=1,
        point_index=i,
        latitude_wgs84=-7.28 - i * 0.001,
        longitude_wgs84=112.735 + i * 0.001,
        time=datetime(2026, 9, 1, t_hour, 0, i),
        **kw,
    )


def _build(points):
    """直接构建区域树（不查库、不入库）"""
    return asyncio.run(track_service._build_region_tree(points))


def _shape(nodes):
    """把树压成可精确比较的结构（递归含子节点），用于两入口一致性比对"""
    return [
        (n['type'], n['name'], n['region'], n['names'], n['point_count'],
         round(n['distance'], 9), n['start_index'], n['end_index'], _shape(n['children']))
        for n in nodes
    ]


class TestBuildRegionTree:
    """共享构建方法：names 层级、回退链、region 分组、道路键"""

    def test_names_per_level(self):
        """四级 names 各取各层的三语值（把任一层的 level 写错即红）"""
        root, _ = _build([_pt(
            0, region='id',
            province='P-zh', province_id='P-id', province_en='P-en',
            city='C-zh', city_id='C-id', city_en='C-en',
            district='D-zh', district_id='D-id', district_en='D-en',
            road_name='R-zh', road_name_id='R-id', road_name_en='R-en',
            road_number='N1',
        )])

        assert len(root) == 1
        province = root[0]
        city = province['children'][0]
        district = city['children'][0]
        road = district['children'][0]

        assert [n['type'] for n in (province, city, district, road)] == [
            'province', 'city', 'district', 'road']
        assert province['names'] == {'zh': 'P-zh', 'id': 'P-id', 'en': 'P-en'}
        assert city['names'] == {'zh': 'C-zh', 'id': 'C-id', 'en': 'C-en'}
        assert district['names'] == {'zh': 'D-zh', 'id': 'D-id', 'en': 'D-en'}
        assert road['names'] == {'zh': 'R-zh', 'id': 'R-id', 'en': 'R-en'}

    def test_names_dedup_same_value(self):
        """某级 zh 与 id 同值（Nominatim 无译文时常见）→ names 里只留一份"""
        root, _ = _build([_pt(
            0, region='id',
            province='Jawa Timur', province_id='Jawa Timur', province_en='East Java',
        )])

        names = root[0]['names']
        assert len(names.values()) == len(set(names.values())), names
        assert names == {'zh': 'Jawa Timur', 'en': 'East Java'}

    def test_display_fallback_chain(self):
        """显示文本走 zh → id → en → 哨兵"""
        # zh 空、id 有值 → 取 id
        root, _ = _build([_pt(0, province=None, province_id='Jawa Timur')])
        assert root[0]['name'] == 'Jawa Timur'

        # zh/id 都空、en 有值 → 取 en
        root, _ = _build([_pt(0, province=None, province_en='East Java')])
        assert root[0]['name'] == 'East Java'

        # 三语全空 → 哨兵
        root, _ = _build([_pt(0)])
        assert root[0]['name'] == '未知区域'
        assert root[0]['names'] == {}

    def test_region_grouping(self):
        """文本相同但 region 不同 → 不并组，各自成根节点、各自计数"""
        common = dict(province='Jawa Timur', city='Surabaya', road_name='Jl. A')
        root, stats = _build([
            _pt(0, region='cn', **common),
            _pt(1, region='id', **common),
        ])

        assert len(root) == 2, '键含 region，同文本不同地区必须分开成组'
        assert [n['region'] for n in root] == ['cn', 'id']
        assert len(stats) == 4
        assert stats['province'] == 2, '同一份省文本要按地区分别计数'
        assert stats['city'] == 2
        assert stats['road'] == 2

    def test_road_number_keying(self):
        """同名道路、编号不同 → 两个道路节点（道路键含编号）"""
        root, stats = _build([
            _pt(0, province='P', city='C', district='D',
                road_name='Jl. Sudirman', road_number='1'),
            _pt(1, province='P', city='C', district='D',
                road_name='Jl. Sudirman', road_number='2'),
        ])

        district = root[0]['children'][0]['children'][0]
        roads = district['children']
        assert len(roads) == 2, '道路键 (region, 名称, 编号) 不同就要各建节点'
        assert [r['road_number'] for r in roads] == ['1', '2']
        assert stats['road'] == 1, 'stats 按 (region, 名称) 去重，编号不计入'


class TestEntryPointsEquivalent:
    """两入口（登录态 / 公开分享）必须返回同构结果"""

    def test_auth_no_auth_equivalent(self, workdir):
        """同轨迹经两入口：结构、stats 一致；且 auth 仍守权限"""

        async def case():
            async with _db_env(workdir) as (db, user):
                track = await track_service.create_from_gpx(
                    db, user, 't.gpx', _gpx(), 't', region='id'
                )
                # 给点补上区域信息（含 region 分叉），让树不是玩具树
                pts = await _track_points(db, track.id)
                pts[0].province = 'Jawa Timur'
                pts[0].province_id = 'Jawa Timur'
                pts[0].province_en = 'East Java'
                pts[0].city = 'Surabaya'
                pts[0].district = 'Gubeng'
                pts[0].road_name = 'Jl. A'
                pts[0].road_number = '1'
                pts[0].region = 'id'
                pts[1].province = 'Jawa Timur'
                pts[1].province_id = 'Jawa Timur'
                pts[1].province_en = 'East Java'
                pts[1].city = 'Surabaya'
                pts[1].road_name = 'Jl. B'
                pts[1].region = 'id'
                await db.commit()

                auth = await track_service.get_region_tree(db, track.id, user.id)
                no_auth = await track_service.get_region_tree_no_auth(db, track.id)

                # 非玩具树：省 > 市 > 区/路 至少两级，且 road 计数非 0
                assert len(auth['regions']) == 1
                assert auth['regions'][0]['children'], '至少要有市级节点'
                assert auth['stats']['road'] == 2

                assert _shape(auth['regions']) == _shape(no_auth['regions'])
                assert auth['stats'] == no_auth['stats']

                # auth 侧仍守权限（合并后薄壳不得把权限检查一起吞掉）
                other = await track_service.get_region_tree(db, track.id, user.id + 999)
                assert other == {'regions': [],
                                 'stats': {'province': 0, 'city': 0, 'district': 0, 'road': 0}}

        asyncio.run(case())
