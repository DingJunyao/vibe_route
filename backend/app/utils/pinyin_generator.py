"""
拼音生成工具

用于将中文地名转换为拼音，处理多音字和特殊地名映射。
"""
import yaml
from pathlib import Path
from pypinyin import lazy_pinyin, Style
from typing import Optional


# 省级后缀映射
PROVINCE_SUFFIXES = {
    "省": "Province",
    "自治区": "Autonomous Region",
    "直辖市": "Municipality",
}

# 地级行政单位后缀
PREFECTURE_SUFFIXES = {
    "市": "City",                    # 地级市
    "地区": "Prefecture",            # 地区
    "自治州": "Prefecture",          # 自治州
    "盟": "League",                  # 盟
}

# 县级行政单位后缀
COUNTY_SUFFIXES = {
    "区": "District",               # 市辖区
    "市": "City",                   # 县级市
    "县": "County",                 # 县
    "自治县": "Autonomous County",   # 自治县
    "旗": "Banner",                 # 旗
    "自治旗": "Autonomous Banner",   # 自治旗
    "林区": "Forest District",      # 林区
    "特区": "Special District",     # 特区
}


# 特殊地名映射缓存
_special_mapping: Optional[dict] = None


def load_special_mapping() -> dict:
    """
    加载特殊地名映射表

    Returns:
        dict: 中文名称到英文的映射
    """
    global _special_mapping
    if _special_mapping is not None:
        return _special_mapping

    mapping_file = Path(__file__).parent.parent.parent / "data" / "area_data" / "special_place_mapping.yaml"

    _special_mapping = {}
    if mapping_file.exists():
        with open(mapping_file, "r", encoding="utf-8") as f:
            _special_mapping = yaml.safe_load(f) or {}

    return _special_mapping


def name_to_pinyin(
    name: str,
    level: str,
    special_mapping: Optional[dict] = None
) -> str:
    """
    将中文地名转换为拼音 + 后缀

    Args:
        name: 中文名称
        level: 层级 (province/city/area)
        special_mapping: 特殊地名映射表（可选，如果不提供则从文件加载）

    Returns:
        str: 英文名称（拼音 + 后缀）

    Examples:
        >>> name_to_pinyin("河北省", "province")
        "Hebei Province"
        >>> name_to_pinyin("重庆市", "city")
        "Chongqing Municipality"
        >>> name_to_pinyin("房县", "area")
        "Fangxian County"
        >>> name_to_pinyin("阿克苏地区", "city")
        "Aksu Prefecture"
    """
    if special_mapping is None:
        special_mapping = load_special_mapping()

    # 首先用完整名称查找特殊映射
    if name in special_mapping:
        mapped_value = special_mapping[name]
        # 检查是否是完整英文名称（包含空格，说明已经有完整后缀）
        # 完整映射示例: "延边朝鲜族自治州: Yanbian Korean Autonomous Prefecture"
        # 基础映射示例: "北京市: Beijing" （需要添加后缀）
        if ' ' in mapped_value or 'Autonomous' in mapped_value:
            return mapped_value
        # 基础映射，需要添加后缀
        suffix_type, _ = _extract_suffix_from_name(name, level)
        suffix_en = _get_english_suffix(suffix_type, level)
        if mapped_value and suffix_en:
            return f"{mapped_value} {suffix_en}"
        return mapped_value

    # 获取后缀类型（从名称末尾提取）
    suffix_type, base_name_zh = _extract_suffix_from_name(name, level)

    # 检查基础名称是否在特殊映射中
    base_name_en = None
    if base_name_zh in special_mapping:
        base_name_en = special_mapping[base_name_zh]
    else:
        # 使用拼音转换
        base_name_en = _convert_to_pinyin(base_name_zh)

    # 获取英文后缀
    suffix_en = _get_english_suffix(suffix_type, level)

    # 组合
    if base_name_en and suffix_en:
        return f"{base_name_en} {suffix_en}"
    elif base_name_en:
        return base_name_en
    else:
        return name


def _extract_suffix_from_name(name: str, level: str) -> tuple[str, str]:
    """
    从名称中提取后缀类型和基础名称

    Args:
        name: 完整名称
        level: 层级

    Returns:
        tuple: (后缀类型, 基础中文名称)
    """
    # 省级
    if level == "province":
        for suffix, en in PROVINCE_SUFFIXES.items():
            if name.endswith(suffix):
                return suffix, name[:-len(suffix)]

    # 地级
    if level == "city":
        for suffix, en in PREFECTURE_SUFFIXES.items():
            if name.endswith(suffix):
                return suffix, name[:-len(suffix)]

    # 县级
    if level == "area":
        for suffix, en in COUNTY_SUFFIXES.items():
            if name.endswith(suffix):
                return suffix, name[:-len(suffix)]

    # 默认：没有后缀
    return "", name


def _convert_to_pinyin(name: str) -> str:
    """
    将中文名称转换为拼音

    Args:
        name: 中文名称（不含后缀）

    Returns:
        str: 拼音（首字母大写，单词间合并）
    """
    pinyin_list = lazy_pinyin(name, style=Style.NORMAL)
    return "".join(pinyin_list).capitalize()


def _get_english_suffix(suffix_type: str, level: str) -> str:
    """
    获取英文后缀

    Args:
        suffix_type: 后缀类型（如 "市"、"县" 等）
        level: 层级

    Returns:
        str: 英文后缀
    """
    if not suffix_type:
        # 没有识别出后缀，根据层级返回默认值
        if level == "province":
            return "Province"
        elif level == "city":
            return "City"
        elif level == "area":
            return "County"
        return ""

    # 根据层级和后缀类型返回英文
    if level == "province":
        return PROVINCE_SUFFIXES.get(suffix_type, "Province")
    elif level == "city":
        return PREFECTURE_SUFFIXES.get(suffix_type, "City")
    elif level == "area":
        return COUNTY_SUFFIXES.get(suffix_type, "County")
    return ""


def get_name_en(
    name: str,
    code: str,
    level: str,
    special_mapping: Optional[dict] = None
) -> str:
    """
    获取行政区划的英文名称

    根据代码判断类型（直辖市/自治区等）

    Args:
        name: 中文名称
        code: 行政区划代码
        level: 层级
        special_mapping: 特殊地名映射表

    Returns:
        str: 英文名称
    """
    return name_to_pinyin(name, level, special_mapping)
