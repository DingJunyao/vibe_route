"""
管理员相关 API 路由
"""
from typing import List
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.deps import get_current_admin_user
from app.models.user import User
from app.models.config import InviteCode
from app.schemas.user import UserResponse, UserUpdate, ResetPassword
from app.schemas.config import (
    ConfigResponse,
    ConfigUpdate,
    InviteCodeCreate,
    InviteCodeResponse,
    FontConfig,
    FontInfo,
)
from app.services.user_service import user_service
from app.services.config_service import config_service
from app.core.config import settings

router = APIRouter(prefix="/admin", tags=["管理员"])

# 字体文件目录（与 svg_gen.py 中的路径保持一致）
FONTS_DIR = Path(settings.ROAD_SIGN_DIR).parent / 'fonts'
FONTS_DIR.mkdir(exist_ok=True, parents=True)


# 分页响应模型
class PaginatedResponse(BaseModel):
    items: List
    total: int


# ========== 用户管理 ==========

@router.get("/users")
async def get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, description="搜索用户名或邮箱"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向"),
    roles: List[str] | None = Query(None, description="角色筛选"),
    statuses: List[str] | None = Query(None, description="状态筛选"),
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取用户列表（管理员）
    支持分页：page 和 page_size
    支持搜索：search 参数模糊搜索用户名或邮箱
    支持排序：sort_by 和 sort_order
    支持筛选：roles 和 statuses
    """
    skip = (page - 1) * page_size

    # 构建基础查询
    base_query = select(User).where(User.is_valid == True)

    # 搜索条件
    if search:
        search_pattern = f"%{search}%"
        base_query = base_query.where(
            (User.username.ilike(search_pattern)) | (User.email.ilike(search_pattern))
        )

    # 角色筛选
    if roles and len(roles) < 2:  # 没有全选时才筛选
        if "admin" in roles and "user" not in roles:
            base_query = base_query.where(User.is_admin == True)
        elif "user" in roles and "admin" not in roles:
            base_query = base_query.where(User.is_admin == False)

    # 状态筛选
    if statuses and len(statuses) < 2:  # 没有全选时才筛选
        if "active" in statuses and "inactive" not in statuses:
            base_query = base_query.where(User.is_active == True)
        elif "inactive" in statuses and "active" not in statuses:
            base_query = base_query.where(User.is_active == False)

    # 获取总数
    count_query = select(func.count(User.id)).where(User.is_valid == True)
    if search:
        search_pattern = f"%{search}%"
        count_query = count_query.where(
            (User.username.ilike(search_pattern)) | (User.email.ilike(search_pattern))
        )
    if roles and len(roles) < 2:
        if "admin" in roles and "user" not in roles:
            count_query = count_query.where(User.is_admin == True)
        elif "user" in roles and "admin" not in roles:
            count_query = count_query.where(User.is_admin == False)
    if statuses and len(statuses) < 2:
        if "active" in statuses and "inactive" not in statuses:
            count_query = count_query.where(User.is_active == True)
        elif "inactive" in statuses and "active" not in statuses:
            count_query = count_query.where(User.is_active == False)
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 排序
    order_column = getattr(User, sort_by, User.created_at)
    base_query = base_query.order_by(
        order_column.desc() if sort_order == "desc" else order_column.asc()
    )

    # 获取分页数据
    query = base_query.offset(skip).limit(page_size)
    result = await db.execute(query)
    users = result.scalars().all()
    items = [UserResponse.model_validate(u) for u in users]

    return {"items": items, "total": total}


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    更新用户信息（管理员）
    """
    user = await user_service.get_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 构建更新数据
    update_data = user_update.model_dump(exclude_unset=True)

    # 不允许修改自己的管理员状态和启用状态
    if user_id == current_admin.id:
        if "is_admin" in update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能修改自己的管理员状态",
            )
        if "is_active" in update_data and not update_data["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能禁用自己",
            )

    # 获取第一位用户（ID 最小的）
    first_user_result = await db.execute(
        select(User).where(User.is_valid == True).order_by(User.id).limit(1)
    )
    first_user = first_user_result.scalar_one_or_none()

    # 不允许修改/删除第一位用户的关键状态
    if first_user and user_id == first_user.id:
        if "is_admin" in update_data and not update_data["is_admin"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能取消首位用户的管理员状态",
            )
        if "is_active" in update_data and not update_data["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能禁用首位用户",
            )

    # 如果要取消管理员身份，检查是否至少还有一位管理员
    if user.is_admin and "is_admin" in update_data and not update_data["is_admin"]:
        admin_count_result = await db.execute(
            select(func.count(User.id)).where(
                User.is_valid == True,
                User.is_admin == True
            )
        )
        admin_count = admin_count_result.scalar()
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="系统至少需要保留一位管理员",
            )

    updated_user = await user_service.update(db, user, current_admin.id, **update_data)
    return UserResponse.model_validate(updated_user)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    软删除用户（管理员）
    """
    user = await user_service.get_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 不允许删除自己
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己",
        )

    # 获取第一位用户（ID 最小的）
    first_user_result = await db.execute(
        select(User).where(User.is_valid == True).order_by(User.id).limit(1)
    )
    first_user = first_user_result.scalar_one_or_none()

    # 不允许删除第一位用户
    if first_user and user_id == first_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除首位用户",
        )

    # 如果要删除的是管理员，检查是否至少还有一位管理员
    if user.is_admin:
        admin_count_result = await db.execute(
            select(func.count(User.id)).where(
                User.is_valid == True,
                User.is_admin == True
            )
        )
        admin_count = admin_count_result.scalar()
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="系统至少需要保留一位管理员",
            )

    await user_service.delete(db, user, current_admin.id)
    return {"message": "用户已删除"}


@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    password_data: ResetPassword,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    重置用户密码（管理员）
    """
    user = await user_service.get_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 不允许重置自己的密码
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能重置自己的密码",
        )

    # 获取第一位用户（ID 最小的）
    first_user_result = await db.execute(
        select(User).where(User.is_valid == True).order_by(User.id).limit(1)
    )
    first_user = first_user_result.scalar_one_or_none()

    # 不允许重置第一位用户的密码
    if first_user and user_id == first_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能重置首位用户的密码",
        )

    await user_service.reset_password(db, user, password_data.new_password, current_admin.id)
    return {"message": "密码已重置"}


# ========== 系统配置 ==========

@router.get("/config", response_model=ConfigResponse)
async def get_config(
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取系统配置（管理员）
    """
    configs = await config_service.get_all_configs(db)

    # 获取字体配置
    font_config = configs.get("font_config", {})
    if isinstance(font_config, str):
        import json
        font_config = json.loads(font_config)

    return ConfigResponse(
        registration_enabled=configs.get("registration_enabled", True),
        invite_code_required=configs.get("invite_code_required", False),
        default_map_provider=configs.get("default_map_provider", "osm"),
        geocoding_provider=configs.get("geocoding_provider", "nominatim"),
        geocoding_config=configs.get("geocoding_config", {}),
        map_layers=configs.get("map_layers", {}),
        font_config=FontConfig(**font_config) if font_config else FontConfig(),
    )


@router.put("/config", response_model=ConfigResponse)
async def update_config(
    config_update: ConfigUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    更新系统配置（管理员）
    """
    update_data = config_update.model_dump(exclude_unset=True)

    # 处理字体配置
    if "font_config" in update_data and update_data["font_config"]:
        update_data["font_config"] = update_data["font_config"].model_dump()

    configs = await config_service.update_config(db, update_data, current_admin.id)

    # 获取字体配置
    font_config = configs.get("font_config", {})
    if isinstance(font_config, str):
        import json
        font_config = json.loads(font_config)

    return ConfigResponse(
        registration_enabled=configs.get("registration_enabled", True),
        invite_code_required=configs.get("invite_code_required", False),
        default_map_provider=configs.get("default_map_provider", "osm"),
        geocoding_provider=configs.get("geocoding_provider", "nominatim"),
        geocoding_config=configs.get("geocoding_config", {}),
        map_layers=configs.get("map_layers", {}),
        font_config=FontConfig(**font_config) if font_config else FontConfig(),
    )


# ========== 邀请码管理 ==========

@router.post("/invite-codes", response_model=InviteCodeResponse)
async def create_invite_code(
    invite_code_data: InviteCodeCreate,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    创建邀请码（管理员）
    """
    invite_code = await config_service.create_invite_code(
        db,
        code=invite_code_data.code,
        max_uses=invite_code_data.max_uses,
        created_by=current_admin.id,
        expires_in_days=invite_code_data.expires_in_days,
    )
    return InviteCodeResponse(
        id=invite_code.id,
        code=invite_code.code,
        max_uses=invite_code.max_uses,
        used_count=invite_code.used_count,
        created_by=invite_code.created_by,
        created_at=invite_code.created_at,
        expires_at=invite_code.expires_at,
        is_valid=invite_code.is_valid,
    )


@router.get("/invite-codes")
async def get_invite_codes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取邀请码列表（管理员）
    支持分页：page 和 page_size
    """
    skip = (page - 1) * page_size

    # 获取总数
    count_query = select(func.count(InviteCode.id)).where(InviteCode.is_valid == True)
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 获取分页数据
    invite_codes = await config_service.get_invite_codes(db, skip=skip, limit=page_size)
    items = [
        InviteCodeResponse(
            id=ic.id,
            code=ic.code,
            max_uses=ic.max_uses,
            used_count=ic.used_count,
            created_by=ic.created_by,
            created_at=ic.created_at,
            expires_at=ic.expires_at,
            is_valid=ic.is_valid,
        )
        for ic in invite_codes
    ]

    return {"items": items, "total": total}


@router.delete("/invite-codes/{invite_code_id}")
async def delete_invite_code(
    invite_code_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    软删除邀请码（管理员）
    """
    from app.models.config import InviteCode
    from sqlalchemy import select, and_

    result = await db.execute(
        select(InviteCode).where(
            and_(InviteCode.id == invite_code_id, InviteCode.is_valid == True)
        )
    )
    invite_code = result.scalar_one_or_none()

    if not invite_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="邀请码不存在",
        )

    await config_service.delete_invite_code(db, invite_code, current_admin.id)
    return {"message": "邀请码已删除"}


# ========== 道路标志字体管理 ==========

@router.get("/fonts")
async def get_fonts(
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取字体文件列表（管理员）
    返回所有字体文件和当前激活的字体配置
    """
    # 获取字体文件列表
    fonts = []
    for font_file in FONTS_DIR.iterdir():
        if font_file.is_file():
            stat = font_file.stat()
            fonts.append(FontInfo(
                filename=font_file.name,
                size=stat.st_size,
            ))

    # 获取当前激活的字体配置
    configs = await config_service.get_all_configs(db)
    font_config = configs.get("font_config", {})
    if isinstance(font_config, str):
        import json
        font_config = json.loads(font_config)

    active_fonts = FontConfig(**font_config) if font_config else FontConfig()

    return {
        "fonts": fonts,
        "active_fonts": active_fonts,
    }


@router.post("/fonts/{font_type}/set-active")
async def set_active_font(
    font_type: str,
    filename: str,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    设置激活的字体文件
    font_type: a (A型), b (B型), c (C型)
    filename: 字体文件名（不含路径）
    """
    if font_type not in ("a", "b", "c"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="字体类型必须是 a, b 或 c",
        )

    # 验证文件存在
    filename = Path(filename).name
    file_path = FONTS_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="字体文件不存在",
        )

    # 更新配置
    configs = await config_service.get_all_configs(db)
    font_config = configs.get("font_config", {})
    if isinstance(font_config, str):
        import json
        font_config = json.loads(font_config)

    # 设置激活字体
    font_config[f"font_{font_type}"] = filename

    await config_service.update_config(db, {"font_config": font_config}, current_admin.id)

    return {"message": "字体设置成功"}


@router.post("/fonts/upload")
async def upload_font(
    file: UploadFile = File(...),
    current_admin: User = Depends(get_current_admin_user),
):
    """
    上传字体文件（管理员）
    文件保持原始名称，不添加类型前缀
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件名不能为空",
        )

    # 验证文件扩展名
    allowed_extensions = {".ttf", ".otf", ".ttc"}
    file_ext = Path(file.filename).suffix.lower() if file.filename else ""
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件格式，支持的格式: {', '.join(allowed_extensions)}",
        )

    # 使用原始文件名保存
    filename = Path(file.filename).name
    target_path = FONTS_DIR / filename

    # 检查文件是否已存在
    if target_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件 {filename} 已存在，请先删除旧文件或重命名后上传",
        )

    content = await file.read()

    with open(target_path, "wb") as f:
        f.write(content)

    return {"message": "字体上传成功", "filename": filename}


@router.delete("/fonts/{filename}")
async def delete_font(
    filename: str,
    current_admin: User = Depends(get_current_admin_user),
):
    """
    删除字体文件（管理员）
    """
    # 安全检查：确保文件名不包含路径
    filename = Path(filename).name
    file_path = FONTS_DIR / filename

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="字体文件不存在",
        )

    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的文件路径",
        )

    # 删除文件
    file_path.unlink()

    # 更新配置（如果删除的文件是激活字体，则清除该配置）
    async for db in get_db():
        try:
            configs = await config_service.get_all_configs(db)
            font_config = configs.get("font_config", {})
            if isinstance(font_config, str):
                import json
                font_config = json.loads(font_config)

            # 检查是否为激活字体，是则清除
            if font_config.get("font_a") == filename:
                font_config.pop("font_a", None)
            if font_config.get("font_b") == filename:
                font_config.pop("font_b", None)
            if font_config.get("font_c") == filename:
                font_config.pop("font_c", None)

            await config_service.update_config(
                db,
                {"font_config": font_config},
                current_admin.id,
            )
            break
        finally:
            await db.close()

    return {"message": "字体已删除"}
