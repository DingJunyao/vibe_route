"""
初始化系统预设覆盖层模板

运行方式：python -m app.init_overlay_templates
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import async_session_maker
from app.models.overlay_template import OverlayTemplate
from app.schemas.overlay_template import (
    OverlayTemplateConfig,
    SafeAreaConfig,
    BackgroundConfig,
)


# 系统预设模板配置
SYSTEM_TEMPLATES = [
    {
        "name": "默认样式",
        "description": "底部信息条布局，包含区域、道路、速度、海拔",
        "config": OverlayTemplateConfig(
            safe_area=SafeAreaConfig(top=0.05, bottom=0.05, left=0.05, right=0.05),
            background=BackgroundConfig(color="#000000", opacity=0),
            elements=[
                {
                    "id": "area_name",
                    "type": "text",
                    "name": "区域名称",
                    "visible": True,
                    "position": {
                        "container_anchor": "bottom-left",
                        "element_anchor": "bottom-left",
                        "x": 0.02,
                        "y": -0.02,
                        "use_safe_area": True
                    },
                    "size": {"width": 0.25, "height": 0.08},
                    "content": {"source": "province", "prefix": "", "suffix": "", "format": "{}"},
                    "layout": {
                        "horizontal_align": "left",
                        "vertical_align": "bottom",
                        "wrap": False,
                        "line_height": 1.2
                    },
                    "style": {
                        "font_family": "system_msyh",
                        "font_size": 0.025,
                        "color": "#FFFFFF"
                    }
                },
                {
                    "id": "road_name",
                    "type": "text",
                    "name": "道路名称",
                    "visible": True,
                    "position": {
                        "container_anchor": "bottom-left",
                        "element_anchor": "bottom-left",
                        "x": 0.02,
                        "y": -0.10,
                        "use_safe_area": True
                    },
                    "size": {"width": 0.40, "height": 0.06},
                    "content": {"source": "road_name", "prefix": "", "suffix": "", "format": "{}"},
                    "layout": {
                        "horizontal_align": "left",
                        "vertical_align": "bottom",
                        "wrap": False,
                        "line_height": 1.2
                    },
                    "style": {
                        "font_family": "system_msyh",
                        "font_size": 0.030,
                        "color": "#FFFFFF"
                    }
                },
                {
                    "id": "speed",
                    "type": "text",
                    "name": "速度",
                    "visible": True,
                    "position": {
                        "container_anchor": "bottom-right",
                        "element_anchor": "bottom-right",
                        "x": -0.02,
                        "y": -0.02,
                        "use_safe_area": True
                    },
                    "size": {"width": 0.15, "height": 0.08},
                    "content": {"source": "speed", "prefix": "", "suffix": "\nkm/h", "format": "{:.0f}"},
                    "layout": {
                        "horizontal_align": "right",
                        "vertical_align": "bottom",
                        "wrap": False,
                        "line_height": 1.0
                    },
                    "style": {
                        "font_family": "system_arial",
                        "font_size": 0.035,
                        "color": "#FFFFFF"
                    }
                }
            ]
        )
    },
    {
        "name": "极简风格",
        "description": "仅显示核心信息，右上角布局",
        "config": OverlayTemplateConfig(
            safe_area=SafeAreaConfig(top=0.05, bottom=0.05, left=0.05, right=0.05),
            background=None,
            elements=[
                {
                    "id": "speed_minimal",
                    "type": "text",
                    "name": "速度",
                    "visible": True,
                    "position": {
                        "container_anchor": "top-right",
                        "element_anchor": "top-right",
                        "x": -0.02,
                        "y": 0.02,
                        "use_safe_area": True
                    },
                    "size": {"width": 0.12, "height": 0.06},
                    "content": {"source": "speed", "prefix": "", "suffix": " km/h", "format": "{:.0f}"},
                    "layout": {
                        "horizontal_align": "right",
                        "vertical_align": "top",
                        "wrap": False,
                        "line_height": 1.0
                    },
                    "style": {
                        "font_family": "system_arial",
                        "font_size": 0.035,
                        "color": "#FFFFFF"
                    }
                }
            ]
        )
    },
    {
        "name": "电影风格",
        "description": "上下黑边，信息居中，适合电影感视频",
        "config": OverlayTemplateConfig(
            safe_area=SafeAreaConfig(top=0.08, bottom=0.08, left=0.05, right=0.05),
            background=BackgroundConfig(color="#000000", opacity=0.5),
            elements=[
                {
                    "id": "area_cinematic",
                    "type": "text",
                    "name": "区域",
                    "visible": True,
                    "position": {
                        "container_anchor": "bottom",
                        "element_anchor": "bottom",
                        "x": 0,
                        "y": -0.03,
                        "use_safe_area": False
                    },
                    "size": {"width": 0.30, "height": 0.05},
                    "content": {"source": "province", "prefix": "", "suffix": "", "format": "{}"},
                    "layout": {
                        "horizontal_align": "center",
                        "vertical_align": "bottom",
                        "wrap": False,
                        "line_height": 1.2
                    },
                    "style": {
                        "font_family": "system_msyh",
                        "font_size": 0.025,
                        "color": "#FFFFFF"
                    }
                },
                {
                    "id": "speed_cinematic",
                    "type": "text",
                    "name": "速度",
                    "visible": True,
                    "position": {
                        "container_anchor": "top",
                        "element_anchor": "top",
                        "x": 0,
                        "y": 0.03,
                        "use_safe_area": False
                    },
                    "size": {"width": 0.15, "height": 0.05},
                    "content": {"source": "speed", "prefix": "", "suffix": " km/h", "format": "{:.0f}"},
                    "layout": {
                        "horizontal_align": "center",
                        "vertical_align": "top",
                        "wrap": False,
                        "line_height": 1.0
                    },
                    "style": {
                        "font_family": "system_arial",
                        "font_size": 0.030,
                        "color": "#FFFFFF"
                    }
                }
            ]
        )
    },
    {
        "name": "完整信息",
        "description": "显示区域、道路、速度、海拔、时间等完整信息",
        "config": OverlayTemplateConfig(
            safe_area=SafeAreaConfig(top=0.05, bottom=0.05, left=0.05, right=0.05),
            background=BackgroundConfig(color="#000000", opacity=0.3),
            elements=[
                {
                    "id": "area_full",
                    "type": "text",
                    "name": "区域",
                    "visible": True,
                    "position": {
                        "container_anchor": "bottom-left",
                        "element_anchor": "bottom-left",
                        "x": 0.02,
                        "y": -0.02,
                        "use_safe_area": True
                    },
                    "size": {"width": 0.30, "height": 0.06},
                    "content": {"source": "province", "prefix": "", "suffix": "", "format": "{}"},
                    "layout": {
                        "horizontal_align": "left",
                        "vertical_align": "bottom",
                        "wrap": False,
                        "line_height": 1.2
                    },
                    "style": {
                        "font_family": "system_msyh",
                        "font_size": 0.022,
                        "color": "#FFFFFF"
                    }
                },
                {
                    "id": "road_full",
                    "type": "text",
                    "name": "道路",
                    "visible": True,
                    "position": {
                        "container_anchor": "bottom-left",
                        "element_anchor": "bottom-left",
                        "x": 0.02,
                        "y": -0.08,
                        "use_safe_area": True
                    },
                    "size": {"width": 0.40, "height": 0.06},
                    "content": {"source": "road_name", "prefix": "", "suffix": "", "format": "{}"},
                    "layout": {
                        "horizontal_align": "left",
                        "vertical_align": "bottom",
                        "wrap": True,
                        "max_lines": 2,
                        "line_height": 1.2
                    },
                    "style": {
                        "font_family": "system_msyh",
                        "font_size": 0.025,
                        "color": "#FFFFFF"
                    }
                },
                {
                    "id": "elevation_full",
                    "type": "text",
                    "name": "海拔",
                    "visible": True,
                    "position": {
                        "container_anchor": "bottom-right",
                        "element_anchor": "bottom-right",
                        "x": -0.02,
                        "y": -0.02,
                        "use_safe_area": True
                    },
                    "size": {"width": 0.12, "height": 0.06},
                    "content": {"source": "elevation", "prefix": "", "suffix": " m", "format": "{:.0f}"},
                    "layout": {
                        "horizontal_align": "right",
                        "vertical_align": "bottom",
                        "wrap": False,
                        "line_height": 1.0
                    },
                    "style": {
                        "font_family": "system_arial",
                        "font_size": 0.030,
                        "color": "#FFFFFF"
                    }
                },
                {
                    "id": "speed_full",
                    "type": "text",
                    "name": "速度",
                    "visible": True,
                    "position": {
                        "container_anchor": "bottom-right",
                        "element_anchor": "bottom-right",
                        "x": -0.15,
                        "y": -0.02,
                        "use_safe_area": True
                    },
                    "size": {"width": 0.12, "height": 0.06},
                    "content": {"source": "speed", "prefix": "", "suffix": " km/h", "format": "{:.0f}"},
                    "layout": {
                        "horizontal_align": "right",
                        "vertical_align": "bottom",
                        "wrap": False,
                        "line_height": 1.0
                    },
                    "style": {
                        "font_family": "system_arial",
                        "font_size": 0.030,
                        "color": "#FFFFFF"
                    }
                }
            ]
        )
    }
]


async def init_system_templates():
    """初始化系统预设模板"""
    async with async_session_maker() as db:
        for template_data in SYSTEM_TEMPLATES:
            # 检查是否已存在
            from sqlalchemy import select
            from app.models.overlay_template import OverlayTemplate

            result = await db.execute(
                select(OverlayTemplate)
                .where(OverlayTemplate.name == template_data["name"])
                .where(OverlayTemplate.is_system == True)
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"模板 '{template_data['name']}' 已存在，跳过")
                continue

            # 创建新模板
            template = OverlayTemplate(
                name=template_data["name"],
                description=template_data["description"],
                config=template_data["config"].model_dump(),
                user_id=None,  # 系统模板没有所有者
                is_public=True,
                is_system=True
            )
            db.add(template)

        await db.commit()
        print(f"系统模板初始化完成，共 {len(SYSTEM_TEMPLATES)} 个模板")


if __name__ == "__main__":
    asyncio.run(init_system_templates())
