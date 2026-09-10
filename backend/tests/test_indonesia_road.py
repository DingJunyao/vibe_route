# -*- coding: utf-8 -*-
"""印尼道路编号解析与地区代码表单元测试。

用例移植自 gpxutil tests/test_indonesia_road.py 与 tests/test_indonesia_province.py
（同作者），签名差异：本仓库 road_names 为序列（[road_name, road_name_id]）、
字段名为 province_code（gpxutil 为 region_code）。
"""

from app.gpxutil_wrapper.indonesia import (
    INDONESIA_PROVINCE_CODE_MAP,
    IndonesiaRoadLevel,
    get_indonesia_province_code,
    parse_indonesia_road_num,
)

TOL_KEYWORDS = ['收费', 'Tol']
# 东爪哇省的 kode wilayah（KP.1324/AJ.001/DRJD/2019 Lampiran I）为 16（非 BPS 的 35）
PROVINCES = ['Provinsi Jawa Timur', '东爪哇省']


class TestParseIndonesiaRoadNum:
    """编号解析（spec §8 用例 1）"""

    def test_nasional(self):
        info = parse_indonesia_road_num('3', ['Jl. Nasional III'], PROVINCES, TOL_KEYWORDS)
        assert info is not None and info.level == IndonesiaRoadLevel.NASIONAL
        assert info.code == '3'
        assert info.province_code == '16'

    def test_nasional_two_digits(self):
        info = parse_indonesia_road_num('15', None, [], TOL_KEYWORDS)
        assert info is not None and info.level == IndonesiaRoadLevel.NASIONAL

    def test_tol_by_chinese_keyword(self):
        info = parse_indonesia_road_num('8', ['泗水-波龙收费公路'], PROVINCES, TOL_KEYWORDS)
        assert info is not None and info.level == IndonesiaRoadLevel.TOL
        assert info.code == '8'

    def test_tol_by_indonesian_keyword(self):
        info = parse_indonesia_road_num('8', ['Jl. Tol Pandaan - Malang'], PROVINCES, TOL_KEYWORDS)
        assert info is not None and info.level == IndonesiaRoadLevel.TOL

    def test_tol_by_uppercase_english_keyword(self):
        # 大写路名文本同样命中 TOL（大小写不敏感）
        info = parse_indonesia_road_num('8', ['JALAN TOL'], [], TOL_KEYWORDS)
        assert info is not None and info.level == IndonesiaRoadLevel.TOL

    def test_tol_from_road_name_id(self):
        # 判定文本取 road_name 与 road_name_id 任一命中（road_names 序列）
        info = parse_indonesia_road_num('8', ['', 'Jalan Tol Jagorawi'], [], TOL_KEYWORDS)
        assert info is not None and info.level == IndonesiaRoadLevel.TOL

    def test_tol_word_boundary_not_substring(self):
        # 本仓库相对 gpxutil 的修正：词边界，'Toleransi' 不误判为 TOL
        info = parse_indonesia_road_num('8', ['Jalan Toleransi'], [], TOL_KEYWORDS)
        assert info is not None and info.level == IndonesiaRoadLevel.NASIONAL

    def test_no_road_name_not_tol(self):
        # 无路名时无关键词可判，不判 TOL
        info = parse_indonesia_road_num('8', None, [], TOL_KEYWORDS)
        assert info is not None and info.level == IndonesiaRoadLevel.NASIONAL

    def test_force_tol_without_name(self):
        # 无路名时用 force_tol 强制判定为收费公路
        info = parse_indonesia_road_num('8', None, PROVINCES, TOL_KEYWORDS, force_tol=True)
        assert info is not None and info.level == IndonesiaRoadLevel.TOL
        assert info.code == '8'

    def test_force_tol_ignored_for_three_digit(self):
        # force_tol 对 3 位编号（省道）无效
        info = parse_indonesia_road_num('023', None, PROVINCES, TOL_KEYWORDS, force_tol=True)
        assert info is not None and info.level == IndonesiaRoadLevel.PROVINSI

    def test_provinsi_three_digit(self):
        info = parse_indonesia_road_num('023', ['图姆庞大街'], PROVINCES, TOL_KEYWORDS)
        assert info is not None and info.level == IndonesiaRoadLevel.PROVINSI
        assert info.code == '023'
        assert info.province_code == '16'

    def test_provinsi_with_embedded_province(self):
        info = parse_indonesia_road_num('16-024', None, [], TOL_KEYWORDS)
        assert info is not None and info.level == IndonesiaRoadLevel.PROVINSI
        assert info.code == '024'
        assert info.province_code == '16'

    def test_provinsi_with_embedded_city_code(self):
        # 县市码内嵌（'16.17' = 东爪哇第 17 个县/市）：色带显示 'PROVINSI 16.17'
        info = parse_indonesia_road_num('16.17-024', ['图卢斯阿尤大街'], PROVINCES, TOL_KEYWORDS)
        assert info is not None and info.level == IndonesiaRoadLevel.PROVINSI
        assert info.code == '024'
        assert info.province_code == '16.17'

    def test_embedded_prefix_not_in_code_map_falls_back(self):
        # 'abc-023'：前缀非地区代码，不得作为地区代码，回退到 province_texts 查找
        info = parse_indonesia_road_num('abc-023', ['某路'], PROVINCES, TOL_KEYWORDS)
        assert info is not None and info.code == '023'
        assert info.province_code == '16'

    def test_embedded_unused_code_falls_back(self):
        # '99-024'：'99' 不在地区代码表中，回退到 province_texts 查找
        info = parse_indonesia_road_num('99-024', ['某路'], PROVINCES, TOL_KEYWORDS)
        assert info is not None and info.province_code == '16'

    def test_empty_embedded_prefix_falls_back(self):
        # '-024'：空前缀不得产生空串地区代码，回退到 province_texts 查找
        info = parse_indonesia_road_num('-024', ['某路'], PROVINCES, TOL_KEYWORDS)
        assert info is not None and info.code == '024'
        assert info.province_code == '16'

    def test_legacy_bps_prefixed_code_falls_back(self):
        # 旧数据 '35-024'（BPS 码）：'35' 不再是合法地区代码 → 回退省名查表得 '16'
        info = parse_indonesia_road_num('35-024', ['某路'], PROVINCES, TOL_KEYWORDS)
        assert info is not None and info.level == IndonesiaRoadLevel.PROVINSI
        assert info.code == '024'
        assert info.province_code == '16'

    def test_spaces_around_hyphen(self):
        # 连字符两侧空白：各段 strip 后再解析
        info = parse_indonesia_road_num(' 16 - 024 ', ['图卢斯阿尤大街'], PROVINCES, TOL_KEYWORDS)
        assert info is not None and info.code == '024'
        assert info.province_code == '16'

    def test_unicode_digit_not_recognized(self):
        assert parse_indonesia_road_num('３', ['某路'], PROVINCES, TOL_KEYWORDS) is None
        assert parse_indonesia_road_num('16-０２４', ['某路'], PROVINCES, TOL_KEYWORDS) is None

    def test_no_province_anywhere(self):
        info = parse_indonesia_road_num('023', ['某路'], [], TOL_KEYWORDS)
        assert info is not None and info.province_code is None

    def test_province_texts_accept_code(self):
        # province_texts 直接传省级地区代码（如 '16'）也有效
        info = parse_indonesia_road_num('024', ['某路'], ['16'], TOL_KEYWORDS)
        assert info is not None and info.province_code == '16'

    def test_province_texts_accept_english_name(self):
        info = parse_indonesia_road_num('024', ['某路'], ['Province of East Java'], TOL_KEYWORDS)
        assert info is not None and info.province_code == '16'

    def test_province_from_chinese_text(self):
        info = parse_indonesia_road_num('024', None, ['东爪哇省'], TOL_KEYWORDS)
        assert info is not None and info.province_code == '16'

    def test_province_from_prefixless_text(self):
        # 本仓库相对 gpxutil 的修正：Nominatim 风格无前缀省名也要能查到
        info = parse_indonesia_road_num('024', None, ['Jawa Timur'], TOL_KEYWORDS)
        assert info is not None and info.province_code == '16'

    def test_empty_returns_none(self):
        assert parse_indonesia_road_num('', None, [], TOL_KEYWORDS) is None
        assert parse_indonesia_road_num(None, None, [], TOL_KEYWORDS) is None

    def test_garbage_returns_none(self):
        assert parse_indonesia_road_num('abc', None, [], TOL_KEYWORDS) is None
        assert parse_indonesia_road_num('16-ab', None, [], TOL_KEYWORDS) is None
        # 过长编号
        assert parse_indonesia_road_num('1234', None, [], TOL_KEYWORDS) is None


# 印尼 34 省（2019 年）→ 道路编号的地区代码（kode wilayah，Peraturan Dirjen Hubdat
# KP.1324/AJ.001/DRJD/2019 Lampiran I）：省级为 1-34 序号，与行政区划代码（BPS）无关
# （如中爪哇 kode wilayah 为 14，BPS 为 33；东爪哇为 16，BPS 为 35）。
# 键为三语省名：印尼语（province_id 字段）、中文（province 字段）、英文（province_en 字段）。
# 注：2022 年新设的巴布亚四省无法规代码，未收录。
EXPECTED_PROVINCE_CODES = {
    'Provinsi Aceh': '1', '亚齐特别行政区': '1', 'Province of Aceh': '1',
    'Provinsi Sumatera Utara': '2', '北苏门答腊省': '2', 'Province of North Sumatra': '2',
    'Provinsi Riau': '3', '廖内省': '3', 'Province of Riau': '3',
    'Provinsi Sumatera Barat': '4', '西苏门答腊省': '4', 'Province of West Sumatra': '4',
    'Provinsi Jambi': '5', '占碑省': '5', 'Province of Jambi': '5',
    'Provinsi Sumatera Selatan': '6', '南苏门答腊省': '6', 'Province of South Sumatra': '6',
    'Provinsi Bengkulu': '7', '明古鲁省': '7', 'Province of Bengkulu': '7',
    'Provinsi Lampung': '8', '楠榜省': '8', 'Province of Lampung': '8',
    'Provinsi Kepulauan Riau': '9', '廖内群岛省': '9', 'Province of Riau Islands': '9',
    'Provinsi Kepulauan Bangka Belitung': '10', '邦加勿里洞群岛省': '10', 'Province of Bangka Belitung Islands': '10',
    'Provinsi Banten': '11', '万丹省': '11', 'Province of Banten': '11',
    'Provinsi Jawa Barat': '12', '西爪哇省': '12', 'Province of West Java': '12',
    'Daerah Khusus Ibukota Jakarta': '13', '雅加达首都特区': '13', 'Special Capital Region of Jakarta': '13',
    'Provinsi Jawa Tengah': '14', '中爪哇省': '14', 'Province of Central Java': '14',
    'Daerah Istimewa Yogyakarta': '15', '日惹特区': '15', 'Special Region of Yogyakarta': '15',
    'Provinsi Jawa Timur': '16', '东爪哇省': '16', 'Province of East Java': '16',
    'Provinsi Bali': '17', '巴厘省': '17', 'Province of Bali': '17',
    'Provinsi Nusa Tenggara Barat': '18', '西努沙登加拉省': '18', 'Province of West Nusa Tenggara': '18',
    'Provinsi Nusa Tenggara Timur': '19', '东努沙登加拉省': '19', 'Province of East Nusa Tenggara': '19',
    'Provinsi Kalimantan Barat': '20', '西加里曼丹省': '20', 'Province of West Kalimantan': '20',
    'Provinsi Kalimantan Tengah': '21', '中加里曼丹省': '21', 'Province of Central Kalimantan': '21',
    'Provinsi Kalimantan Selatan': '22', '南加里曼丹省': '22', 'Province of South Kalimantan': '22',
    'Provinsi Kalimantan Timur': '23', '东加里曼丹省': '23', 'Province of East Kalimantan': '23',
    'Provinsi Kalimantan Utara': '24', '北加里曼丹省': '24', 'Province of North Kalimantan': '24',
    'Provinsi Sulawesi Selatan': '25', '南苏拉威西省': '25', 'Province of South Sulawesi': '25',
    'Provinsi Sulawesi Barat': '26', '西苏拉威西省': '26', 'Province of West Sulawesi': '26',
    'Provinsi Sulawesi Tenggara': '27', '东南苏拉威西省': '27', 'Province of Southeast Sulawesi': '27',
    'Provinsi Sulawesi Tengah': '28', '中苏拉威西省': '28', 'Province of Central Sulawesi': '28',
    'Provinsi Gorontalo': '29', '哥伦打洛省': '29', 'Province of Gorontalo': '29',
    'Provinsi Sulawesi Utara': '30', '北苏拉威西省': '30', 'Province of North Sulawesi': '30',
    'Provinsi Maluku': '31', '马鲁古省': '31', 'Province of Maluku': '31',
    'Provinsi Maluku Utara': '32', '北马鲁古省': '32', 'Province of North Maluku': '32',
    'Provinsi Papua Barat': '33', '西巴布亚省': '33', 'Province of West Papua': '33',
    'Provinsi Papua': '34', '巴布亚省': '34', 'Province of Papua': '34',
}


class TestProvinceCodeMap:
    """34 省三语代码表完整性（spec §8 用例 2）"""

    def test_map_complete(self):
        # 34 省 × 三语键 = 102 条，无缺漏、无多余别名（锁住值错位）
        assert len(INDONESIA_PROVINCE_CODE_MAP) == len(EXPECTED_PROVINCE_CODES) == 102
        assert INDONESIA_PROVINCE_CODE_MAP == EXPECTED_PROVINCE_CODES

    def test_all_values_in_1_to_34(self):
        assert set(INDONESIA_PROVINCE_CODE_MAP.values()) == {str(i) for i in range(1, 35)}

    def test_three_keys_per_code(self):
        # 每个代码三语各一键：中文名非 ASCII，印尼语/英语名均为 ASCII
        seen = {}
        for name, code in INDONESIA_PROVINCE_CODE_MAP.items():
            seen.setdefault(code, []).append(name)
        for code, names in seen.items():
            assert len(names) == 3, code
            assert len([n for n in names if n.isascii()]) == 2, code
            assert len([n for n in names if not n.isascii()]) == 1, code

    def test_get_code_by_name(self):
        assert get_indonesia_province_code('Provinsi Jawa Timur') == '16'
        assert get_indonesia_province_code('东爪哇省') == '16'
        assert get_indonesia_province_code('Province of East Java') == '16'
        assert get_indonesia_province_code('Jawa Timur') == '16'  # 无前缀容错
        assert get_indonesia_province_code(None) is None
        assert get_indonesia_province_code('不存在的地方') is None

    def test_get_zh_by_id_text(self):
        from app.gpxutil_wrapper.indonesia import get_indonesia_province_zh
        assert get_indonesia_province_zh('Provinsi Jawa Timur') == '东爪哇省'
        assert get_indonesia_province_zh('不存在的地方') is None
