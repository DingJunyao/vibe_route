# -*- coding: utf-8 -*-
"""地区常量与印尼道路编号/省份代码逻辑。

移植自 gpxutil 项目 src/gpxutil/models/indonesia.py（同作者），两处修正：
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

# 印尼省份代码（ISO 3166-2:ID 两位代码）：印尼语省名（CSV province_id 字段）与中文省名双键。
# 印尼语名与中文名成对出现；_PROVINCE_ZH_BY_CODE/_PROVINCE_ID_BY_CODE 按 isascii 属性区分推导。
INDONESIA_PROVINCE_CODE_MAP = {
    'Provinsi Aceh': '11', '亚齐特别行政区': '11',
    'Provinsi Sumatera Utara': '12', '北苏门答腊省': '12',
    'Provinsi Sumatera Barat': '13', '西苏门答腊省': '13',
    'Provinsi Riau': '14', '廖内省': '14',
    'Provinsi Jambi': '15', '占碑省': '15',
    'Provinsi Sumatera Selatan': '16', '南苏门答腊省': '16',
    'Provinsi Bengkulu': '17', '明古鲁省': '17',
    'Provinsi Lampung': '18', '楠榜省': '18',
    'Provinsi Kepulauan Bangka Belitung': '19', '邦加勿里洞群岛省': '19',
    'Provinsi Kepulauan Riau': '21', '廖内群岛省': '21',
    'Daerah Khusus Ibukota Jakarta': '31', '雅加达首都特区': '31',
    'Provinsi Jawa Barat': '32', '西爪哇省': '32',
    'Provinsi Jawa Tengah': '33', '中爪哇省': '33',
    'Daerah Istimewa Yogyakarta': '34', '日惹特区': '34',
    'Provinsi Jawa Timur': '35', '东爪哇省': '35',
    'Provinsi Banten': '36', '万丹省': '36',
    'Provinsi Bali': '51', '巴厘省': '51',
    'Provinsi Nusa Tenggara Barat': '52', '西努沙登加拉省': '52',
    'Provinsi Nusa Tenggara Timur': '53', '东努沙登加拉省': '53',
    'Provinsi Kalimantan Barat': '61', '西加里曼丹省': '61',
    'Provinsi Kalimantan Tengah': '62', '中加里曼丹省': '62',
    'Provinsi Kalimantan Selatan': '63', '南加里曼丹省': '63',
    'Provinsi Kalimantan Timur': '64', '东加里曼丹省': '64',
    'Provinsi Kalimantan Utara': '65', '北加里曼丹省': '65',
    'Provinsi Sulawesi Utara': '71', '北苏拉威西省': '71',
    'Provinsi Sulawesi Tengah': '72', '中苏拉威西省': '72',
    'Provinsi Sulawesi Selatan': '73', '南苏拉威西省': '73',
    'Provinsi Sulawesi Tenggara': '74', '东南苏拉威西省': '74',
    'Provinsi Gorontalo': '75', '哥伦打洛省': '75',
    'Provinsi Sulawesi Barat': '76', '西苏拉威西省': '76',
    'Provinsi Maluku': '81', '马鲁古省': '81',
    'Provinsi Maluku Utara': '82', '北马鲁古省': '82',
    'Provinsi Papua': '91', '巴布亚省': '91',
    'Provinsi Papua Barat': '92', '西巴布亚省': '92',
    'Provinsi Papua Selatan': '93', '南巴布亚省': '93',
    'Provinsi Papua Tengah': '94', '中巴布亚省': '94',
    'Provinsi Papua Pegunungan': '95', '高地巴布亚省': '95',
    'Provinsi Papua Barat Daya': '96', '西南巴布亚省': '96',
}

# 印尼省份常见前缀（查表容错用）。'Jawa Timur' → 'Provinsi Jawa Timur'
_PROVINCE_NAME_PREFIXES = ('Provinsi ', 'Daerah Istimewa ', 'Daerah Khusus Ibukota ')

# 由双键表推导：省代码 → 中文省名（fill geocoding 中文回填用）
_PROVINCE_ZH_BY_CODE = {
    code: zh for name, code in INDONESIA_PROVINCE_CODE_MAP.items()
    if not name.isascii() for zh in (name,)
}
# 省代码 → 印尼语省名（备查）
_PROVINCE_ID_BY_CODE = {
    code: id_ for name, code in INDONESIA_PROVINCE_CODE_MAP.items()
    if name.isascii() for id_ in (name,)
}


def get_indonesia_province_code(province_text: str | None) -> str | None:
    """按省名文本查省代码：支持印尼语全名、中文名与省略前缀的印尼语名（如 'Jawa Timur'）。

    查不到返回 None。
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
    province_code: str | None  # 省份代码，色带显示用（如 '35'）


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
) -> IndonesiaRoadInfo | None:
    """
    解析印尼道路编号（spec 第 5 节规则）。

    :param road_num: CSV road_num 字段，如 '3'、'023'、'35-024'；空则无盾牌
    :param road_names: 道路名文本序列（如 [road_name, road_name_id]），任一含 TOL 关键词即判 TOL
    :param province_texts: 候选省份文本（印尼语名、中文名，可为 None），按顺序查代码
    :param tol_keywords: TOL 判定关键词（如 ['收费', 'Tol']）
    :return: 解析结果；无法识别返回 None
    """
    if not road_num:
        return None
    road_num = road_num.strip()

    province_code = None
    if '-' in road_num:
        # '35-024'：连字符前为省代码；须命中省代码表才作为省码，
        # 否则（含 'abc-024'、'99-024' 等）回退到下方 province_texts 查找；
        # 空前缀（'-024'）无内嵌省码可查，视为无法识别的乱串
        embedded, code = road_num.split('-', 1)
        embedded, code = embedded.strip(), code.strip()
        if not embedded:
            return None
        if embedded in INDONESIA_PROVINCE_CODE_MAP.values():
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
        if any(_keyword_in_text(kw, names_lower) for kw in tol_keywords):
            level = IndonesiaRoadLevel.TOL
        else:
            level = IndonesiaRoadLevel.NASIONAL
    else:
        return None

    if province_code is None:
        for text in province_texts:
            province_code = get_indonesia_province_code(text)
            if province_code:
                break

    return IndonesiaRoadInfo(level=level, code=code, province_code=province_code)
