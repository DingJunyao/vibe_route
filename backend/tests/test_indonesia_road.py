# -*- coding: utf-8 -*-
"""印尼道路编号解析与省份代码表单元测试"""

from app.gpxutil_wrapper.indonesia import (
    INDONESIA_PROVINCE_CODE_MAP,
    IndonesiaRoadLevel,
    get_indonesia_province_code,
    parse_indonesia_road_num,
)


class TestParseIndonesiaRoadNum:
    """编号解析（spec §8 用例 1）"""

    def test_nasional(self):
        info = parse_indonesia_road_num('3', None, [], ['收费', 'Tol'])
        assert info is not None and info.level == IndonesiaRoadLevel.NASIONAL
        assert info.code == '3'

    def test_nasional_two_digits(self):
        info = parse_indonesia_road_num('15', None, [], ['收费', 'Tol'])
        assert info is not None and info.level == IndonesiaRoadLevel.NASIONAL

    def test_tol_by_chinese_keyword(self):
        info = parse_indonesia_road_num('8', ['泗水收费高速'], [], ['收费', 'Tol'])
        assert info is not None and info.level == IndonesiaRoadLevel.TOL

    def test_tol_by_english_keyword_case_insensitive(self):
        info = parse_indonesia_road_num('8', ['jalan tol'], [], ['收费', 'Tol'])
        assert info is not None and info.level == IndonesiaRoadLevel.TOL

    def test_no_road_name_not_tol(self):
        # 无路名不判 TOL
        info = parse_indonesia_road_num('8', None, [], ['收费', 'Tol'])
        assert info is not None and info.level == IndonesiaRoadLevel.NASIONAL

    def test_tol_by_uppercase_english_keyword(self):
        # 大写路名文本同样命中 TOL（词边界大小写不敏感）
        info = parse_indonesia_road_num('8', ['JALAN TOL'], [], ['收费', 'Tol'])
        assert info is not None and info.level == IndonesiaRoadLevel.TOL

    def test_tol_word_boundary_not_substring(self):
        # 词边界：Toleransi 不应误判为 TOL
        info = parse_indonesia_road_num('8', ['Jalan Toleransi'], [], ['收费', 'Tol'])
        assert info is not None and info.level == IndonesiaRoadLevel.NASIONAL

    def test_tol_from_road_name_id(self):
        # 判定文本取 road_name 与 road_name_id 任一命中（road_names 序列）
        info = parse_indonesia_road_num(
            '8', ['', 'Jalan Tol Jagorawi'], [], ['收费', 'Tol'])
        assert info is not None and info.level == IndonesiaRoadLevel.TOL

    def test_provinsi_three_digits(self):
        info = parse_indonesia_road_num('023', None, [], ['收费', 'Tol'])
        assert info is not None and info.level == IndonesiaRoadLevel.PROVINSI
        assert info.code == '023'
        assert info.province_code is None

    def test_provinsi_with_embedded_code(self):
        info = parse_indonesia_road_num('35-024', None, [], ['收费', 'Tol'])
        assert info is not None and info.level == IndonesiaRoadLevel.PROVINSI
        assert info.code == '024'
        assert info.province_code == '35'

    def test_embedded_code_not_in_table_falls_back(self):
        # 99 不是合法省码：回退到省名文本查找
        info = parse_indonesia_road_num(
            '99-024', None, ['Provinsi Jawa Timur', '东爪哇省'], ['收费', 'Tol'])
        assert info is not None and info.level == IndonesiaRoadLevel.PROVINSI
        assert info.province_code == '35'

    def test_province_from_chinese_text(self):
        info = parse_indonesia_road_num('024', None, ['东爪哇省'], ['收费', 'Tol'])
        assert info is not None and info.province_code == '35'

    def test_province_from_prefixless_text(self):
        # Nominatim 风格无前缀省名也要能查到
        info = parse_indonesia_road_num('024', None, ['Jawa Timur'], ['收费', 'Tol'])
        assert info is not None and info.province_code == '35'

    def test_empty_returns_none(self):
        assert parse_indonesia_road_num('', None, [], ['收费', 'Tol']) is None
        assert parse_indonesia_road_num(None, None, [], ['收费', 'Tol']) is None

    def test_garbage_returns_none(self):
        assert parse_indonesia_road_num('abc', None, [], ['收费', 'Tol']) is None
        assert parse_indonesia_road_num('35-ab', None, [], ['收费', 'Tol']) is None
        assert parse_indonesia_road_num('-024', None, [], ['收费', 'Tol']) is None
        # 全角数字视为无法识别
        assert parse_indonesia_road_num('３', None, [], ['收费', 'Tol']) is None
        # 过长编号
        assert parse_indonesia_road_num('1234', None, [], ['收费', 'Tol']) is None


class TestProvinceCodeMap:
    """38 省代码表完整性（spec §8 用例 2）"""

    def test_full_map_size(self):
        # 38 个省份 × 双键 = 76 个条目
        assert len(INDONESIA_PROVINCE_CODE_MAP) == 76

    def test_no_duplicate_keys(self):
        keys = list(INDONESIA_PROVINCE_CODE_MAP.keys())
        assert len(keys) == len(set(keys))

    def test_all_values_two_digits(self):
        for code in INDONESIA_PROVINCE_CODE_MAP.values():
            assert code.isdigit() and len(code) == 2, code

    def test_roundtrip_by_code(self):
        # 每个省代码同时有印尼语名与中文名两个键
        seen = {}
        for name, code in INDONESIA_PROVINCE_CODE_MAP.items():
            seen.setdefault(code, []).append(name)
        for code, names in seen.items():
            assert len(names) == 2, code
            id_name = names[0] if names[0].isascii() else names[1]
            zh_name = names[1] if names[0].isascii() else names[0]
            # 中文名含中文，印尼语名全 ASCII
            assert id_name.isascii() and not zh_name.isascii()

    def test_get_code_by_name(self):
        assert get_indonesia_province_code('Provinsi Jawa Timur') == '35'
        assert get_indonesia_province_code('东爪哇省') == '35'
        assert get_indonesia_province_code('Jawa Timur') == '35'  # 无前缀容错
        assert get_indonesia_province_code(None) is None
        assert get_indonesia_province_code('不存在的地方') is None
