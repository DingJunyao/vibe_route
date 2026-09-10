# -*- coding: utf-8 -*-
"""region 分派与缓存键测试（spec §8 用例 4、8）"""
import pytest

from app.gpxutil_wrapper.svg_gen import generate_road_sign
from app.services.road_sign_service import RoadSignService, road_sign_service

ID_CONFIG = {
    # pytest cwd = backend/，与 Task 4 测试同约定（服务层的 DATA_DIR 相对路径拼接见 RoadSignService 内 base_dir 逻辑）
    'template': 'data/templates/id_sheild.svg',
    'upper': 'data/fonts/ClearviewHwy1W.ttf',
    'lower': 'data/fonts/ClearviewHwy2W.ttf',
    'tol_keywords': ['收费', 'Tol'],
}


class TestGenerateRoadSignDispatch:
    """generate_road_sign region 分派"""

    def test_cn_default_unchanged(self):
        # cn 路径无 region/indonesia 参数即可工作（way 模板存在时）
        svg = generate_road_sign('way', 'G221')
        assert 'viewBox' in svg

    def test_id_nasional(self):
        svg = generate_road_sign(
            'way', '3', region='id', indonesia_config=ID_CONFIG)
        assert 'viewBox' in svg and 'polygon' in svg

    def test_id_tol_from_chinese_name(self):
        """name 含「收费」→ TOL（与「两语皆无关键词」基线渲染不同）"""
        base = generate_road_sign(
            'expwy', '8', name='雅加达高速', region='id',
            indonesia_config=ID_CONFIG, name_id='Jalan Jagorawi')
        tol = generate_road_sign(
            'expwy', '8', name='雅加达收费高速', region='id',
            indonesia_config=ID_CONFIG, name_id='Jalan Jagorawi')
        # TOL 与 NASIONAL 同为红头（#B5273C），色带文字不同，只能比对整体渲染
        assert tol != base

    def test_id_tol_detected_from_name_id(self):
        """name 无关键词、name_id 命中 tol → 仍判 TOL（与基线渲染不同）"""
        base_kwargs = dict(sign_type='expwy', code='8', name='雅加达高速',
                           region='id', indonesia_config=ID_CONFIG,
                           name_id='Jalan Jagorawi')
        base = generate_road_sign(**base_kwargs)
        # 守卫：同输入两次渲染须一致，否则下面的 != 断言会因非确定性假通过
        assert generate_road_sign(**base_kwargs) == base
        tol = generate_road_sign(
            'expwy', '8', name='雅加达高速', region='id',
            indonesia_config=ID_CONFIG, name_id='Jalan Tol Jagorawi')
        assert tol != base
        import xml.etree.ElementTree as ET
        head = [e for e in ET.fromstring(tol).iter()
                if e.tag.split('}')[-1] == 'polygon' and e.attrib.get('id') == 'head']
        # 色带红 = spec §5「实现时对齐 gpxutil」的 #B5273C（非国标红 #ED1724）
        assert head and head[0].attrib['fill'].upper() == '#B5273C'

    def test_id_force_tol_without_name(self):
        """force_tol：无路名时强制 TOL（与默认 NASIONAL 渲染不同）"""
        base = generate_road_sign('way', '8', region='id', indonesia_config=ID_CONFIG)
        forced = generate_road_sign(
            'way', '8', region='id', indonesia_config=ID_CONFIG, force_tol=True)
        assert forced != base
        import xml.etree.ElementTree as ET
        head = [e for e in ET.fromstring(forced).iter()
                if e.tag.split('}')[-1] == 'polygon' and e.attrib.get('id') == 'head']
        assert head and head[0].attrib['fill'].upper() == '#B5273C'

    def test_id_force_tol_ignored_for_three_digits(self):
        # 3 位编号恒为 PROVINSI，force_tol 不改变渲染
        a = generate_road_sign('way', '023', region='id', indonesia_config=ID_CONFIG)
        b = generate_road_sign(
            'way', '023', region='id', indonesia_config=ID_CONFIG, force_tol=True)
        assert a == b

    def test_id_county_code_banner(self):
        # 县市码内嵌 → 色带 'PROVINSI 16.17'，与无省码版渲染不同
        with_code = generate_road_sign(
            'way', '16.17-024', region='id', indonesia_config=ID_CONFIG)
        without = generate_road_sign(
            'way', '024', region='id', indonesia_config=ID_CONFIG)
        assert with_code != without

    def test_id_unrecognizable_raises(self):
        with pytest.raises(ValueError):
            generate_road_sign('way', 'abc', region='id', indonesia_config=ID_CONFIG)

    def test_id_without_config_raises(self):
        with pytest.raises(ValueError):
            generate_road_sign('way', '3', region='id', indonesia_config=None)


class TestRoadSignRequestRegion:
    """id 请求的 province 承载印尼语省名，不套用中文简称白名单（Step 5）"""

    def test_id_request_accepts_province_text(self):
        from app.api.road_signs import RoadSignRequest
        req = RoadSignRequest(
            sign_type='way', code='3', region='id', province='Provinsi Jawa Timur')
        assert req.province == 'Provinsi Jawa Timur'

    def test_cn_invalid_province_still_rejected(self):
        from app.api.road_signs import RoadSignRequest
        with pytest.raises(ValueError):
            RoadSignRequest(sign_type='expwy', code='S1', province='豫X')


class TestGenerateEndpoint:
    """HTTP 层：force_tol / region 是否正确透传到 svg_gen（端点接线是本类唯一覆盖点）"""

    def test_force_tol_reaches_generator(self, monkeypatch):
        import asyncio
        from httpx import ASGITransport, AsyncClient
        from app.main import app

        seen = {}

        async def _fake_get_or_create_sign(db, **kwargs):
            seen.update(kwargs)
            return '<svg viewBox="0 0 1 1"/>', False

        monkeypatch.setattr(road_sign_service, 'get_or_create_sign', _fake_get_or_create_sign)

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as c:
                r = await c.post('/api/road-signs/generate', json={
                    'sign_type': 'way', 'code': '8', 'region': 'id',
                    'name_id': 'Jalan Tol Jagorawi', 'province_id': 'Provinsi Jawa Timur',
                    'force_tol': True,
                })
                assert r.status_code == 200, r.text

        asyncio.run(_run())
        assert seen['force_tol'] is True
        assert seen['region'] == 'id'
        assert seen['name_id'] == 'Jalan Tol Jagorawi'
        assert seen['province_id'] == 'Provinsi Jawa Timur'


class TestCacheKey:
    """缓存键含 region 与多语字段（spec §8 用例 8）"""

    def test_cache_key_differs_by_region(self):
        svc = RoadSignService()
        key_cn = svc._generate_cache_key('way', 'G221', None, None)
        assert isinstance(key_cn, str) and len(key_cn) == 32

    def test_region_part_of_key(self):
        svc = RoadSignService()
        # 同一 code 不同 region 键不同
        k1 = svc._generate_cache_key('way', '3', None, None, region='cn')
        k2 = svc._generate_cache_key('way', '3', None, None, region='id')
        assert k1 != k2
        # 多语路名参与键
        k3 = svc._generate_cache_key(
            'way', '8', None, None, region='id', name_id='Jalan Tol Jagorawi')
        k4 = svc._generate_cache_key(
            'way', '8', None, None, region='id', name_id='Jalan Tol Cipularang')
        assert k3 != k4

    def test_force_tol_only_appended_when_true(self):
        """force_tol=False 的键与历史版本逐字节相同 → 旧缓存行继续命中"""
        svc = RoadSignService()
        import hashlib
        legacy = hashlib.md5('id:way:8::雅加达收费高速::'.encode()).hexdigest()
        assert svc._generate_cache_key(
            'way', '8', None, '雅加达收费高速', region='id') == legacy
        # 同一输入 force_tol=True 走另一键，不污染旧行
        assert svc._generate_cache_key(
            'way', '8', None, '雅加达收费高速', region='id', force_tol=True) != legacy


class TestMissingAssets:
    """资源缺失路径（质量审查变异 D：此前该分支零覆盖）"""

    def test_missing_indonesia_assets_raises(self, monkeypatch):
        """DATA_DIR 指向空目录 → get_or_create_sign(region='id') 抛 FileNotFoundError"""
        import asyncio
        import tempfile
        from app.core.config import settings
        from app.services.config_service import config_service
        from app.services.road_sign_service import RoadSignService

        class _StubResult:
            def scalar_one_or_none(self):
                return None

        class _StubDB:
            async def execute(self, *args, **kwargs):
                return _StubResult()

        async def _empty_configs(_db):
            return {}

        with tempfile.TemporaryDirectory() as empty_dir:
            monkeypatch.setattr(settings, 'DATA_DIR', empty_dir)
            monkeypatch.setattr(config_service, 'get_all_configs', _empty_configs)
            with pytest.raises(FileNotFoundError, match='印尼盾牌资源缺失'):
                asyncio.run(RoadSignService().get_or_create_sign(
                    _StubDB(), 'way', '3', region='id'))
