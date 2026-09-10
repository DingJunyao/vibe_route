# -*- coding: utf-8 -*-
"""地区常量与印尼道路编号/省份代码逻辑。

移植自 gpxutil 项目 src/gpxutil/models/indonesia.py（同作者），与之对齐，并保留两处修正：
1. TOL 关键词匹配：ASCII 词使用 \\b 词边界（'Tol' 不误伤 'Toleransi'），中文等非 ASCII 词用子串；
2. 省名查表对无前缀文本容错（Nominatim 返回的 'Jawa Timur' 可补 'Provinsi ' 前缀命中）。

region 值域（'cn' | 'id'）常量暂居本文件；后续新增地区时如跨模块泛用，
再抽独立常量模块（ponytail: 现阶段仅本文件与两处判断点引用）。
"""
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, unique

REGION_CN = 'cn'
REGION_ID = 'id'
REGION_VALUES = (REGION_CN, REGION_ID)

# 印尼道路编号的地区代码（kode wilayah，Peraturan Dirjen Hubdat
# KP.1324/AJ.001/DRJD/2019 Lampiran I）：省级为 1-34 序号，与行政区划代码（BPS/ISO）无关
# （如东爪哇为 '16'，而非 BPS 的 '35'）；县市级为"省码.省内序号"（如 '16.17'）。
# 键为三语省名：印尼语（CSV province_id 字段）、中文（province 字段）、英文（province_en 字段）。
# 注：2022 年新设的巴布亚四省尚无法规代码，未收录。
INDONESIA_PROVINCE_CODE_MAP = {
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

# 印尼省份常见前缀（查表容错用）。'Jawa Timur' → 'Provinsi Jawa Timur'
_PROVINCE_NAME_PREFIXES = ('Provinsi ', 'Daerah Istimewa ', 'Daerah Khusus Ibukota ')

# 由三语表推导：地区代码 → 中文省名（fill geocoding 中文回填用）。
# 中文名非 ASCII，印尼语/英语名均为 ASCII，故按 isascii 取非 ASCII 键。
_PROVINCE_ZH_BY_CODE = {
    code: zh for name, code in INDONESIA_PROVINCE_CODE_MAP.items()
    if not name.isascii() for zh in (name,)
}


def get_indonesia_province_code(province_text: str | None) -> str | None:
    """按省名文本查地区代码：支持印尼语全名、中文名、英文名与省略前缀的印尼语名（如 'Jawa Timur'）。

    注意：返回的是 kode wilayah（'1'~'34'），不是 BPS 码。查不到返回 None。
    """
    if not province_text:
        return None
    text = province_text.strip()
    if text in INDONESIA_PROVINCE_CODE_MAP:
        return INDONESIA_PROVINCE_CODE_MAP[text]
    # 无前缀容错：补常见前缀再查
    for prefix in _PROVINCE_NAME_PREFIXES:
        key = prefix + text
        if key in INDONESIA_PROVINCE_CODE_MAP:
            return INDONESIA_PROVINCE_CODE_MAP[key]
    return None


def get_indonesia_province_zh(province_id_text: str | None) -> str | None:
    """按印尼语省名文本回查中文省名（fill geocoding 中文尽力而为用）。查不到返回 None。"""
    code = get_indonesia_province_code(province_id_text)
    return _PROVINCE_ZH_BY_CODE.get(code) if code else None


@unique
class IndonesiaRoadLevel(Enum):
    """印尼道路等级"""
    NASIONAL = 1
    TOL = 2
    PROVINSI = 3


@dataclass
class IndonesiaRoadInfo:
    """解析后的印尼道路信息"""
    level: IndonesiaRoadLevel
    code: str              # 纯编号，盾牌大字显示用（如 '024'）
    province_code: str | None  # 地区代码，色带显示用（国家级/收费公路为省码如 '16'，
                               # 省级公路为县市码如 '16.17'）


def _keyword_in_text(keyword: str, text_lower: str) -> bool:
    """关键词匹配：ASCII 字母数字词用词边界（\\btol\\b 不误伤 Toleransi），其余子串。"""
    # 注意：\b 为 Unicode 词边界，CJK 亦视为词字符，中英紧邻（如「泗水Tol高速」）会漏配；
    # 实际判定文本由各语言路名以空格 join，中英被空格隔开，风险低；如需纯 ASCII 词边界可用 (?a) 内联标志。
    if keyword.isascii() and keyword.isalnum():
        return re.search(rf'\b{re.escape(keyword.lower())}\b', text_lower) is not None
    return keyword.lower() in text_lower


def parse_indonesia_road_num(
        road_num: str | None,
        road_names: Sequence[str | None] | None,
        province_texts: Sequence[str | None],
        tol_keywords: list[str],
        force_tol: bool = False,
) -> IndonesiaRoadInfo | None:
    """
    解析印尼道路编号（spec 第 5 节规则）。

    :param road_num: CSV road_num 字段，如 '3'、'023'、'16-024'、'16.17-024'；空则无盾牌
    :param road_names: 道路名文本序列（如 [road_name, road_name_id]），任一含 TOL 关键词即判 TOL
    :param province_texts: 候选省份文本（印尼语/中文/英文省名，或省级地区代码），按顺序查代码
    :param tol_keywords: TOL 判定关键词（如 ['收费', 'Tol']）
    :param force_tol: 强制按收费公路（TOL）解析，仅 1-2 位编号有效
    :return: 解析结果；无法识别返回 None
    """
    if not road_num:
        return None
    road_num = road_num.strip()

    province_code = None
    if '-' in road_num:
        # '16-024'（省码）、'16.17-024'（县市码）：连字符前为地区代码，
        # 须命中省代码值集（或为 省码.县序号 形式）才作为地区代码，
        # 否则（含 'abc-024'、'99-024'、'-024' 等）回退到下方 province_texts 查找
        embedded, code = road_num.split('-', 1)
        embedded, code = embedded.strip(), code.strip()
        if embedded in INDONESIA_PROVINCE_CODE_MAP.values():
            province_code = embedded
        elif '.' in embedded:
            province_part, city_part = embedded.split('.', 1)
            if (province_part in INDONESIA_PROVINCE_CODE_MAP.values()
                    and city_part.isascii() and city_part.isdigit()):
                province_code = embedded
    else:
        code = road_num.strip()

    # 仅接受 ASCII 数字，'３'（全角）等 Unicode 数字视为无法识别
    if not (code.isascii() and code.isdigit()):
        return None

    if len(code) == 3:
        level = IndonesiaRoadLevel.PROVINSI
    elif len(code) in (1, 2):
        # road_names 可为 None（无路名），此时无关键词可判，不判 TOL
        names_lower = ' '.join(n for n in (road_names or []) if n).lower()
        if force_tol or any(_keyword_in_text(kw, names_lower) for kw in tol_keywords):
            level = IndonesiaRoadLevel.TOL
        else:
            level = IndonesiaRoadLevel.NASIONAL
    else:
        return None

    if province_code is None:
        for text in province_texts:
            if text is None:
                continue
            # 允许直接传省级地区代码（如 '16'）
            if text in INDONESIA_PROVINCE_CODE_MAP.values():
                province_code = text
                break
            province_code = get_indonesia_province_code(text)
            if province_code:
                break

    return IndonesiaRoadInfo(level=level, code=code, province_code=province_code)
