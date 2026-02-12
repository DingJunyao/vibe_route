"""
覆盖层模板管理服务
"""
import os
import yaml
from typing import Optional, List
from pathlib import Path
from io import BytesIO

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, UploadFile

from app.models.overlay_template import OverlayTemplate, Font
from app.models.track import Track, TrackPoint
from app.models.user import User
from app.schemas.overlay_template import (
    OverlayTemplateCreate,
    OverlayTemplateUpdate,
    OverlayTemplateConfig,
    SafeAreaConfig,
    BackgroundConfig,
)
from app.services.overlay_renderer import OverlayRenderer, create_sample_point
from app.core.config import settings


class OverlayTemplateService:
    """覆盖层模板管理服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_template(
        self,
        data: OverlayTemplateCreate,
        user_id: int
    ) -> OverlayTemplate:
        """创建新模板"""
        template = OverlayTemplate(
            name=data.name,
            description=data.description,
            config=data.config.model_dump(),
            user_id=user_id,
            is_public=False,
            is_system=False,
        )
        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)
        return template

    async def get_template(self, template_id: int) -> Optional[OverlayTemplate]:
        """获取单个模板"""
        result = await self.db.execute(
            select(OverlayTemplate)
            .where(OverlayTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    async def list_templates(
        self,
        user_id: int,
        include_system: bool = True,
        only_public: bool = False
    ) -> List[OverlayTemplate]:
        """获取模板列表"""
        query = select(OverlayTemplate).where(OverlayTemplate.is_valid == True)

        if only_public:
            # 只返回公开和系统模板
            query = query.where(
                (OverlayTemplate.is_public == True) | (OverlayTemplate.is_system == True)
            )
        else:
            # 返回系统模板 + 公开模板 + 用户自己的模板
            query = query.where(
                (OverlayTemplate.is_system == True) |
                (OverlayTemplate.is_public == True) |
                (OverlayTemplate.user_id == user_id)
            )

        if not include_system:
            query = query.where(OverlayTemplate.is_system == False)

        query = query.order_by(OverlayTemplate.is_system.desc(), OverlayTemplate.created_at.desc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_template(
        self,
        template_id: int,
        data: OverlayTemplateUpdate,
        user_id: int
    ) -> Optional[OverlayTemplate]:
        """更新模板"""
        template = await self.get_template(template_id)
        if not template:
            return None

        # 权限检查：只能修改自己的模板或系统模板的副本
        if template.is_system:
            raise HTTPException(403, "系统模板不能直接修改，请先复制")

        if template.user_id != user_id:
            raise HTTPException(403, "无权修改此模板")

        # 更新字段
        if data.name is not None:
            template.name = data.name
        if data.description is not None:
            template.description = data.description
        if data.config is not None:
            template.config = data.config.model_dump()
        if data.is_public is not None:
            template.is_public = data.is_public

        await self.db.commit()
        await self.db.refresh(template)
        return template

    async def delete_template(self, template_id: int, user_id: int) -> bool:
        """删除模板（软删除）"""
        template = await self.get_template(template_id)
        if not template:
            return False

        # 权限检查
        if template.is_system:
            raise HTTPException(403, "系统模板不能删除")

        if template.user_id != user_id:
            raise HTTPException(403, "无权删除此模板")

        template.is_valid = False
        await self.db.commit()
        return True

    async def duplicate_template(
        self,
        template_id: int,
        user_id: int
    ) -> OverlayTemplate:
        """复制模板"""
        original = await self.get_template(template_id)
        if not original:
            raise HTTPException(404, "模板不存在")

        # 创建副本
        template = OverlayTemplate(
            name=f"{original.name} (副本)",
            description=original.description,
            config=original.config,
            user_id=user_id,
            is_public=False,
            is_system=False,
        )
        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)
        return template

    async def export_template_yaml(self, template_id: int) -> str:
        """导出模板为 YAML"""
        template = await self.get_template(template_id)
        if not template:
            raise HTTPException(404, "模板不存在")

        # 构建导出数据
        export_data = {
            'name': template.name,
            'description': template.description or '',
            'version': '1.0',
            'author': '系统预设' if template.is_system else '用户创建',
            **template.config
        }

        # 转换为 YAML
        yaml_content = yaml.dump(
            export_data,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False
        )

        return yaml_content

    async def import_template_yaml(
        self,
        yaml_content: str,
        user_id: int
    ) -> OverlayTemplate:
        """从 YAML 导入模板"""
        try:
            # 解析 YAML
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise HTTPException(400, f"YAML 格式错误: {str(e)}")

        # 提取元数据
        name = data.pop('name', '导入的模板')
        description = data.pop('description', '')
        data.pop('version', None)
        data.pop('author', None)

        # 验证配置
        try:
            config = OverlayTemplateConfig(**data)
        except Exception as e:
            raise HTTPException(400, f"配置验证失败: {str(e)}")

        # 创建模板
        template = OverlayTemplate(
            name=name,
            description=description,
            config=config.model_dump(),
            user_id=user_id,
            is_public=False,
            is_system=False,
        )
        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)
        return template

    async def generate_preview(
        self,
        template_id: int
    ) -> bytes:
        """生成模板预览图（使用模板配置中的画布尺寸）"""
        template = await self.get_template(template_id)
        if not template:
            raise HTTPException(404, "模板不存在")

        # 加载配置
        config = OverlayTemplateConfig(**template.config)

        # 使用模板配置中的画布尺寸
        width = config.canvas.width
        height = config.canvas.height

        # 创建渲染器
        renderer = OverlayRenderer(config, (width, height))

        # 使用示例数据生成预览
        sample_point = create_sample_point()
        img = renderer.render(sample_point)

        # 转换为字节
        buf = BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()

    async def generate_preview_with_config(
        self,
        config: OverlayTemplateConfig
    ) -> bytes:
        """使用指定配置生成预览图（不保存到数据库）"""
        # 使用模板配置中的画布尺寸
        width = config.canvas.width
        height = config.canvas.height

        # 创建渲染器
        renderer = OverlayRenderer(config, (width, height))

        # 使用示例数据生成预览
        sample_point = create_sample_point()
        img = renderer.render(sample_point)

        # 转换为字节
        buf = BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()


class FontService:
    """字体管理服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_fonts(self, user_id: int) -> List[Font]:
        """获取可用字体列表"""
        result = await self.db.execute(
            select(Font)
            .where(
                (Font.type == 'system') |
                (Font.type == 'admin') |
                ((Font.type == 'user') & (Font.owner_id == user_id))
            )
            .where(Font.is_valid == True)
        )
        return list(result.scalars().all())

    async def get_font(self, font_id: str) -> Optional[Font]:
        """获取单个字体"""
        result = await self.db.execute(
            select(Font)
            .where(Font.id == font_id)
            .where(Font.is_valid == True)
        )
        return result.scalar_one_or_none()

    async def upload_user_font(
        self,
        user_id: int,
        filename: str,
        file_content: bytes
    ) -> Font:
        """上传用户字体"""
        # 检查是否允许用户上传字体
        if not settings.overlay_allow_user_fonts:
            raise HTTPException(403, "用户字体上传功能已关闭")

        # 检查数量限制
        from sqlalchemy import func
        count_result = await self.db.execute(
            select(func.count(Font.id))
            .where(Font.owner_id == user_id)
            .where(Font.type == 'user')
            .where(Font.is_valid == True)
        )
        count = count_result.scalar() or 0
        if count >= settings.overlay_max_user_fonts:
            raise HTTPException(
                400,
                f"已达到字体数量上限 ({settings.overlay_max_user_fonts})"
            )

        # 检查大小限制
        file_size = len(file_content)
        size_result = await self.db.execute(
            select(func.sum(Font.file_size))
            .where(Font.owner_id == user_id)
            .where(Font.type == 'user')
            .where(Font.is_valid == True)
        )
        total_size = size_result.scalar() or 0
        max_size_bytes = settings.overlay_max_user_fonts_size_mb * 1024 * 1024
        if total_size + file_size > max_size_bytes:
            raise HTTPException(
                400,
                f"已达到存储空间上限 ({settings.overlay_max_user_fonts_size_mb}MB)"
            )

        # 保存文件
        upload_dir = Path(settings.UPLOAD_DIR) / "fonts" / "user"
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / filename
        with open(file_path, 'wb') as f:
            f.write(file_content)

        # 创建字体记录
        font = Font(
            id=f"user_{user_id}_{filename}",
            name=filename.rsplit('.', 1)[0],  # 去掉扩展名
            filename=filename,
            type='user',
            owner_id=user_id,
            file_path=str(file_path),
            file_size=file_size,
            supports_chinese=True,  # 假设支持中文
        )
        self.db.add(font)
        await self.db.commit()
        await self.db.refresh(font)

        return font

    async def delete_font(self, font_id: str, user_id: int, is_admin: bool) -> bool:
        """删除字体"""
        font = await self.get_font(font_id)
        if not font:
            return False

        # 权限检查
        if font.type == 'system':
            raise HTTPException(403, "系统字体不能删除")
        if font.type == 'admin' and not is_admin:
            raise HTTPException(403, "无权删除管理员字体")
        if font.type == 'user' and font.owner_id != user_id:
            raise HTTPException(403, "无权删除此字体")

        # 软删除
        font.is_valid = False
        await self.db.commit()
        return True


class OverlayExportService:
    """覆盖层导出服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def export_overlay_sequence(
        self,
        track_id: int,
        template_id: int,
        frame_rate: int,
        start_index: int,
        end_index: int,
        output_format: str,
        output_dir: Path
    ) -> tuple:
        """
        导出覆盖层序列（使用模板配置中的画布尺寸）

        Returns:
            (output_path, frame_count)
        """
        # 获取轨迹
        track_result = await self.db.execute(
            select(Track).where(Track.id == track_id)
        )
        track = track_result.scalar_one_or_none()
        if not track:
            raise HTTPException(404, "轨迹不存在")

        # 获取模板
        template_result = await self.db.execute(
            select(OverlayTemplate).where(OverlayTemplate.id == template_id)
        )
        template = template_result.scalar_one_or_none()
        if not template:
            raise HTTPException(404, "模板不存在")

        # 加载配置
        config = OverlayTemplateConfig(**template.config)

        # 使用模板配置中的画布尺寸
        width = config.canvas.width
        height = config.canvas.height

        # 创建渲染器
        renderer = OverlayRenderer(config, (width, height))

        # 获取轨迹点
        points_result = await self.db.execute(
            select(TrackPoint)
            .where(TrackPoint.track_id == track_id)
            .order_by(TrackPoint.time.asc(), TrackPoint.created_at.asc())
        )
        all_points = list(points_result.scalars().all())

        # 应用范围
        if end_index < 0 or end_index >= len(all_points):
            end_index = len(all_points) - 1
        points = all_points[start_index:end_index + 1]

        if not points:
            raise HTTPException(400, "指定范围内没有轨迹点")

        # 创建输出目录
        output_dir.mkdir(parents=True, exist_ok=True)

        # 生成图片序列
        frame_count = 0
        for i, point in enumerate(points):
            # 跳帧控制
            if frame_rate > 0 and i % frame_rate != 0:
                continue

            # 渲染
            img = renderer.render(point)

            # 保存
            filename = f"frame_{frame_count:06d}.png"
            img.save(output_dir / filename)
            frame_count += 1

        # 根据格式返回
        if output_format == 'zip':
            import zipfile
            zip_path = output_dir.parent / f"{output_dir.name}.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file in sorted(output_dir.glob("*.png")):
                    zf.write(file, file.name)

            # 清理临时文件
            for file in output_dir.glob("*"):
                file.unlink()
            output_dir.rmdir()

            return str(zip_path), frame_count
        else:
            return str(output_dir), frame_count
