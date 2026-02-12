"""
覆盖层模板 API 路由
"""
import logging
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Form
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_admin_user
from app.core.config import settings
from app.models.user import User
from app.schemas.overlay_template import (
    OverlayTemplateCreate,
    OverlayTemplateUpdate,
    OverlayTemplateResponse,
    OverlayTemplateListResponse,
    FontResponse,
    FontListResponse,
    OverlayExportRequest,
    PreviewWithConfigRequest,
    OverlayTemplateConfig,
)
from app.services.overlay_template_service import (
    OverlayTemplateService,
    FontService,
    OverlayExportService,
)

router = APIRouter(prefix="/overlay-templates", tags=["覆盖层模板"])
logger = logging.getLogger(__name__)


# ============================================================================
# 模板管理
# ============================================================================

@router.get("", response_model=OverlayTemplateListResponse)
async def list_templates(
    include_system: bool = Query(True, description="是否包含系统模板"),
    only_public: bool = Query(False, description="只返回公开模板"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取覆盖层模板列表"""
    service = OverlayTemplateService(db)
    templates = await service.list_templates(
        user_id=current_user.id,
        include_system=include_system,
        only_public=only_public
    )
    return OverlayTemplateListResponse(total=len(templates), items=templates)


@router.get("/{template_id}", response_model=OverlayTemplateResponse)
async def get_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取单个覆盖层模板"""
    service = OverlayTemplateService(db)
    template = await service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    return template


@router.post("", response_model=OverlayTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: OverlayTemplateCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建新的覆盖层模板"""
    service = OverlayTemplateService(db)
    return await service.create_template(data, current_user.id)


@router.put("/{template_id}", response_model=OverlayTemplateResponse)
async def update_template(
    template_id: int,
    data: OverlayTemplateUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新覆盖层模板"""
    service = OverlayTemplateService(db)
    try:
        return await service.update_template(template_id, data, current_user.id)
    except HTTPException:
        raise


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除覆盖层模板"""
    service = OverlayTemplateService(db)
    await service.delete_template(template_id, current_user.id)


@router.post("/{template_id}/duplicate", response_model=OverlayTemplateResponse)
async def duplicate_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """复制覆盖层模板"""
    service = OverlayTemplateService(db)
    return await service.duplicate_template(template_id, current_user.id)


# ============================================================================
# 模板导入/导出
# ============================================================================

@router.get("/{template_id}/export")
async def export_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出模板为 YAML"""
    service = OverlayTemplateService(db)
    yaml_content = await service.export_template_yaml(template_id)

    return Response(
        content=yaml_content,
        media_type="text/yaml",
        headers={
            "Content-Disposition": f'attachment; filename="template_{template_id}.yaml"'
        }
    )


@router.post("/import")
async def import_template(
    file: UploadFile = File(..., description="YAML 文件"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """从 YAML 导入模板"""
    if not file.filename.endswith(('.yaml', '.yml')):
        raise HTTPException(400, "只支持 YAML 文件格式")

    content = await file.read()
    yaml_content = content.decode('utf-8')

    service = OverlayTemplateService(db)
    template = await service.import_template_yaml(yaml_content, current_user.id)
    return template


# ============================================================================
# 预览
# ============================================================================

@router.get("/{template_id}/preview")
async def preview_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """生成模板预览图（使用模板配置中的画布尺寸）"""
    service = OverlayTemplateService(db)
    image_bytes = await service.generate_preview(template_id)

    return Response(
        content=image_bytes,
        media_type="image/png",
    )


@router.post("/preview-with-config")
async def preview_with_config(
    request: PreviewWithConfigRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """使用指定配置生成预览图（不保存到数据库）"""
    service = OverlayTemplateService(db)
    image_bytes = await service.generate_preview_with_config(request.config)

    return Response(
        content=image_bytes,
        media_type="image/png",
    )


# ============================================================================
# 字体管理
# ============================================================================

@router.get("/fonts/list", response_model=FontListResponse)
async def list_fonts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取可用字体列表"""
    service = FontService(db)
    fonts = await service.list_fonts(current_user.id)
    return FontListResponse(total=len(fonts), items=fonts)


@router.post("/fonts/upload", response_model=FontResponse)
async def upload_font(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传自定义字体"""
    if not file.filename.endswith(('.ttf', '.otf', '.ttc', '.woff2')):
        raise HTTPException(400, "只支持 TTF/OTF/TTC/WOFF2 格式")

    content = await file.read()
    service = FontService(db)
    return await service.upload_user_font(
        user_id=current_user.id,
        filename=file.filename,
        file_content=content
    )


@router.delete("/fonts/{font_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_font(
    font_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除字体"""
    is_admin = current_user.is_admin
    service = FontService(db)
    await service.delete_font(font_id, current_user.id, is_admin)


# ============================================================================
# 导出覆盖层
# ============================================================================

@router.post("/tracks/{track_id}/export")
async def export_overlay(
    track_id: int,
    template_id: int = Form(...),
    frame_rate: int = Form(1),
    start_index: int = Form(0),
    end_index: int = Form(-1),
    output_format: str = Form("zip"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    导出覆盖层图片序列（使用模板配置中的画布尺寸）

    - template_id: 模板ID
    - frame_rate: 采样率（0=全部，1=每秒1帧）
    - start_index: 起始点索引
    - end_index: 结束点索引（-1=到最后）
    - output_format: 输出格式（zip 或 png_sequence）
    """
    from pathlib import Path
    from datetime import datetime, timezone

    service = OverlayExportService(db)

    # 创建输出目录
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir = Path(settings.EXPORT_DIR) / "overlays" / f"track_{track_id}_{timestamp}"

    try:
        output_path, frame_count = await service.export_overlay_sequence(
            track_id=track_id,
            template_id=template_id,
            frame_rate=frame_rate,
            start_index=start_index,
            end_index=end_index,
            output_format=output_format,
            output_dir=output_dir
        )

        if output_format == 'zip':
            # 返回文件
            return Response(
                content=Path(output_path).read_bytes(),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f'attachment; filename="overlay_{track_id}_{timestamp}.zip"'
                }
            )
        else:
            # 返回目录信息
            return {
                "output_path": output_path,
                "frame_count": frame_count
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导出覆盖层失败: {str(e)}")
        raise HTTPException(500, f"导出失败: {str(e)}")
