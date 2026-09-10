# -*- coding: utf-8 -*-
"""Nominatim region 分派回归守卫：语言集、*_id 字段映射、S 前缀门控

Task 6 质量审查 Important #2：本 Task 的核心分派逻辑此前零覆盖。
无网络、无数据库：替换 httpx.AsyncClient 为按 accept-language 回放固定 geocodejson 的假 client。
"""
import asyncio

import pytest

from app.gpxutil_wrapper import geocoding as geo_module
from app.gpxutil_wrapper.geocoding import NominatimGeocoding
from app.services.track_service import _should_backfill_province_zh


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def _payload(osm_type='way', name=None, admin=None, place_id=1):
    """构造单 feature 的 geocodejson 响应（字段层级与 Nominatim 实际响应一致）"""
    geocoding = {'osm_type': osm_type, 'admin': admin or {}, 'place_id': place_id}
    if name is not None:
        geocoding['name'] = name
    return {'features': [{'properties': {'geocoding': geocoding}}]}


@pytest.fixture
def fake_http(monkeypatch):
    """替换 httpx.AsyncClient：记录每次请求参数，按 accept-language 回放固定响应"""
    state = {'calls': [], 'payloads': {}}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url, params=None):
            params = dict(params or {})
            state['calls'].append((url, params))
            if url.endswith('/details'):
                return _FakeResponse(state['payloads']['details'])
            return _FakeResponse(state['payloads'][params['accept-language']])

    monkeypatch.setattr(geo_module.httpx, 'AsyncClient', _FakeAsyncClient)
    return state


def _svc():
    return NominatimGeocoding({'url': 'http://fake-nominatim'})


def _reverse_langs(state):
    """按调用顺序取出 reverse 请求的 accept-language（排除 /details）"""
    return [p['accept-language'] for u, p in state['calls'] if not u.endswith('/details')]


def _details_count(state):
    return sum(1 for u, _ in state['calls'] if u.endswith('/details'))


class TestRegionDispatch:
    """region 分派：语言集、*_id 映射、S 前缀门控"""

    def test_id_three_languages_and_id_fields(self, fake_http):
        """region='id' → 三语请求；*_id 取印尼语响应；S 编号不套中国省份前缀"""
        fake_http['payloads'].update({
            'zh-CN': _payload(name='Jalan Dago', admin={
                'level4': 'Jawa Barat', 'level5': 'Kota Bandung', 'level6': 'Coblong'}),
            'id': _payload(name='Jalan Dago', admin={
                'level4': 'Provinsi Jawa Barat', 'level5': 'Kota Bandung', 'level6': 'Coblong'}),
            'en': _payload(name='Dago Street', admin={
                'level4': 'West Java', 'level5': 'Bandung', 'level6': 'Coblong'}),
            'details': {'names': {'ref': 'S123,024'}},
        })
        info = asyncio.run(_svc().get_point_info(-6.9, 107.6, region='id'))

        assert _reverse_langs(fake_http) == ['zh-CN', 'id', 'en']
        assert _details_count(fake_http) == 1
        # 中文列取 zh-CN 响应、英文列取 en、印尼语列取 id
        assert info['province'] == 'Jawa Barat'
        assert info['province_en'] == 'West Java'
        assert info['province_id'] == 'Provinsi Jawa Barat'
        assert info['city_id'] == 'Kota Bandung'
        assert info['area_id'] == 'Coblong'
        assert info['road_name'] == 'Jalan Dago'
        assert info['road_name_en'] == 'Dago Street'
        assert info['road_name_id'] == 'Jalan Dago'
        # 印尼 raw ref 原样输出，不加省份前缀
        assert info['road_num'] == 'S123,024'

    def test_cn_two_languages_and_province_prefix(self, fake_http):
        """两参调用（既有调用点形态）→ 双语；S 编号加中国省份简称前缀"""
        fake_http['payloads'].update({
            'zh-CN': _payload(name='沪宁高速', admin={'level4': '江苏省'}),
            'en': _payload(name='Hu-Ning Expressway', admin={'level4': 'Jiangsu'}),
            'details': {'names': {'ref': 'S123'}},
        })
        # 注意：不传 region，守住 live_recording_service 等既有调用点
        info = asyncio.run(_svc().get_point_info(31.3, 120.6))

        assert _reverse_langs(fake_http) == ['zh-CN', 'en']
        assert info['province'] == '江苏省'
        assert info['road_num'] == '苏S123'
        assert info['province_id'] == ''  # cn 不写印尼语字段
        assert info['city_id'] == ''
        assert info['road_name_id'] == ''

    def test_non_way_skips_road_fields(self, fake_http):
        """osm_type 非 way → 不取路名、不发 /details（既有分支）"""
        fake_http['payloads'].update({
            'zh-CN': _payload(osm_type='node', admin={'level4': '江苏省'}),
            'en': _payload(osm_type='node', admin={'level4': 'Jiangsu'}),
        })
        info = asyncio.run(_svc().get_point_info(31.3, 120.6))

        assert info['province'] == '江苏省'
        assert info['road_name'] == ''
        assert info['road_num'] == ''
        assert _details_count(fake_http) == 0


class TestBackfillDecision:
    """印尼中文省名回填判定（复审变异 E：此前 isascii 兜底零覆盖）"""

    def test_should_backfill(self):
        # 需要回填：zh 为空 / zh 与 id 相同 / zh 是非中文（ASCII，如 Nominatim 返回英文名）
        assert _should_backfill_province_zh('', 'Jawa Barat')
        assert _should_backfill_province_zh('Jawa Barat', 'Jawa Barat')
        assert _should_backfill_province_zh('West Java', 'Jawa Barat')

    def test_should_not_backfill(self):
        # 已是中文 → 不覆盖
        assert not _should_backfill_province_zh('江苏省', 'Jiangsu')
        assert not _should_backfill_province_zh('西爪哇省', 'Jawa Barat')
        # 无印尼语省名可取 → 不触发
        assert not _should_backfill_province_zh('', '')
        assert not _should_backfill_province_zh('West Java', '')
