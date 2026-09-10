# 印尼多语言与道路图标适配实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Vibe Route 从仅中国内地适配扩展为支持印尼：保存/导入/导出多语言轨迹信息（zh/id/en）、生成印尼六边形道路盾牌并按 region 在轨迹详情正确显示，架构上预留其他地区（region 值域可扩展）。

**Architecture:** region（`cn`/`id`，可扩展）为点级权威概念：`track_points.region` 决定图标解析/显示体系，`tracks.region` 是新建点的默认值，`road_sign_cache.region` 隔离不同地区缓存。多语言文本用语言后缀平铺列承载（中文无后缀历史遗留、`*_id` 印尼语、`*_en` 英语）。编号解析器/图标生成器按 region 分派，注册点集中在后端 `svg_gen.generate_road_sign` 与 `indonesia.py`。

**Tech Stack:** Python FastAPI + SQLAlchemy async + Alembic（SQLite/MySQL/PostgreSQL 三引擎 SQL 脚本）、pytest（backend/tests 新建）、Vue3 + TS + Element Plus、fontTools/svgpathtools/svgwrite。

**已批准设计:** `docs/superpowers/specs/2026-09-09-indonesia-multilanguage-design.md`（commit ef9386b）。本计划逐任务落实该 spec 第 10 节实施顺序。

**执行环境须知（写入时核对，防止漂移）:**
- 直接在 master 分支执行，每个任务一次 commit，git 署名追加 `Co-Authored-By: Claude Code <noreply@anthropic.com>`。
- 后端测试运行：`cd backend && ../.venv/Scripts/python -m pytest tests/xxx.py -v`（pytest 9.1.1 已装于根 .venv）。仓库无 pytest 配置——Task 1 建立。
- 前端无测试 runner，验证用 `npm run build:check`（vue-tsc && vite build）。
- 后端文件较大（track_service.py 已 3960+ 行），修改前先 Read 目标区段核对。**本计划中所有 `track_service.py` 行号都是历史快照，且会随每个任务持续漂移——一律以语义锚点（函数名 / 字段名 / 注释文本）grep 定位，行号只用于理解结构，不要按数字跳转。**
- 所有错误消息/注释/日志沿用仓库中文风格。
- 冒烟阶段需用户配合的事项（Clearview 字体许可确认）见 Task 3 开头，由执行协调者在 Task 3 前向用户确认。

**对 spec 的已记录实现级决策（写计划时确认，勿再变更）:**
1. 前端「名称 tooltip」用原生 `title` 属性实现（多语言文本拼接），不引入新 UI 组件——单语言无 title。
2. 前端为印尼图标请求 `/road-signs/generate` 时不传省名文本（道路节点拿不到父级省名），色带降级为只显示等级词（`NASIONAL`/`TOL`/`PROVINSI`）；`35-024` 类内嵌省码不受影响。spec 测试条目 8.3「无省码降级」因此是常态路径。
3. 前端 parse 分派不做单测：仓库无前端测试基础设施，`parseRoadNumber` 的 id 分支是单行直通逻辑，以 `build:check` + 双 region 浏览器冒烟替代（spec §8.10 调整，冒烟覆盖）。
4. `fill_geocoding_info` 的 region 参数缺省 None 时回读 `track.region`——上游 create 路径与 live recording 填充调用点零改动。
5. 区域树聚合中地区键统一取「回退链显示文本」（zh→id→en→哨兵），region 并入键；节点 `names` 记录各组创建后首见的各语言非空值（组内语言中途变化不拆组——现状也只在主文本切换时拆组，`ponytail:` 近似）。
6. SQL 脚本沿用仓库惯例放 `backend/alembic/versions/` 与迁移同目录，命名 `016_xxx.sql.sqlite|mysql|postgresql`（spec 未指定目录）。

---

### Task 1: pytest 基建 + 移植 `indonesia.py`（编号解析与 38 省表，含 TOL 词边界修正）+ 单元测试

**Files:**
- Create: `backend/tests/test_indonesia_road.py`
- Create: `backend/app/gpxutil_wrapper/indonesia.py`
- Modify: 无（本任务不碰既有文件）

移植自 `D:\code\gpxutil\src\gpxutil\models\indonesia.py`（同作者项目），修正两处：① TOL 关键词匹配由子串改为「ASCII 词边界 + 中文子串」；② 省名查表对 Nominatim 风格无前缀文本（如 `Jawa Timur`）容错（补 `Provinsi ` 等前缀再查）。

- [ ] **Step 1: 建目录并创建测试文件（红）**

`backend/tests/` 目录不存在，创建之。写入 `backend/tests/test_indonesia_road.py`：

```python
# -*- coding: utf-8 -*-
"""印尼道路编号解析与省份代码表单元测试"""
import pytest

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

    def test_tol_keyword_upper(self):
        info = parse_indonesia_road_num('8', None, [], ['收费', 'Tol'])
        assert info is None or info.level == IndonesiaRoadLevel.NASIONAL  # 无路名不判 TOL

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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && ../.venv/Scripts/python -m pytest tests/test_indonesia_road.py -q`
Expected: 报 `ModuleNotFoundError: No module named 'app.gpxutil_wrapper.indonesia'`（模块不存在即红）。

- [ ] **Step 3: 创建 `backend/app/gpxutil_wrapper/indonesia.py`**

```python
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
# 键顺序固定为 [印尼语名, 中文名] 成对出现，_PROVINCE_ZH_BY_CODE 依赖该约定推导。
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
    if keyword.isascii() and keyword.isalnum():
        return re.search(rf'\b{re.escape(keyword.lower())}\b', text_lower) is not None
    return keyword.lower() in text_lower


def parse_indonesia_road_num(
        road_num: str | None,
        road_names: Sequence[str | None],
        province_texts: Sequence[str | None],
        tol_keywords: list[str],
) -> IndonesiaRoadInfo | None:
    """
    解析印尼道路编号（spec 第 5 节规则）。

    :param road_num: CSV road_num 字段，如 '3'、'023'、'35-024'；空则无盾牌
    :param road_names: 道路名文本序列（如 [road_name, road_name_id]），任一含 TOL 关键词即判 TOL
    :param province_texts: 候选省份文本（印尼语名、中文名，可为 None），按顺序查代码
    :param tol_keywords: TOL 判定关键词（默认 ['收费', 'Tol']）
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && ../.venv/Scripts/python -m pytest tests/test_indonesia_road.py -q`
Expected: 全部通过（约 20 passed）。

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_indonesia_road.py backend/app/gpxutil_wrapper/indonesia.py
git commit -m "feat(indonesia): 移植印尼道路编号解析与38省代码表，修正TOL词边界匹配

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: 数据模型 + alembic 迁移 016 + 三引擎 SQL 脚本

**Files:**
- Modify: `backend/app/models/track.py`（Track、TrackPoint）
- Modify: `backend/app/models/road_sign.py`
- Create: `backend/alembic/versions/016_add_multilanguage_region.py`
- Create: `backend/alembic/versions/016_add_multilanguage_region.sql.sqlite`
- Create: `backend/alembic/versions/016_add_multilanguage_region.sql.mysql`
- Create: `backend/alembic/versions/016_add_multilanguage_region.sql.postgresql`

新增列清单（spec §2）：
| 表 | 列 | 定义 |
|---|---|---|
| tracks | region | String(10) NOT NULL default 'cn' |
| track_points | region | String(10) NOT NULL default 'cn' |
| track_points | province_id / city_id / district_id | String(100) NULL（对齐 *_en 尺寸） |
| track_points | road_name_id | String(200) NULL |
| road_sign_cache | region | String(10) NOT NULL default 'cn' |

- [ ] **Step 1: 修改 `backend/app/models/track.py`**

在 Track 的 `original_crs` 行（L25）后插入：

```python
    region = Column(String(10), nullable=False, default='cn', server_default='cn', comment="地区: cn=中国, id=印尼")
```

在 TrackPoint 的 `road_name_en` 行（L94）后插入：

```python

    # 多语言（印尼语，*_en 为英语历史惯例；中文无后缀）
    province_id = Column(String(100), nullable=True)
    city_id = Column(String(100), nullable=True)
    district_id = Column(String(100), nullable=True)
    road_name_id = Column(String(200), nullable=True)

    # 地区（图标/显示体系的点级权威）
    region = Column(String(10), nullable=False, default='cn', server_default='cn', comment="地区: cn=中国, id=印尼")
```

- [ ] **Step 2: 修改 `backend/app/models/road_sign.py`**

先 Read 该文件（22 行）。在合适的字段后加：

```python
    region = Column(String(10), nullable=False, default='cn', server_default='cn', comment="地区: cn=中国, id=印尼")
```

（字段名以文件内既有字段风格为准，保持与 Track/TrackPoint 注释一致。）

- [ ] **Step 3: 创建 alembic 迁移 `backend/alembic/versions/016_add_multilanguage_region.py`**

head 当前为 `eac60779d33a`（`revision = 'eac60779d33a'`、`down_revision = '015_add_overlay_templates'`），先 Read 该文件确认格式与最新 revision id，若与下述不同以文件实际为准（revision 是新十六进制串或描述性串均可，须全局唯一）。

```python
"""add multilanguage and region columns for Indonesia support

Revision ID: 016_add_multilanguage_region
Revises: eac60779d33a
Create Date: 2026-09-09

兼容 SQLite / MySQL / PostgreSQL。
tracks/track_points 增加 region 默认 'cn'；track_points 增加 *_id 印尼语列；
road_sign_cache 增加 region。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '016_add_multilanguage_region'
down_revision = 'eac60779d33a'
branch_labels = None
depends_on = None


def _add_column_if_missing(table: str, column_name: str, column: sa.Column) -> None:
    """检查列不存在再添加（数据库可能已手动建过）"""
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {c['name'] for c in inspector.get_columns(table)}
    if column_name not in columns:
        op.add_column(table, column)


def upgrade():
    """添加地区与多语言列"""
    # tracks.region
    _add_column_if_missing(
        'tracks', 'region',
        sa.Column('region', sa.String(10), nullable=False,
                  server_default='cn', comment='地区: cn=中国, id=印尼')
    )
    # track_points.region + *_id
    _add_column_if_missing(
        'track_points', 'region',
        sa.Column('region', sa.String(10), nullable=False,
                  server_default='cn', comment='地区: cn=中国, id=印尼')
    )
    for col in ('province_id', 'city_id', 'district_id'):
        _add_column_if_missing(
            'track_points', col,
            sa.Column(col, sa.String(100), nullable=True)
        )
    _add_column_if_missing(
        'track_points', 'road_name_id',
        sa.Column('road_name_id', sa.String(200), nullable=True)
    )
    # road_sign_cache.region
    _add_column_if_missing(
        'road_sign_cache', 'region',
        sa.Column('region', sa.String(10), nullable=False,
                  server_default='cn', comment='地区: cn=中国, id=印尼')
    )


def downgrade():
    """回滚：删除新增列（列存在才删）"""
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)

    def drop_if_exists(table: str, column_name: str) -> None:
        columns = {c['name'] for c in inspector.get_columns(table)}
        if column_name in columns:
            op.drop_column(table, column_name)

    for col in ('road_name_id', 'province_id', 'city_id', 'district_id'):
        drop_if_exists('track_points', col)
    drop_if_exists('track_points', 'region')
    drop_if_exists('tracks', 'region')
    drop_if_exists('road_sign_cache', 'region')
```

注意：down_revision 先 Read `backend/alembic/versions/eac60779d33a_add_animation_export_task_table.py` 头部确认 `revision` 的确切值，若不同则以实际为准并同步更新上面代码。

- [ ] **Step 4: 创建三份 SQL 脚本**

`backend/alembic/versions/016_add_multilanguage_region.sql.sqlite`：

```sql
-- ============================================
-- 为印尼多语言支持添加 region 与 *_id 列（SQLite）
-- ============================================
-- 执行方式: sqlite3 vibe_route.db < 016_add_multilanguage_region.sql.sqlite

ALTER TABLE tracks ADD COLUMN region VARCHAR(10) NOT NULL DEFAULT 'cn';

ALTER TABLE track_points ADD COLUMN region VARCHAR(10) NOT NULL DEFAULT 'cn';
ALTER TABLE track_points ADD COLUMN province_id VARCHAR(100);
ALTER TABLE track_points ADD COLUMN city_id VARCHAR(100);
ALTER TABLE track_points ADD COLUMN district_id VARCHAR(100);
ALTER TABLE track_points ADD COLUMN road_name_id VARCHAR(200);

ALTER TABLE road_sign_cache ADD COLUMN region VARCHAR(10) NOT NULL DEFAULT 'cn';

-- 验证
SELECT name FROM pragma_table_info('tracks') WHERE name = 'region';
SELECT name FROM pragma_table_info('track_points') WHERE name IN ('region','province_id','city_id','district_id','road_name_id');
SELECT name FROM pragma_table_info('road_sign_cache') WHERE name = 'region';
```

`backend/alembic/versions/016_add_multilanguage_region.sql.mysql`：

```sql
-- ============================================
-- 为印尼多语言支持添加 region 与 *_id 列（MySQL）
-- ============================================
-- 执行方式: mysql -u vibe_route -p vibe_route < 016_add_multilanguage_region.sql.mysql

ALTER TABLE tracks
    ADD COLUMN region VARCHAR(10) NOT NULL DEFAULT 'cn' COMMENT '地区: cn=中国, id=印尼';

ALTER TABLE track_points
    ADD COLUMN region VARCHAR(10) NOT NULL DEFAULT 'cn' COMMENT '地区: cn=中国, id=印尼',
    ADD COLUMN province_id VARCHAR(100) NULL,
    ADD COLUMN city_id VARCHAR(100) NULL,
    ADD COLUMN district_id VARCHAR(100) NULL,
    ADD COLUMN road_name_id VARCHAR(200) NULL;

ALTER TABLE road_sign_cache
    ADD COLUMN region VARCHAR(10) NOT NULL DEFAULT 'cn' COMMENT '地区: cn=中国, id=印尼';

-- 验证
SHOW COLUMNS FROM tracks LIKE 'region';
SHOW COLUMNS FROM track_points LIKE '%_id';
SHOW COLUMNS FROM track_points LIKE 'region';
SHOW COLUMNS FROM road_sign_cache LIKE 'region';
```

`backend/alembic/versions/016_add_multilanguage_region.sql.postgresql`：

```sql
-- ============================================
-- 为印尼多语言支持添加 region 与 *_id 列（PostgreSQL）
-- ============================================
-- 执行方式: psql -U vibe_route -d vibe_route -f 016_add_multilanguage_region.sql.postgresql

ALTER TABLE tracks
    ADD COLUMN region VARCHAR(10) NOT NULL DEFAULT 'cn';

ALTER TABLE track_points
    ADD COLUMN region VARCHAR(10) NOT NULL DEFAULT 'cn',
    ADD COLUMN province_id VARCHAR(100),
    ADD COLUMN city_id VARCHAR(100),
    ADD COLUMN district_id VARCHAR(100),
    ADD COLUMN road_name_id VARCHAR(200);

ALTER TABLE road_sign_cache
    ADD COLUMN region VARCHAR(10) NOT NULL DEFAULT 'cn';

-- 验证
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'tracks' AND column_name = 'region';

SELECT column_name FROM information_schema.columns
WHERE table_name = 'track_points' AND column_name IN
    ('region','province_id','city_id','district_id','road_name_id')
ORDER BY column_name;

SELECT column_name FROM information_schema.columns
WHERE table_name = 'road_sign_cache' AND column_name = 'region';
```

- [ ] **Step 5: 验证迁移可执行（临时 sqlite）**

对开发库不做任何改动（CLAUDE.md：不经允许不动数据库）。用临时 sqlite 验证 016 迁移可执行。

执行注意（Task 2 实现时实测，已回写）：
- **`DATABASE_URL` env 无效**：`backend/app/core/config.py` 中它是 property（pydantic-settings 忽略该 env），实际由 `backend/.env` 的 `DATABASE_TYPE` / `SQLITE_DB_PATH` 决定（相对 backend/ 解析）。指向临时库必须设 **`SQLITE_DB_PATH`**。
- **空库跑完整迁移链会失败**（001 假定基础表已存在），仓库惯例为 create_all 建表 + 手工 stamp `alembic_version`（见 README）。故验证方案：临时库 create_all → drop 新列还原 pre-016 形态 → stamp 到 `eac60779d33a` → `upgrade head`（016 实际执行 ALTER）→ `downgrade -1`（对称删列）→ 再 upgrade 成功。
- 若报 `alembic.ini` 缺失：该文件被 gitignore 且不随仓库提供，需先按标准模板重建一份（gitignored，不入库）。

Run:
```bash
cd backend
export SQLITE_DB_PATH=data/_migrate_check_016.db
../.venv/Scripts/python - <<'EOF'
import asyncio
from sqlalchemy import text
from app.core.database import engine, Base
import app.models  # noqa: F401 确保模型注册

async def main():
    async with engine.begin() as conn:
        await conn.execute(text('DROP TABLE IF EXISTS alembic_version'))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        # 还原 pre-016 形态（drop 新列；含存量数据行的回填语义可自行插入一行验证 region='cn'）
        for col in ('region', 'province_id', 'city_id', 'district_id', 'road_name_id'):
            await conn.execute(text(f'ALTER TABLE track_points DROP COLUMN {col}'))
        for col in ('region',):
            await conn.execute(text(f'ALTER TABLE tracks DROP COLUMN {col}'))
            await conn.execute(text(f'ALTER TABLE road_sign_cache DROP COLUMN {col}'))
asyncio.run(main())
EOF
# stamp 会自行创建 alembic_version 表并写入版本（空库直接 upgrade 全链会失败：
# 001 假定基础表已由 create_all 建立，仓库惯例如此）
../.venv/Scripts/python -m alembic stamp eac60779d33a
../.venv/Scripts/python -m alembic upgrade head
../.venv/Scripts/python -m alembic downgrade -1
../.venv/Scripts/python -m alembic upgrade head
rm -f data/_migrate_check_016.db
```
Expected: 三轮命令均无报错；迁移链从 016 前形态执行到 016 无错、降级删列成功、再升级成功（若报错多因 down_revision 写错，对照 Step 3 修正后重跑）。验证完删除临时 db，确认 `git status` 无 db 文件变更。

- [ ] **Step 6: Commit**

注意：`.sql.sqlite` 文件名被 `.gitignore` 的 `*.sqlite` 规则命中，`git add` 需带 `-f`（其余文件正常 add 即可）。

```bash
git add backend/app/models/track.py backend/app/models/road_sign.py \
  backend/alembic/versions/016_add_multilanguage_region.py \
  backend/alembic/versions/016_add_multilanguage_region.sql.mysql \
  backend/alembic/versions/016_add_multilanguage_region.sql.postgresql
git add -f backend/alembic/versions/016_add_multilanguage_region.sql.sqlite
git commit -m "feat(db): tracks/track_points/road_sign_cache 增加 region 与多语言列（迁移016）

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: 资源拷贝（模板/字体）+ 配置默认值 + schemas 字段（config/track/road_sign）

> **前置确认（执行协调者在执行本任务前向用户确认，得到答复后再动手）：**
> spec §5 提示 ClearviewHwy1W/2W.ttf 为商业字体。若 gpxutil 中该字体许可无法确认，选项：(a) 照常拷贝使用（个人项目 + 同源项目，风险自担）；(b) 换开源字体（如 SourceSans3，视觉效果有差异）。默认推荐 (a)。用户答复后按答复执行，本任务 Step 1 含拷贝。

**Files:**
- Create(copy): `backend/data/templates/id_sheild.svg`（来自 `D:\code\gpxutil\asset\template\id_sheild.svg`）
- Create(copy): `backend/data/fonts/ClearviewHwy1W.ttf`、`backend/data/fonts/ClearviewHwy2W.ttf`（来自 `D:\code\gpxutil\asset\font\`）
- Modify: `backend/app/services/config_service.py`
- Modify: `backend/app/schemas/config.py`
- Modify: `backend/app/api/admin.py`（config 构造点）
- Modify: `backend/app/schemas/track.py`
- Modify: `backend/app/api/auth.py`（PublicConfigResponse 构造点——无新增键则不动，见 Step 4）
- Test: 无（配置默认值与 schemas 由 Task 5 后集成测试覆盖）

- [ ] **Step 1: 拷贝资源并检查**

Run:
```bash
cp "D:/code/gpxutil/asset/template/id_sheild.svg" backend/data/templates/id_sheild.svg
cp "D:/code/gpxutil/asset/font/ClearviewHwy1W.ttf" backend/data/fonts/ClearviewHwy1W.ttf
cp "D:/code/gpxutil/asset/font/ClearviewHwy2W.ttf" backend/data/fonts/ClearviewHwy2W.ttf
ls -la backend/data/templates/id_sheild.svg backend/data/fonts/ClearviewHwy*.ttf
```
Expected: 3 个文件存在且非空（id_sheild.svg 为含 `id="back"` 组的 SVG；两个 ttf 约数百 KB）。

- [ ] **Step 2: `config_service.py` 增加默认配置与深度合并**

在 `DEFAULT_CONFIGS` 的 `"allow_server_poster": True,` 行（L28）之后加：

```python
        "indonesia_road_sign": {
            "template": "id_sheild.svg",      # backend/data/templates/ 下模板文件名
            "tol_keywords": ["收费", "Tol"],   # TOL 判定：ASCII 词边界 + 中文子串（见 indonesia.py）
            "font_upper": "ClearviewHwy1W.ttf",  # 色带小字（backend/data/fonts/ 下）
            "font_lower": "ClearviewHwy2W.ttf",  # 白色区大字
        },
```

在 `get_all_configs` 的 `elif config.key == 'geocoding_config' and isinstance(parsed_value, dict):` 分支之后（对应 else 分支之前），加第三个特判分支（与 map_layers 的深度合并模式相同，保证后端后续新增默认子键不会因 DB 旧值丢失）：

```python
                    elif config.key == 'indonesia_road_sign' and isinstance(parsed_value, dict):
                        # 与默认配置深度合并，新增默认键不因 DB 旧值丢失
                        for key, value in self.DEFAULT_CONFIGS['indonesia_road_sign'].items():
                            if key not in parsed_value:
                                parsed_value[key] = value
                        configs[config.key] = parsed_value
```

- [ ] **Step 3: `schemas/config.py` 增加 schema 字段**

在 `FontConfig` 定义后加：

```python
class IndonesiaRoadSignConfig(BaseModel):
    """印尼道路盾牌配置 schema"""
    template: Optional[str] = Field(None, description="盾牌模板文件名（data/templates/ 下）")
    tol_keywords: Optional[List[str]] = Field(None, description="TOL 判定关键词（ASCII 词边界 + 中文子串）")
    font_upper: Optional[str] = Field(None, description="色带小字字体文件名（data/fonts/ 下）")
    font_lower: Optional[str] = Field(None, description="白色区大字字体文件名（data/fonts/ 下）")
```

`ConfigResponse` 加字段（font_config 行后）：

```python
    indonesia_road_sign: IndonesiaRoadSignConfig = Field(default_factory=IndonesiaRoadSignConfig)
```

`ConfigUpdate` 加字段：

```python
    indonesia_road_sign: Optional[IndonesiaRoadSignConfig] = None
```

PublicConfigResponse **不加**（道路盾牌生成在服务端，公开配置无需下发）。

- [ ] **Step 4: `admin.py` 两处 config 构造点补键**

`backend/app/api/admin.py` 的 GET /config 与 PUT /config 均手工构造 `ConfigResponse`。GET（约 L311-330 区域）在 `allow_server_poster=configs.get("allow_server_poster", True),` 后加：

```python
        indonesia_road_sign=IndonesiaRoadSignConfig(**configs.get("indonesia_road_sign", {}))
        if configs.get("indonesia_road_sign") else IndonesiaRoadSignConfig(),
```

同时把 import 改成：`from app.schemas.config import ConfigResponse, ConfigUpdate, FontConfig, IndonesiaRoadSignConfig`。

PUT 分支（约 L334-362）同样在 `allow_server_poster=...` 后加相同两行（configs 为 update_config 返回值，已含默认合并，可直接 `configs.get("indonesia_road_sign", {})` 且必非空——两处可统一写为一行形式：

```python
        indonesia_road_sign=IndonesiaRoadSignConfig(**configs.get("indonesia_road_sign") or {}),
```

（读文件后二选一，保持文件内两处一致即可。）

- [ ] **Step 5: `schemas/track.py` 补字段**

`TrackResponse`（share_token 前任意位置）加：

```python
    region: str = 'cn'  # 地区: cn=中国, id=印尼（新建点默认值）
```

`UnifiedTrackResponse` 同步加同字段同默认。

`TrackUpdate` 加：

```python
    region: Optional[str] = Field(None, description="地区: cn/id")
```

`TrackPointResponse`（road_name_en 后）加：

```python
    province_id: Optional[str] = None
    city_id: Optional[str] = None
    district_id: Optional[str] = None
    road_name_id: Optional[str] = None
    region: str = 'cn'
```

`RegionNode` 加：

```python
    region: str = 'cn'  # 该组所属地区（同文本不同地区分组建树）
    names: Optional[dict] = None  # 各语言代表文本 {zh, id, en}，非空才出现
```

- [ ] **Step 6: 语法检查**

Run: `cd backend && ../.venv/Scripts/python -c "from app.schemas.config import ConfigResponse, ConfigUpdate, IndonesiaRoadSignConfig; from app.schemas.track import TrackResponse, TrackUpdate, TrackPointResponse, RegionNode; import app.api.admin; import app.services.config_service; print('ok')"`
Expected: 打印 ok（无 ImportError/语法错误）。

- [ ] **Step 7: Commit**

字体**不入库**（Task 3 实测决策，已回写）：`.gitignore` 的 `backend/data/fonts/*`（注释 "Road sign fonts (user provided)"）是既有策略，现有 jtbz 系字体同样未跟踪；且 `.dockerignore` 含 `backend/data`，镜像不携带字体。故字体由使用者手工放置到 `backend/data/fonts/`（Step 1 的 cp 即为本地放置）。模板 svg 走 templates 目录正常入库。

```bash
git add backend/data/templates/id_sheild.svg
git add backend/app/services/config_service.py backend/app/schemas/config.py backend/app/api/admin.py backend/app/schemas/track.py
git commit -m "feat(config/schema): 拷贝印尼盾牌模板与Clearview字体，配置默认值与多语言schema字段

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: svg_gen 印尼盾牌生成器 + 单元测试

> `generate_road_sign` 的 region 参数与分派在 **Task 5** 完成（本任务只新增印尼盾牌生成器与 helper，cn 既有函数零改动）。

**Files:**
- Modify: `backend/app/gpxutil_wrapper/svg_gen.py`（735 行）
- Create: `backend/tests/test_indonesia_shield.py`

移植 `D:\code\gpxutil\src\gpxutil\utils\svg_gen.py` L411-616 的印尼盾牌生成（含居中排版 helper），对齐 vibe 风格：函数返回字符串（tostring 后清理 width/height）、错误消息中文、常量内置。

- [ ] **Step 1: 创建测试文件（红）**

`backend/tests/test_indonesia_shield.py`：

```python
# -*- coding: utf-8 -*-
"""印尼六边形盾牌 SVG 生成单元测试（spec §8 用例 3）"""
import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from app.gpxutil_wrapper.indonesia import IndonesiaRoadLevel
from app.gpxutil_wrapper.svg_gen import generate_indonesia_shield

# 颜色/字号断言用 spec 字面值而非实现常量，避免自比对（改了实现常量测试仍须失败）
BANNER_RED = '#B5273C'       # spec §5：对齐 gpxutil 印尼配置
PROVINCE_BLUE = '#003E86'    # spec §5：PROVINSI 蓝
BANNER_TEXT_HEIGHT = 45      # spec §5：色带小字
NUMBER_TEXT_HEIGHT = 135     # spec §5：白色区大字

TEMPLATE = 'data/templates/id_sheild.svg'   # pytest cwd = backend/（执行修正：相对 backend 运行目录）
UPPER_FONT = 'data/fonts/ClearviewHwy1W.ttf'
LOWER_FONT = 'data/fonts/ClearviewHwy2W.ttf'


@pytest.fixture
def workdir():
    """临时目录（供合成模板/输出文件用）

    不用 pytest 的 `tmp_path`：它依赖 basetemp 根目录 `%TEMP%/pytest-of-<user>`，
    该目录一旦残留且当前令牌不可访问（实测本机 `%TEMP%/pytest-of-Administrator`
    即如此，非提权无法接管/删除），所有 `tmp_path` 用例会在 fixture 阶段
    PermissionError。`tempfile.TemporaryDirectory()` 直接建随机子目录，绕开该根目录。
    """
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture(scope='module')
def shield_config():
    """模板与字体路径（相对 backend 运行目录）"""
    base = Path(os.getcwd())
    assert (base / TEMPLATE).exists(), '模板缺失，先执行 Task 3 资源拷贝'
    assert (base / UPPER_FONT).exists(), '字体缺失，先执行 Task 3 资源拷贝'
    assert (base / LOWER_FONT).exists(), '字体缺失，先执行 Task 3 资源拷贝'
    return {
        'template': str(base / TEMPLATE),
        'upper': str(base / UPPER_FONT),
        'lower': str(base / LOWER_FONT),
    }


def _parse(svg: str):
    return ET.fromstring(svg)


def _ns_free(elem):
    return elem.tag.split('}')[-1]


def _paths_with_fill(root, fill):
    """返回所有 fill 属性等于 fill 的 path 元素"""
    out = []
    for elem in root.iter():
        if _ns_free(elem) == 'path' and elem.attrib.get('fill', '').upper() == fill.upper():
            out.append(elem)
    return out


def _bbox(d: str):
    """用 svgpathtools 计算 path d 的 bbox"""
    from svgpathtools import parse_path
    xmin, xmax, ymin, ymax = parse_path(d).bbox()
    return xmin, ymin, xmax, ymax


def test_nasional_shield_structure(shield_config):
    svg = generate_indonesia_shield('3', IndonesiaRoadLevel.NASIONAL, '35', shield_config)
    root = _parse(svg)
    # 六边形（polygon）+ 色带（polygon）+ 黑色描边（path）
    polygons = [e for e in root.iter() if _ns_free(e) == 'polygon']
    assert len(polygons) == 2
    # NASIONAL 色带红色（spec 值断言，非实现常量自比对）
    head = [e for e in polygons if e.attrib.get('id') == 'head']
    assert len(head) == 1 and head[0].attrib['fill'].upper() == BANNER_RED.upper()


def test_tol_shield_red(shield_config):
    svg = generate_indonesia_shield('3', IndonesiaRoadLevel.TOL, None, shield_config)
    root = _parse(svg)
    head = [e for e in root.iter()
            if _ns_free(e) == 'polygon' and e.attrib.get('id') == 'head']
    assert head and head[0].attrib['fill'].upper() == BANNER_RED.upper()


def test_provinsi_shield_blue(shield_config):
    svg = generate_indonesia_shield('024', IndonesiaRoadLevel.PROVINSI, '35', shield_config)
    root = _parse(svg)
    head = [e for e in root.iter()
            if _ns_free(e) == 'polygon' and e.attrib.get('id') == 'head']
    assert head and head[0].attrib['fill'].upper() == PROVINCE_BLUE.upper()


def test_has_upper_and_lower_text_paths(shield_config):
    # 色带白字（PROVINSI 35）与大字黑字（024）
    svg = generate_indonesia_shield('024', IndonesiaRoadLevel.PROVINSI, '35', shield_config)
    root = _parse(svg)
    white_paths = _paths_with_fill(root, '#FFFFFF')
    black_paths = _paths_with_fill(root, '#000000')
    assert white_paths, '色带文字缺失'
    assert black_paths, '大号数字文字缺失'

    # 大字为纯编号：024 → 3 个字符 path（空格无字形则以退化 path 占位）
    # 描边 path 带 id='outline'（环形填充亦为 #000000），按身份排除而非下标
    glyphs = [e for e in black_paths if e.attrib.get('id') != 'outline']
    assert len(glyphs) == 3
    # 空格占位 path 不绘制像素：'PROVINSI 35' 的空格 path bbox 四点重合（零宽度退化 path）
    degenerate = [b for b in (_bbox(e.attrib['d']) for e in white_paths)
                  if b[0] == b[2] and b[1] == b[3]]
    assert len(degenerate) == 1


def test_banner_text_level_and_province(shield_config):
    """色带文字 = 等级词 [+ 空格 + 省码]：逐字符一个 path，空格为退化 path 占位（spec §8.3）"""
    def _banner_len(code, level, province):
        svg = generate_indonesia_shield(code, level, province, shield_config)
        return len(_paths_with_fill(_parse(svg), '#FFFFFF'))

    assert _banner_len('3', IndonesiaRoadLevel.NASIONAL, '35') == len('NASIONAL 35')
    assert _banner_len('024', IndonesiaRoadLevel.PROVINSI, '35') == len('PROVINSI 35')
    # 无省码降级：仅等级词，无多余空格占位
    assert _banner_len('3', IndonesiaRoadLevel.TOL, None) == len('TOL')


def test_text_heights(shield_config):
    """字号：色带 45px、大字 135px（spec §5 排版制式）"""
    svg = generate_indonesia_shield('024', IndonesiaRoadLevel.PROVINSI, '35', shield_config)
    root = _parse(svg)

    def _height(elem):
        x1, y1, x2, y2 = _bbox(elem.attrib['d'])
        return y2 - y1

    number_paths = [e for e in _paths_with_fill(root, '#000000')
                    if e.attrib.get('id') != 'outline']
    number_h = max(_height(e) for e in number_paths)
    banner_h = max(_height(e) for e in _paths_with_fill(root, '#FFFFFF'))
    assert abs(number_h - NUMBER_TEXT_HEIGHT) <= 1
    assert abs(banner_h - BANNER_TEXT_HEIGHT) <= 1


def test_upper_text_centered_on_head(shield_config):
    """色带文字水平居中于六边形中心、垂直居中于 head bbox 中心（容差放宽到 ±8px）"""
    from app.gpxutil_wrapper.svg_gen import _get_head_bbox, _get_template_size
    template = shield_config['template']
    w, h = _get_template_size(template)
    hx1, hy1, hx2, hy2 = _get_head_bbox(template)
    svg = generate_indonesia_shield('3', IndonesiaRoadLevel.NASIONAL, '35', shield_config)
    root = _parse(svg)
    white_bboxes = [_bbox(e.attrib['d']) for e in _paths_with_fill(root, '#FFFFFF')]
    assert white_bboxes
    xs = [b[0] for b in white_bboxes] + [b[2] for b in white_bboxes]
    ys = [b[1] for b in white_bboxes] + [b[3] for b in white_bboxes]
    center_x = (min(xs) + max(xs)) / 2
    center_y = (min(ys) + max(ys)) / 2
    assert abs(center_x - w / 2) <= 8
    assert abs(center_y - (hy1 + hy2) / 2) <= 8


def test_no_width_height_attr(shield_config):
    """输出保留 viewBox、移除固定 width/height（与 CN 生成器一致，前端可自适应）"""
    svg = generate_indonesia_shield('3', IndonesiaRoadLevel.NASIONAL, None, shield_config)
    assert 'width=' not in svg and 'height=' not in svg
    assert 'viewBox' in svg


def _write_synthetic_template(path, scale=1):
    """合成最小模板：viewBox 与 head 坐标按 scale 缩放（验证布局由模板推导而非硬编码）"""
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {562 * scale} {451 * scale}">'
        f'<g id="back">'
        f'<g id="background">'
        f'<polygon points="0,0 {562 * scale},0 {562 * scale},{451 * scale}"/>'
        f'<path d="M 0,0 L {562 * scale},0"/>'
        f'</g>'
        f'<polygon id="head" points="0,{5 * scale} {562 * scale},{5 * scale} '
        f'{562 * scale},{113 * scale} 0,{113 * scale}"/>'
        f'</g></svg>',
        encoding='utf-8',
    )
    return str(path)


def test_layout_follows_template_scale(shield_config, workdir):
    """换模板自适应：2× 模板下文字中心随 viewBox/head 缩放（spec §5 核心不变量）"""
    from app.gpxutil_wrapper.svg_gen import _get_head_bbox, _get_template_size
    template = _write_synthetic_template(workdir / 'scaled_2x.svg', scale=2)
    w, h = _get_template_size(template)
    assert (w, h) == (1124.0, 902.0)
    cfg = dict(shield_config, template=template)
    root = _parse(generate_indonesia_shield('3', IndonesiaRoadLevel.NASIONAL, '35', cfg))
    white_bboxes = [_bbox(e.attrib['d']) for e in _paths_with_fill(root, '#FFFFFF')]
    assert white_bboxes
    xs = [b[0] for b in white_bboxes] + [b[2] for b in white_bboxes]
    ys = [b[1] for b in white_bboxes] + [b[3] for b in white_bboxes]
    # 水平中心随 viewBox 宽度 → 562（硬编码 281 会失败）
    assert abs((min(xs) + max(xs)) / 2 - 562) <= 8
    # 垂直中心随 head bbox 中心 → (10 + 226) / 2 = 118（硬编码 59 会失败）
    hx1, hy1, hx2, hy2 = _get_head_bbox(template)
    assert abs((min(ys) + max(ys)) / 2 - (hy1 + hy2) / 2) <= 8
    # 大字垂直中心随「head 下沿到模板底」的中点 → (226 + 902) / 2 = 564
    # （硬编码 282 或整体偏移 30px 均会失败）
    black = [e for e in _paths_with_fill(root, '#000000')
             if e.attrib.get('id') != 'outline']
    assert black
    number_ys = [b for bb in (_bbox(e.attrib['d']) for e in black) for b in (bb[1], bb[3])]
    assert abs((min(number_ys) + max(number_ys)) / 2 - (hy2 + h) / 2) <= 8


def test_output_path_branch(shield_config, workdir):
    """output_path 分支：写文件并返回该路径，内容与返回字符串同构"""
    out = workdir / 'shield.svg'
    ret = generate_indonesia_shield(
        '3', IndonesiaRoadLevel.NASIONAL, None, shield_config, str(out))
    assert ret == str(out)
    content = out.read_text(encoding='utf-8')
    assert '<svg' in content and 'viewBox' in content


def test_errors(shield_config):
    """错误分支：空编号 / 等级非枚举实例 / 配置缺失"""
    with pytest.raises(ValueError):
        generate_indonesia_shield('', IndonesiaRoadLevel.NASIONAL, None, shield_config)
    # 非枚举实例（此处为 int 1）：Python ≥3.12 `in Enum` 按值比较不会报错，
    # 故守卫须用 isinstance，否则后续 road_level.name 崩 AttributeError
    with pytest.raises(ValueError):
        generate_indonesia_shield('3', 1, None, shield_config)
    with pytest.raises(ValueError):
        generate_indonesia_shield('3', IndonesiaRoadLevel.NASIONAL, None, {})


def test_missing_template_head_raises(shield_config, workdir):
    """模板结构不符（缺 id=head）抛 ValueError 而非 TypeError/AttributeError"""
    bad = workdir / 'no_head.svg'
    bad.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 562 451">'
        '<g id="back"><g id="background"><polygon points="0,0 10,0 10,10"/></g></g></svg>',
        encoding='utf-8',
    )
    with pytest.raises(ValueError, match='id=head'):
        generate_indonesia_shield('3', IndonesiaRoadLevel.NASIONAL, None,
                                  dict(shield_config, template=str(bad)))
```

- [ ] **Step 2: 运行确认红**

Run: `cd backend && ../.venv/Scripts/python -m pytest tests/test_indonesia_shield.py -q`
Expected: ImportError（`generate_indonesia_shield` 等不存在）。

- [ ] **Step 3: 修改 `svg_gen.py`**

在文件顶部 import 区（L14 之后）加：

```python
import xml.etree.ElementTree as ET
```

同一 import 区（`from app.core.config import settings` 之后）加：

```python
from app.gpxutil_wrapper.indonesia import IndonesiaRoadLevel
```

（`indonesia.py` 只依赖标准库、不反向 import 本模块，模块级导入不成环；后续函数内不再局部 import）

颜色常量区（L29 GREEN 后）加：

```python
INDONESIA_PROVINCE_BLUE = '#003E86'  # 印尼省道（PROVINSI）色带蓝
# 印尼色带红：对齐 gpxutil 印尼配置（spec §5「实现时对齐 gpxutil」），亦为模板 id_sheild.svg 的 st2 原色；
# 不复用国标红 RED（#ED1724），避免与 CN 体系混淆
INDONESIA_BANNER_RED = '#B5273C'
```

印尼文字排版常量（模块级，EXPWY_BANNER_TEXT_HEIGHT 后加）：

```python
# 印尼盾牌文字制式（模板 viewBox 坐标系，移植自 gpxutil 配置默认值）
INDONESIA_BANNER_TEXT_HEIGHT = 45    # 色带小字（ClearviewHwy1W）
INDONESIA_NUMBER_TEXT_HEIGHT = 135   # 白色区大字（ClearviewHwy2W）
```

文件末尾（generate_road_sign 之前或之后均可，放 `generate_road_sign` 之前）追加以下函数（整体移植自 gpxutil，错误消息中文化、输出对齐 vibe 的字符串清理）：

```python
# ============ 印尼六边形盾牌 ============
# 移植自 gpxutil svg_gen.py 的 generate_indonesia_shield 家族
# （模板 id_sheild.svg：白六边形 + 顶部色带 + 占位文字；布局由模板元素 bbox 推导）


def _parse_polygon_points(points: str) -> list[tuple[float, float]]:
    """解析 polygon 的 points 属性为坐标对列表（兼容逗号与空格分隔）"""
    nums = [float(v) for v in points.replace(',', ' ').split()]
    return list(zip(nums[0::2], nums[1::2]))


def get_element_bbox_by_id(svg_path: str, element_id: str):
    """解析 SVG 模板，取指定 id 元素的 bbox（支持 polygon）。

    :return: (xmin, ymin, xmax, ymax)；找不到该 id 元素返回 None
    """
    tree = ET.parse(svg_path)
    root = tree.getroot()
    for elem in root.iter():
        if elem.attrib.get('id') == element_id:
            if elem.tag.split('}')[-1] == 'polygon':
                points = _parse_polygon_points(elem.attrib.get('points', ''))
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                return min(xs), min(ys), max(xs), max(ys)
            return None
    return None


def _get_back_group_elements(svg_path: str) -> list[tuple[str, dict]]:
    """解析印尼盾牌模板，取 id='back' 组内绘制元素（跳过占位字形组）。

    模板多边形不被 svg2paths 解析，这里用 XML 直接取出。
    :return: 按文档顺序的 (标签名, 属性字典) 列表；head 多边形以 id='head' 标识
    :raise ValueError: 模板中找不到 id='back' 的组
    """
    root = ET.parse(svg_path).getroot()
    back_group = None
    for elem in root.iter():
        if elem.tag.split('}')[-1] == 'g' and elem.attrib.get('id') == 'back':
            back_group = elem
            break
    if back_group is None:
        raise ValueError(f'印尼盾牌模板 {svg_path} 中找不到 id=back 的元素')
    result = []
    for elem in back_group:
        tag = elem.tag.split('}')[-1]
        if tag == 'g' and elem.attrib.get('id') == 'background':
            # 展开背景组：白色六边形 polygon + 黑色描边 path，保持模板内顺序
            for child in elem:
                result.append((child.tag.split('}')[-1], child.attrib))
        else:
            result.append((tag, elem.attrib))
    return result


def calculate_centered_scaled_char_info(
    code: str, center_x: float, center_y: float,
    height: float, font: str,
) -> list:
    """
    按固定高度缩放一段文字，水平居中于 center_x、垂直居中于 center_y（无额外字距）。
    空格无字形轮廓：按字体 ascent 比例换算其 advance 宽度占位排版，生成占位 path
    保持与字符一一对应（不绘制像素），保证与字形 path 同样的绘制流程。

    :param code: 文字（可为含空格文本，如 'NASIONAL 35'）
    :param center_x: 文字水平中心 x
    :param center_y: 文字垂直中心 y
    :param height: 文字高度
    :param font: 字体文件路径
    :return: 各字符（含空格）path 列表（空格为 M 0,0h0 零长度退化 path）
    :raise ValueError: 文字为空
    """
    if not code:
        raise ValueError('文字为空，无法生成字形 path')
    font_obj = None
    space_scale = 0.0
    space_advance = 0.0
    scaled_char_path_list = []
    scaled_char_width_list = []
    for char in code:
        if char == ' ':
            if font_obj is None:
                font_obj = TTFont(font)
                # 字形按各自轮廓 bbox 高度缩放到 height，其纵向跨度约为基线到字帽高度；
                # ascent 与该跨度同一量级，空格无轮廓，以 ascent 作统一纵向基准把
                # advance（字面宽）换算到像素。近似值，勿按 bug 修改。
                space_scale = height / font_obj['hhea'].ascent
                space_glyph = font_obj.getBestCmap()[ord(' ')]
                space_advance = font_obj['hmtx'][space_glyph][0]
            scaled_char_width_list.append(space_advance * space_scale)
            scaled_char_path_list.append(None)
            continue
        paths_char = char_to_svg_path(font, char)
        char_minx, char_maxx, char_miny, char_maxy = paths_char.bbox()
        char_height = char_maxy - char_miny
        ratio = height / char_height
        scaled_path_char = paths_char.scaled(ratio)
        scaled_char_minx, scaled_char_maxx, scaled_char_miny, scaled_char_maxy = scaled_path_char.bbox()
        scaled_char_width = scaled_char_maxx - scaled_char_minx
        scaled_path_char = scaled_path_char.translated(complex(-scaled_char_minx, -scaled_char_miny))
        scaled_char_width_list.append(scaled_char_width)
        scaled_char_path_list.append(scaled_path_char)

    total_width = reduce(lambda x, y: x + y, scaled_char_width_list)
    start_x = center_x - total_width / 2
    start_y = center_y - height / 2
    char_x = start_x
    result = []
    for path, width in zip(scaled_char_path_list, scaled_char_width_list):
        if path is None:
            # 空格占位：零长度退化 path，只占排版位置、不绘制像素
            path = parse_path('M 0,0h0')
        result.append(path.translated(complex(char_x, start_y)))
        char_x += width
    return result


def _get_template_size(svg_path: str) -> tuple[float, float]:
    """读取 SVG 模板 viewBox 尺寸 (width, height)

    注：调用处按「原点为 0 0」使用模板原生坐标（输出 `viewBox='0 0 w h'`），
    非零原点模板会静默错位；现有模板均为零原点，换模板时须一并确认。
    """
    root = ET.parse(svg_path).getroot()
    viewbox = [float(i) for i in root.get('viewBox').split()]
    return viewbox[2] - viewbox[0], viewbox[3] - viewbox[1]


def _get_head_bbox(svg_path: str):
    """取模板中 id=head 色带多边形 bbox；找不到抛 ValueError"""
    bbox = get_element_bbox_by_id(svg_path, 'head')
    if bbox is None:
        raise ValueError(f'印尼盾牌模板 {svg_path} 中找不到 id=head 的元素')
    return bbox


def generate_indonesia_shield(
    code: str,
    road_level,
    province_code: str | None = None,
    config: dict | None = None,
    output_path: Optional[str] = None,
) -> str:
    """
    生成印尼六边形道路盾牌 SVG（布局由模板元素 bbox 推导，模板 id='text'
    组为占位字形不绘制，仅画背景与色带）。

    :param code: 道路编号（盾牌大字），如 '3'、'024'
    :param road_level: IndonesiaRoadLevel 枚举实例，决定色带颜色与等级词
    :param province_code: 省份代码（色带小字部分），可为 None
    :param config: dict {template: 模板绝对路径, upper: 色带字体路径, lower: 大字字体路径}
        注：key 名为 upper/lower，由服务层从配置的 font_upper/font_lower 映射而来
    :param output_path: 输出文件路径，None 则返回 SVG 内容
    :return: SVG 内容（保留 viewBox，移除固定 width/height 便于自适应）
    :raise ValueError: code 为空 / road_level 非 IndonesiaRoadLevel 实例 / config 缺 key
        / 模板缺 id=back 或 id=head
    :raise FileNotFoundError: 模板或字体文件不存在（透传）
    """
    if not code:
        raise ValueError('道路编号不能为空')
    # 须判实例而非 `road_level in IndonesiaRoadLevel`：Python ≥3.12 起 `in Enum`
    # 按值比较（`1 in IndonesiaRoadLevel` 为真），int 会溜过校验并在 road_level.name 崩掉
    if not isinstance(road_level, IndonesiaRoadLevel):
        raise ValueError(f'未知的印尼道路等级: {road_level}')
    if not config or not all(config.get(k) for k in ('template', 'upper', 'lower')):
        raise ValueError('缺少印尼盾牌配置（template/upper/lower 路径）')

    # 色带颜色：NASIONAL/TOL 红、PROVINSI 蓝
    head_fill = INDONESIA_BANNER_RED
    if road_level == IndonesiaRoadLevel.PROVINSI:
        head_fill = INDONESIA_PROVINCE_BLUE

    banner_text = road_level.name
    if province_code:
        banner_text += f' {province_code}'

    width, height = _get_template_size(config['template'])
    head_bbox = _get_head_bbox(config['template'])
    center_x = width / 2
    head_center_y = (head_bbox[1] + head_bbox[3]) / 2
    lower_center_y = (head_bbox[3] + height) / 2

    dwg = svgwrite.Drawing(
        size=(f'{width}px', f'{height}px'),
        viewBox=f'0 0 {width} {height}',
        profile='full'
    )

    # 模板背景：白色六边形 → 黑色描边 → 色带（保持顺序，色带覆盖描边顶部）
    for tag, attrib in _get_back_group_elements(config['template']):
        if tag == 'polygon':
            if attrib.get('id') == 'head':
                fill = head_fill
                polygon = dwg.polygon(
                    points=_parse_polygon_points(attrib['points']),
                    fill=fill, id='head'
                )
            else:
                fill = WHITE
                polygon = dwg.polygon(
                    points=_parse_polygon_points(attrib['points']), fill=fill
                )
            dwg.add(polygon)
        elif tag == 'path':
            # svgwrite 不接受模板里紧凑的 path 语法，先解析再序列化
            # 描边带 id='outline'：其 fill 亦为 BLACK，测试按身份排除而非下标
            dwg.add(dwg.path(d=parse_path(attrib['d']).d(), fill=BLACK, id='outline'))
        else:
            # 模板结构变更（如描边改成 rect）时留痕，避免静默少画元素
            logger.warning(f'印尼盾牌模板 {config["template"]} 中忽略未支持的 <{tag}> 元素')

    # 色带小字（白）与大字（黑）
    for path in calculate_centered_scaled_char_info(
            banner_text, center_x, head_center_y,
            INDONESIA_BANNER_TEXT_HEIGHT, config['upper']):
        dwg.add(dwg.path(d=path.d(), fill=WHITE))
    for path in calculate_centered_scaled_char_info(
            code, center_x, lower_center_y,
            INDONESIA_NUMBER_TEXT_HEIGHT, config['lower']):
        dwg.add(dwg.path(d=path.d(), fill=BLACK))

    if output_path:
        dwg.saveas(output_path)
        return output_path
    svg_string = dwg.tostring()
    # 移除固定 width/height，保留 viewBox 自适应
    # 尺寸经 float() 解析后以 f'{width}px' 传入 svgwrite，输出带小数（width="562.0px"），
    # 故用 [\d.]+ 兼容整数与小数
    svg_string = re.sub(r' width="[\d.]+px"', '', svg_string)
    svg_string = re.sub(r' height="[\d.]+px"', '', svg_string)
    return svg_string
```

（test 引用的 `_get_head_bbox`/`_get_template_size` 即上述模块级函数，已提供。）

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && ../.venv/Scripts/python -m pytest tests/test_indonesia_shield.py -q`
Expected: 12 passed（若居中断言因模板坐标偏差失败，先人工打开 `data/templates/id_sheild.svg` 确认 viewBox 与 head 结构后放宽容差至 12px 并注明原因）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/gpxutil_wrapper/svg_gen.py backend/tests/test_indonesia_shield.py
git commit -m "feat(svg): 移植印尼六边形盾牌生成器（居中排版+bbox推导+Clearview字体）

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: 道路标志服务与 API 支持 region（含印尼解析分派、缓存隔离）

**Files:**
- Modify: `backend/app/gpxutil_wrapper/svg_gen.py`（`generate_road_sign` 分派）
- Modify: `backend/app/services/road_sign_service.py`
- Modify: `backend/app/api/road_signs.py`
- Create: `backend/tests/test_road_sign_region.py`（纯逻辑层测试，无 DB）

设计（spec §5 API 与缓存）：
- `generate_road_sign` 增 `region='cn'`；`id` 分支按「编号 + 路名文本序列 + 省名文本序列」调 `parse_indonesia_road_num`，结果交 `generate_indonesia_shield`。CN 分支完全不变。
- service 缓存键含 region；`RoadSignCache.region` 落库；生成 id 图标时从 `configs['indonesia_road_sign']` 解析模板/字体文件名并拼 `data/templates`、`data/fonts` 路径（用 `Path(settings.DATA_DIR)`，与 `admin.py:906` 既有约定一致；`DATA_DIR` 默认值 `"data"` **是相对路径**，随进程 cwd 解析，cn 分支的 `svg_gen.TEMPLATE_DIR` 同此约定）。
- API `RoadSignRequest` 加 `region/name_id/province_id`（cn 行为不变，id 时跳过 CN 正则校验）；`RoadSignResponse` 回显 region。

- [ ] **Step 1: 测试（红）**

`backend/tests/test_road_sign_region.py`：

```python
# -*- coding: utf-8 -*-
"""region 分派与缓存键测试（spec §8 用例 4、8）"""
import pytest

from app.gpxutil_wrapper.svg_gen import generate_road_sign
from app.services.road_sign_service import RoadSignService

ID_CONFIG = {
    # pytest cwd = backend/，与 Task 4 测试同约定（服务层的绝对路径拼接见 RoadSignService 内 base_dir 逻辑）
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

    # 注意：下面两个 TOL 用例的断言**已被下文「Task 5 fix loop」的 Step 9 取代**——
    # 原断言只看 head 颜色，而 TOL 与 NASIONAL 同为 #B5273C（仅 PROVINSI 为蓝），
    # 拦不住 TOL 判定回归（变异证实）。逐字执行本 Step 时以 Step 9 的版本为准。
    def test_id_tol_from_chinese_name(self):
        svg = generate_road_sign(
            'expwy', '8', name='雅加达收费高速', region='id',
            indonesia_config=ID_CONFIG, name_id='Jalan Tol Jagorawi')
        assert 'polygon' in svg

    def test_id_tol_detected_from_name_id(self):
        # name 无关键词、name_id 命中 tol → 仍判 TOL（红色 head）
        svg = generate_road_sign(
            'expwy', '8', name='雅加达高速', region='id',
            indonesia_config=ID_CONFIG, name_id='Jalan Tol Jagorawi')
        import xml.etree.ElementTree as ET
        head = [e for e in ET.fromstring(svg).iter()
                if e.tag.split('}')[-1] == 'polygon' and e.attrib.get('id') == 'head']
        # 色带红 = spec §5「实现时对齐 gpxutil」的 #B5273C（非国标红 #ED1724）
        assert head and head[0].attrib['fill'].upper() == '#B5273C'

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
```

- [ ] **Step 2: 运行确认红**

Run: `cd backend && ../.venv/Scripts/python -m pytest tests/test_road_sign_region.py -q`
Expected: TypeError（`generate_road_sign` 无 region 参数）。

- [ ] **Step 3: `svg_gen.py` 的 `generate_road_sign` 加 region 分派**

先把 Task 4 已提到模块顶部的 import 行扩成：

```python
from app.gpxutil_wrapper.indonesia import (
    REGION_CN, REGION_ID, IndonesiaRoadLevel, parse_indonesia_road_num,
)
```

（`indonesia.py` 只依赖标准库，不成环；本文件其余依赖也全在顶部，勿用函数内 import）

然后将 `generate_road_sign` 签名与主体（L708-735）替换为：

```python
def generate_road_sign(
    sign_type: str,
    code: str,
    province: Optional[str] = None,
    name: Optional[str] = None,
    region: str = 'cn',
    indonesia_config: Optional[dict] = None,
    name_id: Optional[str] = None,
    province_id: Optional[str] = None,
    font_config: Optional[dict] = None,
    output_path: Optional[str] = None,
) -> str:
    """
    统一的道路标志生成入口（按 region 分派）。

    Args:
        sign_type: 标志类型 ('way' 或 'expwy')，region='id' 时忽略
        code: 道路编号（cn: 如 G221/S21；id: 如 3、35-024）
        province: 省份（cn: 简称仅高速用；id: 省名文本，查省码用，可选）
        name: 道路名称（cn: 可选；id: 中文路名，TOL 关键词判定文本之一）
        region: 地区 ('cn' | 'id')
        indonesia_config: region='id' 时需要，dict {template, upper, lower, tol_keywords}
        name_id: region='id' 时印尼语路名（TOL 关键词判定文本之二）
        province_id: region='id' 时印尼语省名文本（查省码用，可选）
        font_config: 字体配置字典（仅 cn 用）
        output_path: 输出路径

    Returns:
        SVG 内容或文件路径

    Raises:
        ValueError: 未知 region / id 无法识别编号 / id 缺配置 / cn 缺模板字体等
    """
    if region == REGION_CN:
        if sign_type == 'way':
            return generate_way_num_sign(code, font_config, output_path)
        elif sign_type == 'expwy':
            return generate_expwy_sign(code, province, name, font_config, output_path)
        raise ValueError(f"未知的标志类型: {sign_type}")
    elif region == REGION_ID:
        if not indonesia_config:
            raise ValueError('缺少印尼盾牌配置（template/字体/关键词）')
        # 编号 + 路名（zh 与 id 任一命中 TOL 关键词）+ 省名文本 → 等级解析
        info = parse_indonesia_road_num(
            code,
            [name, name_id],
            [province_id, province],
            indonesia_config.get('tol_keywords') or ['收费', 'Tol'],
        )
        if not info:
            raise ValueError(f"无法识别的印尼道路编号: {code or ''}")
        return generate_indonesia_shield(
            info.code, info.level, info.province_code,
            {
                'template': indonesia_config['template'],
                'upper': indonesia_config['upper'],
                'lower': indonesia_config['lower'],
            },
            output_path,
        )
    raise ValueError(f"未知的地区: {region}")
```

- [ ] **Step 4: `road_sign_service.py` 增加 region 支持**

修改 `_generate_cache_key` 签名与实现：

```python
    def _generate_cache_key(
        self,
        sign_type: str,
        code: str,
        province: Optional[str] = None,
        name: Optional[str] = None,
        region: str = 'cn',
        name_id: Optional[str] = None,
        province_id: Optional[str] = None,
    ) -> str:
        """生成缓存键（含 region，不同地区的同编号不串样）"""
        key_data = (f"{region}:{sign_type}:{code}:{province or ''}:{name or ''}:"
                    f"{name_id or ''}:{province_id or ''}")
        return hashlib.md5(key_data.encode()).hexdigest()
```

修改 `get_or_create_sign`：签名加 `region: str = 'cn', name_id: Optional[str] = None, province_id: Optional[str] = None`；docstring 同步；`cache_key` 调用改为 `self._generate_cache_key(sign_type, code, province, name, region, name_id, province_id)`。

在 `configs = await config_service.get_all_configs(db)` 之后、现有 `font_config` 读取附近，将生成段替换为 region 分支：

```python
        # 获取配置
        configs = await config_service.get_all_configs(db)
        font_config = configs.get('font_config')

        # 印尼配置：文件名解析为 DATA_DIR 下的资源路径（DATA_DIR 默认 'data'，相对路径随 cwd 解析）
        indonesia_config = None
        if region == 'id':
            id_cfg = configs.get('indonesia_road_sign') or {}
            base_dir = Path(settings.DATA_DIR)
            template_file = base_dir / 'templates' / (id_cfg.get('template') or 'id_sheild.svg')
            upper_file = base_dir / 'fonts' / (id_cfg.get('font_upper') or 'ClearviewHwy1W.ttf')
            lower_file = base_dir / 'fonts' / (id_cfg.get('font_lower') or 'ClearviewHwy2W.ttf')
            missing = [str(f) for f in (template_file, upper_file, lower_file) if not f.exists()]
            if missing:
                logger.error(f"Missing indonesia road sign assets: {missing}")
                raise FileNotFoundError('印尼盾牌资源缺失（模板/字体），请检查 data 目录')
            indonesia_config = {
                'template': str(template_file),
                'upper': str(upper_file),
                'lower': str(lower_file),
                'tol_keywords': id_cfg.get('tol_keywords') or ['收费', 'Tol'],
            }

        # 生成新的 SVG
        try:
            svg_content = generate_road_sign(
                sign_type=sign_type,
                code=code,
                province=province,
                name=name,
                region=region,
                indonesia_config=indonesia_config,
                name_id=name_id,
                province_id=province_id,
                font_config=font_config,
                output_path=svg_path
            )
```

同时文件顶部补 `from pathlib import Path`（`data/` 下资源解析沿用本仓既有写法 `Path(settings.DATA_DIR) / ...`，见 `app/api/admin.py:906`）。

缓存行构造 `RoadSignCache(...)` 加 `region=region`；`RoadSignCache(region=region, ...)`。在 `cached` 命中且文件存在时无需变动（缓存按 region 键隔离）。update 分支 `cached.svg_path = svg_path` 后加 `cached.region = region`（同键更新安全）。

- [ ] **Step 5: `api/road_signs.py` 请求/响应模型**

`RoadSignRequest` 改造（替换类体中相关部分）：

```python
class RoadSignRequest(BaseModel):
    """道路标志生成请求"""
    sign_type: str = Field(..., description="标志类型: way(普通道路) 或 expwy(高速)；region=id 时忽略")
    code: str = Field(..., description="道路编号（cn: G221/S88 等；id: 3/35-024/023 等）")
    province: Optional[str] = Field(None, description="省份（cn: 简称如 '豫'；id: 省名文本如 'Provinsi Jawa Timur'，查省码用）")
    name: Optional[str] = Field(None, description="道路名称（id: 中文路名，TOL 判定文本）")
    region: str = Field('cn', description="地区: cn(中国国标) 或 id(印尼六边形盾牌)")
    name_id: Optional[str] = Field(None, description="印尼语道路名称（region=id 时 TOL 判定文本）")
    province_id: Optional[str] = Field(None, description="印尼语省名文本（region=id 时查省码用）")

    @field_validator('region')
    @classmethod
    def validate_region(cls, v: str) -> str:
        if v not in ('cn', 'id'):
            raise ValueError("无效的地区，可选值: cn, id")
        return v

    @field_validator('code')
    @classmethod
    def normalize_code(cls, v: str) -> str:
        """规范化道路编号：转大写（仅 cn 有意义；id 数字不受影响）"""
        return v.strip().upper()

    @model_validator(mode='after')
    def validate_road_sign(self) -> 'RoadSignRequest':
        """校验道路编号（region=cn 时执行现有规则，region=id 时不套用国标正则）"""
        code = self.code
        sign_type = self.sign_type
        province = self.province

        if not code:
            raise ValueError("道路编号不能为空")

        if self.region == 'id':
            # 印尼编号由后端按编号+路名+省名解析（parse_indonesia_road_num），不做格式猜测
            return self

        if sign_type == 'way':
            # 普通道路：字母 + 三位数字
            if not re.match(r'^[A-Z]\d{3}$', code):
                raise ValueError("普通道路编号格式错误：应为字母 + 三位数字，如 G221、S221、X221")

        elif sign_type == 'expwy':
            # 高速公路：国家高速或省级高速
            if code.startswith('G'):
                if not re.match(r'^G\d{1,4}$', code):
                    raise ValueError("国家高速编号格式错误：应为 G + 1-4位数字，如 G5、G45、G4511")
            elif code.startswith('S'):
                letter_format_match = re.match(r'^S([A-Z]\d{0,3})$', code)
                if letter_format_match:
                    if province != '川':
                        raise ValueError("字母格式的省级高速编号（如 SA、SC、SA1）仅限四川省使用，请使用纯数字编号（如 S1、S11）或选择四川省")
                elif not re.match(r'^S\d{1,4}$', code):
                    raise ValueError("省级高速编号格式错误：应为 S + 1-4位数字（如 S1、S11、S1111），或仅限四川省使用 S + 字母 + 可选数字（如 SA、SC、SA1）")
            else:
                raise ValueError("高速公路编号应以 G（国家高速）或 S（省级高速）开头")

        return self
```

原 `validate_province` field_validator 对所有 region 都会跑，`province` 字段在 `region='id'` 时承载的是印尼语省名（如 'Provinsi Jawa Timur'），会被中文简称白名单误拒。**按以下方式改造（不要用 `info.data.get('region')` 判分支——field_validator 的 `info.data` 只含"已校验过的字段"，依赖字段声明顺序且 `province` 声明在 `region` 之前时恒取不到，脆弱）**：

把白名单检查整体移入 `validate_road_sign` 的 cn 分支，原 field_validator 只保留规范化职责，并把白名单提到模块级常量（原来每次调用重建 set）：

```python
# 中国省份简称白名单（仅 region='cn' 校验用）
_VALID_PROVINCE_ABBR = frozenset({
    '京', '津', '冀', '晋', '蒙', '辽', '吉', '黑',
    '沪', '苏', '浙', '皖', '闽', '赣', '鲁', '豫',
    '鄂', '湘', '粤', '桂', '琼', '渝', '川', '贵',
    '云', '藏', '陕', '甘', '青', '宁', '新',
})
```

```python
    @field_validator('province')
    @classmethod
    def normalize_province(cls, v: Optional[str]) -> Optional[str]:
        """规范化省份：去空白，空串归一为 None（简称白名单见 validate_road_sign，仅 cn 适用）"""
        if v is None:
            return None
        return v.strip() or None
```

在 `validate_road_sign` 中 `if self.region == 'id': return self` **之后**（即 cn 路径上）加：

```python
        if province and province not in _VALID_PROVINCE_ABBR:
            raise ValueError(f"无效的省份简称：{province}。应为标准省份简称，如'京'、'津'、'冀'等")
```

（cn 行为等价：先 strip、空串转 None、再查白名单。**唯一的非等价点**是错误文案中回显的值由未 strip 的原值 `v` 变为 strip 后的 `province`，仅当输入含首尾空白时可观察到，属有意收紧。测试补一条 id 请求带任意 province 文本通过的断言。）

`RoadSignResponse` 加：

```python
    region: str = 'cn'
```

生成端点 body 传参加四个字段（request → service 调用与响应构造）：

```python
        svg_content, cached = await road_sign_service.get_or_create_sign(
            db=db,
            sign_type=request.sign_type,
            code=request.code,
            province=request.province,
            name=request.name,
            region=request.region,
            name_id=request.name_id,
            province_id=request.province_id,
        )

        return RoadSignResponse(
            svg=svg_content,
            cached=cached,
            sign_type=request.sign_type,
            code=request.code,
            province=request.province,
            name=request.name,
            region=request.region,
        )
```

- [ ] **Step 6: 运行测试**

Run: `cd backend && ../.venv/Scripts/python -m pytest tests/test_road_sign_region.py tests/test_indonesia_road.py tests/test_indonesia_shield.py -q`
Expected: 全部通过。

语法检查（api 层）：
Run: `cd backend && ../.venv/Scripts/python -c "import app.api.road_signs; import app.services.road_sign_service; print('ok')"`
Expected: ok。

- [ ] **Step 7: Commit**

```bash
git add backend/app/gpxutil_wrapper/svg_gen.py backend/app/services/road_sign_service.py backend/app/api/road_signs.py backend/tests/test_road_sign_region.py
git commit -m "feat(road-sign): generate 接口与缓存按 region 分派，支持印尼六边形盾牌

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

#### Task 5 fix loop（质量审查回写，2026-09-10）

质量审查结论：1 Critical + 2 Important。以下 Step 8-12 全部完成后**用 `git commit --amend --no-edit` 并入 Task 5 的提交**（保持单任务单 commit）。

- [ ] **Step 8: [Critical] 放宽 `road_sign_cache.province` 列宽**

问题：`province` 为 `String(10)`，而 `region='id'` 时该列承载印尼语省名，最长 `'Daerah Khusus Ibukota Jakarta'`（29 字符）。SQLite 不校验长度故当前无感；MySQL 严格模式（默认 `STRICT_TRANS_TABLES`）报 1406 `Data too long`、PostgreSQL 报 `value too long for type character varying(10)` → `POST /road-signs/generate` 变 500；MySQL 非严格模式静默截断为 `'Provinsi J'`。

`backend/app/models/road_sign.py` 第 17 行：

```python
    province = Column(String(100), nullable=True)  # 省份（cn: 简称如 '豫'；id: 印尼语省名）
```

`backend/alembic/versions/016_add_multilanguage_region.py` 的 `upgrade()` 末尾（`road_sign_cache.region` 之后）追加：

```python
    # road_sign_cache.province 放宽：region='id' 时该列承载印尼语省名
    # （最长 'Daerah Khusus Ibukota Jakarta' 29 字符；原 String(10) 在 MySQL 严格模式
    #  报 1406 Data too long、PostgreSQL 报 value too long for type character varying(10)）
    # 用 batch_alter_table：SQLite 不支持直接改列类型，batch 模式会重建表；
    # MySQL / PostgreSQL 下退化为普通 ALTER COLUMN。
    with op.batch_alter_table('road_sign_cache') as batch_op:
        batch_op.alter_column(
            'province', type_=sa.String(100), existing_type=sa.String(10),
            existing_nullable=True,
        )
```

`downgrade()` 里对称加回（放在 `drop_if_exists('road_sign_cache', 'region')` 之前）：

```python
    with op.batch_alter_table('road_sign_cache') as batch_op:
        batch_op.alter_column(
            'province', type_=sa.String(10), existing_type=sa.String(100),
            existing_nullable=True,
        )
```

三份 SQL 脚本同步（016 是本特性未发布迁移，直接改比新增 017 更小）：

- `016_add_multilanguage_region.sql.mysql`（`road_sign_cache` 段之后、验证段之前）：
  ```sql
  -- province 放宽：region='id' 时承载印尼语省名（最长 29 字符）
  ALTER TABLE road_sign_cache MODIFY COLUMN province VARCHAR(100) NULL;
  ```
- `016_add_multilanguage_region.sql.postgresql`（同位置）：
  ```sql
  -- province 放宽：region='id' 时承载印尼语省名（最长 29 字符）
  ALTER TABLE road_sign_cache ALTER COLUMN province TYPE VARCHAR(100);
  ```
- `016_add_multilanguage_region.sql.sqlite`（`road_sign_cache` 段之后）——**只加注释，不加语句**：
  ```sql
  -- road_sign_cache.province 无需变更：SQLite 不校验 VARCHAR 长度，
  -- 模型侧的 String(100) 仅为与 MySQL / PostgreSQL 对齐
  ```

开发库已在 016 上（用户决策「保留 016」），但 SQLite 不校验长度，无需重跑；`alembic upgrade head` 对新库会执行新版 016。

- [ ] **Step 9: [Important] 加强两个 TOL 用例的断言（原断言空转）**

问题：`INDONESIA_BANNER_RED`(#B5273C) 同时用于 `NASIONAL` 与 `TOL`，仅有 `PROVINSI` 是蓝 `#003E86`；故 `code='8'` 无论有无 TOL 关键词，head fill 都是 `#B5273C`。变异测试证实：把 `parse_indonesia_road_num(code, [name, name_id], …)` 分别改成 `[name]`（丢 name_id）或 `[name_id]`（丢 name），**42 个用例全绿** —— 两个 TOL 判定入口均无有效覆盖。

**先验证断言有区分力**（SVG 需确定性与可区分，两步都须通过；任一失败则改用「色带文字路径条数」比对，TOL 3 字 vs NASIONAL 8 字）：

```bash
cd backend && ../.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0, '.')
from app.gpxutil_wrapper.svg_gen import generate_road_sign
c = {'template': 'data/templates/id_sheild.svg', 'upper': 'data/fonts/ClearviewHwy1W.ttf',
     'lower': 'data/fonts/ClearviewHwy2W.ttf', 'tol_keywords': ['收费', 'Tol']}
a = generate_road_sign(sign_type='way', code='8', region='id', indonesia_config=c)
b = generate_road_sign(sign_type='way', code='8', region='id', indonesia_config=c)
t = generate_road_sign(sign_type='way', code='8', region='id', indonesia_config=c, name='雅加达收费高速')
assert a == b, 'SVG 非确定性，不能整体比对'
assert a != t, 'TOL 与 NASIONAL 渲染相同，需换断言方式'
print('ok')
"
```

把 `test_road_sign_region.py` 的两个用例替换为（**每个变体只覆盖一个入口**：丢 `name` 时中文用例红、丢 `name_id` 时 name_id 用例红）：

```python
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
        base = generate_road_sign(
            'expwy', '8', name='雅加达高速', region='id',
            indonesia_config=ID_CONFIG, name_id='Jalan Jagorawi')
        tol = generate_road_sign(
            'expwy', '8', name='雅加达高速', region='id',
            indonesia_config=ID_CONFIG, name_id='Jalan Tol Jagorawi')
        assert tol != base
        import xml.etree.ElementTree as ET
        head = [e for e in ET.fromstring(tol).iter()
                if e.tag.split('}')[-1] == 'polygon' and e.attrib.get('id') == 'head']
        # 色带红 = spec §5「实现时对齐 gpxutil」的 #B5273C（非国标红 #ED1724）
        assert head and head[0].attrib['fill'].upper() == '#B5273C'
```

改完**必须逐条变异自证**（改坏 → 确认用例变红 → 还原，`git hash-object` 留证）：
- 变异 E：`[name, name_id]` → `[name]` ⇒ `test_id_tol_detected_from_name_id` 红
- 变异 F：`[name, name_id]` ⇒ `[name_id]` ⇒ `test_id_tol_from_chinese_name` 红

- [ ] **Step 10: [Important] 补资源缺失分支的用例**

问题：`road_sign_service.py:102-105` 的 `FileNotFoundError` 分支零覆盖——把 `raise` 改成静默吞掉后 42 个用例仍全绿。该分支在真实部署中可达（Clearview 字体需手工放置、不入库）。资源检查在 `config_service.get_all_configs(db)` 之后、`db.add` 之前，用 stub 会话即可覆盖，不需要真实数据库。

在 `test_road_sign_region.py` 末尾追加：

```python
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
```

- [ ] **Step 11: 两处 Minor 修正**

1. `backend/app/services/road_sign_service.py:94` 注释「…下的绝对路径」→ 实际 `settings.DATA_DIR` 默认值是相对路径 `"data"`：
   ```python
        # 印尼配置：文件名解析为 DATA_DIR 下的资源路径（DATA_DIR 默认 'data'，相对路径随 cwd 解析）
   ```
2. `backend/app/api/road_signs.py:32` 的 `sign_type` 描述与实际校验不符（`region='id'` 时端点仍强制 `way`/`expwy`，否则 400）：
   ```python
    sign_type: str = Field(..., description="标志类型: way(普通道路) 或 expwy(高速)；region=id 时该值不参与生成，但仍须为 way/expwy")
   ```

- [ ] **Step 12: 全量验证 + amend 提交**

```bash
cd backend && ../.venv/Scripts/python.exe -m pytest tests/ -q
```
Expected: **43 passed**（原 42 + 资源缺失 1 条；两个 TOL 用例是替换不是新增，不增计数）。

```bash
cd /d/code/vibe_route && git add backend/app/models/road_sign.py \
  backend/alembic/versions/016_add_multilanguage_region.py \
  backend/alembic/versions/016_add_multilanguage_region.sql.mysql \
  backend/alembic/versions/016_add_multilanguage_region.sql.postgresql \
  backend/alembic/versions/016_add_multilanguage_region.sql.sqlite \
  backend/app/services/road_sign_service.py backend/app/api/road_signs.py \
  backend/tests/test_road_sign_region.py
git commit --amend --no-edit
```

> **执行教训（本次已发生一次）**：`--amend` 改的是 **HEAD**，若控制方在派发 fix loop 前又提交了别的东西（如计划文档），HEAD 就不是任务提交了，修复会被并进那个提交。本次因此产生一次历史重建（`git diff <错误提交> HEAD` 为空可证内容无损）。**后续任务的 fix loop**：派发前先确认 `git log --oneline -1` 就是该任务的提交，或在 fix 指令里写明「amend 前先 `git log -1` 确认 HEAD == 任务提交，不等则停下报告」。

**已知但本轮不修**（记录备查）：
- `road_sign_cache` 的 DB 落库分支（新建/命中/更新三分支的 `region` 写入）无测试覆盖（计划声明该文件不测 DB）；端到端冒烟（Task 13）兜底。
- 缓存键换算法使既有 cn 缓存 100% 失效（实测 88 行 0 命中）→ 旧行与 `data/road_signs/*.svg` 成为孤儿，`/road-signs/list` 会对同编号显示新旧两条；发布后调一次 `POST /road-signs/clear-cache` 即可（写入 Task 14 的 cc 文档）。
- `RoadSignListItem` 未暴露 `region`，列表页无法区分 cn/id 同编号图标；若 Task 12 前端需要再加 `region=cache.region`。
- `_VALID_PROVINCE_ABBR` 与 `geocoding.PROVINCE_NAME_TO_SHORT.values()` 内容相同（跨层 import 会引入耦合，保持现状）。
- 缓存键以 `:` 手拼自由文本的理论碰撞面（`name='a:b'` 跨字段移位）；旧键已有此性质，未构造出真实渲染分歧。

- [ ] **Step 13: 复审 Minor 收尾（质量复审回写，2026-09-10）**

复审结论 ✅ 通过（三项修复经变异反向验证）。以下 4 条 Minor 一并收尾，仍 `git commit --amend --no-edit` 并入 Task 5 提交：

1. `backend/tests/test_road_sign_region.py:9` 的注释漏改（与 Step 11 同类的措辞）：
   ```python
       # pytest cwd = backend/，与 Task 4 测试同约定（服务层的 DATA_DIR 相对路径拼接见 RoadSignService 内 base_dir 逻辑）
   ```
2. `test_id_tol_detected_from_name_id` 补一道确定性守卫——该用例的 `assert tol != base` 比对的是**两份不同输入**，若渲染变得不确定（同输入两次输出不同），断言会因错误理由通过。把该用例改为：
   ```python
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
   ```
3. 三份 SQL 的 province 注释补一句「就地改写迁移」的补执行提示（MySQL / PostgreSQL 两份）：
   ```sql
   -- province 放宽：region='id' 时承载印尼语省名（最长 29 字符）
   -- 若某环境已执行过本迁移的早期版本（alembic 视为已应用而跳过），需手工补执行本行
   ```
4. SQLite 的 016 头注已在 Step 8 处理，无需再动。

验收：`../.venv/Scripts/python.exe -m pytest tests/ -q` → **43 passed**（Step 13 只加断言不加用例）。


---

### Task 6: Nominatim 多语言请求 + fill_geocoding_info 写 `*_id` 与 region + 中文省回填

**Files:**
- Modify: `backend/app/gpxutil_wrapper/geocoding.py`（NominatimGeocoding.get_point_info）
- Modify: `backend/app/services/track_service.py`（fill_geocoding_info L503-672）
- Modify: `backend/app/api/tracks.py`（fill-geocoding 端点 L492-531 加 region Query）

设计：region='id' 时 Nominatim 发 **zh-CN / id / en 三请求**（cn 现状两请求不变），结果新增 `province_id/city_id/area_id/road_name_id` 键；`fill_geocoding_info` 增加 `region: Optional[str] = None`——缺省回读 `track.region`（live recording 调用点零改动），region 明确时：点写 `region`、4 个 `*_id` 字段、印尼省级中文尽力回填（38 省表，province 空或与 province_id 相同才回填），完成时 `track.region` 同步。S 前缀中国高速逻辑仅在 cn 生效。

- [ ] **Step 1: 修改 `geocoding.py` 的 `NominatimGeocoding.get_point_info`**

方法签名加 region，把固定 zh/en 双请求改成按 region 的语言集循环。整体替换 `get_point_info`（L59-152）与结果初始化：

```python
    async def get_point_info(self, lat: float, lon: float, region: str = 'cn') -> dict[str, Any]:
        """获取点的地理信息

        Args:
            region: 地区（'cn' 现状逻辑；'id' 增加印尼语请求，写入 *_id 字段）
        """
        result = {
            'province': '',
            'city': '',
            'area': '',
            'town': '',
            'road_name': '',
            'road_num': '',
            'province_en': '',
            'city_en': '',
            'area_en': '',
            'town_en': '',
            'road_name_en': '',
            # 印尼语（region='id' 时填充）
            'province_id': '',
            'city_id': '',
            'area_id': '',
            'road_name_id': '',
            'memo': ''
        }

        # 语言请求集：cn 维持现状（中文+英文），id 增加印尼语；
        # 未识别的 region 走 cn 集（spec §9：不选/未知地区 = 现状不变）
        languages = ['zh-CN', 'id', 'en'] if region == 'id' else ['zh-CN', 'en']

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                params = {
                    'lat': lat,
                    'lon': lon,
                    'format': 'geocodejson',
                    'layer': 'address',
                    'extratags': 1,
                    'zoom': 17,
                    'accept-language': 'zh-CN'
                }

                # 各语言依次请求（结果存 revs[语言]）
                revs: dict[str, dict] = {}
                for lang in languages:
                    params['accept-language'] = lang
                    response = await client.get(f"{self.url}/reverse", params=params)
                    revs[lang] = response.json()

                rev = revs['zh-CN']
                if 'features' not in rev or not rev['features']:
                    result['memo'] = 'No results found'
                    return result

                # 按语言取 admin 层级（zh-CN 无中译时多为本地名，后续尽力回填）
                for lang in languages:
                    feats = revs[lang].get('features') or []
                    admin = feats[0]['properties']['geocoding']['admin'] if feats else {}
                    suffix = '' if lang == 'zh-CN' else f'_{lang}'
                    result[f'province{suffix}'] = admin.get('level4', '')
                    result[f'city{suffix}'] = admin.get('level5', '')
                    result[f'area{suffix}'] = admin.get('level6', '')
                    result[f'town{suffix}'] = admin.get('level8', '')

                # 获取道路信息（取各语言请求的道路名，id 时 *_id 用 id 请求名）
                if rev['features'][0]['properties']['geocoding']['osm_type'] == 'way':
                    for lang in languages:
                        feats = revs[lang].get('features') or []
                        if not feats:
                            continue
                        name = feats[0]['properties']['geocoding'].get('name', '')
                        suffix = '' if lang == 'zh-CN' else f'_{lang}'
                        result[f'road_name{suffix}'] = name
                    # 现状：英文名与中文名相同时置空
                    if result['road_name_en'] == result['road_name']:
                        result['road_name_en'] = ''

                    # 获取道路编号
                    place_id = rev['features'][0]['properties']['geocoding']['place_id']
                    details_response = await client.get(f"{self.url}/details", params={'place_id': place_id})
                    details = details_response.json()
                    if 'names' in details and 'ref' in details['names']:
                        road_nums = details['names']['ref'].split(';')
                        processed_nums = []
                        for num in road_nums:
                            num = num.strip().upper()
                            # 为省级高速添加省份前缀为中国专属逻辑（仅 cn），印尼 raw ref 直接用
                            if region == 'cn' and num.startswith('S') and len(num) >= 2 and num[1:].isdigit():
                                has_province_prefix = any(
                                    num.startswith(prefix)
                                    for prefix in PROVINCE_NAME_TO_SHORT.values()
                                )
                                if not has_province_prefix:
                                    province_short = None
                                    if result['province']:
                                        province_short = PROVINCE_NAME_TO_SHORT.get(result['province'])
                                    elif result['province_en']:
                                        province_short = PROVINCE_EN_TO_SHORT.get(result['province_en'])
                                    if province_short:
                                        num = f"{province_short}{num}"
                            processed_nums.append(num)
                        result['road_num'] = ','.join(processed_nums)

        except Exception as e:
            result['memo'] = str(e)

        return result
```

- [ ] **Step 2: 修改 `track_service.py` 的 `fill_geocoding_info`**

签名加 region（`incremental` 之后）：

```python
    async def fill_geocoding_info(
        self,
        db: AsyncSession,
        track_id: int,
        user_id: int,
        incremental: bool = False,
        region: Optional[str] = None,
    ):
```

docstring 补参数说明：`region: 填充的地区（'cn'/'id'）；None 时使用轨迹自身 region（默认 'cn'）`。

在 L525 `async with async_session_maker() as db:`（函数自建新会话，因调用方会话可能已关闭）之后的 try 主逻辑内、L528 获取轨迹点之前（L527 处）插入 region 解析与轨迹读取；尾部（Step 4）对 Track 的重复查询（L650-653）改为复用这里的 `track_row`：

```python
                # 读取轨迹确定有效 region（region 缺省时回读轨迹自身 region；live recording 调用点零改动）
                track_row = (await db.execute(select(Track).where(Track.id == track_id))).scalar_one_or_none()
                region = region or (getattr(track_row, 'region', None) or 'cn')
                if region not in ('cn', 'id'):
                    logger.warning(f"Invalid fill region '{region}' for track {track_id}, fallback to 'cn'")
                    region = 'cn'
```

- [ ] **Step 3: 填充循环写点（L590-624 区段改造）**

先在循环外判定 provider 能力，插在 L572 `logger.info(f"Geocoding service acquired: ...")` 之后、L574 `updated_count = 0` 之前——`region='id'` 只有 Nominatim 支持（amap/baidu/gdf 只服务中国），判定放循环外可避免逐点刷告警：

```python
                # 印尼多语言仅 Nominatim 支持（amap/baidu/gdf 只服务中国）；判定放循环外，避免逐点重复告警
                from app.gpxutil_wrapper.geocoding import NominatimGeocoding
                supports_id = isinstance(geocoding_service, NominatimGeocoding)
                if region == 'id' and not supports_id:
                    logger.warning(
                        f"Track {track_id} region=id but geocoding provider "
                        f"{type(geocoding_service).__name__} has no Indonesian support"
                    )
```

再把循环内「获取信息 + 写点」段（**原 L591 `lat = point.latitude_wgs84` 到 L624 `updated_count += 1`**）整体替换为下方代码。原 L621-624 的 `point.updated_by = user_id` 与 `updated_count += 1` 已包含在下方代码块内，**替换后不要保留旧行**（否则重复赋值）；替换段之后的 L626-627 进度更新保持原位不动。

```python
                    try:
                        lat = point.latitude_wgs84
                        lon = point.longitude_wgs84
                        if supports_id:
                            info = await geocoding_service.get_point_info(lat, lon, region=region)
                        else:
                            info = await geocoding_service.get_point_info(lat, lon)

                        # 检查是否获取到有效数据（至少有一个非空字段）
                        has_valid_data = any([
                            info.get('province'),
                            info.get('city'),
                            info.get('area'),
                            info.get('road_name'),
                            info.get('road_num'),
                            info.get('province_en'),
                            info.get('city_en'),
                            info.get('area_en'),
                            info.get('road_name_en'),
                            info.get('province_id'),
                            info.get('city_id'),
                            info.get('area_id'),
                            info.get('road_name_id'),
                        ])

                        if has_valid_data:
                            # 同时填充行政区划和道路信息
                            point.province = info.get('province', '')
                            point.city = info.get('city', '')
                            point.district = info.get('area', '')
                            point.road_name = info.get('road_name', '')
                            point.road_number = info.get('road_num', '')
                            # 英文字段
                            point.province_en = info.get('province_en', '')
                            point.city_en = info.get('city_en', '')
                            point.district_en = info.get('area_en', '')
                            point.road_name_en = info.get('road_name_en', '')
                            # 印尼语字段（非 nominatim provider 结果为缺省空串，不额外处理）
                            point.province_id = info.get('province_id', '')
                            point.city_id = info.get('city_id', '')
                            point.district_id = info.get('area_id', '')
                            point.road_name_id = info.get('road_name_id', '')
                            # 点级 region（fill 后点归该地区，轨迹级同步见尾部）
                            point.region = region

                            # 印尼省级中文尽力回填：zh-CN 结果为空或与印尼语相同
                            # （Nominatim 对无中译省份返回本地名）→ 用 38 省译名表
                            if region == 'id':
                                zh_province = info.get('province', '')
                                id_province = info.get('province_id', '')
                                if (not zh_province or zh_province == id_province) and id_province:
                                    from app.gpxutil_wrapper.indonesia import get_indonesia_province_zh
                                    zh = get_indonesia_province_zh(id_province)
                                    if zh:
                                        point.province = zh

                            # 更新审计字段
                            point.updated_by = user_id

                            updated_count += 1
```

（说明：`NominatimGeocoding` 的 import 放在循环外的判定处；若你更希望放函数顶部、与 Step 2 引入的其它 import 合并亦可，以「无重复 import 且可运行」为准。`supports_id` 在循环外算好，循环内直接复用。）

- [ ] **Step 4: 尾部轨道更新（L649-659 区段）**

将原：

```python
                # 更新轨迹标记（只有成功填充了数据才标记为 True）
                track_result = await db.execute(
                    select(Track).where(Track.id == track_id)
                )
                track = track_result.scalar_one_or_none()
                if track:
                    # 只有成功填充了至少一个点，才设置标记
                    if updated_count > 0:
                        track.has_area_info = True
                        track.has_road_info = True
                    track.updated_by = user_id
```

替换为（复用 Step 2 开头取的 `track_row`，并同步轨迹 region 为本次填充地区）：

```python
                # 更新轨迹标记（只有成功填充了数据才标记为 True）
                track = track_row
                if track:
                    # 只有成功填充了至少一个点，才设置标记
                    if updated_count > 0:
                        track.has_area_info = True
                        track.has_road_info = True
                        track.region = region  # 填充地区成为该轨迹的默认地区
                    track.updated_by = user_id
```

- [ ] **Step 5: fill-geocoding API 加 region 参数（`backend/app/api/tracks.py` L492-531）**

```python
@router.post("/{track_id}/fill-geocoding")
async def fill_track_geocoding(
    track_id: int,
    incremental: bool = Query(False, description="增量模式：仅填充行政区划为空的点，不覆盖已有数据"),
    region: Optional[str] = Query(None, description="填充的地区 (cn/id)；缺省用轨迹自身 region"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
```

内部 fill_task 调用改为：

```python
                await track_service.fill_geocoding_info(
                    new_db, track_id, current_user.id,
                    incremental=incremental, region=region)
```

- [ ] **Step 6: 语法检查**

Run: `cd backend && ../.venv/Scripts/python -c "import app.gpxutil_wrapper.geocoding; import app.api.tracks; print('ok')"`
Expected: ok

- [ ] **Step 7: Commit**

```bash
git add backend/app/gpxutil_wrapper/geocoding.py backend/app/services/track_service.py backend/app/api/tracks.py
git commit -m "feat(geocoding): Nominatim 印尼三语请求，填充写入 *_id 与点级 region，38省中文回填

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6 fix loop（质量审查 2 Important + 1 Minor，2026-09-10）

质量审查结论 **✅ 通过**（无 Critical），另提 2 项 Important、5 项 Minor。本 fix loop 只处理其中 3 项（#1 参数校验、#2 补测、#4 回填判定）；其余在文末「不改判定」记录，**不要顺手改**。

**审查者实测的背景（Why）**：
- `region` Query 参数无类型约束 → 传 `region='ID'`（大写）时服务层按非法值回落 `'cn'` 仅记 warning → 一条 `region='id'` 的轨迹**所有点**被写 `region='cn'`、`*_id` 全部清空、`track.region` 被持久化为 `'cn'`。而 `track.region` 是点级权威字段，误改后 `incremental=True` **修不回来**（增量条件只看 `province` 是否为空，id/cn 填充后都非空），只能整条重填。
- 本 Task 的核心分派（语言集、`*_id` 映射、S 前缀门控）在 `tests/` 中**零覆盖**——现有 43 用例全部来自 Task 1/4/5。其中「cn 高速编号丢省份前缀」是**既有功能回归**，最贵。

**Files:**
- Modify: `backend/app/api/tracks.py`（L5 导入 + L496 参数类型）
- Modify: `backend/app/services/track_service.py`（L658 回填判定条件）
- Create: `backend/tests/test_nominatim_region.py`

- [ ] **Step 1: 写测试 `backend/tests/test_nominatim_region.py`**

说明：本组测试是对**已完成实现**的回归守卫（不是 TDD 新功能），写完即应全绿；若某条红，说明实现有缺陷，**停下来报告**，不要改测试去迁就实现。

```python
# -*- coding: utf-8 -*-
"""Nominatim region 分派回归守卫：语言集、*_id 字段映射、S 前缀门控

Task 6 质量审查 Important #2：本 Task 的核心分派逻辑此前零覆盖。
无网络、无数据库：替换 httpx.AsyncClient 为按 accept-language 回放固定 geocodejson 的假 client。
"""
import asyncio

import pytest

from app.gpxutil_wrapper import geocoding as geo_module
from app.gpxutil_wrapper.geocoding import NominatimGeocoding


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
```

- [ ] **Step 2: 跑测试**

Run: `cd backend && ../.venv/Scripts/python -m pytest tests/test_nominatim_region.py -v`
Expected: **3 passed**。若任一红 → 停止并报告（实现缺陷，不要改测试迁就）。

- [ ] **Step 3: `tracks.py` 收紧 `region` 参数类型（Important #1）**

L5 导入改为：

```python
from typing import Optional, Literal
```

L496 改为：

```python
    region: Optional[Literal['cn', 'id']] = Query(None, description="填充的地区 (cn/id)；缺省用轨迹自身 region"),
```

（FastAPI 会依此生成 enum 校验，非法值直接 422，不再进入服务层的「回落 'cn'」路径。
服务层 `fill_geocoding_info` 内的非法值告警回落**保留不动**——它是内部调用（如 `region=None`）的防御，现在不会再被外部误触发。）

- [ ] **Step 4: `track_service.py` 回填判定加 ASCII 兜底（Minor #4）**

实测 L658，将：

```python
                                if (not zh_province or zh_province == id_province) and id_province:
```

改为：

```python
                                if (not zh_province or zh_province == id_province
                                        or zh_province.isascii()) and id_province:
```

理由：zh-CN 请求在无中译时可能返回英文/拼音形态（如 `West Java` 而 id 侧为 `Jawa Barat`），
此时旧条件不成立 → 中文列留下非中文值。加 `isascii()` 后仍由 `if zh:` 守卫兜底
（查表失败不会清空已有值）。

- [ ] **Step 5: 全量测试 + 参数校验的 schema 断言**

```bash
cd backend
../.venv/Scripts/python -m pytest tests/ -q
```
Expected: **46 passed**（原 43 + 新增 3）

```bash
../.venv/Scripts/python -c "from app.main import app; p=[x for x in app.openapi()['paths']['/api/tracks/{track_id}/fill-geocoding']['post']['parameters'] if x['name']=='region'][0]; print(p['schema']); assert ['cn','id'] in [b.get('enum',[]) for b in p['schema'].get('anyOf',[p['schema']])]"
```
Expected: 打印 `{'anyOf': [{'enum': ['cn', 'id'], 'type': 'string'}, {'type': 'null'}], 'title': 'Region', ...}` 且断言通过
（若路径前缀不是 `/api`，以实际 OpenAPI 为准）

> **⚠️ 2026-09-10 实测修正**：`Optional[Literal['cn','id']]` 在 Pydantic v2 下被包进 `anyOf`，
> 顶层**没有** `enum` 键——写 `p['schema']['enum']` 会 `KeyError`。上面的断言已按实际形状书写
> （`anyOf` 缺失时回落顶层 `enum` 的兼容分支）。这是**计划文本缺陷**，与代码无关：
> `Literal` 写法本身正确，422 校验由函数签名标注保证，**不要**为迁就 OpenAPI 的呈现形状去改代码。

- [ ] **Step 6: Commit（amend 到 Task 6 的提交）**

```bash
git log --oneline -1        # 必须输出 a38ea6f feat(geocoding): ...（Task 6 的提交）
```
**若 HEAD 不是 `a38ea6f`（例如控制方在此期间提交了文档），不要 amend，改用普通 `git commit`**——这是 Task 5 那次 amend 事故的防范。

```bash
git add backend/app/api/tracks.py backend/app/services/track_service.py backend/tests/test_nominatim_region.py
git commit --amend --no-edit
```

**不改判定（记录，勿动）**

| 审查项 | 判定 | 理由 |
|---|---|---|
| Minor #3 三语循环内任一请求异常 → 整点数据全丢 | 不改 | **非本 Task 引入**（旧实现 en 失败同样全丢，审查者实测一致）。改它会改变 cn 失败路径行为，破坏「cn 路径零回归」的验收基线；当前「整点失败 → 不写 → 下次重试」不会留下半截数据，是安全的 |
| Minor #5 多出 `town_id` 键 | 不改 | 实测不入库（`track_service` 只取 4 个键）、`TrackPoint` 无 `town`/`town_id` 列、无撞车；与旧实现同样不写 town 系列 |
| Minor #6 三次 reverse 串行 | 不改 | 长轨迹主导开销是每点固定 `sleep(0.2)`，请求数非瓶颈；如要提速应先动 sleep 与并发 |
| Minor #7 告警措辞对 Google 不准确 | 不改 | 本 Task 计划即限定 Nominatim；Google provider 的印尼语支持属后续任务（`GoogleGeocoding._request` 已带 `language` 参数，改动很小） |
| 范围外：`live_recording_service` 实时填充用两参调用 | 记录 | 实时记录过程的即时填充恒 cn 行为，且不写 `point.region`/`*_id`。**可接受的绕行**：记录结束后用 PATCH `/tracks/{id}` 把 `track.region` 改为 `'id'`，再跑一次 fill-geocoding（`region` 缺省 → 回读轨迹 region）即可正确填充。**Task 14 要点须记录此项**（实时记录界面的地区选择是后续工作，Task 7/12 均不含 `live_recording_service.py`） |

---

### Task 6 fix loop 2（复审发现：`isascii()` 兜底零覆盖，2026-09-10）

复审结论：fix loop 三处改动**均可靠**（变异 A/B/C/D/F 精准打红，`Literal` 经有效认证实测确为 422、`isascii()` 五个边界场景行为正确、git 结构为 3 文件标准 amend 形态）。唯一 Important：**变异 E** —— 删掉 `track_service.py` 的 `or zh_province.isascii()` 后**全量 46 passed 全绿**，本次唯一裸奔的改动。

**不采用**复审者给的「伪 session 驱动整个 `fill_geocoding_info`」方案（桩 `async_session_maker` + `_get_geocoding_service`，约 40-60 行）：它强耦合内部结构（两次 `execute` 的返回顺序、`_filling_progress` 形态、`_get_geocoding_service` 签名），一次重构就碎，维护成本高于它守护的 1 行逻辑。**改为抽出纯函数 + 直接断言**：5 行测试换同样的保护，且不随内部结构漂移。

**Files:**
- Modify: `backend/app/services/track_service.py`（新增模块级纯函数 + 改回填调用点）
- Modify: `backend/tests/test_nominatim_region.py`（顶部 import + 追加一个测试类）

- [ ] **Step 1: 追加失败测试**

`tests/test_nominatim_region.py` 顶部 import 区加：

```python
from app.services.track_service import _should_backfill_province_zh
```

文件末尾追加：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && ../.venv/Scripts/python -m pytest tests/test_nominatim_region.py -q`
Expected: 收集期即 **ImportError: cannot import name '_should_backfill_province_zh'**（整个文件 0 用例可跑，属预期的红灯）

- [ ] **Step 3: 抽出纯函数并改调用点**

在 `track_service.py` 的**模块级区域**（import 之后、`class TrackService` 之前，列 0 缩进）加：

> ⚠️ **不要放到 `MERGE_GAP_THRESHOLD_SECONDS` 那里**——它是**类属性**、在 `class TrackService` **内部**（4 空格缩进），放进去会变成类方法而非模块级函数，Step 1 的 `from app.services.track_service import _should_backfill_province_zh` 会直接失败。（Task 6 fix loop 2 执行时实测发现此描述有误，此处已修正。）

```python
def _should_backfill_province_zh(zh_province: str, id_province: str) -> bool:
    """印尼省级中文名是否需要回填

    Nominatim 对无中译的省份返回本地名或英文名（zh 请求可能拿到 'Jawa Barat'
    或 'West Java'），此时用 38 省译名表按印尼语名回填中文。
    """
    if not id_province:
        return False
    return not zh_province or zh_province == id_province or zh_province.isascii()
```

回填调用点（**实测 L655-662**，语义锚：`if region == 'id':` 内的 `zh_province = info.get('province', '')` 起）改为：

```python
                            if region == 'id':
                                zh_province = info.get('province', '')
                                id_province = info.get('province_id', '')
                                if _should_backfill_province_zh(zh_province, id_province):
                                    from app.gpxutil_wrapper.indonesia import get_indonesia_province_zh
                                    zh = get_indonesia_province_zh(id_province)
                                    if zh:
                                        point.province = zh
```

**行为必须与现状逐字等价**——`if zh:` 守卫**必须保留**（查表失败时不清空已有中文，复审已实测该场景）。此步是纯粹的结构提取，**不得**顺手改判定条件或加新分支。

- [ ] **Step 4: 跑测试**

Run: `cd backend && ../.venv/Scripts/python -m pytest tests/ -q`
Expected: **48 passed**（原 46 + 新增 2）

- [ ] **Step 5: 变异自检（必做，报告里附证据）**

1. 临时把 `return not zh_province or zh_province == id_province or zh_province.isascii()`
   改成 `return not zh_province or zh_province == id_province`（即去掉本次兜底）
2. 跑 `../.venv/Scripts/python -m pytest tests/test_nominatim_region.py -q`
   → **必须红**（`test_should_backfill` 的 `'West Java'` 断言失败）
3. 还原该行，再跑一次确认全绿，并用 `git diff --stat` 证明工作区只剩计划列出的两个文件的预期改动

- [ ] **Step 6: Commit（amend 到 `7588cef`）**

```bash
git log --oneline -1        # 必须输出 7588cef feat(geocoding): ...（Task 6 + fix loop 的提交）
```
**若 HEAD 不是 `7588cef`（例如控制方提交了文档），不要 amend，改用普通 `git commit`。**

```bash
git add backend/app/services/track_service.py backend/tests/test_nominatim_region.py
git commit --amend --no-edit
```

**只 add 这两个文件**——工作区仍有控制方未提交的计划文档改动，**不要** `git add -A` / `git add docs/`。

**本轮不改（复审 Minor，仅记录）**

| 复审项 | 判定 | 理由 |
|---|---|---|
| C2：只删 `region == 'cn' and` 半边门控 → 未红 | 不改 | 要触发的现实条件极苛刻（id 侧 `province_en` 恰为中国省英文名**且** ref 形如 `S<纯数字>`），印尼数据不会同时满足。加固需把 fixture 的 `en.level4` 改成 `'Jiangsu'`，牺牲 fixture 真实性换一个不可达分支的覆盖——YAGNI |
| 假 client 的 `KeyError` 被宽 `except` 吞 → 失败信息不指向真因 | 不改 | 纯可读性；A 变异已证实仍会红，拦截能力不受影响 |
| 既有 `road_name_en == road_name` 置空逻辑无覆盖 | 不改 | 该行为在 Task 6 diff 中是上下文行而非新增，属既有代码，超出本 fix loop 范围 |

---

### Task 7: 上传/创建/修改链路的 region 贯通（Form、create_* 签名、5 处批量插入、详情响应）

> **⚠️ 行号基准（2026-09-10 实测；`track_service.py` 会随每个任务持续漂移）**
> 下表数值为 Task 6 **首轮**完成时点；其后 Task 6 fix loop 2 又在 L19 前插入 11 行纯函数，故 **表中数值一律 +11**。更重要的是：**不要按数字跳转**——每个锚点都请用左列语义锚点（函数名 / 字段名 / 注释文本）grep 定位后再改，行号只用于理解相对结构。
> 本节原有的行号基于 Task 6 之前；Task 6 在该文件 L503 之后插入了 region 解析与分派代码，**L503 之后的所有锚点整体后移约 41 行**。以下为实测行号，**请以此表 + 语义锚点（函数名/字段名/注释文本）定位，正文中的旧行号仅作参考**：
>
> | 锚点 | 实测行号 |
> |---|---|
> | `create_from_gpx` 定义 / `Track()` / `insert_values` / 尾部 fill | L271 / L410 / L432 / L479 |
> | `create_from_csv` 定义 / `Track()` / `insert_values` / 尾部 fill | L2593 / L2812 / L2834 / L2881 |
> | `_create_from_csv_project_format` 定义 / `Track()` / `insert_values` | L2888 / L3102 / L3124 |
> | `create_from_kml` 定义 / `Track()` / `insert_values` / 尾部 fill | L3179 / L3383 / L3405 / L3452 |
> | `create_from_xlsx` 定义 | L3459 |
> | `merge_tracks` 定义 / `Track()` / `insert_values` | L3892 / L3921 / L3944 |
> | unified 列表 `'original_crs': track.original_crs,` / 虚拟实时项 `'original_crs': 'wgs84',` | L967 / L1005 |
> | `fill_geocoding_info` 定义 | L503 |
> | `_create_from_csv_project_format(` 调用点（在 `create_from_csv` / `create_from_xlsx` 内，**已实测**） | L2661 / L3529 |
>
> `tracks.py` 的行号未受 Task 6 影响（已实测吻合：`upload_track` L39、四个创建调用 L110/L131/L144/L175、第二个 KML 调用 L196）。

**Files:**
- Modify: `backend/app/api/tracks.py`（upload Form + 详情手工 dict + 点接口 dict + 各 create 调用传 region）
- Test: `backend/tests/test_region_propagation.py`（新建；Task 7 执行时补的回归测试，13 个用例覆盖 region 在 Form→create_*→Track()→批量插入→各响应序列化点的贯通。**规格审查判定它不在原 Files 清单内但内容全部落在 Task 7 明列的字段与行为上**，故登记为 Task 7 的正式产物）
- Modify: `backend/app/api/shared.py`（Step 5b：公开分享页 TrackPointResponse 构造补字段）
- Modify: `backend/app/services/track_service.py`（create_from_gpx/csv/xlsx/kml 签名与 Track() 构造、5 处批量插入、merge_tracks、gpx/csv/kml 尾部 fill 调用）
- 说明：PATCH `/tracks/{id}`（update）无需改动——`track_service.update` 是通用 `setattr`（L673-687），Task 3 已给 `TrackUpdate` 加 `region` 字段，前端传即生效。

region 语义：`track.region` 是新建点默认；行级 CSV region（Task 9）会逐点覆盖。

- [ ] **Step 1: `tracks.py` upload 端点加 region Form 并校验**

签名区（L38-48）加 `region: str = Form("cn")`，文件类型校验后加：

```python
    if region not in ('cn', 'id'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的地区，可选值: cn, id",
        )
```

四个 create 调用加 `region=region`：
- `create_from_gpx(...)`（L110-120 调用块）末尾加 `region=region,`
- `create_from_csv(...)`（L131-141 调用块）末尾加 `region=region,`
- `create_from_xlsx(...)`（L144-151 调用块）末尾加 `region=region,`
- `create_from_kml(...)` 两处（KMZ L175-185、KML L196-206）末尾各加 `region=region,`

- [ ] **Step 2: `track_service.py` create_from_gpx / create_from_csv / create_from_kml 签名加 region**

三个方法签名末尾加参数（`fill_geocoding: bool = False,` 后）：

```python
        region: str = 'cn',  # 地区: cn=中国, id=印尼（新点的默认 region）
```

`create_from_xlsx` 签名同样加 `region: str = 'cn'`。

各方法内 Track() 构造（gpx **L410** / csv **L2812** / kml **L3383** / xlsx 走 project 格式 **L3102**）加一行 `region=region,`。project 格式（`_create_from_csv_project_format`）签名加 `region: str = 'cn'` 并在 `create_from_xlsx` 与 `create_from_csv` 的 project 分支调用处透传：
- `create_from_csv` 的 project 分支调用（原文 L2618-2622；**按 +41 换算约 L2659-2663，未逐一实测——以 `_create_from_csv_project_format(` 的调用点为语义锚 grep 定位**）改为 `return await self._create_from_csv_project_format(db, user, filename, rows, name, description, region)`；签名按位置序加 region 参数
- `create_from_xlsx` 的调用（原文 L3488-3490；**同样按 +41 换算约 L3529-3531**）改为 `return await self._create_from_csv_project_format(db, user, filename, rows, name, description, region)`

- [ ] **Step 3: gpx/csv/kml 尾部 fill_geocoding 调用加 region**

gpx 尾部（**L479**，位于 Task 6 插入点之前故未偏移）、csv 尾部（**L2881**）、kml 尾部（**L3452**）三处：

```python
            task = asyncio.create_task(
                self.fill_geocoding_info(db, track_obj.id, user.id, region=region)
            )
```

- [ ] **Step 4: 5 处批量插入的 insert_values 加键**

每处 dict 在 `"road_name_en": ...` 后加一行（project 格式在 road_name_en 后、created_by 前；merge 在 road_name_en 后、memo 前）：

**① create_from_gpx（实测 `insert_values` 起点 L432；在 `"road_name_en"` 行后插入）** —— point_data 无 region 键，全部用轨迹 region：

```python
                "region": region,
```

**② create_from_csv GPS Logger（实测 `insert_values` 起点 L2834）**：

```python
                "region": region,
```

**③ _create_from_csv_project_format（insert_values 实测 L3124）** —— **本步只注入轨迹默认 `region`**：行级 `region` 列解析与 `*_id` 别名解析**统一由 Task 9 一次实现**（避免同一个 dict 改两遍）。本步**不改** `point_data` 构造：

```python
                "region": region,
```

**④ create_from_kml（实测 `insert_values` 起点 L3405）**：

```python
                "region": region,
```

**⑤ merge_tracks（实测 `insert_values` 起点 L3944）** —— 点级数据复制：

```python
                "province_id": point.province_id,
                "city_id": point.city_id,
                "district_id": point.district_id,
                "road_name_id": point.road_name_id,
                "region": point.region or 'cn',
```

merge 的 Track() 构造（实测 L3921）加一行——首段源轨迹的 region 作为默认：

```python
            region=plan['tracks'][0].region or 'cn',
```

（plan['tracks'][0] 为第一个源轨迹对象，已在 _build_merge_plan 中加载。注意 merge 产物点级 region 已被逐点复制，track.region 仅作默认/回退值。）

- [ ] **Step 5: 轨迹手工构造 dict 补 region（`tracks.py` 两处）**

① `GET /tracks/{id}`（`tracks.py` L420-446 的 `response_data`）——在 `"original_crs": track.original_crs,` 后加：

```python
        "region": track.region or 'cn',
```

② **海报公开端点 `get_track_public`**（实测 `app/api/tracks.py:1047` 的 `response_data`，同为手工构造、同样有 `"original_crs": track.original_crs,`）——同样在该行后加**完全相同的一行**：

```python
        "region": track.region or 'cn',
```

> ⚠️ ② 是 **Task 7 执行时发现的计划遗漏**（原计划全篇未提及该端点）。两处漏传的后果相同：schema 里 `region` 带默认值 `'cn'`，漏传不报错、被静默掩盖 → 印尼轨迹的**海报生成**与公开分享会拿到 `region='cn'`，渲染中国式图标与中文回退文本。
>
> 执行时请顺带 grep 全 `app/api/` 下的手工 dict 构造（`"original_crs": track.`），确认没有第三处漏网再收工——这是根因层面的查全，不是只补这一个点。
>
> `live_recordings` detail 与列表页走 `TrackResponse.model_validate(track)` 自动携带，无需处理。

- [ ] **Step 5b: 其余点序列化处补多语言/region 字段（Task 3 质量审查发现的「字段已宣告、生产者未填充」缺口）**

新加的点级字段是本类中唯一带默认值的（其余地名/道路字段无默认），漏传不报错、被默认值静默掩盖 → 公开分享页与轨迹点接口对印尼轨迹会返回 `region='cn'` 并丢失印尼语名称。以下 4 处必须补：

① `backend/app/api/shared.py`（L48-73，`TrackPointResponse(...)` 逐字段构造，公开分享页唯一构造点）——在 `road_name_en=p.road_name_en,` 后加：

```python
            province_id=p.province_id,
            city_id=p.city_id,
            district_id=p.district_id,
            road_name_id=p.road_name_id,
            region=p.region or 'cn',
```

② `backend/app/api/tracks.py`（`GET /tracks/{id}/points` 端点 L676-705 的点 dict，含全部地名/道路字段）——在 `"road_name_en": point.road_name_en,` 后加：

```python
            "province_id": point.province_id,
            "city_id": point.city_id,
            "district_id": point.district_id,
            "road_name_id": point.road_name_id,
            "region": point.region or 'cn',
```

③ `backend/app/services/track_service.py` unified 列表 item dict（原文 L920-946，**实测 `'original_crs': track.original_crs,` 在 L967**）——在该行后加：

```python
                'region': track.region or 'cn',
```

④ 同文件虚拟实时项 dict（原文 L958 起，无关联轨迹的录制；**实测 `'original_crs': 'wgs84',` 在 L1005**）——在该行后加：

```python
                    'region': 'cn',
```

> 不加的处：`tracks.py` download 端点（约 L1104）的点 dict 不含任何地名/道路字段（只有坐标/索引/时间），与既有字段集一致，**不补**。

- [ ] **Step 6: 语法检查 + grep 核对全部 create/fill 调用**

Run: `cd backend && ../.venv/Scripts/python -c "import app.api.tracks; import app.api.shared; import app.services.track_service; print('ok')"`
然后 grep 核对 `fill_geocoding_info(`：本步做完后应命中 **5 处** —— ① `track_service.py` 的方法定义（实测 L517）；② `app/api/tracks.py` 的 `POST /tracks/{id}/fill-geocoding` 端点调用（Task 6 所加，已带 `region=region`）；③④⑤ 本 Task Step 3 刚加参数的 gpx / csv / kml 三处创建尾部。**若仍只有一两处，说明 Step 3 没改到位**。

> ⚠️ **本节原有描述有误（Task 7 执行时实测修正）**：曾写「② 是 `live_recording_service.py` 的调用」——该文件**根本不调用** `fill_geocoding_info`，它走自己的内联地理编码（`live_recording_service.py:435-459`，`geo_service.get_point_info(lat, lon)` 两参调用，不写 `*_id` 也不写 `point.region`）。5 处的实际成分如上，**数字 5 不变**。
Expected: ok

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/tracks.py backend/app/api/shared.py backend/app/services/track_service.py backend/tests/test_region_propagation.py
git commit -m "feat(upload): 上传/创建/合并链路贯通 region（Form 参数、批量插入注入点级region）

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 7 fix loop（质量审查发现：响应侧字段与 API 上传分支零覆盖，2026-09-10）

质量审用 9 组变异确认：**5 处 insert 注入点全部有守卫**（M1/M2/M3/M6 各自可精确归因到具体用例），薄弱环节集中在**响应侧字段**与 **API 上传分支**——M4a/M4b/M5a/M5b 四组改动生产代码后 13 个用例**全绿**。另有 1 处位置参数透传的未来失败模式。本轮修 5 处。

> **关键背景（决定本轮为什么值得修）**：这 5 处 `insert_values` 都是「循环内同一个字面量」生成的**等键 dict 列表**，删掉某个键 = 整批少一列 → 该列被 INSERT 省略 → 模型 `default='cn'`（`models/track.py:104`）静默生效、**不抛任何异常**。这一层**没有「响亮失败」模式**，测试守卫是唯一防线。

- [ ] **Step 1: I1 —— 4 个 `*_id` 字段的取值守卫（`tests/test_region_propagation.py`）**

变异证据：删掉 `shared.py` 的 4 行 `*_id` 或 `tracks.py` 点 dict 的 4 行，13 个用例**全绿**。根因是测试全程 `fill_geocoding=False`，落库 `*_id` 恒为 `None`，而 schema 里它们是 `Optional[str] = None` → 漏传被默认值掩盖。更糟的是现有断言**只看键在不在、不看值从哪来**，所以「传错来源」（如 `province_id=p.city_id`）同样拦不住。

新用例：create 之后用 ORM 赋**四个互不相同**的哨兵值，再断言取值：

```python
class TestMultilingualFieldPassthrough:
    """4 个 *_id 字段的取值守卫（质量审 I1：此前只断言键、不断言值来源）"""

    async def test_id_fields_reach_all_responses(self, ...):
        pt = (await _track_points(db, track.id))[0]
        # 四个值必须互不相同，否则「传错来源」仍会绿
        pt.province_id, pt.city_id, pt.district_id, pt.road_name_id = 'PID', 'CID', 'DID', 'RID'
        await db.commit()

        pts = await tracks.get_track_points(track.id, db=db, current_user=user)
        assert (pts[0]['province_id'], pts[0]['city_id']) == ('PID', 'CID')
        # ... 四个字段逐一断言；再对 shared 公开页断言一次
```

**2 处消费者都要覆盖**：`GET /tracks/{id}/points` 的 dict、`shared.py` 的公开分享页（`TrackPointResponse`）。

> ⚠️ **本节原有描述有误（fix loop 执行时实测修正）**：曾写「**三处**消费者，含 `GET /tracks/{id}` 详情」并给出 `detail['points'][0]['province_id']` 的示例——**该示例在本代码库无法成立**。实测 `list(TrackResponse.model_fields)` 里既无 `points` 也无任何 `*_id`（详情是**轨迹级**响应，不携带点级字段），照抄会 `KeyError`。全库响应侧消费 `*_id` 的生产者**只有 2 处**：`app/api/shared.py` 与 `app/api/tracks.py` 的点端点 dict（`app/api/road_signs.py` 的同名字段是盾牌接口的**入参**，与点序列化无关）。

- [ ] **Step 2: I2 —— 五个上传分支 + Form 默认值（同文件）**

变异证据：删掉 `tracks.py` xlsx 分支或 KMZ 分支的 `region=region,` → 13 个用例**全绿**（只有 GPX 分支被测过）。另外 `region: str = Form("cn")` 的默认值若被误改为 `Form("id")` **无任何测试变红**（现有 `test_default_is_cn` 测的是 **service 层**默认值，不是 Form 默认值）——那会导致**所有既有客户端上传的轨迹被静默标成 id**。

改法：把 `test_region_passthrough` 参数化，复用文件里已有的 `_csv_project()` / `_xlsx()` / `_kml()` 内容，各配一个**扩展名正确**的 `UploadFile`；kmz 用 `zipfile` 把 `_kml()` 打包（若成本确实过高，可显式标注「kmz 不测」，但**不要**静默跳过）。再加一个用例钉死 Form 默认值：

```python
    async def test_upload_without_region_defaults_to_cn(self, ...):
        # 请求里不带 region 字段 —— 钉住 Form("cn") 默认值
        ...
        assert track.region == 'cn'
```

- [ ] **Step 3: I3 —— 两处位置参数改关键字（`track_service.py`）**

两处 `_create_from_csv_project_format(` 调用点（分别在 `create_from_csv` 与 `create_from_xlsx` 内）目前以 7 个**位置参数**透传 region。危险的不是少传（会 TypeError 响亮失败），而是**将来在 `description` 与 `region` 之间插入一个带默认值的形参**（如 `original_crs: str = 'wgs84'`）→ 7 个实参填满前 7 个形参，`region` 悄悄退回 `'cn'` 且不报错。改法：两处最后那个位置实参改成 `region=region`。

- [ ] **Step 4: M3 —— `TrackUpdate.region` 收紧（`app/schemas/track.py`）**

`TrackUpdate.region` 是 `Optional[str] = Field(None, ...)`，`track_service.py` 的 update 直接 `setattr` → `PATCH /tracks/{id}` 可写入**任意字符串**。Task 7 把 PATCH 的 region 接到了「新建点的默认 region」上，这个口子因此从「存着不用的字段」变成可达。用户的 PATCH 是信任边界，收紧：

```python
    region: Optional[str] = Field(None, pattern="^(cn|id)$", description="地区: cn=中国, id=印尼")
```

> 这也是 **M1 不修**的理由：`Literal` 只是类型注解、**运行时完全不校验**，把 5 处 `str` 换成别名不产生任何实际防护；真正的收口是这条 schema 校验。

- [ ] **Step 5: M6 —— 让 merge 的 region 语义真正被钉住（测试）**

`test_merge_keeps_per_point_region` 里 `a`（8 点）**既是第一个入参、又是最早轨迹**，所以即使实现取的是 `track_ids[0]`，断言照样通过——它没有钉住注释声称的「start_time 较早者」。改：倒转入参顺序传 `[b.id, a.id]`，断言 `merged.region == 'id'` 仍成立。一行成本，语义才真正被固定。

- [ ] **Step 6: 验证、变异自检与提交**

Run: `cd backend && ../.venv/Scripts/python -m pytest tests/ -q`
Expected: 全绿（用例数会因 Step 1/2 增加；先记下改动前的数字以便对比）

**强制变异自检**（复现质量审的发现，证明新守卫真的拦得住——这是本轮的核心验收点）：
1. 删掉 `shared.py` 的 4 行 `*_id` → 必须**红**（改动前为全绿）
2. 删掉 `tracks.py` xlsx 分支的 `region=region,` → 必须**红**
3. 把 `Form("cn")` 改成 `Form("id")` → 必须**红**
4. 每次还原后给出 `sha256sum` 一致、或 `git status --short` 干净的证据

提交：先 `git log --oneline -1` 确认 HEAD 是否仍是 Task 7 的提交；是则 `--amend --no-edit`，否则普通 commit。**只 add 实际改动的文件**，禁止 `git add -A` / `git add docs/`。

#### fix loop 2（复审残余：merge 侧 `*_id` 复制仍零覆盖 + 测试全局副作用）

复审独立重做 8 组变异（V1–V8）全部见红、确认 fix loop 1 的五处修复到位且无越界。仅剩两条：

- [ ] **Step 1（R1）：钉住 merge 的 `*_id` 复制（`tests/test_region_propagation.py`）**

`merge_tracks` 的 `insert_values` 逐点复制 4 个 `*_id`，但**没有任何用例断言 merge 产物的 `*_id` 取值**——现有 `test_merge_keeps_per_point_region` 只断言 `merged.region` 与逐点 `region`，而 `TestMultilingualFieldPassthrough` 的断言全在**消费端**（点接口 / 分享页）。所以把 `"province_id": point.province_id` 改成 `point.city_id` 对全部用例**全绿**。这正是 Task 10 的 `collect_names` 直读的字段，写错会静默污染多语 tooltip。

改法：在 `test_merge_keeps_per_point_region` 里、**合并之前**给 a / b 两轨的点各赋**互不相同**的 `*_id`（如 `'A1'..'A4'` / `'B1'..'B4'`），合并后断言这些值随点迁移到 merge 产物。这同时把「merge 只复制这几列」这一事实钉死。

- [ ] **Step 2（R2）：收窄测试的全局副作用（同文件）**

`test_upload_without_region_form_defaults_to_cn` 的 `finally: app.dependency_overrides.clear()` 清空的是**全局**覆盖表。今天安全（其他用例都不用 override），但将来任何并行/集成用例一旦设置 override，就会在跑过这条之后被静默摘掉，产生极难定位的假失败。改为只摘自己设的两个键：

```python
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
```

（用实际的依赖函数名；`pop` 不存在时返回 `None`，无副作用。）

- [ ] **Step 3：验证与提交**

Run: `cd backend && ../.venv/Scripts/python -m pytest tests/ -q`
Expected: 全绿（用例数不变，本轮只加断言）。

**变异自检（证明 R1 的新断言真的拦得住）**：把 merge 的 `"province_id": point.province_id` 改成 `point.city_id` → 必须**红**（改动前为全绿）→ 还原并给 `sha256sum` 一致或 `git diff` 为空的证据。

- [ ] **Step 4（R1 补强）：把同轨点序错位也封上**

**首轮执行已完成**（`2a6de1c`，变异自检证据完整：变异前/还原后 `sha256` 一致、变异期 `1 failed` 且失败信息正是被复制错的 `province_id`）。但 implementer 上报一条真实残余：**同轨内点序错位仍零覆盖**——同一轨的两个点共享同一组 `*_id`（`'A1'..'A4'`），所以「merge 把 point[1] 的 ids 复制给了 point[0]」这类**点位错位**不会变红；逐点 region 断言同样拦不住（同轨两点 region 相同）。而「批量逐点复制时取错点」正是 R1 存在的理由，故判定**值得补**。

改法（**用集合比较，避免引入「同轨内点序」这一脆弱前提**）：赋值时把点位序号编进值里，断言时比较**排序后的元组列表**（顺序已由上面的 `[p.region ...]` 断言钉住，此处只需保证多集合正确）：

```python
                id_fields = ('province_id', 'city_id', 'district_id', 'road_name_id')
                for track, prefix in ((a, 'A'), (b, 'B')):
                    for i, pt in enumerate(await _track_points(db, track.id), start=1):
                        for n, field in enumerate(id_fields, start=1):
                            setattr(pt, field, f'{prefix}{i}{n}')
                await db.commit()
                ...
                got = sorted(tuple(getattr(p, f) for f in id_fields) for p in points)
                assert got == sorted([
                    ('A11', 'A12', 'A13', 'A14'), ('A21', 'A22', 'A23', 'A24'),
                    ('B11', 'B12', 'B13', 'B14'), ('B21', 'B22', 'B23', 'B24'),
                ])
```

同轨两点值此时互不相同 → 点位错位必红。**变异自检**：把 merge 的 `"province_id": point.province_id` 改成对同轨第二个点取错（如把 `point` 换成循环外的固定点）不易构造时，退而验证：手工交换某轨两点的赋值顺序后断言仍绿（证明集合比较不依赖点序），再用 V-型变异确认字段错位仍红。

提交：确认 `git log --oneline -1` 是否仍是 Task 7 的提交；是则 `--amend --no-edit`，否则普通 commit（**若 HEAD 已是 Task 8 的提交，必须用普通 commit，不要 amend 到 Task 8 上**）。

> ⚠️ **执行前必须确认 Task 8 已提交完毕**（`git log --oneline -1` 不是 Task 8 的在途状态、`git status` 无他人的未完成改动）——两个 agent 并发提交会抢 git 索引。

#### 本轮不改（含理由，防止后续任务误改）

| 项 | 判定 | 理由 |
|---|---|---|
| M1 服务层 `region: str` → `Literal` 别名 | 不改 | `Literal` 运行时零校验，纯注解；真收口在 Step 4 的 schema `pattern` |
| M2 同一参数两种错误码（400 手工 vs 422 自动） | 不改 | 手工 400 是规格逐字给定；改成 `Literal` 会把既有 400 契约变 422，前端若按 400 分支处理会受损 |
| M4 点 dict 里 `region` 打断了 `road_number`/`road_name` 相邻 | 不改 | 规格明确要求插在 `road_name_en` 之后；纯可读性，无行为差异 |
| M5 点接口 dict 缺 `memo`（`tracks.py` 点端点） | 不改 | 既有问题、非本轮引入；该端点未声明 `response_model`，补 `memo` 会改变响应契约，属独立议题 |
| R3 `TrackUpdate` 允许显式 `null` → 写 NOT NULL 列 500 | 不改 | 与 `name`（`models/track.py` 同为 NOT NULL）**完全同形**，是 PATCH 端点的既有通病、**非 region 回归**；只为 region 打补丁会造成同族字段行为不一致，要收口应在端点/服务层统一 `model_dump(exclude_none=True)`，属独立议题 |
| R4 本提交用过 `amend`，旧哈希 `5f1935b` 已不在历史中 | 不改 | 已 grep `docs/` 与 `cc/`，无悬空引用（复审确认） |
| BOM 独占首行：`csv_lines = ["﻿", headers, ...]` 经 `"\n".join` 后导出 CSV 的首行是**只含 BOM 的空行**，表头落在第 2 行 | **已于 Task 9 修复** | **既有问题、非本计划引入**（`2ba3326` 之前即如此）。与本计划的多语言列改名无关；修它要动导出拼接结构（应把 BOM 并进首个字段而非独立元素），属独立议题。**已于 Task 9 修复**（见下「Task 9 的越界修复」）——修它不是因为顺手，而是因为**本计划要求的导出→导入闭环用例在未修时根本不可能通过**：BOM 独占首行会让 `DictReader` 的 `fieldnames` 变成空列表 `[]`，此后每行的键都是 `None`（实测 `[{None: ['index','province']}, ...]`），于是 `row.get("index")` 恒为 `None` → **静默匹配 0 个点、返回 `matched_by: none`，不报错**。 |

#### 交接提醒（Task 9 必读，已同步写入 Task 9 段落）

`_create_from_csv_project_format` 内的 `point_data` **当前不含 `region` 键**，所以 Step 4 注入的 `"region": region` 字面量今天是正确的。**Task 9 接行级 region 时这里必须改成 `point_data.get("region") or region`**，否则行级值会被轨迹默认值覆盖。

### Task 8: CSV/XLSX 导出使用新列名（region + `*_zh/_id/_en`）

**Files:**
- Modify: `backend/app/services/track_service.py`（export_points_to_csv L1806-1886、export_points_to_xlsx L1937-2013）
- Test: 无（表格结构变更由 Task 13 冒烟 + 导入闭环验证；后端当前无导出单测基建）

> **⚠️ 行号基准（2026-09-10 实测；`track_service.py` 会随每个任务持续漂移）**
> 下表数值为 Task 6 **首轮**完成时点；其后 Task 6 fix loop 2 又在 L19 前插入 11 行纯函数，故 **表中数值一律 +11**。更重要的是：**不要按数字跳转**——每个锚点都请用左列语义锚点（函数名 / 字段名 / 注释文本）grep 定位后再改，行号只用于理解相对结构。
>
> | 锚点（语义定位用） | 计划旧行号 | **实测行号** |
> |---|---|---|
> | `export_points_to_csv` 内 CSV 表头列表 `headers = [` | L1806-1815 | **L1847-1856** |
> | `export_points_to_csv` 内行值地理字段（`point.province or ""` … `getattr(point,'memo')`） | L1866-1875 | **L1907-1916** |
> | `export_points_to_xlsx` 内 XLSX 表头列表 `headers = [` | L1937-1946 | **L1978-1987** |
> | `export_points_to_xlsx` 内行值地理字段（`point.province` … `getattr(point,'memo')`） | L2003-2012 | **L2044-2053** |
>
> 统一偏移 **+41 行**（Task 6 在 `fill_geocoding_info` 内净增 41 行，全部位于这四个锚点之前）。
> 下文步骤已按实测行号书写；若前序任务又有改动，**以语义锚点（函数名 + 字段序列）为准，重新 grep 定位**。
> 注意：`headers = [` 在同一文件另有 L2519 / L3502 两处（导入侧），**不要改错**——只改 `export_points_to_csv`
> （函数 def 实测 L1809）与 `export_points_to_xlsx`（实测 L1935）内的那两处。

导出表头新格式（spec §3，坐标等既有列不重排，region 在 speed 之后）：

```
index, time_date, time_time, time_microsecond, elapsed_time,
longitude_wgs84, latitude_wgs84, longitude_gcj02, latitude_gcj02, longitude_bd09, latitude_bd09,
elevation, distance, course, speed,
region,
province_zh, province_id, province_en,
city_zh, city_id, city_en,
area_zh, area_id, area_en,
road_num, road_name_zh, road_name_id, road_name_en, memo
```

- [ ] **Step 1: CSV 表头与行值（export_points_to_csv）**

表头（实测 L1847-1856，即 `export_points_to_csv` 内的 `headers = [` 到 `]`）替换：

```python
        headers = [
            "index", "time_date", "time_time", "time_microsecond", "elapsed_time",
            "longitude_wgs84", "latitude_wgs84",
            "longitude_gcj02", "latitude_gcj02",
            "longitude_bd09", "latitude_bd09",
            "elevation", "distance", "course", "speed",
            "region",
            "province_zh", "province_id", "province_en",
            "city_zh", "city_id", "city_en",
            "area_zh", "area_id", "area_en",
            "road_num", "road_name_zh", "road_name_id", "road_name_en", "memo"
        ]
```

行值（实测 L1907-1916，即 `row = [` 列表内从 `point.province or ""` 到 `getattr(point, 'memo', None) or ""` 的 10 行）替换：

```python
                point.region or 'cn',
                point.province or "",
                point.province_id or "",
                point.province_en or "",
                point.city or "",
                point.city_id or "",
                point.city_en or "",
                point.district or "",
                point.district_id or "",
                point.district_en or "",
                point.road_number or "",
                point.road_name or "",
                point.road_name_id or "",
                point.road_name_en or "",
                getattr(point, 'memo', None) or "",
```

- [ ] **Step 2: XLSX 表头与行值（export_points_to_xlsx）**

表头（实测 L1978-1987）替换为与 CSV 相同的 30 列列表。行值（实测 L2044-2053，即 `row_data = [` 列表内从 `point.province` 到 `getattr(point, 'memo', None)` 的 10 行）替换为与 CSV 相同的字段序。

> 兜底值统一为 `'cn'`（**CSV 与 XLSX 两处一致**）：`region` 列为 `nullable=False, server_default='cn'`，从库中读出的点不会为 `None`，故兜底实际不可达；取 `'cn'` 而非 `''` 是因为它与列默认值同值，万一将来出现内存中未 flush 的点，导出的也是可被导入端识别为合法 region 的值，而非空串。（**此段早前版本称「为稳妥与 CSV 一致」而 CSV 写的是 `''`，理由与事实不符，已随两处统一为 `'cn'` 修正。**）

```python
                point.region or 'cn',
                point.province,
                point.province_id,
                point.province_en,
                point.city,
                point.city_id,
                point.city_en,
                point.district,
                point.district_id,
                point.district_en,
                point.road_number,
                point.road_name,
                point.road_name_id,
                point.road_name_en,
                getattr(point, 'memo', None),
```

- [ ] **Step 3: 语法检查**

Run: `cd backend && ../.venv/Scripts/python -c "import app.services.track_service; print('ok')"`
Expected: ok

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/track_service.py
git commit -m "feat(export): CSV/XLSX 导出新列名（region + province/city/area/road_name 三语言列）

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

#### 首轮执行后的处置（2026-09-10）

Task 8 首轮已提交（`2ba3326`，67 passed）。implementer 上报一条 DONE_WITH_CONCERNS：**Step 1 要求 CSV 写 `point.region or ""`、Step 2 要求 XLSX 写 `point.region or 'cn'`，同一提交里两处不一致，且 Step 2 给的理由（「为稳妥与 CSV 一致」）与事实相反**。implementer 按「计划是权威」照做并上报，判断正确。

处置：**不改实现方向，改为统一为 `'cn'`**——兜底在库侧不可达（列 `nullable=False, server_default='cn'`，迁移 016 已回填），但两处写不同值属于无谓的不一致，且 `''` 对导入端是无效 region。计划两处已同步改为 `point.region or 'cn'`；CSV 处的一行改动随本 Task 的审后修复一起提交。

---

### Task 9: 导入器：列名别名表 + 行级 region（import_points_from_file 与 create 路径）

**Files:**
- Modify: `backend/app/services/track_service.py`（`update_point_fields`、`has_area`/`has_road` 重算、`_create_from_csv_project_format` 地理字段与检测段、`point_data`、`insert_values`；GPS Logger 检测后 project 分支）
- Test: `backend/tests/test_import_multilanguage.py`（**新建，Step 6**）

> ⚠️ **为什么本 Task 必须有测试**（本段与下面那句「写错了测试不红就等于没写」是同一条理由）：别名表与行级 region 的全部失效模式都是**静默**的——别名查不到 = 该字段不更新（不报错）；`point_data`/`insert_values` 少一个键 = INSERT 省略该列 = 模型 `default` 生效（不报错）；`insert_values` 里的 `"region": region` 忘了改成 `point_data.get("region") or region` = 行级 region 被轨迹默认值整体覆盖（不报错）。**这三种错了都不会让任何既有用例变红，因为此前没有任何用例跑过导入路径。** 故本 Task 的测试不是「顺手补」，是这次改动的唯一防线。

> ⚠️ **Task 7 交接的必改点**：`_create_from_csv_project_format` 内的 `point_data` 字典**目前不含 `region` 键**，Task 7 注入的是 `"region": region` 这个字面量（当时正确）。**本 Task 接行级 region 时必须把它改成 `point_data.get("region") or region`**——否则行级解析出的 region 会被轨迹级默认值覆盖，行级功能静默失效（且因为列有默认值，不会报错）。
>
> 参考：质量审的变异测试已证实**这类「少一列」的写法不会抛异常**——`insert_values` 是等键 dict 列表，缺键 = INSERT 省略该列 = 模型 `default` 静默生效。**同样的静默性也适用于本 Task 的行级 region：写错了测试不红就等于没写。**

> **⚠️ 行号基准（2026-09-10 实测；`track_service.py` 会随每个任务持续漂移）**
> 下表数值为 Task 6 **首轮**完成时点；其后 Task 6 fix loop 2 又在 L19 前插入 11 行纯函数，故 **表中数值一律 +11**。更重要的是：**不要按数字跳转**——每个锚点都请用左列语义锚点（函数名 / 字段名 / 注释文本）grep 定位后再改，行号只用于理解相对结构。
>
> | 锚点（语义定位用） | 计划旧行号 | **实测行号** |
> |---|---|---|
> | `update_point_fields` 函数体（`def` 行 → `point.updated_by = user_id` 行） | L2377-2430 | **L2418-2471** |
> | `has_area` / `has_road` 重算（`any(... for p in points)`） | L2520-2535 | **L2562-2575** |
> | `_create_from_csv_project_format` 内地理字段硬编码读取（`# 解析地理信息` 注释起） | L2959-2968 | **L3000-3009** |
> | 同函数内检测段（`if province or city or ...: has_area_info = True`） | L2970-2974 | **L3011-3015** |
> | `point_data = {` 内地理字段（`'province': province,` → `'road_name_en': road_name_en,`） | L3036-3044 | **L3077-3085** |
> | `insert_values.append({` 内地理字段（`"province": point_data.get("province")` → `"road_name_en"`） | L3098-3106 | **L3139-3147** |
>
> 统一偏移 **+41 行**（Task 6 在 `fill_geocoding_info` 内净增 41 行，全部位于这些锚点之前）。
> 下文步骤已按实测行号书写；若前序任务又有改动，**以语义锚点（函数名 + 字段序列 + 注释文本）为准，重新 grep 定位**。
> 引用风格提示：现文件中 `update_point_fields` 与 `insert_values` 用**双引号**、`point_data` 与
> `_create_from_csv_project_format` 用**单引号**——两者都是既有风格，计划代码块的引号仅示意，照抄或因循原文皆可，不影响正确性。

别名表（列表常量，放 track_service.py 的**模块级区域**——`class TrackService` 之前、列 0 缩进；也可以就近放方法内——**推荐模块级**，两处使用）：

```python
# ========== CSV/XLSX 导入列名别名 ==========
# 新格式带语言后缀（province_zh/province_id/province_en）；样例与旧版 vibe 导出
# 无后缀列表示中文（province/city/area/road_name/road_name_en 等历史格式）。
# 解析顺序即优先级：语言后缀全显式的新列优先，其次旧列名。
_IMPORT_FIELD_ALIASES = {
    'province': ['province_zh', 'province'],
    'city': ['city_zh', 'city'],
    'district': ['area_zh', 'area'],
    'province_en': ['province_en'],
    'city_en': ['city_en'],
    'district_en': ['area_en'],
    'province_id': ['province_id'],
    'city_id': ['city_id'],
    'district_id': ['area_id'],
    'road_name': ['road_name_zh', 'road_name'],
    'road_name_en': ['road_name_en'],
    'road_name_id': ['road_name_id'],
    'road_num': ['road_num'],
    'memo': ['memo'],
    'region': ['region'],
}
```

- [ ] **Step 1: `update_point_fields` 改别名驱动（实测 L2418-2471 整体替换函数体）**

```python
        def update_point_fields(point: TrackPoint, row: dict, headers: set | list | None = None):
            """更新点的可编辑字段（多语言别名列名 + 行级 region）

            只要文件里某字段的任一别名列存在，就用其值（包括空值）覆盖数据库中的值；
            所有别名列都不存在时，才保留数据库中的原值。
            region 特殊：列存在但该行值为空 → 回退到轨迹级 region（track.region or 'cn'）；
            列完全不存在 → 不动该点 region。
            """
            def has_key(field: str) -> bool:
                """字段是否有任一别名列存在于文件中"""
                for alias in _IMPORT_FIELD_ALIASES.get(field, []):
                    if isinstance(row, dict):
                        if alias in row:
                            return True
                    else:
                        if headers and alias in headers:
                            return True
                return False

            def get_val(field: str) -> str | None:
                """取字段值：按别名优先级取第一个存在的列；无则 None"""
                for alias in _IMPORT_FIELD_ALIASES.get(field, []):
                    if isinstance(row, dict):
                        if alias in row:
                            val = row.get(alias)
                            return val.strip() if val else None
                    else:
                        if headers and alias in headers:
                            idx = headers.index(alias)
                            if idx < len(row):
                                val = row[idx]
                                return str(val).strip() if val else None
                return None

            # 行政区划信息：只要列存在就更新（含 *_id 印尼语列）
            if has_key('province'):
                point.province = get_val('province')
            if has_key('city'):
                point.city = get_val('city')
            if has_key('district'):
                point.district = get_val('district')
            if has_key('province_en'):
                point.province_en = get_val('province_en')
            if has_key('city_en'):
                point.city_en = get_val('city_en')
            if has_key('district_en'):
                point.district_en = get_val('district_en')
            if has_key('province_id'):
                point.province_id = get_val('province_id')
            if has_key('city_id'):
                point.city_id = get_val('city_id')
            if has_key('district_id'):
                point.district_id = get_val('district_id')

            # 道路信息：只要列存在就更新
            if has_key('road_num'):
                point.road_number = get_val('road_num')
            if has_key('road_name'):
                point.road_name = get_val('road_name')
            if has_key('road_name_en'):
                point.road_name_en = get_val('road_name_en')
            if has_key('road_name_id'):
                point.road_name_id = get_val('road_name_id')

            # 备注：只要列存在就更新
            if has_key('memo'):
                point.memo = get_val('memo')

            # region：行级地区（跨地区文件主通道）。列存在且值为空 → 用轨迹默认；
            # 值非法抛错终止导入（防误输入整段错区）。
            if has_key('region'):
                region_val = get_val('region')
                if region_val is None or region_val == '':
                    point.region = track.region or 'cn'
                elif region_val in ('cn', 'id'):
                    point.region = region_val
                else:
                    raise ValueError(
                        f"无效的地区值 '{region_val}'，可选值: cn, id")

            point.updated_by = user_id
```

注意：`track` 在 `update_point_fields` 闭包可见（函数定义在 import_points_from_file 方法体内，track 已在上文获取）。CSV 的 row 是 DictReader 行（dict）；XLSX 走 `row, headers` 列表分支——现有调用 `update_point_fields(point, row)`（CSV）与 `update_point_fields(point, row, headers)`（XLSX），签名已兼容。

- [ ] **Step 2: has_area/has_road 重算加 *_id 列（实测 L2562-2575）**

```python
        has_area = any(
            p.province or p.city or p.district or
            p.province_en or p.city_en or p.district_en or
            p.province_id or p.city_id or p.district_id
            for p in points
        )
        has_road = any(
            p.road_number or p.road_name or p.road_name_en or p.road_name_id
            for p in points
        )
```

- [ ] **Step 3: `_create_from_csv_project_format` 地理字段别名解析（实测 L3000-3009）**

将硬编码无后缀读取替换为别名 helper（模块级或方法级，与 Task 9 Step 1 复用同一函数不便——CSV dict 行读取逻辑不同（create 是整行解析为字段而非列存在语义）。create 路径按行全量建点，语义：列存在 → 值；不存在 → None。添加方法级小工具 `_row_aliased(row, field, default=None)`——直接按别名表顺序取第一个非空值（create 语义无需区分「列存在但空」与「无列」，最终值都是 None 或空）：

```python
            # 解析地理信息（别名：新格式 *_zh / *_id / *_en；旧格式无后缀=中文）
            province = (row.get('province_zh') or row.get('province') or '').strip() or None
            city = (row.get('city_zh') or row.get('city') or '').strip() or None
            district = (row.get('area_zh') or row.get('area') or '').strip() or None
            province_en = (row.get('province_en') or '').strip() or None
            city_en = (row.get('city_en') or '').strip() or None
            district_en = (row.get('area_en') or '').strip() or None
            province_id = (row.get('province_id') or '').strip() or None
            city_id = (row.get('city_id') or '').strip() or None
            district_id = (row.get('area_id') or '').strip() or None
            road_number = (row.get('road_num') or '').strip() or None
            road_name = (row.get('road_name_zh') or row.get('road_name') or '').strip() or None
            road_name_en = (row.get('road_name_en') or '').strip() or None
            road_name_id = (row.get('road_name_id') or '').strip() or None
            # 行级 region（可选）：非空须为 cn/id，空则用轨迹默认
            row_region = (row.get('region') or '').strip()
            if row_region and row_region not in ('cn', 'id'):
                raise ValueError(f"无效的地区值 '{row_region}'，可选值: cn, id")
            point_region = row_region or region
```

（`region` 为方法参数，Task 7 已加。）

- [ ] **Step 4: has_area/has_road 检测与 point_data/insert（project 格式内）**

检测段（实测 L3011-3015）替换：

```python
            if (province or city or district or province_en or city_en or district_en
                    or province_id or city_id or district_id):
                has_area_info = True
            if road_number or road_name or road_name_en or road_name_id:
                has_road_info = True
```

point_data dict（实测 L3077-3085）改为：

```python
                'province': province,
                'city': city,
                'district': district,
                'province_en': province_en,
                'city_en': city_en,
                'district_en': district_en,
                'province_id': province_id,
                'city_id': city_id,
                'district_id': district_id,
                'road_number': road_number,
                'road_name': road_name,
                'road_name_en': road_name_en,
                'road_name_id': road_name_id,
                'region': point_region,
```

insert_values（实测 L3139-3147）替换为：

```python
                "province": point_data.get("province"),
                "city": point_data.get("city"),
                "district": point_data.get("district"),
                "province_en": point_data.get("province_en"),
                "city_en": point_data.get("city_en"),
                "district_en": point_data.get("district_en"),
                "province_id": point_data.get("province_id"),
                "city_id": point_data.get("city_id"),
                "district_id": point_data.get("district_id"),
                "road_name": point_data.get("road_name"),
                "road_number": point_data.get("road_number"),
                "road_name_en": point_data.get("road_name_en"),
                "road_name_id": point_data.get("road_name_id"),
                "region": point_data.get("region") or region,
```

- [ ] **Step 5: 语法检查 + GPS Logger 分支确认**

Run: `cd backend && ../.venv/Scripts/python -c "import app.services.track_service; print('ok')"`
Expected: ok

同步确认：GPS Logger 格式（无 project 列）不读地理列 → 无需改动（Track() 与插入已由 Task 7 注入 region）。`create_from_xlsx` 走 `_create_from_csv_project_format` 自动获得别名/行级 region 能力（xlsx 表头与 CSV 一致的假定不变）。

- [ ] **Step 6: 闭环测试（新建 `backend/tests/test_import_multilanguage.py`）**

**推荐顺序**：先写本步骤的测试并确认它们**红**（此时别名表还不存在 → 新格式的 `*_zh`/`*_id`/`region` 列解析不到；行级 region 被轨迹默认值整体覆盖），再执行 Step 1-5，最后回到本步骤确认转绿。

复用 `tests/test_region_propagation.py` 里的 `workdir` fixture 与 `_db_env` 上下文（**不要用 `tmp_path`**——本机 `%TEMP%/pytest-of-Administrator` 不可访问，会直接 `PermissionError`）。建轨迹用现有的 `track_service.create_from_gpx(db, user, 'a.gpx', _gpx(8), 'a', region=...)` helper。

关键接口（已实测）：
- `await track_service.import_points_from_file(db, track_id, user_id, file_content: bytes, file_format='csv', match_mode='index')`
- `await track_service.export_points_to_csv(db, track_id, user_id) -> (filename, content: str)`
- CSV 导入走 `csv.DictReader`，且已 `decode('utf-8-sig')` → BOM 与首行空行不成问题

新格式表头常量（与 Task 8 导出的 30 列一致）：

```python
NEW_HEADERS = ("index,time_date,time_time,time_microsecond,elapsed_time,"
               "longitude_wgs84,latitude_wgs84,longitude_gcj02,latitude_gcj02,"
               "longitude_bd09,latitude_bd09,elevation,distance,course,speed,"
               "region,province_zh,province_id,province_en,city_zh,city_id,city_en,"
               "area_zh,area_id,area_en,road_num,road_name_zh,road_name_id,"
               "road_name_en,memo")
```

用例清单：
1. `test_new_format_all_columns_applied` —— 新格式两行（region 列分别 `id` / `cn`）；导入后逐点断言 `province/province_id/province_en`、`city*`、`area*`（注意落到模型的 `district*`）、`road_number/road_name/road_name_id/road_name_en`、`region` 全部等于文件值。
2. `test_row_region_overrides_track_default` —— **必须同时覆盖两条路径**（首轮执行时发现本节原描述有误，见下方「路径错配」）：
   - **导入路径**（`import_points_from_file`）：轨迹建成 `region='cn'`，文件 region 列写 `id` → 点 `region == 'id'`。这条钉的是 Step 1 `update_point_fields` 里的行级 region 分支。
   - **创建路径**（`create_from_csv(..., region='cn')`）：**Step 4 的 `"region": point_data.get("region") or region` 只在创建路径生效**，导入路径根本不经过它。若只测导入路径，把该行改成字面量 `region` 仍会全绿——即该行**没有防线**。故必须补创建路径断言。
   - 两条路径的字段断言应抽成共享 helper，避免重复，同时保证两条路径都被逐字段钉住。
3. `test_empty_region_falls_back_to_track` —— region 列**存在但值为空** → 点 region 取轨迹自身 region；另建一条跑**旧格式**（无 region 列）→ 点 region **保持原值不变**（不是被改成轨迹 region）。
4. `test_invalid_region_raises` —— region 列写 `sg` → `pytest.raises(ValueError)`。
5. `test_legacy_format_still_works` —— 旧格式表头（`index,province,city,area,road_num,road_name`，无后缀）→ 中文列照旧落库（回归守卫，防别名表把老文件读坏）。
6. `test_export_import_roundtrip` —— 建一条带全套多语言字段的轨迹 → `export_points_to_csv` 取 content → `content.encode('utf-8')` 直接喂回 `import_points_from_file`（喂给**另一条**轨迹）→ 断言目标点与源点字段一致。**这条把 Task 8 的 30 列导出与 Task 9 的别名表锁在一起**，是「导出→导入闭环」的直接验证（否则该闭环只剩 Task 13 的冒烟覆盖）。
7. `test_create_path_invalid_region_raises` —— **创建路径**的 `raise ValueError`（Step 3 的 `row_region` 校验）：`create_from_csv` 喂入 region 列写 `sg` 的文件 → `pytest.raises(ValueError)`。**这与用例 4 不是同一条分支**：用例 4 走 `import_points_from_file` → Step 1 的 region 分支；本条走 `create_from_csv` → Step 3 的 `row_region` 校验。删掉任一处校验，只有对应用例会红。
8. `test_create_path_id_only_sets_has_area_flag` —— **创建路径**的检测段（Step 4 的 `has_area_info`/`has_road_info`）：`create_from_csv` 喂入**只有 `*_id` 列有值、中文/英文列全空**的行 → 断言返回轨迹的 `has_area_info`（与 `has_road_info`）为真。**用例 1/2 的 `has_area` 断言走的是导入路径的重算（Step 2）；创建路径的检测段此前无任何断言**，删掉检测段里的 `*_id` 判断不会有任何用例变红。implementer 首轮自加的 `test_id_only_columns_set_has_area_flag` 覆盖的是**导入路径**那一份，本条补**创建路径**那一份，两者不可互替。

**变异自检（至少 2 项；每项给出「变异前 / 还原后 sha256 一致」或 `git diff` 为空的证据）**：
- 把 `insert_values` 的 `"region": point_data.get("region") or region` 改回 `"region": region` → 用例 2 **必须红**
- 把 `_IMPORT_FIELD_ALIASES` 里 `'district': ['area_zh', 'area']` 的 `'area_zh'` 删掉 → 用例 1 **必须红**（证明别名表真的被读取，而非碰巧同名命中）

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/track_service.py backend/tests/test_import_multilanguage.py
git commit -m "feat(import): CSV/XLSX 导入列名别名表（兼容三类格式）与行级 region 写入

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

#### 首轮执行后的处置（2026-09-10）

Task 9 首轮已提交（`1b0c90a`，2 files / 442 insertions / 61 deletions；全量 **74 passed** = 基线 67 + 新建 7 个用例）。三件事需要记录：

**1. 路径错配（本节原描述有误，已在上方 Step 6 用例 2 修正）**：Step 4 的 `"region": point_data.get("region") or region` **只在创建路径生效**，而本节原用例 2 描述的是**导入**路径（`import_points_from_file`）——导入路径的行级 region 由 Step 1 的 `update_point_fields` 处理，根本不经过 `insert_values`。implementer 按「不变红即等于该行无防线」补了创建路径分支，变异自检随即转红（变异期 1 failed）。**这与 Task 7「三处消费者」那次是同一类错误：凭印象分配守卫，未先确认哪条代码路径真正执行。**

**2. 越界修复（必要，非顺手）**：首轮 implementer 修了 `export_points_to_csv` 的 BOM 独占首行缺陷（**Task 8 的函数**）。经独立复现确认该缺陷真实且后果严重——旧写法下 `DictReader` 的 `fieldnames` 为 `[]`、每行键为 `None`，导入**静默匹配 0 个点**。也就是说本节要求的 `test_export_import_roundtrip` **在未修时不可能通过**，修它是完成本 Task 的前提而非扩大范围。**已同步更正上方「本轮不改」表与 Task 14 第 11 条**（原判「不改、记为已知问题」已作废）。

**3. 新发现未修（既有缺口）**：`_create_from_csv_project_format` **既不解析也不写入 `memo`** —— 走「创建」路径的 CSV/XLSX 会丢备注（导入路径正常）。不在本计划列出的 `insert_values` 字段清单内，属既有缺口，已在测试 helper 的文档串中标明。**是否补属独立议题**（补它要同时改 `point_data` 与 `insert_values` 两处，且与多语言无关）。**→ 此定性已被质量审推翻，见下条 F9。**

#### 质量审后的处置（2026-09-10）

质量审结论：**无严重缺陷**（无数据丢失/安全问题；`region` 只有入参或 `track.region or 'cn'` 两个来源，不会写 NULL；导入路径的 `ValueError` 在 `db.commit()` 之前抛出，会话关闭即回滚，无半写状态）。全量 **76 passed** 经实跑确认；别名表与 Task 8 导出的 30 列**逐列核对无遗漏**，旧格式 10 个历史列名全部仍可达；`region` 兜底值在导出/导入/创建/响应四处已统一 `'cn'`。判定 **修完可合**。以下为逐条裁决。

**采纳（9 项，交 fix loop 执行）**

| # | 问题 | 修法 |
|---|---|---|
| F1 | **创建路径完全绕过 `_IMPORT_FIELD_ALIASES`**（L3087-3099 是硬编码列名对），日后改表（加列/调优先级）只有导入侧生效 | 按本节 L3278 原提议补模块级 `_row_aliased(row, field)`（紧邻别名表），十三行改调用；并在 `_create_from_csv_project_format` docstring 写明两条路径的语义差异（见下「裁决说明」） |
| F2 | **`_build_merge_plan` 的 `has_area/has_road` 未同步加 `*_id`**，与紧邻注释「口径同 `import_points_from_file`」直接矛盾 | `track_service.py:3887-3894` 各补 `or p.province_id or p.city_id or p.district_id` 与 `or p.road_name_id`（共 2 行） |
| F3 | **XLSX 导入分支零覆盖**：`get_val` 的 `headers.index(alias)` 分支（L2498-2503）是本次重写的代码，而 `tests/` 里 `file_format` 只出现 `'csv'` | 新文件补一个 `file_format='xlsx'` 用例（openpyxl 写 `NEW_HEADERS` + 两行），复用 `_new_format_csv` 的字段值与 `_assert_full_fields` |
| F4 | **旧格式「无 region 列」断言无分辨力**（`test_import_multilanguage.py:262-270`：期望值恰等于轨迹自身默认值） | 让点值与轨迹值**不同**（建轨迹 `region='cn'` 后把点改成 `'id'`，或反之），使「一律写 `track.region`」这种错误必红 |
| F5 | `headers: set \| list \| None` 注解与实现不符（`.index` 对 set 抛 `AttributeError`；旧代码的 `list(headers)` 兜底本次被去掉） | 注解删去 `set`（无 set 调用者 —— 两处调用点传的是 dict 与 list，YAGNI） |
| F6 | region 白名单项目**已有** `REGION_VALUES`（`gpxutil_wrapper/indonesia.py:18`）却未被复用（**该常量此前无引用点，本次首次启用**——论据更正见本节末） | 本次新增的两处（`update_point_fields`、`_create_from_csv_project_format`）改用 `REGION_VALUES` |
| F7 | `pytest.raises(ValueError)` 未带 `match`，任意 `ValueError` 都能顶替 | 两处补 `match='无效的地区值'` |
| F8 | 创建路径 region 用例两行同值（`_new_format_csv(region0='id', region1='id')`），分辨力弱 | 改 `region1='cn'`；并补一条「`province_zh` 列**存在但为空** + 旧列 `province` 有值 → 创建路径取旧列值」钉住 F1 的语义 |
| F9 | **`memo` 在创建路径丢失**（走「创建」路径的 CSV/XLSX 丢备注） | `point_data` 与 `insert_values` 各加 1 行（`"memo": point_data.get("memo")`），并加创建路径的 memo 断言 |

**裁决说明**

- **F1 只统一来源，不改语义**：两条路径的取值语义本就不同——导入路径是「第一个**存在**的列，空值也算值」（**覆盖**语义：用户清空一列即期望清空），创建路径是「第一个**非空**的值」（**建点**语义：无既有值可覆盖）。质量审实测的分歧（表头 `province_zh` 空 + `province` 有值 → 导入 `province=None`、创建 `province='旧省'`）**予以保留**并写进 docstring。理由：该组合只在「新旧列混排」的文件里出现，而 Task 8 导出的 30 列**不含无后缀旧列**，故「导出 → 上传」闭环里不可达；强行统一反而会让「清空某列」的语义在创建路径失效。
- **F9 推翻了上条第 3 项的定性**。原判「既有缺口、与多语言无关、是否补属独立议题」在**事实层面**成立（base commit 同函数同样只有 docstring 提到 memo，非本次引入），但漏了两点：① 三处 docstring（`create_from_csv`、`_create_from_csv_project_format`、`create_from_xlsx`）至今**对外宣称支持 memo**，且导出（`export_points_to_csv` / `export_points_to_xlsx`）**确实写出 memo 列** —— 即「导出 → 上传」这条闭环会丢备注；② 本 Task 正在改的正是这两个 dict，补它是**各 1 行**。故改判为**补**：Task 8 建立的 30 列导出与上传链路的闭环完整性属本计划范围。

**不改（记录理由）**

| 项 | 判定 | 理由 |
|---|---|---|
| `fill_geocoding` 的 region 兜底（`track_service.py:569-571`）遇未知地区 `logger.warning` 后**静默按 `cn` 填充** | 不改 | 本 Task 未触及，且修它要先判断填充语义（拒绝，还是按点级 region 分流）；质量审认定它是六处白名单里**唯一会静默填出整段错区数据**的一处 → **记入 Task 14 已知限制**，不掩盖 |
| 测试 helper 第三份拷贝（`test_region_propagation.py` / `test_import_multilanguage.py` 逐字节相同，`test_indonesia_shield.py` 亦有 `workdir`） | 不在本 Task 抽 | 抽 `conftest.py` 要改动既有测试文件、扩大本 Task 的审查面；**改列为 Task 10 的 Step 0**（单独 commit），届时正好出现第 4 份 |

#### Fix loop 落地（2026-09-10，`dcd6223` + `d9c4e46`）

九项全部落地，**78 passed**（基线 76，**+2**；协调者独立复跑确认），5 项变异自检全部转红并成功还原。实现者**主动多改了第三个文件** `tests/test_region_propagation.py`（+4 行，在 `test_merge_keeps_per_point_region` 上补 F2 的 `has_area_info` 断言）——该文件的源点恰好只有 `*_id` 有值，正是 F2 的输入形态，比在新文件里重建一套 merge fixture 更省；**采纳**。F9 选了「memo 加进 `_assert_full_fields` 并同步改 docstring」这条，消除了「docstring 说不含 memo、实际却含」的矛盾；`_import` 的签名放宽（支持 bytes 以跑 xlsx）不影响既有调用点。

**F1 的等价性结论被更正（重要）**：本清单原写「行为必须逐字保持不变」，**实测不成立**。实现者用穷举把旧表达式与 `_row_aliased` 对拍（取值域 `{键缺失, None, '', '   ', ' X ', 'X'}`，双别名键全组合，共 **204** 组）：**196 组一致，8 组不一致**，且 8 组是同一形状——

> `{'province_zh': '   ', 'province': 'X'}` → 旧写法 `None`，新写法 `'X'`
>
> 原因：旧写法 `(row.get(a) or row.get(b) or '').strip() or None` 按**原始**真值短路（`'   '` 为真 → 短路 → strip 后为空 → `None`）；`_row_aliased` 按 **strip 后**是否为空决定是否继续下一个别名。（8 组 = 4 个双别名键 [`province`/`city`/`district`/`road_name`] × 2 组取值。）

**裁决：保留新行为**——空白单元格不应遮蔽旧列的真值，且新写法更贴合 `_row_aliased` 自己声明的「第一个非空」语义。**但已用测试钉住**（`d9c4e46`）：`_bare_province_csv()` 增加第 4 行「`province_zh` 只有空白 + `province` 有值」→ 断言创建路径取 `'旧省四'`；变异（判空改回原始真值短路）实测该用例**变红**，还原后 sha256 一致。钉它的理由：这个子情形正是「两条路径语义分歧」的核心（**空白算不算值**），不钉住就可能被日后「恢复等价」的人静默改回去。

**关于「先红后绿」的诚实说明（记录为后续 Task 的范例）**：F3/F4/F7/F8 的断言在实现前**就是绿的**（它们钉的是既有正确行为，不是本次修出来的），只有 F9（memo）与 F2（merge 口径）真的先红。实现者没有把这四条说成 TDD 红过，而是用变异自检证明其**非空转**（M1/M4/M5）——这是正确且必要的补证方式。

#### ⚠️ 变异自检的还原验收标准（本窗口实测教训，**Task 10-13 通用**）

协调者本轮亲手踩了一次，务必写进每个 Task 的自检要求：

> **还原的验收标准是 `git status --porcelain` 为空（或 shell 侧 `sha256sum` 一致），不是脚本自己算的哈希。**
>
> 原因：Python 的 `Path.read_text()` / `write_text()` 会做**换行符翻译**（读时 `\r\n`→`\n`；Windows 上写时 `\n`→`\r\n`）。一次「读-改-写」往返会把整个文件的换行符翻掉——实测把 4134 行的 `track_service.py` 从 LF 变成 CRLF，`git diff` 显示 **4134 增 / 4134 删**。而**若 sha256 也是用同样的 `read_text` 算的，它对这个错误是瞎的**：两侧都归一化了，哈希当然一致。
>
> 正确做法二选一：① 变异脚本用 `read_bytes()`/`write_bytes()`（二进制，无翻译）或 `open(..., newline='')`；② 还原后用 **`git status --porcelain` / `git diff`** 或 **shell 的 `sha256sum`**（读原始字节）验收。**git 是唯一的地面真相。**
>
> 本 window 的修复 loop（`dcd6223`）用的是 ②（`sha256sum -c`），方法本身没问题；踩坑的是协调者自写的 Python 脚本。
>
> **③ 还原的范围必须精确到变异本身**（协调者本轮第二次踩坑：`e29f11d` 提交里少了 `track_service.py`，靠 `6a72e31` 补回）：`git checkout -- <file>` 还原的是**整个文件**，会把同文件里**尚未提交**的正常改动一并抹掉。危险之处在于它伪装成成功——`git status --porcelain` 确实「干净」了，但「干净」有两种成因（变异被还原 ✓ / 连正常改动一起被还原 ✗），**单看 status 分不出来**。正确做法二选一：**先提交正常改动再做变异**，或提交前用 `git diff --stat` 核对文件数与改动条数是否与预期一致（事故就是靠这一步发现的）。

#### 复审后的收尾（2026-09-10，`e29f11d` + `6a72e31`）

fix loop 的独立复审结论：**九项逐条按规格落地、diff 面严格限于规格内、无附带损害、无越界改动/遗留调试代码**，工作树干净，**78 passed** 复现一致 → **Task 9 可关闭**。复审另提 4 条次要项，处置如下（均为 1 行级，由协调者就地修，未再派 subagent）：

| # | 项 | 处置 |
|---|---|---|
| 次要 1 | `test_import_multilanguage.py` 导入侧断言 `[None, None]`：点由 `create_from_gpx` 建出时 `province` **本就是 `None`** → 「覆盖为空」与「整段没动」不可区分 | **修**：导入前给两点设哨兵 `'哨兵'`，再断言 `[None, None]`。变异（`point.province = get_val('province')` 改 `pass`）实测目标用例变红（连带 5 个同族用例） |
| 次要 2 | `track_service.py:2488` 的 `row: dict` 对 xlsx 调用点（传 tuple）是错误注解；函数体内 `has_key`/`get_val` 均已按 `isinstance(row, dict)` 分派 | **修**：改 `row: dict \| tuple` |
| 次要 3 | 同文件 ① 分支「列存在、值为空」的**既有**弱断言（不在本次 diff 内）：轨迹与点都是 `'id'` → 「整段没动」也会绿，**与 F4 完全同型** | **修**：轨迹改 `region='cn'`、两点改 `'id'`，期望 `{'cn'}`。变异（删掉落回轨迹的赋值）实测变红 |
| 次要 4 | 计划为 F6 写的论据「`svg_gen.py` 已在用」不准确；`_create_from_csv_project_format` docstring 对「空白串」的落点描述不精确 | **修**：见下两条更正 |

**F6 论据更正**：`REGION_VALUES` 在本 Task 之前**无任何引用点**——实测 `svg_gen.py:987/993` 用的是 `REGION_CN`/`REGION_ID` 两个**标量**，不是这个元组。结论不变（常量本就定义在 `indonesia.py`，是 region 白名单的既定归属地，复用它优于新写字面量），但「已有代码在用」这半句不成立：本条是**首次启用**该常量。

**docstring 措辞更正**：原文「导入路径则把 province 覆盖为 None」严格说只对**空串**成立——`get_val` 的 `val.strip() if val else None` 真值判断在 strip **之前**，故仅含空白的串（`'   '`）落为 `''` 而非 `None`（这正是上文 F1 对拍里那 8 组差异的成因）。已改为「空串落为 None，仅含空白的串落为 `''`，两者都不是『保留原值』」，使两条路径在「空白串」这一格的真实落点可直接读出。

次要 1/3 属于**同一类缺陷**（期望值恰等于原值 → 断言无分辨力），与刚修完的 F4 同型；**不留作后续**的理由与本 Task 的性质有关：该文件的 docstring 自称「静默失效的唯一防线」，把已知无分辨力的断言留在防线里，等于把刚付过学费的坑重新埋回去。

---

### Task 10: 区域树：共享聚合重构 + region 分组 + names + 显示回退链

**Files:**
- Create: `backend/tests/conftest.py`（**Step 0**）
- Modify: `backend/tests/test_region_propagation.py`、`backend/tests/test_import_multilanguage.py`（**Step 0**：删除本地副本、改为 import）
- Modify: `backend/app/services/track_service.py`（`get_region_tree`、`get_region_tree_no_auth` → 提取共享 `_build_region_tree`）
- Test: `backend/tests/test_region_tree.py`（**新建，Step 5**）

- [ ] **Step 0: 抽 `backend/tests/conftest.py`（独立 commit，在动 `track_service.py` 之前）**

本 Task 的 Step 5 用例 5 需要入库（走两个公共入口），若照旧就地复制就是**第 4 份** helper 拷贝：`test_region_propagation.py` 与 `test_import_multilanguage.py` 的 `workdir`/`_db_env`/`_track_points`/`_gpx` 经质量审**逐字节比对完全相同**，`test_indonesia_shield.py` 另有一份 `workdir`；而 `tests/` 下**没有 conftest.py**。`_db_env` 一改（加模型、换 `expire_on_commit`）要同步改四处，**漏改一处是静默的**（该文件的测试会用上缺模型的 schema）——此前收窄 `dependency_overrides` 清理范围时就已付出过一次代价。

**前提已核（不必再试）**：`backend/tests/` 下**没有 `__init__.py`**，仓库里也**没有任何 pytest 配置文件**（无 `pytest.ini`/`pyproject.toml`/`setup.cfg`/`tox.ini`）。故 pytest 用 prepend 导入模式，把测试文件所在目录 `backend/tests` 插入 `sys.path` → `from conftest import _db_env, _track_points, _gpx` 可用（现有的 `from app.models import ...` 也正是靠从 `backend/` 跑 `python -m pytest` 时 cwd 在 `sys.path` 上）。

**做法（最小 diff）**：新建 `backend/tests/conftest.py`，把 `workdir`（fixture）与 `_db_env`/`_track_points`/`_gpx`（普通函数）**逐字搬过去，保持原名**（`_` 前缀不影响 pytest 注入 fixture，也无需改名——改名会波及三份拷贝里的全部引用点，得不偿失）。两个测试文件里**删掉已搬走的定义**，各加一行 `from conftest import _db_env, _track_points, _gpx`（`workdir` 是 fixture，自动注入，无需 import）。

**验收**：`cd backend && ../.venv/Scripts/python -m pytest tests/ -q` 与改动前**用例数与通过数完全一致**（当前基线 **76 passed**）；两个既有测试文件除「删定义 + 加一行 import」外**无其他改动**（用 `git diff` 自查，`_db_env` 的正文必须是**逐字未改**的搬运）。

> ⚠️ **Step 0 是独立 commit**（`test: 抽 tests/conftest.py 收编共享 fixture`），与 Step 1-6 分开，便于单独回滚与审查。若实测 `from conftest import ...` 不可用，**跳过 Step 0 并在报告中说明**，用例 5 就地复制 helper 即可（它是「可选但推荐」的一条）——不要为抽 helper 把 Task 10 主体搭进去。

> **⚠️ 行号基准（2026-09-10 第二次实测，Task 9 完成后；`track_service.py` 会随每个任务持续漂移）**
> **不要按数字跳转**——每个锚点都请用左列语义锚点（函数名 / 字段名 / 注释文本）grep 定位后再改，行号只用于理解相对结构。
>
> | 锚点（语义定位用） | 计划旧行号 | **本次实测行号** |
> |---|---|---|
> | `_aggregate_node_stats`（`def` 行 → 函数末） | L1269 | **L1349-1394** |
> | `get_region_tree`（`async def` 行至函数末） | L1316-1557 | **L1396-1637** |
> | `get_region_tree` 内权限检查段（`track = await self.get_by_id(...)` → `return {'regions': [], ...}`） | L1338-1341 | **L1418-1421** |
> | `get_region_tree_no_auth`（`async def` 行至函数末） | L1559-1766 | **L1639-1846** |
>
> 早前版本此表记的是「Task 6 首轮行号 + 统一 +11 / +41 偏移」——**那套偏移量已随 Task 7/8/9 的改动失效**，本次按语义锚点重新实测并整表覆盖。
> 下文步骤文字中若还留有更早的行号，**一律以上表与语义锚点为准**；Step 1 / Step 5 内已写入的 L1396-1637、L1639-1846、L1386 等均为本次实测值。
- Modify: `backend/app/schemas/track.py`（RegionNode——Task 3 已加字段；无需再动）

行为（spec §6）：
- 分组键 = (region, 各级显示文本)；同文本不同 region 的分开成组（深港：cn/香港节点分开——注意香港点 region 会是什么？跨地区文件行级 region 显式 'cn'/'id'。香港本身不在值域内（cn|id）——深港示例中港段实际由用户选 region（cn）→ 同 province '未知区域'?? 不深究：**region 并入键 + names 记录语言** 即 spec 要求，示例是解释性的）
- 显示文本：每级文本在组内取回退链 zh → id → en → 哨兵（名称文本与 原 point.xxx 非空检测一致）。实际上层是「取各级原始字段并组成 key」：省文本 = point.province or point.province_id or point.province_en or '未知区域'——但显示 prefer zh。回退链 zh→id→en 与现状「province 为空视为未知」兼容：cn 点只有 province 非空 → 原样。id 点 province 可能空（未回填）而 province_id 有 → 新行为显示 province_id。OK
- 节点 names = 组内**创建时首见**的三个语言非空代表（zh/id/en）；组内语言中途变化不拆组（决策 5）
- stats 去重键 = (region, name)

实现：因两函数（1316/1559）除权限检查与 create_node 微小差异外全同（no_auth 每点额外 own point_count++ 后又被 _aggregate_node_stats 覆盖 → 与 auth 等价），提取单一共享方法。Task 步骤：

- [ ] **Step 1: 读 `_aggregate_node_stats` 与两个待合并的公共方法，**先验证二者确实等价**

先 Read `_aggregate_node_stats`（锚点：`def _aggregate_node_stats`）确认行为（已核：聚合基于 own_* 字段并写回 distance/point_count）。

**然后是本 Task 最关键的一步**：完整读 `get_region_tree` 与 `get_region_tree_no_auth` 两个函数体，**逐段比对**，确认它们除「权限检查」与「no_auth 每点额外的 own_point_count++（随后被 `_aggregate_node_stats` 覆盖）」之外**确实没有其他差异**。

> ⚠️ 本计划断言二者等价，但**这个断言本身没有证据**。把两个函数合并成一个共享实现，前提就是这个等价性成立——若不成立，合并会**静默改变其中一个端点**的行为，而两个端点分别服务于「登录用户看自己轨迹」与「公开分享页」，受影响面不同且不会被任何既有测试发现。
>
> **请把逐段比对结果写进报告**（哪些段落相同、哪些不同、不同处是否可安全归一）。若发现**实质差异**（不只是那两处），**停下来报告，不要合并**。Step 4 的冒烟验证是对等价性的**实证复核**，不是替代品——它只在开发库有轨迹、且该轨迹同时能被两个入口读到时才有效。
>
> **已核（协调者独立逐段比对，2026-09-10；实现者请复核，而非重新从零发现）**：逐段比对了 `get_region_tree`（L1396-1637）与 `get_region_tree_no_auth`（L1639-1846），**差异只有两处**，均可安全归一：
> 1. **权限检查**：auth L1418-1421（`track = await self.get_by_id(db, track_id, user_id)` → 早退空结构 `{'regions': [], 'stats': {...0}}`）；no_auth 无此段。→ **保留在薄壳里，不进共享方法**。
> 2. **`point_count` 多加一次**：no_auth L1803-1804 比 auth L1595 多一行 `active_node['point_count'] += 1`。→ **无害**：`_aggregate_node_stats`（L1386）对每个节点**无条件赋值** `node['point_count'] = total_points`，而 `total_points` 从 `own_point_count` 起算（L1355），该行在 `for node in root_nodes:` 后处理时被覆盖。**共享方法只保留 `own_point_count += 1`**，与 auth 版一致。
>
> 其余逐段一致，无差异：SQL（同 `select` / `and_(is_valid == True)` / `order_by(time, created_at)`）、空点集早退（两函数都返回同一空结构）、`create_node` 结构（差异仅在中文字面注释）、省/市/区/路四级建节点与各层 `end_index` 收尾、`start_time`/`end_time` 更新、`await self.spatial_service.distance(...)` 距离累加、末尾 `_aggregate_node_stats` 与 `stats` 四键组装。
> **若你比对出上表之外的差异，以你的发现为准并立刻停下来报告** —— 上表是协调者的比对结论，不是你复核的替代品。
>
> **一处需知晓的行为变化（不是等价性问题，是回退链的必然结果）**：`province` 现在可能取自 `province_id`/`province_en`，而市节点的判定 `city_key = city if city and city != province else None` 仍拿 city 与它比较。故当「省的中文为空、且其 id/en 值恰与 city 值相同」时会**不再生成市级节点**（雅加达这类省市同名的情形）。这与既有「city == province 则并入省级」的意图一致，且原实现下该点因 `province` 落到哨兵 `'未知区域'` 本就会另建市节点——属**可接受的行为变化，无需额外处理**；若实现者认为必须保序，请停下来报告。

- [ ] **Step 2: 新增共享方法 `_build_region_tree(self, points)`（放 get_region_tree 之前）**

整体（提取 auth 版逻辑 + region/names/回退链；供两个公共方法共用）。**必须是 `async def`**：距离计算沿用现状的 `await self.spatial_service.distance(...)` 且留在点循环内（本方法同步化会把 await 挤到循环外、语义变化）：

```python
    async def _build_region_tree(self, points: list[TrackPoint]) -> tuple[list[dict], dict]:
        """按时间顺序构建区域树（两个公共入口共用）

        分组键含 (region, 文本)：同文本不同地区分开成组；节点显示文本按
        回退链 zh → id → en → 哨兵；names 记录组内首见的各语言非空值。
        返回 (root_nodes, stats)。
        """
        root_nodes = []
        node_counter = [0]

        # 统计各级区域数量（去重键 = (region, 显示文本)）
        province_set = set()
        city_set = set()
        district_set = set()
        road_set = set()

        def fallback_text(*values) -> str:
            """回退链 zh → id → en → 哨兵：取第一个非空（哨兵在值空时兜底）"""
            for v in values:
                if v:
                    return v
            return '未知区域'

        def create_node(name: str, node_type: str, road_number: str = None,
                        names: Optional[dict] = None, region: str = 'cn') -> dict:
            """创建一个新节点（names 为各语言代表文本，非空才出现）"""
            node_counter[0] += 1
            return {
                'id': f"node_{node_counter[0]}",
                'name': name,
                'type': node_type,
                'road_number': road_number,
                'names': names or {},
                'region': region,
                'own_distance': 0.0,
                'distance': 0.0,
                'own_point_count': 0,
                'point_count': 0,
                'start_time': None,
                'end_time': None,
                'start_index': -1,
                'end_index': -1,
                'children': [],
            }

        def collect_names(point: TrackPoint, level: str) -> dict:
            """取点在本级展示的语言代表值（非空才入 names）

            `level` ∈ {'province','city','district','road'} —— **必须按节点层级取对应字段**。
            （早前版本用 `is_road: bool` 只有「道路 / 非道路」两分支，导致市节点与区节点
            拿到的是**省**的三语名；`names` 是 Task 12 前端 tooltip 的数据源，
            会把省名显示成市名/区名，且冒烟验证发现不了。已修正为按层级取。）

            按 zh → id → en 顺序**对值去重**：Nominatim 无译文时各语言常返回同一个
            本地名（如 zh 与 id 都是 'Jawa Timur'），不去重会让 tooltip 显示
            「Jawa Timur / Jawa Timur」、也让前端「单语言不出 tooltip」判定失效。
            """
            candidates = {
                'province': (('zh', point.province), ('id', point.province_id),
                             ('en', point.province_en)),
                'city': (('zh', point.city), ('id', point.city_id),
                         ('en', point.city_en)),
                'district': (('zh', point.district), ('id', point.district_id),
                             ('en', point.district_en)),
                'road': (('zh', point.road_name), ('id', point.road_name_id),
                         ('en', point.road_name_en)),
            }[level]
            names = {}
            for key, value in candidates:
                if value and value not in names.values():
                    names[key] = value
            return names

        # 当前活跃的节点路径（(region, 显示文本, 节点)）
        current_province = None
        current_city = None
        current_district = None
        current_road = None
        prev_point = None

        for time_idx, point in enumerate(points):
            region = point.region or 'cn'
            province = fallback_text(point.province, point.province_id, point.province_en)
            city = point.city or point.city_id or point.city_en  # 可为空
            district = point.district or point.district_id or point.district_en  # 可为空
            road_name = point.road_name or point.road_name_id or point.road_name_en
            road_number = point.road_number

            # 统计各级区域（排除"未知区域"和重复名称；键含 region 防跨地区串并）
            if province != '未知区域': province_set.add((region, province))
            if city and city != province and city != '未知区域': city_set.add((region, city))
            if district and district != city and district != '未知区域': district_set.add((region, district))
            if road_name and road_name != '未知区域': road_set.add((region, road_name))

            # 检查是否需要创建新的省级节点（键 = (region, 文本)）
            if current_province is None or current_province[0] != (region, province):
                # 先结束所有下层节点的索引范围
                if current_road is not None and prev_point is not None:
                    current_road[1]['end_index'] = time_idx - 1
                if current_district is not None and prev_point is not None:
                    current_district[1]['end_index'] = time_idx - 1
                if current_city is not None and prev_point is not None:
                    current_city[1]['end_index'] = time_idx - 1
                # 结束旧省级节点的索引范围
                if current_province is not None and prev_point is not None:
                    current_province[1]['end_index'] = time_idx - 1
                # 创建新省级节点并设置起始索引
                new_province = create_node(
                    province, 'province',
                    names=collect_names(point, 'province'), region=region)
                new_province['start_index'] = time_idx
                root_nodes.append(new_province)
                current_province = ((region, province), new_province)
                current_city = None
                current_district = None
                current_road = None

            province_node = current_province[1]

            # 检查是否需要创建新的市级节点
            city_key = city if city and city != province else None
            if city_key and (current_city is None or current_city[0] != ((region, city_key))):
                # 先结束所有下层节点的索引范围
                if current_road is not None and prev_point is not None:
                    current_road[1]['end_index'] = time_idx - 1
                if current_district is not None and prev_point is not None:
                    current_district[1]['end_index'] = time_idx - 1
                # 结束旧市级节点的索引范围
                if current_city is not None and prev_point is not None:
                    current_city[1]['end_index'] = time_idx - 1
                # 创建新市级节点并设置起始索引
                new_city = create_node(
                    city_key, 'city',
                    names=collect_names(point, 'city'), region=region)
                new_city['start_index'] = time_idx
                province_node['children'].append(new_city)
                current_city = ((region, city_key), new_city)
                current_district = None
                current_road = None
            elif not city_key and current_city is not None:
                # city 为空但之前有市级节点，需要重置
                if current_road is not None and prev_point is not None:
                    current_road[1]['end_index'] = time_idx - 1
                if current_district is not None and prev_point is not None:
                    current_district[1]['end_index'] = time_idx - 1
                if prev_point is not None:
                    current_city[1]['end_index'] = time_idx - 1
                current_city = None
                current_district = None
                current_road = None

            city_node = current_city[1] if current_city else province_node

            # 检查是否需要创建新的区级节点
            district_key = district if district and district != city_key else None
            if district_key and (current_district is None or current_district[0] != ((region, district_key))):
                if current_road is not None and prev_point is not None:
                    current_road[1]['end_index'] = time_idx - 1
                if current_district is not None and prev_point is not None:
                    current_district[1]['end_index'] = time_idx - 1
                new_district = create_node(
                    district_key, 'district',
                    names=collect_names(point, 'district'), region=region)
                new_district['start_index'] = time_idx
                city_node['children'].append(new_district)
                current_district = ((region, district_key), new_district)
                current_road = None

            district_node = current_district[1] if current_district else city_node

            # 道路节点键 = (region, 名称, 编号)
            if road_name:
                road_key = ((region, road_name), road_number or '')
            else:
                road_name = '（无名）'
                road_key = ((region, road_name), road_number or '')

            if current_road is None or current_road[0] != road_key:
                if current_road is not None and prev_point is not None:
                    current_road[1]['end_index'] = time_idx - 1
                new_road = create_node(
                    road_name, 'road', road_number,
                    names=collect_names(point, 'road'), region=region)
                new_road['start_index'] = time_idx
                district_node['children'].append(new_road)
                current_road = (road_key, new_road)

            # 确定当前最低层级的活跃节点
            if current_road:
                active_node = current_road[1]
            elif current_district:
                active_node = current_district[1]
            elif current_city:
                active_node = current_city[1]
            else:
                active_node = province_node

            # 累加点数
            active_node['own_point_count'] += 1

            # 更新时间范围
            if point.time:
                if active_node['start_time'] is None or point.time < active_node['start_time']:
                    active_node['start_time'] = point.time
                if active_node['end_time'] is None or point.time > active_node['end_time']:
                    active_node['end_time'] = point.time

            # 距离由外层循环计算（原实现逐点 await distance，见 Step 3 说明）
            prev_point = point

        # 设置所有活跃节点的结束索引（使用最后的时间索引）
        last_time_idx = len(points) - 1
        if current_road is not None:
            current_road[1]['end_index'] = last_time_idx
        if current_district is not None:
            current_district[1]['end_index'] = last_time_idx
        if current_city is not None:
            current_city[1]['end_index'] = last_time_idx
        if current_province is not None:
            current_province[1]['end_index'] = last_time_idx

        # 后处理：聚合统计信息，让上级包含下级
        for node in root_nodes:
            self._aggregate_node_stats(node)

        return root_nodes, {
            'province': len(province_set),
            'city': len(city_set),
            'district': len(district_set),
            'road': len(road_set),
        }
```

> 距离计算：原实现在点循环内 `await self.spatial_service.distance(...)`（异步）。把共享构建做成同步方法会把 await 留在循环外。**执行器注意**：`_build_region_tree` 需要是 **async**（距离计算需 await），循环内 active_node['own_distance'] += distance 保留在循环内 await 计算（与现状一致）。即本方法改为 `async def _build_region_tree(self, points)`，循环内距离段原样保留：

```python
            # 计算距离
            if prev_point:
                distance = await self.spatial_service.distance(
                    prev_point.latitude_wgs84, prev_point.longitude_wgs84,
                    point.latitude_wgs84, point.longitude_wgs84
                )
                active_node['own_distance'] += distance
```

（上面 Step 2 代码中的「距离由外层循环计算」注释改为保留该 await 段。以**最终文件行为与现状一致**为准：构建函数 async，内部含原距离计算段。）

- [ ] **Step 3: 两公共方法改薄壳**

`get_region_tree`（实测 L1396-1637）保留权限检查（实测 L1418-1421 不变），其后主体替换为：

```python
        # 获取轨迹点（按时间排序，实时记录场景下 point_index 可能乱序）
        result = await db.execute(
            select(TrackPoint)
            .where(and_(TrackPoint.track_id == track_id, TrackPoint.is_valid == True))
            .order_by(TrackPoint.time, TrackPoint.created_at)
        )
        points = list(result.scalars().all())

        if not points:
            return {'regions': [], 'stats': {'province': 0, 'city': 0, 'district': 0, 'road': 0}}

        root_nodes, stats = await self._build_region_tree(points)
        return {'regions': root_nodes, 'stats': stats}
```

`get_region_tree_no_auth`（实测 L1639-1846）同样替换为薄壳（无权限检查）。删除原两函数内的重复构建体。

- [ ] **Step 4: 冒烟验证等价性（临时脚本，不入库）**

Run:
```bash
cd backend
../.venv/Scripts/python - <<'EOF'
import asyncio
from app.core.database import async_session_maker
from sqlalchemy import select
from app.models.track import Track
from app.services.track_service import track_service

async def main():
    async with async_session_maker() as db:
        t = (await db.execute(select(Track.id).where(Track.is_valid == True).limit(1))).scalar_one_or_none()
        if not t:
            print("no track"); return
        r1 = await track_service.get_region_tree(db, t.id, 1)
        r2 = await track_service.get_region_tree_no_auth(db, t.id)
        print("auth nodes:", len(r1["regions"]), "no_auth nodes:", len(r2["regions"]))
        print("auth stats:", r1["stats"], "no_auth stats:", r2["stats"])
        # 节点结构一致性：auth 首节点含 names/region 键
        if r1["regions"]:
            n = r1["regions"][0]
            print("first node keys ok:", all(k in n for k in ("name", "region", "names")))
asyncio.run(main())
EOF
```
Expected: 两入口节点数与 stats 一致（同轨迹）；首节点含 region/names 键。（若 get_region_tree 因 user_id 非 1 找不到轨迹返回空 → 用数据库实际第一个轨迹的 owner 替换 user_id，或选择共享轨迹 id。执行器以实际数据为准调整查询；若开发库为空则跳过本验证并注明。）

- [ ] **Step 5: 回归测试（新建 `backend/tests/test_region_tree.py`）**

**为什么必须有**：本 Task 的两类缺陷都**不会被冒烟验证发现**——(a) 节点 `names` 取错层级（市/区节点填了省名），冒烟只看「首节点含 region/names 键」，键在就通过；(b) 合并两函数时若等价性不成立，冒烟需要有「能被两个入口同时读到的轨迹」才会暴露。测试是唯一能真正钉住它们的东西。

**做法（前提已核，无需再确认）**：`_build_region_tree(points)` 的输入是**内存中的 `TrackPoint` 列表**，不依赖数据库；`spatial_service.distance` 的两个实现（`app/services/spatial/python_spatial.py:25-35` 与 `app/services/spatial/postgis_spatial.py:24-38`）**都是纯 Haversine、不查库**。故**直接构造 `TrackPoint(...)` 对象（不 add、不 commit）后 `await track_service._build_region_tree(points)`**，断言返回的 `(root_nodes, stats)` 即可——最省、最快，不需要 `workdir` fixture，也不需要建轨迹入库。

（构造时只需给出用例用到的字段：`latitude_wgs84` / `longitude_wgs84` / `time` / `region` / 各级 `province*`/`city*`/`district*`/`road_name*`/`road_number`。用例 5 需要走两个公共入口、必须入库，届时再用 `workdir` fixture；若嫌重可省略该条（计划已标「可选但推荐」）。）

用例清单：
1. `test_names_per_level` —— 构造一个点，**省/市/区/路四级的 zh、id、en 值两两不同**（如省 `P-zh/P-id/P-en`、市 `C-zh/C-id/C-en`…），断言省节点的 `names` 是省的三语值、市节点是市的三语值、区节点是区的三语值、道路节点是路的三语值。**这条直接钉住 `collect_names(point, level)` 的层级正确性**——把任一层的 `level` 参数写错就必红。
2. `test_names_dedup_same_value` —— 某级 zh 与 id 值相同（Nominatim 无译文时的常见情形）→ 断言 `names` 里该值**只出现一次**（`len(names.values()) == len(set(names.values()))`）。
3. `test_display_fallback_chain` —— 某级 zh 为空、id 有值 → 断言节点 `name` 取的是 id 值；zh/id 都空、en 有值 → 取 en 值。
4. `test_region_grouping` —— 两个点的各级文本**完全相同但 `region` 分别为 `cn` 与 `id`** → 断言生成**两个**省级根节点（键含 region，不跨地区并组），且各自 `region` 字段正确、`stats` 把二者分别计数。
5. `test_auth_no_auth_equivalent`（可选但推荐）—— 若有可入库的建轨迹路径：同一条轨迹分别经 `get_region_tree` 与 `get_region_tree_no_auth` → 断言两个返回的 `regions` 结构一致（节点数、各级 `name`/`region`/`point_count`/`distance` 一致）与 `stats` 相等。这是对「两函数确实等价」的**回归固化**，防将来又分叉。
6. `test_road_number_keying` —— 同名道路但 `road_number` 不同 → 断言生成两个道路节点（道路键含编号）。

**变异自检（至少 2 项；每项给出「变异前 / 还原后 sha256 一致」或 `git diff` 为空的证据）**：
- 把市节点的 `collect_names(point, 'city')` 改成 `collect_names(point, 'province')` → 用例 1 **必须红**
- 把分组键里的 region 去掉（如 `(region, province)` → `province`）→ 用例 4 **必须红**

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/track_service.py backend/tests/test_region_tree.py
git commit -m "feat(region-tree): 区域树按(region,文本)分组、节点携带 names/region，抽取共享构建

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

#### 实现与审查记录（2026-09-10，`e4d2505` + `2b6aa0a` + `02a6ebd`）

**Step 0 成功**（`e4d2505`）：`from conftest import ...` 实测可用（prepend 模式，`tests/` 在 `sys.path` 上），未走跳过分支；全量 78 → 78 passed。**已核实**：conftest 的四个定义块与 base 版两处副本 **sha256 逐字节相同**（`d2f6081d…f70097` 三份全等）。一处**有意的偏离**：两个测试文件除「删定义 + 加 import」外还删掉了因此不再使用的 8 个 import 行——审查者按标识符边界**独立计数**确认全部为 0 次代码引用（`Track` 的 4 次命中全是 docstring/注释/KML 字面量），判定为安全清理。

**Step 1 等价性——三重独立复核，结论一致**：实现者逐段比对两版 240 行确认差异只有计划所列两处；spec 审查者另用 `ast` 从 `7cd90bd` 抽出旧函数体、`exec` 成独立协程，配 FakeDB 与新实现跑同一批内存点，**9 个场景**（四级中文 / 省市同名 / city 重置分支 / 无名道路 / 省切换 / 区市同名 / 无时间 / 哨兵省 / zh 与 id·en 并存）**逐字段全等**；质量审再做**3000 组随机点序列**（region ∈ {cn, id, None}，四文本随意交叉）的内存内源码置换变异。差异全部落在计划已认可的回退链一类，**无第三类差异**。

**「防御性 region」的实证裁决（保留）**：质量审把市/区/道路三级键里的 region 去掉后跑 3000 组，**0 处差异**——证实那三处 region **在行为上不可观测**（归纳不变量：region 一变必然使省级键不等 → 新建省级节点 → `current_city/district/road` 全部置 None，故三个下层键的 region 分量恒等于当前 region）。**裁决：保留，不删也不补测试**——它的价值不是防御而是「四处键形状统一」，而统一本身值这一行；变异测不出来是它的定义使然，不是覆盖漏洞。

**测试**：新建 `backend/tests/test_region_tree.py`（6 用例，176 行），实现前 `6 failed` → 实现后 `6 passed`；全量 **78 → 84 passed**。用例 1-4、6 在实现前**红于 `AttributeError`/`KeyError`（API 不存在）而非逻辑红**，实现者如实说明并用 6 项变异（每项只让对应用例变红、其余 5 个保持绿）证明非空转；spec 审查者另做 11 项独立变异复核（7 项有效）。

**质量审结论**：**Ready to merge: Yes**，**无 Critical**；区域树代码总量 **452 行（243+209）→ 324 行**（235 行共享 + 40/31 行两薄壳），`track_service.py` 4135 → 4010 行。10 条 Important/Minor 中**修 7 留 3**：

| 修（`02a6ebd`） | 内容 |
|---|---|
| 薄壳死代码 | 删两处 `if not points:` 早退（`_build_region_tree([])` 已返回同形空结构，实测零行为变化）；**权限检查段的空结构返回保留**（语义不同） |
| `create_node` 静默默认 | `region: str = 'cn'` → `*, region: str`（必填**关键字**参数）。理由：仓库教条即「region 是唯一带默认值的字段、漏传被静默掩盖，故须逐个生产者守卫」，不该新开同类默认值。实现者**纠正了协调者的方案**：Python 不允许有默认值参数后跟无默认值参数（`def g(a, b=None, c)` 实测 `SyntaxError`），而 `region` 前有 `road_number=None`/`names=None`。加 `*` 后 4 个调用点**零改动**（本就用关键字传参），漏传立刻 `TypeError: missing 1 required keyword-only argument`；而「无默认值的位置参数」方案仍允许未来的 `create_node(name, 'road', road_number)` 把 `road_number` **静默**绑进 `region`（实测）——`*` 让这类错位在语法上不可能发生，**严格优于原要求**（理由的精确化见文末复审） |
| docstring 过宽 | 「组内**首见**」→「取**建点那一点**的非空语言值（按 zh → id → en 去重），组内后续点不补全缺失语言」（实现只传触发建点的那个 `point`） |
| 无名道路零断言 | 该分支本 Task 重写过却无断言（删掉 `road_name = '（无名）'` 重赋值不会被拦住，要到 API 层 `RegionNode.name: str` 收到 `None` 才炸）；补 3 条断言（`type`/`name`/`names`）+ 变异自检（删重赋值 → `assert None == '（无名）'` 红） |
| 用例 5 名义入库 | `expire_on_commit=False` 下 commit 后读到的是同一 identity map 的对象、**不经 DB 往返**；加 `db.expunge_all()` + 捕获 `track_id/user_id`（捕获是**防御性**的，非必需——见文末复审） |
| 冗余断言 | 删 `len(names.values()) == len(set(...))`（被紧随的 `names == {...}` 包含） |
| stats 语义 | 注释补「跨地区同文本计两次，前端展示为「N 省级」即 N 个省级条目」 |

**留 3 项的理由（既有债，非本次贡献）**：`node_counter = [0]`（原样搬运的既有风格，`nonlocal` 更直白但不在本次范围）、`city_key`/`district_key` 的命名与「比较处/赋值处各写一遍 `(region, x)`」、`test_indonesia_shield.py` 仍留自己那份 `workdir`（计划明确 Step 0 只收编逐字相同的两份）。**另有既有债一并记录、不阻塞**：253 行方法体与 5 处 `end_index` 收尾块（`git show` 中全是未改动的 context 行）、点查询谓词在全文件出现 11 次（文件级 codemod 议题）、`track_service.py` 4010 行。

**未采纳的一条建议**：质量审建议抽 `_load_region_points(db, track_id)` 消除两薄壳的 5 行查询重复。**不采纳**——5 行重复的抽象成本大于收益，且两个端点的查询将来可能分叉（公开分享页要加过滤），抽早了把两条路径绑死。**同时定为契约**（其 Recommendation 3）：`_build_region_tree(points)` 收 `points` 而非 `db`，这是 6 个用例中 5 个能**全内存跑**（不入库、不依赖 `spatial_service` 是否被换成 PostGIS 实现）的前提，将来不要「顺手把查询也合并进去」。

**计数更正**：协调者转述质量审时写「空 stats 字面量 3 处降到 2 处」，实现者实测更正为 **3 → 1**（权限失败 1 + 两薄壳 2 = 3；删两处后只剩权限失败那处）。**实现者正确，协调者算错**——`_build_region_tree` 末尾的 `stats` 是从四个 set 现算的、不是字面量（`grep -n "'province': 0"` 可验）。

**给 Task 12 的交接（质量审 Recommendation 2，计划层提醒）**：前端判断节点「无数据」**优先用 `Object.keys(names).length === 0` 而不是 `name === '未知区域'`**——`names == {}` ⟺ 三语全空 ⟺ 哨兵，是结构性信号。现有前端四处（`TrackDetail.vue:438/692`、`SharedTrack.vue:272/436`）都在做中文字面量比较，region 一多就会成为「中文硬编码泄漏进印尼语 UI」的来源（`'（无名）'` 同理）。**哨兵取 `'未知区域'` 是 spec 决策，本 Task 不改**，但 Task 12 实现时按上述判据。

**给 Task 14 的回归风险点（质量审 Recommendation 4，须写进 changelog）**：`city`/`district`/`road_name` 现在会回退到 `*_en`/`*_id`，故 cn 轨在「zh 某级为空、en 该级有值」时会**新出现**一个英文名节点，而合并前该点会并进上层。geocoding 的三语取值为同一轮请求、同一 `admin` 层级，presence 应一致 → 实际概率很低，且方向是「显示更多信息而非更少」；但它确实是 commit message「cn 点 zh 非空时一致」这一限定语的**边界**，需在 changelog 留一句。

**fix loop 复审结论（2026-09-10，可关闭）**：7 项全部按裁决落地、**零行为变化**、无越界、无附带损害。复审者逐行归账 8 个 hunk 的每一条都能对上某一项，「明确不修」清单**一处未动**；`--ignore-all-space` 后 stat 完全相同（无格式化噪音），diff 内无 `print`/`breakpoint`/TODO 残留。三处超出要求的独立验证：

1. **自己推了一遍空列表路径**（`for` 不执行 → 四个 `current_*` 全 None → 四个收尾块被 `is not None` 守卫 → `root_nodes == []`；四个 set 全空 → 四个 0 且**键序也相同**），并核实两个消费方（`app/api/tracks.py:834-840`、`app/api/shared.py:180-186`）只做 `.get('regions', [])`/`.get('stats', {})` 透传 → 响应体逐字节不变。
2. **用另一条连接直接改 DB 行**验证第 5 项：commit 后把该行 `province` 从 `AAA` 改成 `BBB`，不 `expunge_all` 时树的省名仍是 `AAA`（identity map 里的旧对象），`expunge_all` 后为 `BBB`。**修复前这条用例证明不了任何 DB 往返，现在能** —— 本轮最有价值的一处修复。
3. **独立变异复核第 4 项**：删 `road_name = '（无名）'` → 红在**新断言那一行**（`assert None == '（无名）'`），而上一行的 `type == 'road'` 仍通过，反证节点身份正确（题目假设的三层 `children` 路径在本 fixture 下会 IndexError，实际道路节点直挂省节点下）。

**复审更正的两处理由（结论均不受影响）**：① 加 `*` 的**结论正确**（实测：漏传得 `TypeError: missing 1 required keyword-only argument`；而无默认值的位置参数方案仍允许未来写法把 `road_number` 静默绑进 `region`），但实现者给的理由不精确——**现有**调用点本就带 `region=` 关键字，把 `region` 提到第三位会得到**响亮的** `TypeError: got multiple values for argument 'region'`，静默错位属于**未来/其他写法**的调用者。② 第 5 项捕获 `track_id/user_id` 是**防御性**而非必需：把两行对调（先 `expunge_all` 再读 `track.id`）用例仍 passed（`expire_on_commit=False` 不使属性失效，detached 对象仍持有已加载值）；保留捕获的理由是 conftest docstring 明说将来可能换 `expire_on_commit`，一行成本换意图清晰，**不作为缺陷**。

**残留风险（已知、可接受）**：两个已删早退没有直接单测（实现者明说未加空列表断言，用例数保持 6）；空轨迹走端点的路径现在只有间接覆盖——但连续两轮独立实证（实现者的等价脚本 + 复审者的空列表推演与实测）已把它钉死。另：`1426` 注释前半句「去重键 = (region, 显示文本)」对**道路级**略宽（stats 的 road 键用的是重赋值前的 `road_name`，故「（无名）」永不进 `road_set`）——属基线文字，本次只加了准确的后半句，不构成回归。

---

### Task 11: 前端 API 层：类型加 region/多语言字段，upload/update 透传 region

**Files:**
- Modify: `frontend/src/api/track.ts`（Track/UnifiedTrack/TrackPoint/RegionNode 类型、upload、update）
- Modify: `frontend/src/api/roadSign.ts`（RoadSignRequest/RoadSignResponse）
- **不改** `frontend/src/utils/roadSignParser.ts`——实现级裁定（记入决策）：`parseRoadNumber` 的全部活动调用点中，cn 分支走现状解析、id 分支在 `renderNodeLabel` 直接绕开 parse 改走后端判级（见 Task 12），无任何调用点需要 region 参数 → 公共函数不加死参数。地图组件 5 处调用不改（id 编号 parse 失败 → 现有文本回退分支自然兜底）。
- **不改** `fillGeocoding` 前端方法——后端 `region` Query 缺省时回读轨迹自身 region（Task 6），行为等价且轨迹 region 为权威，前端无需显式传（见 Task 12 注）。

- [ ] **Step 1: `track.ts` 三个接口类型加字段**

`Track`（original_crs 后）与 `UnifiedTrack` 各加一行：

```ts
  region: string  // 地区: cn=中国, id=印尼（新建点的默认 region，点级权威见 TrackPoint.region）
```

`TrackPoint`（road_name_en 之后、memo 之前）加：

```ts
  province_id: string | null  // 印尼语省级名
  city_id: string | null  // 印尼语市级名
  district_id: string | null  // 印尼语区级名
  road_name_id: string | null  // 印尼语路名
  region: string  // 点级地区（图标与显示回退的权威来源）
```

`RegionNode`（name 之后）加：

```ts
  region?: string  // 节点地区（后端恒返回；可选以便兼容旧数据）
  names?: Record<string, string>  // 组内各语言代表文本，如 { zh, id, en }（非空语言才出现）
```

- [ ] **Step 2: `track.ts` 的 upload/update 方法**

upload 的 data 类型（`fill_geocoding?` 后）加 `region?: string`，方法内 `fill_geocoding` append 之后加：

```ts
    if (data.region !== undefined) formData.append('region', data.region)
```

update 的 data 类型 `{ name?: string; description?: string }` 改为 `{ name?: string; description?: string; region?: string }`（正文不变——region 直接随 JSON PATCH 发送，后端 exclude_unset 语义：不传即不更新）。

- [ ] **Step 3: `roadSign.ts` 请求/响应加印尼字段**

```ts
export interface RoadSignRequest {
  sign_type: 'way' | 'expwy'
  code: string
  province?: string
  name?: string
  region?: string      // 地区: cn(缺省)/id。id 时 sign_type 被忽略，按编号+路名判级生成六边形盾牌
  name_id?: string     // 印尼语路名（TOL 关键词判定文本之一）
}

export interface RoadSignResponse {
  svg: string
  cached: boolean
  sign_type: string
  code: string
  province?: string
  name?: string
  region?: string      // 回显请求地区（缺省 'cn'）
}
```

- [ ] **Step 4: 类型检查**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 无错误（若有与本任务无关的存量错误先记录、不修）。

> ⚠️ **本步实测不可执行（Task 11 执行时发现，协调者独立复核确认）**：本机 `vue-tsc` 完全跑不起来，属**存量环境问题**、与本计划无关。故以 `npx vite build`（项目自身标准，见 `cc/workflow.md:25`「前端在 `frontend` 目录下执行 `npm run build`」）替代，并辅以下述定点自查。详见「Task 11 记录」。
>
> 实证：`npx vue-tsc --version` **自身即崩**（读任何源码之前），报 `Search string not found: "/supportedTSExtensions = .*(?=;)/"`——`vue-tsc@1.8.27` 靠正则给 TypeScript 打补丁，而 `package.json` 声明 `typescript: ^5.3.3` 被解析成 **5.9.3**，该正则已失效。`package-lock.json` 里同样固化着 5.9.3，故 `npm ci` 也修不好。升 `vue-tsc@2` 亦不通：本机 TS 5.9.3 的 `package.json` 未导出 `./lib/tsc`，而 `vue-tsc@2` 正是 `require.resolve('typescript/lib/tsc')`；`npx -p typescript@5.9.3` 的钉版又会被 peer 解析覆盖回 typescript 7.0.2。**修它需动依赖版本（仓库级 blast radius），超出本计划范围——记录并上报，不擅自改。**
>
> **类型检查缺位的风险由「调用点定点自查」兜底**（本计划的函数签名改动均为文件内自洽重写）：`grep -rn "(loadRoadSignSvg|getRoadSignSvg)(" frontend/src` 实测——被改的两个函数其**全部调用点都在被替换的代码块内部**（`TrackDetail.vue:1826/1862`、`SharedTrack.vue:817/853`），5 个地图组件（`BMap`/`GoogleMap`/`TencentMap`/`AMap`/`LeafletMap`）各持**自己的私有同名副本**、不受签名变更影响。故 Task 11 新增的必填字段 `region`，其唯一可破坏面是**对象字面量构造点**，已定点排查（见记录）。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/track.ts frontend/src/api/roadSign.ts
git commit -m "feat(api): 前端 API 类型与上传/更新请求支持 region 与多语言字段

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

**Task 11 记录（执行后回写）**

- 实现：`a8da60e`，`2 files changed, 15 insertions(+), 1 deletion(-)`，`git diff --stat` 越界检查通过（仅 2 文件）。状态 DONE_WITH_CONCERNS，唯一 concern 即上述环境问题。
- **必填字段破坏面定点排查**（无 vue-tsc 兜底，故由实现者手工排查、协调者复核）：`region` 在 `Track`/`UnifiedTrack`/`TrackPoint` 上是必填，全仓对这三类类型**显式标注的数组**只有 `TrackMerge.vue:360`（`UnifiedTrack[]`）与 `Home.vue:782`（`TrackPoint[]`），二者都只 `push` API 返回的现成对象、不构造字面量 → **无破坏面**。
- **字段名溯源核对**（协调者独立做）：前端新增字段与后端权威定义逐字一致——点级 `province_id`/`city_id`/`district_id`/`road_name_id`/`region` 对 `backend/app/schemas/track.py:159-163`；节点级 `region`/`names` 对 `backend/app/schemas/track.py:191-192`；`RoadSignRequest`/`RoadSignResponse` 对 `backend/app/api/road_signs.py:30-38` 与 `105-113`。
  > 附注：道路图标 schema **不在** `backend/app/schemas/` 而在 `backend/app/api/road_signs.py`（易误判为「字段不存在」，审查时注意）。
- **发现但按 YAGNI 未扩范围**：后端 `RoadSignRequest` 尚有 `province_id`（`road_signs.py:38`，注释「印尼语省名文本（region=id 时查省码用）」），前端未加该字段。Task 11 规格本就只列 `region?`/`name_id?`；且 Task 12 的区域树对 id 分支只传 `code/signType/region/name/nameId`，**无任何调用点会发 `province_id`** → 不预先加死字段。**记为 Task 13 端到端冒烟的观察点**：若印尼盾牌实际渲染出现省份码缺失，此处是第一嫌疑。
- ~~观感：`RoadSignRequest` 新增两行注释对齐不齐~~ → **该判断经复审实测推翻，撤回**。审查者逐行测了 `//` 列号：`roadSign.ts` L9/L10/L20 三处注释**全部落在第 23 列，本来就是对齐的**，无错可纠。至于 `track.ts` 新字段（L91-95 列号 30/26/30/31/18）虽不等宽，但**整个 `track.ts` 都不是列对齐风格**——它是「类型后固定两个空格」（对照存量 L28-30 = 33/34/40、L68/70 = 23/29、L96 = 23），新字段恰好符合本文件既有约定。若把 5 行单独对齐，反与紧邻 40 余行存量风格割裂，纯 churn、读者收益为零。**裁定：不改。**
  > 教训：**「视觉上不齐」这类判断不能靠印象**。实现者与我先后都凭观感报了同一处「不齐」，实测列号后两者皆错。凡涉格式的结论，一律用列号/字节级证据说话。

**Task 11 fix loop（spec 审查发现，属计划缺陷、非实现者过失）**

审查发现：`TrackPoint` 新增 5 个**必填**字段后，全仓唯一的 `TrackPoint` 对象字面量 `frontend/src/views/TrackDetail.vue:2883-2909`（`points.value.push({...})`，`points` 是 `ref<TrackPoint[]>([])`，见 L1282）**缺这 5 个键** → 新增 TS2739。

> **这是本计划的自相矛盾**：Task 11 的 Files 只列了 `track.ts`/`roadSign.ts` 并明令「不得触碰其他文件」，却又要求新字段必填——而唯一受影响的字面量在第三个文件里，二者不可同时满足。**责任在计划，不在实现者**（实现者严格守住了范围裁定，是正确执行）。**裁定：授权 Task 11 fix loop 修改 `TrackDetail.vue`（仅此一处字面量），这是对「只改 2 文件」裁定的具名例外。**

**定点排查证据（协调者独立复核，非采信报告）**：全仓 `grep -rn "road_name_en:\|road_name_id:" src/` 交叉验证——`TrackPoint` 字面量**仅此一处**（`OverlayTemplateEditor.vue:872/1533` 是海报模板样例数据、`api/geoEditor.ts:24` 是另一个接口）。实现者先前只查了 `TrackMerge.vue:360` 与 `Home.vue:782` 两处**显式类型标注的数组**，但这两处实为 `items.push(...res.items)`（spread 现成对象，`TrackMerge.vue:362`）与 `sampled.push(points[i])`（推已有元素，`Home.vue:784/789`），**本就不是字面量构造点**——排查方法错位，故漏掉了真破坏点。

**定性校正（避免夸大）**：该处 **base 上本就有 TS2339 存量错误**——`handleNewPointAdded(data: PointAddedData)` 的 `PointAddedData` 从 `@/utils/liveTrackWebSocket` 导入（`TrackDetail.vue:1082`），其 `point` 只声明 9 个字段（`liveTrackWebSocket.ts:62-73`：`id`/`point_index`/`latitude`/`longitude`/`elevation`/`speed`/`time`/`created_at`），而 L2884-2908 大量访问 `point.latitude_wgs84`/`point.province`/`point.memo` 等**不存在于该类型的属性**。故这不是「从类型干净变坏」，而是「本已不干净处又添 5 个必填缺失」。**不修存量 TS2339**（超范围，且属独立议题；且因 vue-tsc 不可用，本仓当前无任何 TS 门禁，存量错误无从暴露）。

**修复值的事实依据**：`backend/app/services/live_recording_service.py` **全文无 `region`**（grep 实测零命中）→ 实时记录建点时不传 region、落模型默认值 `'cn'`。故 4 个 `*_id` 填 `null`、`region` 填 `'cn'` 是**事实正确**而非猜测（与 Task 14 待记录的已知限制「实时记录恒 cn」一致）。

**「本仓前端无 TS 门禁」的加固证据（协调者复核，进一步支持不改依赖的裁决）**

1. **排除 `@ts-nocheck` 豁免**：全仓 `grep -rn "@ts-nocheck\|@ts-ignore\|@ts-expect-error" src/` 只命中 `src/auto-imports.d.ts:3/86` 与 `src/components.d.ts:3`——均为**自动生成**的声明文件，非手写源码。`TrackDetail.vue` 未被豁免。
2. **确认检查强度**：`frontend/tsconfig.json` 为 `"strict": true`、`"noUnusedLocals": true`、`"noUnusedParameters": true`，且 `"include": ["src/**/*.ts", "src/**/*.d.ts", "src/**/*.tsx", "src/**/*.vue"]` → `.vue` 在检查范围内，对象字面量缺必需属性确会报错。**故上一轮「新增 TS2739」的定性成立。**
3. **关键推论（比「vue-tsc 崩了」更重要的裁决依据）**：由 2 与前述存量 TS2339 可知，**`build:check` 即便在 vue-tsc 可用的环境里也是红的**——base 上就有一批存量类型错误。所以修 vue-tsc **不是「恢复一道绿色门禁」，而是「打开一屏存量错误」**，随之而来的是分类、triage 与「哪些算本计划引入」的归属争议。**这是一个独立议题、独立工作量，明确不属于本计划。** 本计划改用 `npm run build`（项目自身文档标准）+ 定点人工核对，是当前最省且最诚实的路径。
4. **由此得出的通用教训（Task 12 及后续前端任务通用）**：`npm run build` 通过**不构成类型正确的证据**——esbuild 只剥离类型。凡涉及**新增必填字段、改函数签名、删改 import**，必须人工定点核对（新增必填字段 → 找对象字面量构造点；改签名 → 找全部调用点；删 import 依赖 → 看有没有别的使用点）。Task 12 的 `ParsedRoadNumber` 未使用 import 正是此类（esbuild 静默丢弃、构建不会变红）。

---

### Task 12: 前端视图：上传地区选择、编辑对话框地区、区域树印尼盾牌与多语 tooltip

**Files:**
- Modify: `frontend/src/views/TrackUpload.vue`（表单加地区）
- Modify: `frontend/src/views/TrackDetail.vue`（编辑对话框加地区、区域树渲染三函数、saveEdit）
- Modify: `frontend/src/views/SharedTrack.vue`（区域树渲染三函数——与 TrackDetail 完全同构、无编辑/填充逻辑）

本节先给出 TrackDetail 的目标代码；SharedTrack 的 getRoadSignSvg/loadRoadSignSvg/renderNodeLabel 三函数**逐字相同**（仅文件内行号不同，SharedTrack 位于 L778-876），执行器在 SharedTrack 重复应用同样的函数体替换。

> 实况前提（Task 5 质量审查实测）：后端 `get_or_create_sign` 走 `output_path` 分支再回读文件，**返回的 SVG 带固定 `width="562.0px" height="451px"`**（仅字符串分支剥 width/height；CN 盾牌同形，前端既有渲染已兼容）。故此处沿用现有内联/尺寸处理即可，**不要**指望靠 viewBox 自适应撑满容器；如需缩放由外层 CSS 定尺寸。

两个文件模板中两处 el-tree slot 均以 `<component :is="() => renderNodeLabel(data)" />` 输出标签 → **模板零改动**（tooltip 用原生 title 属性在 renderNodeLabel 内实现，不侵入 el-tree）。

> ⚠️ **附带必改：`ParsedRoadNumber` 类型 import 会变成未使用（本计划原先漏写，协调者实测补入）**
>
> 实测（`grep -n "ParsedRoadNumber\|parseRoadNumber"`）：
> - `TrackDetail.vue`：import 在 L1081，类型**仅**用于 L1814 的 `loadRoadSignSvg(parsed: ParsedRoadNumber)`；函数 `parseRoadNumber` 用在 L1854。
> - `SharedTrack.vue`：import 在 L557，类型**仅**用于 L805；函数用在 L845。
>
> 本任务的 Step 1/2 把 `loadRoadSignSvg` 的形参改成 `RoadSignFetchOptions` 后，**该类型 import 再无任何使用点** → 成为未使用 import。本仓 `tsconfig.json` 为 `"strict": true` + `"noUnusedLocals": true`，vue-tsc 下会报 TS6133。
>
> **处置**：两文件的 import 行改为只留函数——`import { parseRoadNumber } from '@/utils/roadSignParser'`（**不要**整个删掉该 import：`parseRoadNumber` 在 cn 分支仍被 `renderNodeLabel` 调用，见 Step 1 代码块 `const parsed = parseRoadNumber(num)`）。
>
> **注意这不影响 `npm run build`**：esbuild 会静默丢弃未使用 import，故构建不会因此变红——**这正是本仓无 TS 门禁时最容易漏掉的一类问题**，必须靠人工核对。

- [ ] **Step 1: TrackDetail.vue —— 替换三个 SVG 函数与 renderNodeLabel（L1780-1885 区段整体替换）**

将 `getRoadSignSvg`（L1787-1808）、`loadRoadSignSvg`（L1814-1836）、`renderNodeLabel`（L1842-1885）三函数整体替换为（中间注释行保留原样）：

```ts
/**
 * 道路标志获取/加载的参数与缓存键
 * region 缺省 'cn'；id 时 sign_type 恒 'way'（后端判级），name/name_id 供 TOL 判定
 */
interface RoadSignFetchOptions {
  code: string
  signType: 'way' | 'expwy'
  province?: string
  region?: string
  name?: string
  nameId?: string
}

function buildSignCacheKey(opts: RoadSignFetchOptions): string {
  const region = opts.region || 'cn'
  // cn: 维持现状键（signType:code[:province]）；id: 键含地区与路名
  // （路名决定 TOL/NASIONAL 判定，必须参与键，防同名编号不同路串样）
  if (region !== 'cn') {
    return [region, opts.signType, opts.code, opts.name || ''].filter(Boolean).join(':')
  }
  return opts.province ? `${opts.signType}:${opts.code}:${opts.province}` : `${opts.signType}:${opts.code}`
}

/**
 * 异步获取道路标志 SVG
 * @param opts 编号、类型与地区参数（见 RoadSignFetchOptions）
 * @returns SVG 字符串，失败返回 null
 */
async function getRoadSignSvg(opts: RoadSignFetchOptions): Promise<string | null> {
  const cacheKey = buildSignCacheKey(opts)

  // 检查缓存
  const cached = roadSignSvgCache.value.get(cacheKey)
  if (cached) return cached

  try {
    const isId = (opts.region || 'cn') !== 'cn'
    const response = await roadSignApi.generate({
      sign_type: isId ? 'way' : opts.signType,  // id: sign_type 无意义，后端忽略
      code: opts.code,
      ...(opts.province && { province: opts.province }),
      ...(opts.name && { name: opts.name }),
      ...(isId && { region: opts.region }),
      ...(isId && opts.nameId && { name_id: opts.nameId }),
    })
    const svg = response.svg
    roadSignSvgCache.value.set(cacheKey, svg)
    return svg
  } catch {
    // 生成失败，返回 null 使用文本回退
    return null
  }
}

/**
 * 异步加载单个道路编号的 SVG（不阻塞渲染）
 * @param opts 与 getRoadSignSvg 相同的参数
 */
async function loadRoadSignSvg(opts: RoadSignFetchOptions) {
  // 缓存 key 与 getRoadSignSvg 一致
  const key = buildSignCacheKey(opts)

  // 防止重复加载
  if (loadingSigns.value.has(key)) {
    return
  }

  loadingSigns.value.add(key)

  try {
    const svg = await getRoadSignSvg(opts)
    if (svg) {
      // 触发树组件重新渲染
      treeForceUpdateKey.value++
    }
  } catch {
    // 生成失败，忽略错误
  } finally {
    loadingSigns.value.delete(key)
  }
}

/**
 * 渲染节点标签（支持 SVG 标牌）
 * 节点按自身 region 分派：cn 走国标前端解析；id 编号不经前端解析，
 * 直接交后端（按编号+路名判定等级并生成六边形盾牌）。失败回退纯文本。
 * 多语言节点（names >= 2 种语言）附原生 title 展示全部语言。
 * 返回 VNode
 */
function renderNodeLabel(node: RegionNode) {
  const config = configStore.config
  const showSigns = config?.show_road_sign_in_region_tree ?? true
  const region = node.region || 'cn'

  // 多语言提示：组内非空语言数 >= 2 才有（zh: 中文 / id: 印尼语 / en: 英语）
  const nodeNames = node.names || {}
  const multiLangNames = Object.keys(nodeNames).filter(k => nodeNames[k]).length >= 2
  const titleAttr = multiLangNames ? { title: Object.values(nodeNames).join(' / ') } : {}

  // 处理道路节点且有道路编号
  if (node.type === 'road' && node.road_number) {
    const roadNumbers = node.road_number.split(',').map(s => s.trim())
    const contents: (string | ReturnType<typeof h>)[] = []

    if (showSigns) {
      // 开启标牌模式：尝试渲染 SVG
      roadNumbers.forEach((num, index) => {
        let opts: RoadSignFetchOptions | null = null
        if (region !== 'cn') {
          // 印尼：编号原样交后端（含路名用于 TOL 判定）
          const roadName = node.name && node.name !== '（无名）'
            ? node.name
            : (nodeNames.id || nodeNames.en || '')
          opts = {
            code: num,
            signType: 'way',
            region,
            ...(roadName && { name: roadName }),
            ...(nodeNames.id && { nameId: nodeNames.id }),
          }
        } else {
          const parsed = parseRoadNumber(num)
          if (parsed) {
            opts = { code: parsed.code, signType: parsed.sign_type, ...(parsed.province && { province: parsed.province }) }
          }
        }
        if (opts) {
          const svg = roadSignSvgCache.value.get(buildSignCacheKey(opts))
          if (svg) {
            contents.push(h('span', { innerHTML: svg, class: 'road-sign-inline' }))
          } else {
            contents.push(num)
            loadRoadSignSvg(opts)
          }
        } else {
          contents.push(num)
        }
        if (index < roadNumbers.length - 1) contents.push(' ')
      })
    } else {
      // 关闭标牌模式：显示纯文本编号
      contents.push(roadNumbers.join(' / '))
    }

    // 添加道路名称
    if (node.name && node.name !== '（无名）') {
      contents.push(' ')
      contents.push(node.name)
    }

    return h('span', titleAttr, contents)
  }

  // 非道路节点，使用原文本
  return h('span', titleAttr, node.name)
}
```

> 说明：`titleAttr` 为空对象 `{}` 时 `h('span', {}, children)` 等价于原无属性渲染（Vue 合法），多语言时原生 `title` 属性由浏览器 tooltip 显示——不依赖 el-tree 的插槽透传。节点 `names` 顺序即后端字典序 zh → id → en，tooltip 呈现「东爪哇省 / Provinsi Jawa Timur / Province of East Java」样式。

- [ ] **Step 2: SharedTrack.vue —— 应用同一组替换（L778-876）**

同一份 `RoadSignFetchOptions`/`buildSignCacheKey`/`getRoadSignSvg`/`loadRoadSignSvg`/`renderNodeLabel` 代码应用到 SharedTrack.vue（当前 L771-876，行号以文件实际为准）。SharedTrack 无编辑/填充逻辑，其余零改动。

> ⚠️ **`frontend/src/views/` 下有两个被 git 跟踪的废弃副本：`SharedTrack.vue.bak` 与 `SharedTrack.vue.bak2`**（已实测 `git ls-files` 确认在版本控制内）。两者**都含** `renderNodeLabel`（各在 L418）等同名符号。用 `grep`/全局替换定位时**务必确认命中的是 `SharedTrack.vue` 正式文件**（锚点：`SharedTrack.vue:833` 的 `function renderNodeLabel`），**不要改这两个 `.bak`**——它们是历史遗留、无人引用，改了除污染 diff 外没有任何作用。
> （这两个文件的清理属独立议题，不在本计划范围；如需删除须先取得开发者同意——它们是**已被跟踪**的文件，删除是一次对仓库历史的可见改动。）

- [ ] **Step 3: TrackUpload.vue —— 表单加「地区」选择**

模板「原始坐标系」form-item（L86-96，`.form-tip` 提示段之后、`</el-form-item>` 后）插入：

```html
          <!-- 地区 -->
          <el-form-item label="地区">
            <el-radio-group v-model="form.region">
              <el-radio value="cn">中国</el-radio>
              <el-radio value="id">印尼</el-radio>
            </el-radio-group>
            <div class="form-tip">
              轨迹的默认地区，决定道路图标样式与地理信息填充语言集；多语言列可随 CSV 逐行覆盖
            </div>
          </el-form-item>
```

script：`form` reactive（L170-176）加 `region: 'cn',`；`handleSubmit` 的 `trackApi.upload({...})`（L216-222）加 `region: form.region,`。

- [ ] **Step 4: TrackDetail.vue —— 编辑对话框加「地区」并保存**

**4a. editForm**（L1306-1310）加字段：

```ts
const editForm = ref({
  name: '',
  description: '',
  original_crs: 'wgs84',
  region: 'cn'
})
```

**4b. showEditDialog**（L2496-2503）赋值区加：

```ts
    editForm.value.region = track.value.region || 'cn'
```

**4c. 模板**（「原坐标系」form-item L761-768 的 `</el-form-item>` 后）插入：

```html
        <el-form-item label="地区">
          <el-radio-group v-model="editForm.region">
            <el-radio value="cn">中国</el-radio>
            <el-radio value="id">印尼</el-radio>
          </el-radio-group>
          <div class="form-hint">轨迹的默认地区（新填充/新导入点的默认值；已有轨迹点不受影响）</div>
        </el-form-item>
```

**4d. saveEdit**（L2506-2568 整体）——原逻辑：换坐标系（if 分支）与名称/描述（else 分支）互斥，导致同时改 region+坐标系时 region 丢失；重写为「坐标系变更独立处理 + 名称/描述/地区恒 PATCH」，顺带修复换坐标系时名称/描述改动不保存的存量行为：

```ts
// 保存编辑
async function saveEdit() {
  if (!track.value) return

  if (!editForm.value.name.trim()) {
    ElMessage.warning('轨迹名称不能为空')
    return
  }

  saving.value = true
  try {
    // 检查是否需要更改坐标系
    const needsCrsChange = editForm.value.original_crs !== track.value.original_crs

    if (needsCrsChange) {
      // 需要更改坐标系
      try {
        await ElMessageBox.confirm(
          '更改坐标系会重新计算所有坐标并保存，此操作不可撤销。如果此前填充了轨迹，可能需要重新填充。是否继续？',
          '确认更改坐标系',
          {
            confirmButtonText: '继续',
            cancelButtonText: '取消',
            type: 'warning',
          }
        )
      } catch {
        // 用户取消
        saving.value = false
        return
      }

      changingCrs.value = true
      const updated = await trackApi.changeCrs(track.value.id, editForm.value.original_crs)
      track.value = updated
      // 重新加载轨迹点数据
      await fetchTrackPoints()
      // 强制刷新地图
      await nextTick()
      if (mapRef.value?.resize) {
        mapRef.value.resize()
      }
      if (mapRef.value?.fitBounds) {
        mapRef.value.fitBounds()
      }
      ElMessage.success('坐标系更改成功')
    }

    // 更新名称、描述与地区（无论是否换坐标系都保存）
    const updated = await trackApi.update(track.value.id, {
      name: editForm.value.name.trim(),
      description: editForm.value.description.trim() || undefined,
      region: editForm.value.region,
    })
    track.value = updated

    if (!needsCrsChange) {
      ElMessage.success('保存成功')
    }

    editDialogVisible.value = false
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    saving.value = false
    changingCrs.value = false
  }
}
```

> handleFillGeocoding **不改**：后端 region 缺省回读轨迹自身 region（Task 6），用户把轨迹改为印尼后填充即自动三语请求。
> 地图 5 组件 **不改**：印尼编号前端 parse 失败 → 现有文本回退兜底（标牌只在区域树渲染，spec 范围外项目如地图标牌另行评估）。

- [ ] **Step 5: 类型检查与构建**

Run: `cd frontend && npm run build`（**非** `build:check`——见下方裁决）
Expected: `✓ built in ...`，无错误（存量 chunk >500kB 警告可忽略）。

> ⚠️ **验收命令已由 `build:check` 改为 `build`（Task 11 执行时实测 + 协调者独立复核的裁决）**：`build:check` = `vue-tsc && vite build`，而本机 `vue-tsc` **自身即崩**（`vue-tsc@1.8.27` × `typescript@5.9.3` 不兼容，`npx vue-tsc --version` 就报 `Search string not found: "/supportedTSExtensions = .*(?=;)/"`），属 **lockfile 里固化的存量问题**、与本计划无关。`npm run build`（=`vite build`）是**项目自身文档标准**（`cc/workflow.md:25`），可用。修 vue-tsc 需动依赖版本、有仓库级 blast radius，**超出本计划范围——已上报开发者，不擅自改**。
>
> **代价与对冲**：`vite build` 走 esbuild，**剥离类型但不做类型检查**。而本任务恰恰全是 `.vue` 内的渲染逻辑改写，是类型检查最有价值的场景。对冲手段是**调用点定点自查**（必须在提交前跑）：
>
> ```bash
> cd /d/code/vibe_route && grep -rn "(loadRoadSignSvg\|getRoadSignSvg\|renderNodeLabel)(" frontend/src --include=*.vue
> ```
>
> 逐条确认：(a) `TrackDetail.vue` / `SharedTrack.vue` 两文件内、被替换代码块**之外**没有残留的旧签名调用点（旧签名是 `getRoadSignSvg(code, signType, province?)` / `loadRoadSignSvg(parsed: ParsedRoadNumber)`）；(b) 5 个地图组件（`BMap`/`GoogleMap`/`TencentMap`/`AMap`/`LeafletMap`）各有**自己的私有同名副本**，本任务**不得**触碰，其内部调用自洽；(c) **`.bak`/`.bak2` 一律不得命中修改**。
>
> 已实测的基线（Task 11 时）：两文件内的调用点为 `TrackDetail.vue:1826/1862`、`SharedTrack.vue:817/853`，**全部落在被替换的代码块内部**；地图组件各 2 处（`BMap:118`、`GoogleMap:263`、`TencentMap:472`、`AMap:69`、`LeafletMap:2045`）均为文件内私有副本。`renderNodeLabel` 的调用点全部在模板 slot 内（`<component :is="() => renderNodeLabel(data)" />`），**模板零改动**。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/TrackUpload.vue frontend/src/views/TrackDetail.vue frontend/src/views/SharedTrack.vue
git commit -m "feat(views): 上传/编辑对话框地区选择；区域树按节点 region 渲染印尼盾牌与多语 tooltip

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 13: 数据库迁移（需授权）+ 后端全量测试 + 端到端冒烟

**Files:**
- 无新增（验证与冒烟任务；需要开发者配合：① 数据库迁移授权 ② 浏览器人工冒烟确认）
- 冒烟样例文件（临时，不入库）：`backend/data/smoke_indonesia.csv`

> ⚠️ **授权点 1（数据库）**：Task 2 的迁移文件与 SQL 脚本已就位但未执行。CLAUDE.md 规定开发期间不自行修改数据库——本任务第 1 步需向开发者申请执行迁移（或请开发者手动执行 alembic/SQL 后继续）。**授权前**：Task 1-12 与 pytest（纯函数）不触库可安全执行；Task 10 Step 4 的 DB 冒烟若缺列失败属预期，迁移完成后回跑即可。
>
> ⚠️ **授权点 2（浏览器）**：前端手动冒烟在已打开的 localhost:5173 页面用 Edge devtools MCP 执行，需开发者配合在 UI 上操作/确认（上传对话框、区域树视觉、tooltip）。

- [ ] **Step 1: 申请授权并执行数据库迁移**

向开发者说明：`016_add_multilanguage_region` 迁移新增 Track/TrackPoint 各 1 列 region + TrackPoint 4 个 `*_id` 列 + RoadSignCache.region，请求执行：

Run: `cd backend && ../.venv/Scripts/python -m alembic upgrade head`
Expected: 迁移成功（输出 upgrade 行）。验证列存在：

Run:
```bash
cd backend && ../.venv/Scripts/python - <<'EOF'
import sqlite3, os
from app.core.config import settings  # 或直接按 backend/.env 的 DATABASE_URL
db = settings.DATABASE_URL
print("db:", db)
# SQLite 场景: 直接查询
path = db.replace('sqlite:///', '')
con = sqlite3.connect(path)
cols = [r[1] for r in con.execute("PRAGMA table_info(track_points)")]
print("region in track_points:", 'region' in cols, "| *_id cols:", [c for c in cols if c.endswith('_id')])
EOF
```
Expected: region in track_points: True（_id 列随 Task 2 的完整列表核对）。
若开发者选择手动执行，按其方式执行后跳过本步命令。

- [ ] **Step 2: 后端全量 pytest**

Run: `cd backend && ../.venv/Scripts/python -m pytest tests/ -q`
Expected: 全绿（Task 1 的印尼解析/盾牌/缓存键/分派用例 + 无失败）。

> 环境备注（本机实测）：`%TEMP%/pytest-of-Administrator` 是 2026-08-23 遗留的不可访问目录，
> 当前令牌非提权、无法接管或删除，会让任何用 pytest `tmp_path` 的用例在 fixture 阶段
> `PermissionError: [WinError 5]`。故本计划新增测试一律用 `tests/test_indonesia_shield.py`
> 里的 `workdir` fixture（`tempfile.TemporaryDirectory()`）而非 `tmp_path`；后续新增用例照此。
> 根治需开发者以管理员身份删除该遗留目录（`rd /s /q`），届时可改回 `tmp_path`。

- [ ] **Step 3: 写冒烟样例（新格式印尼 CSV，含 region 列）**

写 `backend/data/smoke_indonesia.csv`（冒烟后删除，不入 git）。四段覆盖：① `35-024` 省道且**中文列留空**（测回退链 zh→id→en，区域树节点显示印尼语、tooltip 两语）② `3` + 中文「收费」→ TOL ③ `3` 无关键词 → NASIONAL（同编号不同名不同等级、缓存键不串）④ 行级 `region=cn` 中国小段（跨地区轨迹分组）：

```csv
index,time_date,time_time,time_microsecond,elapsed_time,longitude_wgs84,latitude_wgs84,elevation,distance,course,speed,region,province_zh,province_id,province_en,city_zh,city_id,city_en,area_zh,area_id,area_en,road_num,road_name_zh,road_name_id,road_name_en,memo
0,2026-09-01,08:00:00,0,0,112.7350,-7.2800,10,0,90,40,id,东爪哇省,Provinsi Jawa Timur,Province of East Java,泗水市,Kota Surabaya,Surabaya,杜库帕基斯区,Kecamatan Dukuh Pakis,Dukuh Pakis District,35-024,,Jl. Raya Mayjen Sungkono,Sungkono Main Road,
1,2026-09-01,08:00:10,0,10,112.7360,-7.2809,10,120,90,40,id,东爪哇省,Provinsi Jawa Timur,Province of East Java,泗水市,Kota Surabaya,Surabaya,杜库帕基斯区,Kecamatan Dukuh Pakis,Dukuh Pakis District,35-024,,Jl. Raya Mayjen Sungkono,Sungkono Main Road,
2,2026-09-01,08:00:20,0,20,112.7370,-7.2818,11,240,90,40,id,东爪哇省,Provinsi Jawa Timur,Province of East Java,泗水市,Kota Surabaya,Surabaya,杜库帕基斯区,Kecamatan Dukuh Pakis,Dukuh Pakis District,35-024,,Jl. Raya Mayjen Sungkono,Sungkono Main Road,
3,2026-09-01,08:00:30,0,30,112.7380,-7.2827,11,360,90,40,id,东爪哇省,Provinsi Jawa Timur,Province of East Java,泗水市,Kota Surabaya,Surabaya,杜库帕基斯区,Kecamatan Dukuh Pakis,Dukuh Pakis District,3,泗水朱安达收费高速,Jalan Tol Juanda,Juanda Toll Road,入口匝道段
4,2026-09-01,08:00:40,0,40,112.7390,-7.2836,12,480,90,40,id,东爪哇省,Provinsi Jawa Timur,Province of East Java,泗水市,Kota Surabaya,Surabaya,杜库帕基斯区,Kecamatan Dukuh Pakis,Dukuh Pakis District,3,泗水朱安达收费高速,Jalan Tol Juanda,Juanda Toll Road,
5,2026-09-01,08:00:50,0,50,112.7400,-7.2845,12,600,90,40,id,东爪哇省,Provinsi Jawa Timur,Province of East Java,泗水市,Kota Surabaya,Surabaya,杜库帕基斯区,Kecamatan Dukuh Pakis,Dukuh Pakis District,3,泗水朱安达收费高速,Jalan Tol Juanda,Juanda Toll Road,
6,2026-09-01,08:01:00,0,60,112.7410,-7.2854,13,720,90,40,id,东爪哇省,Provinsi Jawa Timur,Province of East Java,泗水市,Kota Surabaya,Surabaya,杜库帕基斯区,Kecamatan Dukuh Pakis,Dukuh Pakis District,3,泗水朱安达收费高速,Jalan Tol Juanda,Juanda Toll Road,
7,2026-09-01,08:01:10,0,70,112.7420,-7.2863,13,840,90,40,id,东爪哇省,Provinsi Jawa Timur,Province of East Java,泗水市,Kota Surabaya,Surabaya,杜库帕基斯区,Kecamatan Dukuh Pakis,Dukuh Pakis District,3,艾哈迈德·雅尼路,Jalan Ahmad Yani,Ahmad Yani Street,
8,2026-09-01,08:01:20,0,80,112.7430,-7.2872,14,960,90,40,id,东爪哇省,Provinsi Jawa Timur,Province of East Java,泗水市,Kota Surabaya,Surabaya,杜库帕基斯区,Kecamatan Dukuh Pakis,Dukuh Pakis District,3,艾哈迈德·雅尼路,Jalan Ahmad Yani,Ahmad Yani Street,
9,2026-09-01,08:01:30,0,90,112.7440,-7.2881,14,1080,90,40,id,东爪哇省,Provinsi Jawa Timur,Province of East Java,泗水市,Kota Surabaya,Surabaya,杜库帕基斯区,Kecamatan Dukuh Pakis,Dukuh Pakis District,3,艾哈迈德·雅尼路,Jalan Ahmad Yani,Ahmad Yani Street,
10,2026-09-01,08:01:40,0,100,114.0600,22.5400,5,1200,90,40,cn,广东省,,,深圳市,,,南山区,,,,滨海大道,,,,深港跨界冒烟段
11,2026-09-01,08:01:50,0,110,114.0610,22.5410,5,1320,90,40,cn,广东省,,,深圳市,,,南山区,,,,滨海大道,,,,
```

预期语义核对（冒烟断言用）：
- 树结构：根「东爪哇省」→「泗水市」→「杜库帕基斯区」一个分支，区下并列 3 条道路节点（`35-024` + `Jl. Raya Mayjen Sungkono`、`3` + 泗水朱安达收费高速、`3` + 艾哈迈德·雅尼路）
- 点 0-2 道路节点：PROVINSI 蓝盾牌（35-024 → 大字 `024`，色带 `PROVINSI 35`）；**回退链验证**——该段中文路名留空，节点名显示回退结果 `Jl. Raya Mayjen Sungkono`
- 点 3-6 道路节点：TOL 红盾牌（`3` + 中文「收费」命中；`Jalan Tol Juanda` 中 `\btol\b` 亦命中）
- 点 7-9 道路节点：NASIONAL 红盾牌（`3` 无关键词——验证同编号缓存键含路名不串样：`3`+收费 与 `3`+雅尼路 是两张不同的图）
- 省/市/区组 tooltip 三语（东爪哇省 / Provinsi Jawa Timur / Province of East Java）；`35-024` 路节点 tooltip 两语（id+en）；cn 段节点单语言 → 无 tooltip（spec「单语言则无 tooltip」断言）
- 点 10-11：与印尼段分开成组（区域树出现独立「广东省」根节点，region=cn，仅中文列）

- [ ] **Step 4: 启动后端并用样例导入（API 层冒烟）**

Run（若 8000 未占用）: 用仓库现有启动方式起后端（见 cc/quick-commands.md），然后：

```bash
curl -s -F "file=@backend/data/smoke_indonesia.csv" -F "name=smoke_indonesia" -F "region=id" -b <会话cookie> http://localhost:8000/api/tracks/upload
```
Expected: 返回轨迹对象，region=id。再查详情：
```bash
curl -s -b <cookie> http://localhost:8000/api/tracks/<id> | python -c "import json,sys; d=json.load(sys.stdin); print(d['region'], d['id'])"
curl -s -b <cookie> http://localhost:8000/api/tracks/<id>/regions | python -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d['regions'][:1], ensure_ascii=False, indent=1))"
```
Expected: 区域树根节点含 `region: 'id'`、`names` 三语言（zh/id/en）、道路节点 road_number 含 35-024 等、stats 正确。
（若本机无可用登录会话，改用浏览器 UI 冒烟覆盖此步，见 Step 5。）

- [ ] **Step 5: 浏览器端到端冒烟（需开发者配合确认）**

在已开的 localhost:5173 页面（Edge devtools MCP）：
1. 上传冒烟 CSV（选地区：印尼）→ 详情页
2. 区域树：印尼道路节点显示六边形盾牌（省道蓝色、TOL/收费红、NASIONAL 红），悬停节点出现三语 tooltip（东爪哇省 / Provinsi Jawa Timur / Province of East Java）
3. 编辑轨迹对话框：地区可切中国/印尼并保存
4. 导出 CSV 下载，核对新表头（region、province_zh/id/en…）；用导出的文件再导入一次（闭环），区域树结果一致
5. cn 轨迹回归：打开任一旧中国轨迹，区域树国标盾牌渲染与改动前一致（地区默认中国）

出现视觉异常时用 Edge devtools 截图回传分析。

- [ ] **Step 6: 记录冒烟结果与 Commit（如有样例产物需清理）**

冒烟中发现的问题按 debugging 流程处理（若问题小而明确可直接修并 commit）；全部通过后无代码改动则本任务无 commit（结果记入 Task 14 的 changelog）。

---

### Task 14: 要点记录到 cc/ 文档

**Files:**
- Modify: `cc/changelog.md`（追加本次变更条目）
- Modify: `cc/features.md`（地理编码/道路图标/区域树/配置相关段落补充 region 概念，按需）
- Modify: `cc/architecture.md`（如模型/字段权威语义属架构核心——补充 region 三层存储与语言后缀列模型）

先 Read `cc/changelog.md` 与相关模块看现有格式，按仓库惯例追加，要点（简洁、按模块落位）：

1. **数据模型**：`tracks.region`、`track_points.region`（点级权威）+ 4 个 `*_id` 印尼语列；`road_sign_cache.region`；迁移 `016_add_multilanguage_region` + 三份 SQL（含 sqlite 版新增）
2. **region 贯通**：上传 Form、编辑 PATCH、fill-geocoding Query（缺省读轨迹自身）、CSV 行级 region（跨地区文件主通道）、merge 复制点级
3. **Nominatim 多语**：region=id 三请求（zh-CN/id/en），38 省中文回填表（gpxutil 移植 + 前缀容错），中文缺失留空 + 前端回退链 zh→id→en
4. **印尼图标**：编号解析（NASIONAL/TOL 词边界/PROVINSI，省码三级来源）、六边形盾牌生成（Clearview 字体、模板 bbox 锚点）、config `indonesia_road_sign`、缓存键含 region；字体许可为商业字体（记录在案）
5. **导出新列名 + 导入别名表**（兼容新/样例/旧三格式）、区域树按 (region,文本) 分组 + 节点 names
6. **前端**：上传/编辑对话框地区选择；区域树按节点 region 分派渲染（cn 前端解析 / id 后端判级）；多语 tooltip；地图组件不改（文本回退）
7. **测试**：backend pytest 全量——`tests/` 下本次新建的 5 个文件：`test_indonesia_road.py`、`test_indonesia_shield.py`、`test_road_sign_region.py`、`test_nominatim_region.py`、`test_region_propagation.py`；前端 build:check（以 `tests/` 实际为准）
8. 冒烟结论（含开发者确认过的 UI 表现）
9. **已知限制（必须写，勿省）**：**实时记录链路恒为 `cn`**。`live_recording_service.py:435-459` 走**自己的内联地理编码**（`geo_service.get_point_info(lat, lon)` 两参调用），**不经过** `fill_geocoding_info` → 既不写 `*_id`、也不写 `point.region`；且 `LiveRecording` 模型**无 region 列**（迁移 016 也未加），`app/api/live_recordings.py:474` 调 `create_from_gpx` 不传 region → 模型默认 `'cn'`。后果：印尼实时记录的轨迹会按 cn 渲染图标、走中文回退文本。**绕行方案**：录完后 `PATCH /tracks/{id}` 把 `track.region` 改为 `'id'`，再跑一次 fill-geocoding（`region` 缺省时后端回读轨迹自身 region）即可正确回填点级 region 与 `*_id`。**实时记录界面的地区选择属后续工作**（需新迁移 + 前端改造），列为本次范围外。
10. **已知限制（必须写，勿省）**：**Geo Editor（地理信息编辑器）不认识多语言字段**。`geo_editor_service.py` 读路径（L82-105）构造的 `TrackPointGeoData` 只含 `province/city/district/road_number/road_name` 及其 `_en` 对，**不含 `*_id`、不含 region**；写路径（L152-184）的 `field_mapping` 同样只映射这几对，批量 `update(TrackPoint).values(**update_data)`。后果：在 Geo Editor 里修改印尼轨迹的路名后，`road_name` 被更新而 `road_name_id` 保持旧值 → **tooltip 与 TOL 判定读的是 `*_id`，会与实际路名不一致**。**无数据丢失风险**（`.values()` 只写列出的字段，不误伤 `*_id`/`region`）；**region 与图标不受影响**（编辑器不改 region）。**范围外原因**：修它要改 `app/schemas/geo_editor.py` + 前端 Geo Editor 界面，属独立议题；计划全篇（Task 1-14）未覆盖该文件。若后续要修，最小改动是给 `TrackPointGeoData`/`GeoSegmentUpdate` 加 `*_id` 字段并纳入 `field_mapping`。
11. **修复的既有缺陷（**必须写**，这是本次之外的真实收获）**：**导出的 CSV 首行曾是仅含 BOM 的空行**，导致**自家「导出→再导入」静默失效**。成因：`export_points_to_csv` 以 `csv_lines.append(BOM)` + `csv_lines.append(",".join(headers))` 组成、再 `"\n".join` → BOM 成为独立元素、独占首行；导入侧 `decode('utf-8-sig')` 去掉 BOM 后首行就是空行，`csv.DictReader` 把这一空行当作表头 → `fieldnames` 为 `[]`、每行键为 `None`（实测 `[{None: ['index','province']}, ...]`）→ `row.get("index")` 恒 `None` → **匹配 0 个点、返回 `matched_by: none`，全程不报错**。该缺陷自 `40aabe4` 起存在，与多语言工作无关，但**本计划 Task 9 要求的导出→导入闭环用例在未修时不可能通过**，故于 Task 9 一并修复：`csv_lines.append("﻿" + ",".join(headers))`（BOM 并入首字段）。**结论：vibe_route 自家导出的 CSV 在这次之前无法被自家导入器正确读回**；本次修复后闭环成立。另注：行分隔符仍是 `\n` 而非 RFC 4180 的 `\r\n`（既有，未改，导入侧不受影响）。

- [ ] **Step 1: 读 cc 现状 → 追加 → Commit**

```bash
git add cc/changelog.md cc/features.md cc/architecture.md
git commit -m "docs(cc): 记录印尼多语言轨迹与道路图标适配要点

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 计划自审记录

- **Spec 覆盖核对**：spec §2 模型/迁移 → Task 2；§3 导入导出 → Task 8/9；§4 geocoding → Task 6；§5 图标/API/缓存 → Task 1/4/5；§6 区域树 → Task 10/11/12；§7 配置 → Task 3；§8 测试 → Task 1/4/5 + Task 13；§9 兼容 → 各任务 cn 分支保持；§10 顺序 → 任务序一致。
- **实现级裁定（相对 spec 的显式偏离，均已就地注明）**：
  1. `parseRoadNumber` 不加 region 参数（无调用点需要 → 不加死参数）；id 分派在 `renderNodeLabel` 直接绕开 parse
  2. fill-geocoding 前端不显式传 region（后端缺省回读轨迹自身 region，行为等价且更稳）
  3. 色带省码在 API 请求链不可得（区域树道路节点无父级省文本）→ 色带仅等级词（35-024 内嵌省码除外）——spec 已含此降级分支
  4. 字体许可（Clearview 商业字体照拷）于 Task 3 前置确认
- **类型一致性**：后端 `fill_geocoding_info(...region=)`、`create_from_*(..., region='cn')`、`get_or_create_sign(..., region)`、前端 `upload({region})`、`update({region})`、`generate({region, name_id})` 与 `RoadSignFetchOptions` 各任务间签名互相对齐（Task 6↔7↔11↔12）。

**执行须知汇总**：全部任务在 master 分支线性执行；每个任务独立 commit 并含归属行；Task 13 的两个授权点（数据库迁移、浏览器冒烟）需要主会话向开发者申请后再推进；Task 10 的 DB 冒烟在迁移前失败属预期，可跳过并注明、迁移后回跑。

<!--PLAN-END-->
