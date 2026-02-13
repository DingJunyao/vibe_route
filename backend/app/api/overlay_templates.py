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


@router.get("/fonts/{font_id}/file")
async def get_font_file(
    font_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取字体文件（用于前端加载）- 无需认证，字体文件非敏感资源"""
    from app.models.overlay_template import Font
    from sqlalchemy import select
    from pathlib import Path

    result = await db.execute(
        select(Font).where(Font.id == font_id)
    )
    font = result.scalar_one_or_none()

    # 数据库中不存在，尝试从管理员字体目录（FONTS_DIR）读取
    if not font:
        if font_id.startswith('admin_'):
            from app.core.config import settings

            # 从 font_id 提取文件名（去掉 'admin_' 前缀）
            filename = font_id[6:]  # 去掉 'admin_' 前缀
            admin_fonts_dir = Path(settings.ROAD_SIGN_DIR).parent / 'fonts'

            # 尝试添加常见的字体扩展名
            for ext in ['.ttf', '.otf', '.ttc', '.woff2']:
                font_path = admin_fonts_dir / (filename + ext)
                if font_path.exists():
                    return _serve_font_file(font_path)

            # 如果都不存在，尝试直接用文件名
            font_path = admin_fonts_dir / filename
            if font_path.exists():
                return _serve_font_file(font_path)

        raise HTTPException(status.HTTP_404_NOT_FOUND, "字体不存在")

    # 读取字体文件
    font_path = Path(font.file_path)
    if not font_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "字体文件不存在")

    return _serve_font_file(font_path)


def _serve_font_file(font_path: Path):
    """Font file serving helper - uses cached WOFF2 if available"""
    from pathlib import Path
    from app.core.config import settings
    from io import BytesIO

    print(f"DEBUG: _serve_font_file called with font_path: {font_path}")

    # Initialize variables
    content = None
    mime_type = 'font/sfnt'  # Default MIME type

    # First, try to find the actual TTF file (with underscore)
    source_path = font_path

    # Check if pre-converted WOFF2 exists (for GB 5765 fonts)
    fonts_dir = Path(settings.ROAD_SIGN_DIR).parent / 'fonts'
    woff2_dir = fonts_dir / 'woff2_cache'

    # Generate cache filename
    if font_path.name.endswith('.ttf'):
        woff2_name = font_path.name.replace('.ttf', '.woff2')
    elif font_path.name.endswith('.otf'):
        woff2_name = font_path.name.replace('.otf', '.woff2')
    else:
        woff2_name = font_path.name + '.woff2'

    woff2_path = woff2_dir / woff2_name

    if woff2_path.exists():
        # Check if cache is newer than source
        source_mtime = source_path.stat().st_mtime
        woff2_mtime = woff2_path.stat().st_mtime
        if woff2_mtime >= source_mtime:
            # Use cached WOFF2
            with open(woff2_path, 'rb') as f:
                content = f.read()
            mime_type = 'font/woff2'
            print(f"DEBUG: Using cached WOFF2: {woff2_path.name} ({len(content)} bytes)")
            logger.info(f"Serving cached WOFF2: {woff2_path.name} ({len(content)} bytes)")

    # If no cached content, read and convert original file
    if content is None:
        print(f"DEBUG: Reading and converting source file: {source_path}")
        with open(source_path, 'rb') as f:
            content = f.read()

        original_size = len(content)
        logger.info(f"Serving original font file: {font_path.name} ({original_size} bytes)")

        # Determine MIME type based on file extension
        suffix = font_path.suffix.lower()

        if suffix in ('.ttf', '.otf', '.ttc'):
            # For TTF/OTF files, try to convert to WOFF2
            # Only do full conversion for GB 5765 fonts (jtbz_A, jtbz_B, jtbz_C)
            # Other fonts can be directly served as original format
            gb5765_fonts = ['jtbz_A.ttf', 'jtbz_B.ttf', 'jtbz_C.ttf',
                            'admin_jtbz_A.ttf', 'admin_jtbz_B.ttf', 'admin_jtbz_C.ttf']
            is_gb5765_font = font_path.name in gb5765_fonts

            if is_gb5765_font:
                # GB 5765 fonts need table cleanup for browser compatibility
                try:
                    from fontTools.ttLib import TTFont

                    font = TTFont(BytesIO(content))
                    original_tables = list(font.keys())

                    # Remove problematic tables
                    # vmtx requires vhea, so remove both or neither
                    # post table may be corrupted, remove and rebuild a minimal one
                    problematic_tables = []
                    for table_tag in font.keys():
                        if table_tag in ('VDMX', 'GASP', 'GDEF', 'GPOS', 'GSUB', 'gasp', 'gvar', 'fvar', 'STAT', 'trak', 'kern'):
                            problematic_tables.append(table_tag)
                        # Remove vhea and vmtx together (vmtx depends on vhea)
                        elif table_tag in ('vhea', 'vmtx'):
                            problematic_tables.append(table_tag)
                        # Remove post table (will rebuild a minimal one)
                        elif table_tag == 'post':
                            problematic_tables.append(table_tag)

                    if problematic_tables:
                        print(f"DEBUG: Removing {len(problematic_tables)} problematic tables from {font_path.name}")

                    for table_tag in problematic_tables:
                        try:
                            del font[table_tag]
                        except:
                            pass

                    # Rebuild post table (minimal version)
                    try:
                        from fontTools.ttLib import newTable
                        font['post'] = newTable('post')
                        # Set required attributes for post table header
                        font['post'].formatType = 3.0
                        font['post'].italicAngle = 0.0
                        font['post'].underlinePosition = -100
                        font['post'].underlineThickness = 50
                        font['post'].isFixedPitch = 0
                        font['post'].minMemType42 = 0
                        font['post'].maxMemType42 = 0
                        font['post'].minMemType1 = 0
                        font['post'].maxMemType1 = 0
                        print(f"DEBUG: Rebuilt post table for {font_path.name}")
                    except Exception as e:
                        print(f"DEBUG: Failed to rebuild post table: {e}")
                        raise  # 让错误传播

                    # Save as WOFF2
                    woff2_output = BytesIO()
                    font.save(woff2_output, 'WOFF2')

                    content = woff2_output.getvalue()
                    mime_type = 'font/woff2'

                    print(f"DEBUG: Converted {font_path.name} to WOFF2 ({len(content)} bytes)")

                    # Save to cache for future use
                    try:
                        woff2_path.parent.mkdir(exist_ok=True)
                        with open(woff2_path, 'wb') as f:
                            f.write(content)
                        print(f"DEBUG: Cached WOFF2 to {woff2_path}")
                    except Exception as e:
                        print(f"DEBUG: Failed to cache WOFF2: {e}")

                except Exception as e:
                    print(f"DEBUG: Failed to convert {font_path.name}: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                # Non-GB5765 fonts: just convert to WOFF2 without modifying tables
                try:
                    from fontTools.ttLib import TTFont

                    font = TTFont(BytesIO(content))
                    woff2_output = BytesIO()
                    font.save(woff2_output, 'WOFF2')

                    content = woff2_output.getvalue()
                    mime_type = 'font/woff2'

                    print(f"DEBUG: Converted {font_path.name} to WOFF2 ({len(content)} bytes)")

                    # Save to cache for future use
                    try:
                        woff2_path.parent.mkdir(exist_ok=True)
                        with open(woff2_path, 'wb') as f:
                            f.write(content)
                        print(f"DEBUG: Cached WOFF2 to {woff2_path}")
                    except Exception as e:
                        print(f"DEBUG: Failed to cache WOFF2: {e}")

                except Exception as e:
                    print(f"DEBUG: Failed to convert {font_path.name} to WOFF2: {e}")
                    # Keep original content

                    # Determine original MIME type
                    if suffix == '.ttf':
                        mime_type = 'font/sfnt'
                    elif suffix == '.otf':
                        mime_type = 'font/otf'
                    elif suffix == '.ttc':
                        mime_type = 'font/collection'
        elif suffix == '.woff':
            mime_type = 'font/woff'
        elif suffix == '.woff2':
            mime_type = 'font/woff2'

    # Ensure we have content to return
    if content is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to read font file")

    from fastapi import Response
    return Response(
        content=content,
        media_type=mime_type,
        headers={
            'Cache-Control': 'public, max-age=31536000',
            'Access-Control-Allow-Origin': '*',
        }
    )


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
