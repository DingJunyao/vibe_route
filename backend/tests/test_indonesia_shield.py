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
    svg = generate_indonesia_shield('3', IndonesiaRoadLevel.NASIONAL, '16', shield_config)
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
    svg = generate_indonesia_shield('024', IndonesiaRoadLevel.PROVINSI, '16', shield_config)
    root = _parse(svg)
    head = [e for e in root.iter()
            if _ns_free(e) == 'polygon' and e.attrib.get('id') == 'head']
    assert head and head[0].attrib['fill'].upper() == PROVINCE_BLUE.upper()


def test_has_upper_and_lower_text_paths(shield_config):
    # 色带白字（PROVINSI 35）与大字黑字（024）
    svg = generate_indonesia_shield('024', IndonesiaRoadLevel.PROVINSI, '16', shield_config)
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

    assert _banner_len('3', IndonesiaRoadLevel.NASIONAL, '16') == len('NASIONAL 16')
    assert _banner_len('024', IndonesiaRoadLevel.PROVINSI, '16') == len('PROVINSI 16')
    # kode wilayah 为不补零序号：单数字省码（'3'）排版须自适应，不按固定两位数留位
    assert _banner_len('3', IndonesiaRoadLevel.NASIONAL, '3') == len('NASIONAL 3')
    # 县市码（'16.17'）5 字符，同样整段进色带
    assert _banner_len('024', IndonesiaRoadLevel.PROVINSI, '16.17') == len('PROVINSI 16.17')
    # 无省码降级：仅等级词，无多余空格占位
    assert _banner_len('3', IndonesiaRoadLevel.TOL, None) == len('TOL')


def test_text_heights(shield_config):
    """字号：色带 45px、大字 135px（spec §5 排版制式）"""
    svg = generate_indonesia_shield('024', IndonesiaRoadLevel.PROVINSI, '16', shield_config)
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
    svg = generate_indonesia_shield('3', IndonesiaRoadLevel.NASIONAL, '16', shield_config)
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
    root = _parse(generate_indonesia_shield('3', IndonesiaRoadLevel.NASIONAL, '16', cfg))
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
