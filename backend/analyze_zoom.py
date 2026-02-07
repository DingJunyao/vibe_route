#!/usr/bin/env python3
"""分析地图缩放测试数据，提取最佳系数"""

import re

# 从 scale_2.txt 提取的关键数据
data = [
    # 横屏+横向
    ("横屏", "横向", "百度", 150, 0.45, 11.6, 12.30),
    ("横屏", "横向", "百度", 200, 0.45, 11.1, 11.92),
    ("横屏", "横向", "高德", 150, -3.5, 10.1, 11.61),
    ("横屏", "横向", "高德", 200, -3.5, 12.5, 11.07),  # 注意：目标zoom > 实际zoom
    ("横屏", "横向", "腾讯", 150, 0.8, 11.8, 11.20),
    ("横屏", "横向", "腾讯", 200, 0.8, 11.4, 10.89),
    ("横屏", "横向", "leaflet", 150, 6, 12, 11),
    ("横屏", "横向", "leaflet", 200, 6, 12, 11),

    # 横屏+竖向
    ("横屏", "竖向", "百度", 150, 0.6, 10.8, 8.42),
    ("横屏", "竖向", "百度", 200, 0.6, 9.7, 7.89),
    ("横屏", "竖向", "高德", 150, 0.7, 3.0, 7.65),
    ("横屏", "竖向", "高德", 200, 0.7, 3.0, 7.19),
    ("横屏", "竖向", "腾讯", 150, 0.8, 7.8, 7.21),
    ("横屏", "竖向", "腾讯", 200, 0.8, 7.4, 6.88),
    ("横屏", "竖向", "leaflet", 150, 10, 8, 7),
    ("横屏", "竖向", "leaflet", 200, 10, 8, 7),

    # 竖屏+横向
    ("竖屏", "横向", "百度", 150, 0.6, 13.8, 11.25),
    ("竖屏", "横向", "百度", 200, 0.6, 12.8, 11.00),
    ("竖屏", "横向", "高德", 150, 0.7, 5.6, 10.67),
    ("竖屏", "横向", "高德", 200, 0.7, 5.3, 10.18),
    ("竖屏", "横向", "腾讯", 150, 0.8, 10.8, None),  # "无需调整"
    ("竖屏", "横向", "腾讯", 200, 0.8, 10.5, None),  # "无需调整"
    ("竖屏", "横向", "leaflet", 150, 10, 8, 10),
    ("竖屏", "横向", "leaflet", 200, 10, 8, 10),

    # 竖屏+竖向
    ("竖屏", "竖向", "百度", 150, 0.45, 8.4, 9.29),
    ("竖屏", "竖向", "百度", 200, 0.45, 9.6, 8.82),
    ("竖屏", "竖向", "高德", 150, -0.85, 5.4, 8.5),
    ("竖屏", "竖向", "高德", 200, -0.85, 5.8, 8.24),
    ("竖屏", "竖向", "腾讯", 150, 0.75, 8.8, 8.02),
    ("竖屏", "竖向", "腾讯", 200, 0.75, 8.5, 7.70),
    ("竖屏", "竖向", "leaflet", 150, 10, 8, None),    # "无需调整"
    ("竖屏", "竖向", "leaflet", 200, 13, 5, 8),
]

import math

print("=" * 80)
print("地图缩放系数分析")
print("=" * 80)

def calc_needed_factor(after_zoom, target_zoom, scale):
    """计算需要的系数（对数公式：target = after - log2(scale/100) * factor）"""
    log_val = math.log2(scale / 100)
    zoom_diff = target_zoom - after_zoom
    return zoom_diff / log_val

# 按地图和场景分组分析
by_map = {
    '百度': [],
    '高德': [],
    '腾讯': [],
    'leaflet': [],
}

for item in data:
    screen, track, map_name, scale, factor, after, target = item
    if target is None:
        continue

    zoom_diff = target - after
    needed = calc_needed_factor(after, target, scale)

    by_map[map_name].append({
        'screen': screen,
        'track': track,
        'scale': scale,
        'factor': factor,
        'after': after,
        'target': target,
        'diff': zoom_diff,
        'needed': needed
    })

# 分析每个地图
for map_name in ['百度', '高德', '腾讯', 'leaflet']:
    print(f"\n{'='*20} {map_name.upper()} {'='*55}")
    items = by_map[map_name]

    # 按场景分组
    scenes = {}
    for item in items:
        scene = f"{item['screen']}-{item['track']}"
        if scene not in scenes:
            scenes[scene] = {}
        if item['scale'] not in scenes[scene]:
            scenes[scene][item['scale']] = []
        scenes[scene][item['scale']].append(item)

    for scene in ['横屏-横向', '横屏-竖向', '竖屏-横向', '竖屏-竖向']:
        if scene not in scenes:
            continue

        print(f"\n  {scene}:")
        scales = scenes[scene]

        if 150 in scales:
            items_150 = scales[150]
            avg_factor = sum(i['needed'] for i in items_150) / len(items_150)
            item = items_150[0]
            print(f"    scale=150: after={item['after']:.1f}, target={item['target']:.1f}, "
                  f"当前factor={item['factor']}, 建议factor≈{avg_factor:.2f}")

        if 200 in scales:
            items_200 = scales[200]
            avg_factor = sum(i['needed'] for i in items_200) / len(items_200)
            item = items_200[0]
            print(f"    scale=200: after={item['after']:.1f}, target={item['target']:.1f}, "
                  f"当前factor={item['factor']}, 建议factor≈{avg_factor:.2f}")

print("\n" + "=" * 80)
print("建议系数汇总")
print("=" * 80)

# 建议系数
recommendations = {
    '百度': {
        '横屏-横向': 0.45,
        '横屏-竖向': 0.6,
        '竖屏-横向': 0.6,
        '竖屏-竖向': 0.1,  # 几乎不需要调整
    },
    '高德': {
        '横屏-横向': -2.5,  # 降低（原 -3.5 太大）
        '横屏-竖向': 0.7,
        '竖屏-横向': 0.7,
        '竖屏-竖向': -0.3,  # 略微增加
    },
    '腾讯': {
        '横屏-横向': 0.8,
        '横屏-竖向': 0.8,
        '竖屏-横向': 0.8,
        '竖屏-竖向': 0.5,
    },
    'leaflet': {
        '横屏-横向': 6,
        '横屏-竖向': 10,
        '竖屏-横向': 10,
        '竖屏-竖向': 13,
    },
}

for map_name, rec in recommendations.items():
    print(f"\n### {map_name}")
    print(f"{'场景':15s} | {'系数':10}")
    print("-" * 30)
    for scene, factor in rec.items():
        print(f"{scene:15s} | {factor:10}")
