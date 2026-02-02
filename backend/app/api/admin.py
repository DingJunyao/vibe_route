"""
管理员相关 API 路由
"""
import asyncio
from typing import List, Dict
from pathlib import Path
import yaml
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case
from loguru import logger

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
        show_road_sign_in_region_tree=configs.get("show_road_sign_in_region_tree", True),
        spatial_backend=configs.get("spatial_backend", "auto"),
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

    # 注意：font_config 此时已经是字典，不需要再调用 model_dump()
    # ConfigUpdate 中的 FontConfig 会被自动转换为字典

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
        show_road_sign_in_region_tree=configs.get("show_road_sign_in_region_tree", True),
        spatial_backend=configs.get("spatial_backend", "auto"),
    )


@router.get("/database-info")
async def get_database_info(
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取数据库信息（用于判断是否显示 PostGIS 设置）

    返回：
    - database_type: sqlite, mysql, postgresql
    - postgis_enabled: PostGIS 是否可用（仅 PostgreSQL）
    """
    from sqlalchemy import text
    from app.core.config import settings

    result = {
        "database_type": settings.DATABASE_TYPE,
        "postgis_enabled": False,
    }

    # 检测 PostGIS 是否启用（仅 PostgreSQL）
    if settings.DATABASE_TYPE == "postgresql":
        try:
            check_result = await db.execute(
                text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'postgis')")
            )
            result["postgis_enabled"] = check_result.scalar_one()
        except Exception:
            result["postgis_enabled"] = False

    return result


@router.get("/admin-division-stats")
async def get_admin_division_stats(
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取行政区划数据统计

    返回各层级的数量，以及是否有边界框/PostGIS 几何数据。
    """
    from sqlalchemy import text
    from app.models.admin_division import AdminDivision

    stats = {
        "total": 0,
        "by_level": {},
        "has_bounds": 0,
        "has_postgis": 0,
        "sample_missing_codes": []
    }

    try:
        # 按层级统计
        for level in ["province", "city", "area"]:
            result = await db.execute(
                select(func.count(AdminDivision.id)).where(AdminDivision.level == level)
            )
            count = result.scalar() or 0
            stats["by_level"][level] = count
            stats["total"] += count

        # 有边界框的记录数
        result = await db.execute(
            select(func.count(AdminDivision.id)).where(
                and_(
                    AdminDivision.min_lat.isnot(None),
                    AdminDivision.max_lat.isnot(None),
                    AdminDivision.min_lon.isnot(None),
                    AdminDivision.max_lon.isnot(None)
                )
            )
        )
        stats["has_bounds"] = result.scalar() or 0

        # 检查 PostGIS 表
        try:
            result = await db.execute(
                text("SELECT COUNT(*) FROM admin_divisions_spatial")
            )
            stats["has_postgis"] = result.scalar() or 0
        except Exception:
            stats["has_postgis"] = 0

        # 检查缺少 city_code 的区县记录（排除正常情况）
        # 正常情况：直辖市区县、省辖县级单位
        # 直辖市代码前两位：11(北京)、12(天津)、31(上海)、50(重庆)
        MUNICIPALITY_PREFIXES = ['11', '12', '31', '50']
        result = await db.execute(
            select(
                AdminDivision.code,
                AdminDivision.name,
                AdminDivision.city_code,
                AdminDivision.province_code
            ).where(
                and_(
                    AdminDivision.level == "area",
                    AdminDivision.city_code.is_(None),
                    # 排除直辖市区县
                    func.left(AdminDivision.province_code, 2).notin_(MUNICIPALITY_PREFIXES),
                    # 排除省辖县级单位（parent_code 直接指向省级，以 0000 结尾）
                    or_(
                        AdminDivision.parent_code.is_(None),
                        ~AdminDivision.parent_code.like('%0000')
                    )
                )
            ).limit(5)
        )
        for row in result.fetchall():
            stats["sample_missing_codes"].append({
                "code": row[0],
                "name": row[1],
                "city_code": row[2],
                "province_code": row[3]
            })

    except Exception as e:
        stats["error"] = str(e)

    return stats


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
    from app.core.database import async_session_maker

    async with async_session_maker() as db:
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
        finally:
            await db.close()

    return {"message": "字体已删除"}


# ========== 行政区划数据管理 ==========

@router.get("/admin-division-stats")
async def get_admin_division_stats(
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取行政区划数据统计（管理员）
    """
    from app.models.admin_division import AdminDivision
    from sqlalchemy import text

    stats = {}

    # 各层级统计
    for level in ["province", "city", "area"]:
        result = await db.execute(
            select(func.count(AdminDivision.id)).where(
                and_(
                    AdminDivision.level == level,
                    AdminDivision.is_valid == True
                )
            )
        )
        stats[level] = result.scalar() or 0

    # 检查 PostGIS 可用性
    try:
        result = await db.execute(
            text("SELECT COUNT(*) FROM admin_divisions_spatial")
        )
        stats["postgis_count"] = result.scalar() or 0
        stats["postgis_enabled"] = True
    except Exception:
        stats["postgis_enabled"] = False
        stats["postgis_count"] = 0

    # 检查边界框数据
    result = await db.execute(
        select(func.count(AdminDivision.id)).where(
            and_(
                AdminDivision.min_lat.isnot(None),
                AdminDivision.is_valid == True
            )
        )
    )
    stats["bounds_count"] = result.scalar() or 0

    return stats


@router.post("/import-admin-divisions")
async def import_admin_divisions(
    force: bool = Query(False, description="是否强制重新导入"),
    skip_geojson: bool = Query(False, description="是否跳过 GeoJSON 导入"),
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    导入行政区划数据（管理员）

    从 area_code.sqlite 和 area_geojson/ 导入数据。
    """
    import asyncio
    from app.services.admin_division_import_service import AdminDivisionImportService

    # 检查现有数据
    from app.models.admin_division import AdminDivision
    result = await db.execute(
        select(func.count(AdminDivision.id))
    )
    existing_count = result.scalar() or 0

    if existing_count > 0 and not force:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"数据库中已有 {existing_count} 条行政区划数据，使用 force=true 强制重新导入"
        )

    # 执行导入
    service = AdminDivisionImportService()

    # 进度跟踪
    progress = {"current": 0, "total": 0, "level": ""}

    def progress_callback(level, current, total):
        progress["level"] = level
        progress["current"] = current
        progress["total"] = total

    # 1. 从 SQLite 导入
    stats = await service.import_from_sqlite(
        db,
        progress_callback=progress_callback,
        force=force
    )

    # 2. 从 GeoJSON 导入边界框
    if not skip_geojson:
        bounds_count = await service.import_geojson_bounds(
            db,
            progress_callback=progress_callback
        )
        stats["bounds"] = bounds_count

    # 3. PostGIS 几何导入
    database_type = getattr(settings, 'DATABASE_TYPE', 'sqlite')
    if database_type == "postgresql":
        postgis_count = await service.import_postgis_geometries(
            db,
            progress_callback=progress_callback
        )
        stats["postgis"] = postgis_count

    return {
        "message": "行政区划数据导入完成",
        "stats": stats
    }


@router.delete("/admin-divisions")
async def delete_admin_divisions(
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    删除所有行政区划数据（管理员）
    """
    from app.models.admin_division import AdminDivision
    from sqlalchemy import delete

    # 删除数据
    await db.execute(
        delete(AdminDivision)
    )
    await db.commit()

    return {"message": "行政区划数据已清空"}


# ========== 特殊地名映射管理 ==========

# 特殊地名映射路径
SPECIAL_PLACE_MAPPING_FILE = Path(settings.DATA_DIR) / "area_data" / "special_place_mapping.yaml"


class SpecialPlaceMappingItem(BaseModel):
    """特殊地名映射项"""
    name_zh: str  # 中文名称
    name_en: str  # 英文转写（不含后缀）


class SpecialPlaceMappingResponse(BaseModel):
    """特殊地名映射响应"""
    raw_yaml: str  # 原始 YAML 文件内容（保留注释和格式）
    mappings: Dict[str, str]  # 中文名称 -> 英文转写（解析后的映射，用于前端显示）
    total: int


class UpdateSpecialPlaceMappingRequest(BaseModel):
    """更新特殊地名映射请求"""
    yaml_content: str  # 原始 YAML 内容（保留注释和格式）


@router.get("/special-place-mapping", response_model=SpecialPlaceMappingResponse)
async def get_special_place_mapping(
    current_admin: User = Depends(get_current_admin_user),
):
    """
    获取特殊地名映射表（管理员）

    返回原始 YAML 内容和解析后的映射数据。
    前端可以使用 raw_yaml 进行编辑以保留注释和格式。
    """
    if not SPECIAL_PLACE_MAPPING_FILE.exists():
        return SpecialPlaceMappingResponse(
            raw_yaml="# 特殊地名英文映射表\n",
            mappings={},
            total=0
        )

    with open(SPECIAL_PLACE_MAPPING_FILE, "r", encoding="utf-8") as f:
        raw_yaml = f.read()

    # 解析映射用于前端显示
    mappings = yaml.safe_load(raw_yaml) or {}

    return SpecialPlaceMappingResponse(
        raw_yaml=raw_yaml,
        mappings=mappings,
        total=len(mappings)
    )


@router.put("/special-place-mapping")
async def update_special_place_mapping(
    request: UpdateSpecialPlaceMappingRequest,
    current_admin: User = Depends(get_current_admin_user),
):
    """
    更新特殊地名映射表（管理员）

    接受原始 YAML 内容，直接写入文件以保留注释和格式。
    """
    # 验证 YAML 格式
    try:
        mappings = yaml.safe_load(request.yaml_content) or {}
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"YAML 格式错误: {str(e)}")

    # 确保目录存在
    SPECIAL_PLACE_MAPPING_FILE.parent.mkdir(parents=True, exist_ok=True)

    # 直接写入原始 YAML 内容
    with open(SPECIAL_PLACE_MAPPING_FILE, "w", encoding="utf-8") as f:
        f.write(request.yaml_content)

    return {"message": f"已更新 {len(mappings)} 条特殊地名映射"}


@router.post("/special-place-mapping/regenerate")
async def regenerate_name_en(
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    重新生成所有行政区划的英文名称（管理员）

    使用最新的特殊地名映射表重新生成英文名称。
    """
    from app.models.admin_division import AdminDivision
    from app.utils.pinyin_generator import name_to_pinyin

    # 查询所有行政区划
    result = await db.execute(select(AdminDivision))
    divisions = list(result.scalars().all())

    # 加载特殊地名映射
    if SPECIAL_PLACE_MAPPING_FILE.exists():
        with open(SPECIAL_PLACE_MAPPING_FILE, "r", encoding="utf-8") as f:
            special_mapping = yaml.safe_load(f) or {}
    else:
        special_mapping = {}

    updated = 0
    for div in divisions:
        # 生成新的英文名称
        new_name_en = name_to_pinyin(div.name, div.level, special_mapping)
        if div.name_en != new_name_en:
            div.name_en = new_name_en
            updated += 1

    await db.commit()

    return {
        "message": "英文名称重新生成完成",
        "stats": {
            "total": len(divisions),
            "updated": updated
        }
    }


# ========== 边界数据管理 ==========

class BoundsImportResponse(BaseModel):
    """边界数据导入响应"""
    message: str
    stats: Dict[str, int]


@router.post("/test-upload")
async def test_upload(
    file: UploadFile = File(..., description="测试文件上传"),
    current_admin: User = Depends(get_current_admin_user),
):
    """测试文件上传接口（管理员）"""
    import uuid
    import shutil

    # 读取文件信息
    content = await file.read()
    file_size = len(content)

    logger.info(f"测试上传: filename={file.filename}, content_type={file.content_type}, size={file_size}")

    # 保存到临时目录
    temp_dir = Path(settings.TEMP_DIR) / f"test_upload_{uuid.uuid4()}"
    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"创建临时目录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"无法创建临时目录: {e}"
        )

    test_path = temp_dir / "test.bin"
    try:
        with open(test_path, "wb") as f:
            f.write(content)
    except Exception as e:
        logger.error(f"保存文件失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"无法保存文件: {e}"
        )

    # 清理
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        logger.warning(f"清理临时目录失败: {e}")

    return {
        "message": "文件上传测试成功",
        "file_info": {
            "filename": file.filename,
            "content_type": file.content_type,
            "size": file_size
        }
    }


@router.post("/import-bounds-data", deprecated=True)
async def import_bounds_data(
    file: UploadFile = File(..., description="ZIP 或 RAR 压缩文件，包含 GeoJSON 数据"),
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    [已弃用] 上传边界数据文件并创建后台导入任务（管理员）

    ⚠️ 此端点已弃用，请使用 /admin/admin-divisions/import/online 或
    /admin/admin-divisions/import/upload 替代。

    支持 ZIP 和 RAR 格式。
    压缩文件应包含 GeoJSON 文件，文件名格式为行政区划代码（如 110000.json）。

    返回任务 ID，前端可以通过轮询 /admin/tasks/{task_id} 获取处理进度。
    """
    import asyncio
    import uuid
    from pathlib import Path

    from app.utils.archive_helper import ArchiveExtractor
    from app.services.task_service import task_service

    # 检查文件扩展名
    filename = file.filename or "upload"
    logger.info(f"[边界导入] 接收到文件上传: {filename}")

    if not ArchiveExtractor.is_supported(filename):
        logger.warning(f"[边界导入] 不支持的文件格式: {filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件格式。请上传 ZIP 或 RAR 文件。"
        )

    # 创建临时目录
    temp_dir = Path(settings.TEMP_DIR) / f"bounds_import_{uuid.uuid4()}"
    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"[边界导入] 创建临时目录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"无法创建临时目录: {e}"
        )

    # 生成安全的文件名（防止路径遍历）
    safe_filename = Path(filename).name
    archive_path = temp_dir / safe_filename

    try:
        # 流式保存上传的文件
        logger.info(f"[边界导入] 开始保存文件: {archive_path}")
        with open(archive_path, "wb") as f:
            total_size = 0
            while chunk := await file.read(1024 * 1024):  # 每次读取 1MB
                f.write(chunk)
                total_size += len(chunk)
            logger.info(f"[边界导入] 文件保存完成，大小: {total_size} bytes")

        # 检查文件大小
        file_size = archive_path.stat().st_size
        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="上传的文件为空。"
            )

        # 创建后台任务
        task = await task_service.create_task(db, current_admin.id, "bounds_import")
        logger.info(f"[边界导入] 创建任务 {task.id}")

        # 在后台异步处理导入（不阻塞响应）
        asyncio.create_task(
            _process_bounds_import_task(
                task_id=task.id,
                archive_path=str(archive_path),
                temp_dir=str(temp_dir),
                filename=filename
            )
        )

        return {
            "message": "文件上传成功，正在后台处理",
            "task_id": task.id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[边界导入] 上传失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传失败: {str(e)}"
        )


async def _process_bounds_import_task(
    task_id: int,
    archive_path: str,
    temp_dir: str,
    filename: str
):
    """
    [已弃用] 后台处理边界数据导入任务

    ⚠️ 此函数已弃用，仅为兼容旧版 /import-bounds-data 端点保留。
    """
    import asyncio
    import json
    from pathlib import Path

    from app.core.database import async_session_maker
    from app.models.admin_division import AdminDivision
    from app.utils.archive_helper import ArchiveExtractor, clean_temp_directory
    from app.services.task_service import task_service

    temp_path = Path(temp_dir)
    archive_file = Path(archive_path)

    logger.info(f"[边界导入] 任务 {task_id} 开始处理")

    async with async_session_maker() as db:
        try:
            # 更新状态为运行中
            await task_service.update_task(db, task_id, status="running", progress=5)

            # 在线程池中提取压缩文件（避免阻塞事件循环）
            logger.info(f"[边界导入] 任务 {task_id} 开始提取压缩文件")
            extracted_files = await asyncio.to_thread(ArchiveExtractor.extract, archive_file, temp_path)
            logger.info(f"[边界导入] 任务 {task_id} 提取完成，共 {len(extracted_files)} 个文件")

            await task_service.update_task(db, task_id, progress=10)

            # 在线程池中查找 GeoJSON 文件
            geojson_files = await asyncio.to_thread(ArchiveExtractor.list_geojson_files, temp_path)
            logger.info(f"[边界导入] 任务 {task_id} 找到 {len(geojson_files)} 个 GeoJSON 文件")

            if not geojson_files:
                raise ValueError(
                    f"未找到 GeoJSON 文件。提取的文件: {[Path(f).name for f in extracted_files[:10]]}"
                )

            # 导入边界数据
            updated = 0
            errors = []
            total_features = 0

            for i, geojson_file in enumerate(geojson_files):
                try:
                    # 在线程池中读取 JSON 文件
                    data = await asyncio.to_thread(_read_geojson_file, geojson_file)

                    features = data.get("features", [])
                    features_count = len(features)
                    total_features += features_count
                    logger.info(f"[边界导入] 任务 {task_id} 处理 {geojson_file.name}: {features_count} 个 features")

                    for feature in features:
                        code = feature.get("properties", {}).get("id")
                        if code:
                            result = await db.execute(
                                select(AdminDivision).where(AdminDivision.code == code)
                            )
                            division = result.scalar_one_or_none()
                            if division:
                                coords = _extract_coordinates_from_geometry(feature.get("geometry", {}))
                                if coords:
                                    division.min_lat = int(min(c[0] for c in coords) * 1e6)
                                    division.max_lat = int(max(c[0] for c in coords) * 1e6)
                                    division.min_lon = int(min(c[1] for c in coords) * 1e6)
                                    division.max_lon = int(max(c[1] for c in coords) * 1e6)
                                    updated += 1

                    # 每处理一个文件更新一次进度
                    progress = 10 + int(80 * (i + 1) / len(geojson_files))
                    await task_service.update_task(db, task_id, progress=progress)
                    await db.commit()

                    # 让出控制权，允许其他请求处理
                    await asyncio.sleep(0)

                except Exception as e:
                    logger.error(f"[边界导入] 任务 {task_id} 处理文件 {geojson_file.name} 失败: {e}")
                    errors.append(f"{geojson_file.name}: {str(e)}")

            # 任务完成
            result_summary = f"更新 {updated} 条记录，共 {total_features} 个 features"
            await task_service.update_task(
                db, task_id,
                status="completed",
                progress=100,
                result_path=result_summary
            )

            logger.info(f"[边界导入] 任务 {task_id} 完成: {result_summary}")

        except Exception as e:
            logger.error(f"[边界导入] 任务 {task_id} 失败: {e}")
            await task_service.update_task(
                db, task_id,
                status="failed",
                error_message=str(e)
            )

        finally:
            # 在线程池中清理临时目录
            await asyncio.to_thread(clean_temp_directory, temp_path)


def _read_geojson_file(file_path: Path) -> dict:
    """[已弃用] 在线程池中读取 GeoJSON 文件"""
    import json
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/tasks/{task_id}")
async def get_bounds_import_task(
    task_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取边界导入任务状态（管理员）
    """
    from app.services.task_service import task_service
    from app.models.task import Task

    task = await task_service.get_task(db, task_id)

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )

    # 只有管理员或任务创建者可以查看
    if task.user_id != current_admin.id and not current_admin.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此任务"
        )

    return {
        "id": task.id,
        "type": task.type,
        "status": task.status,
        "progress": task.progress,
        "result_path": task.result_path,
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat(),
        "is_finished": task.is_finished,
    }


def _extract_coordinates_from_geometry(geometry: dict) -> list:
    """从几何对象中提取所有坐标（本地副本）"""
    geom_type = geometry.get("type")
    coords = geometry.get("coordinates", [])

    if geom_type == "Polygon":
        return [(lat, lon) for ring in coords for lon, lat in ring]
    elif geom_type == "MultiPolygon":
        result = []
        for polygon in coords:
            for ring in polygon:
                result.extend([(lat, lon) for lon, lat in ring])
        return result
    return []


@router.get("/bounds-stats")
async def get_bounds_stats(
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取边界数据统计（管理员）
    """
    from app.models.admin_division import AdminDivision

    # 各层级统计
    result = await db.execute(
        select(
            AdminDivision.level,
            func.count(AdminDivision.id),
            func.sum(case((AdminDivision.min_lat != None, 1), else_=0))
        ).group_by(AdminDivision.level)
    )
    level_stats = {}
    for row in result:
        level_stats[row[0]] = {
            "total": row[1],
            "with_bounds": row[2] or 0
        }

    # 缺少边界框的省份统计（包含省份名称和缺少的地区列表）
    # 子查询：获取省份名称
    province_subquery = (
        select(AdminDivision.code, AdminDivision.name)
        .where(AdminDivision.level == "province")
        .subquery()
    )

    # 先获取原始数据：省份代码、省份名称、地区名称
    result = await db.execute(
        select(
            AdminDivision.province_code,
            province_subquery.c.name.label("province_name"),
            AdminDivision.name.label("area_name")
        ).join(
            province_subquery,
            AdminDivision.province_code == province_subquery.c.code
        ).where(
            and_(
                AdminDivision.level == "area",
                AdminDivision.min_lat == None
            )
        ).order_by(AdminDivision.province_code, AdminDivision.name)
    )

    # 在 Python 中分组统计
    from collections import defaultdict
    province_areas = defaultdict(list)
    for row in result:
        province_areas[row[0]].append({
            "province_name": row[1],
            "area_name": row[2]
        })

    # 转换为目标格式并排序（按缺少数量降序，取前10）
    missing_list = []
    for province_code, areas in province_areas.items():
        missing_list.append({
            "province_code": province_code,
            "province_name": areas[0]["province_name"],
            "missing_count": len(areas),
            "missing_areas": "；".join(a["area_name"] for a in areas)
        })

    # 按缺少数量降序排序，取前10
    missing_list.sort(key=lambda x: x["missing_count"], reverse=True)
    missing_by_province = missing_list[:10]

    return {
        "by_level": level_stats,
        "missing_by_province": missing_by_province
    }


# ========== DataV GeoJSON 行政区划导入（新） ==========

class DataVImportRequest(BaseModel):
    """DataV 在线导入请求"""
    province_codes: List[str] | None = None  # 省级代码列表，None 表示全国
    force: bool = False  # 是否强制覆盖
    bounds_only: bool = False  # 仅更新边界数据


class DataVImportResponse(BaseModel):
    """导入响应"""
    message: str
    task_id: int | None = None
    stats: Dict | None = None


@router.get("/admin-divisions/status")
async def get_admin_divisions_status(
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取行政区划数据状态（管理员）

    返回各层级数量、边界数据完整度等信息。
    """
    from app.models.admin_division import AdminDivision

    result = {
        "total": 0,
        "by_level": {},
        "has_bounds": 0,
        "has_center": 0,
        "last_updated": None,
    }

    try:
        # 各层级统计
        for level in ["province", "city", "area"]:
            count_result = await db.execute(
                select(func.count(AdminDivision.id)).where(
                    and_(
                        AdminDivision.level == level,
                        AdminDivision.is_valid == True
                    )
                )
            )
            count = count_result.scalar() or 0
            result["by_level"][level] = count
            result["total"] += count

        # 有边界框的记录数
        bounds_result = await db.execute(
            select(func.count(AdminDivision.id)).where(
                and_(
                    AdminDivision.min_lat.isnot(None),
                    AdminDivision.is_valid == True
                )
            )
        )
        result["has_bounds"] = bounds_result.scalar() or 0

        # 有中心点的记录数
        center_result = await db.execute(
            select(func.count(AdminDivision.id)).where(
                and_(
                    AdminDivision.center_lat.isnot(None),
                    AdminDivision.is_valid == True
                )
            )
        )
        result["has_center"] = center_result.scalar() or 0

        # 最后更新时间
        latest_result = await db.execute(
            select(func.max(AdminDivision.updated_at)).where(
                AdminDivision.is_valid == True
            )
        )
        latest = latest_result.scalar()
        if latest:
            result["last_updated"] = latest.isoformat()

    except Exception as e:
        result["error"] = str(e)

    return result


@router.post("/admin-divisions/import/online", response_model=DataVImportResponse)
async def import_admin_divisions_online(
    request: DataVImportRequest,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    从阿里 DataV 在线拉取并导入行政区划数据（管理员）

    这是一个长时间运行的操作，会创建后台任务。
    返回 task_id 用于查询进度。
    """
    import asyncio
    from app.services.task_service import task_service

    # 创建后台任务
    task = await task_service.create_task(db, current_admin.id, "datav_import")
    logger.info(f"[DataV导入] 创建任务 {task.id}")

    # 在后台异步处理
    asyncio.create_task(
        _process_datav_import_task(
            task_id=task.id,
            province_codes=request.province_codes,
            force=request.force,
            bounds_only=request.bounds_only,
        )
    )

    return DataVImportResponse(
        message="导入任务已创建，正在后台处理",
        task_id=task.id
    )


async def _process_datav_import_task(
    task_id: int,
    province_codes: List[str] | None,
    force: bool,
    bounds_only: bool,
):
    """后台处理 DataV 导入任务"""
    from app.core.database import async_session_maker
    from app.services.admin_division_import_service import AdminDivisionImportService
    from app.services.task_service import task_service

    async def update_progress(progress: int):
        """使用独立会话更新进度，避免会话状态冲突"""
        try:
            async with async_session_maker() as progress_db:
                await task_service.update_task(progress_db, task_id, progress=progress)
        except Exception as e:
            logger.warning(f"[DataV导入] 更新进度失败: {e}")

    async with async_session_maker() as db:
        try:
            await task_service.update_task(db, task_id, status="running", progress=5)

            service = AdminDivisionImportService()

            def progress_callback(message: str, current: int, total: int):
                # 异步更新进度（使用独立会话）
                progress = 5 + int(90 * current / total) if total > 0 else 5
                asyncio.create_task(update_progress(progress))
                logger.info(f"[DataV导入] {message} ({current}/{total})")

            if bounds_only:
                # 仅更新边界
                from app.services.datav_geo_service import datav_geo_service

                if province_codes:
                    features = await datav_geo_service.fetch_provinces_selective(
                        province_codes, progress_callback
                    )
                else:
                    features = await datav_geo_service.fetch_all_recursive(
                        progress_callback=progress_callback
                    )

                # DataV 在线数据使用 GCJ02 坐标系，需要转换为 WGS84
                updated = await service.import_bounds_only(db, features, progress_callback, convert_coords=True)
                result = f"更新边界数据 {updated} 条"
            else:
                # 完整导入
                stats = await service.import_from_datav_online(
                    db,
                    province_codes=province_codes,
                    progress_callback=progress_callback,
                    force=force
                )
                result = f"导入完成: 省 {stats['provinces']}, 市 {stats['cities']}, 区县 {stats['areas']}"

            await task_service.update_task(
                db, task_id,
                status="completed",
                progress=100,
                result_path=result
            )
            logger.info(f"[DataV导入] 任务 {task_id} 完成: {result}")

        except Exception as e:
            logger.error(f"[DataV导入] 任务 {task_id} 失败: {e}")
            await task_service.update_task(
                db, task_id,
                status="failed",
                error_message=str(e)
            )


@router.post("/admin-divisions/import/upload", response_model=DataVImportResponse)
async def import_admin_divisions_upload(
    file: UploadFile = File(..., description="GeoJSON 压缩包（ZIP/RAR）"),
    force: bool = Query(False, description="是否强制覆盖"),
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    上传 GeoJSON 压缩包导入行政区划数据（管理员）

    支持 ZIP 和 RAR 格式，压缩包内应包含 DataV 格式的 GeoJSON 文件。
    """
    import asyncio
    import uuid
    from app.utils.archive_helper import ArchiveExtractor
    from app.services.task_service import task_service

    # 检查文件格式
    filename = file.filename or "upload"
    if not ArchiveExtractor.is_supported(filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持的文件格式，请上传 ZIP 或 RAR 文件"
        )

    # 创建临时目录
    temp_dir = Path(settings.TEMP_DIR) / f"datav_import_{uuid.uuid4()}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 保存上传的文件
    safe_filename = Path(filename).name
    archive_path = temp_dir / safe_filename

    try:
        content = await file.read()
        with open(archive_path, "wb") as f:
            f.write(content)

        if archive_path.stat().st_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="上传的文件为空"
            )

        # 创建后台任务
        task = await task_service.create_task(db, current_admin.id, "datav_upload_import")
        logger.info(f"[DataV上传导入] 创建任务 {task.id}")

        # 在后台异步处理
        asyncio.create_task(
            _process_datav_upload_task(
                task_id=task.id,
                archive_path=str(archive_path),
                temp_dir=str(temp_dir),
                force=force,
            )
        )

        return DataVImportResponse(
            message="文件上传成功，正在后台处理",
            task_id=task.id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[DataV上传导入] 上传失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传失败: {str(e)}"
        )


async def _process_datav_upload_task(
    task_id: int,
    archive_path: str,
    temp_dir: str,
    force: bool,
):
    """后台处理 DataV 压缩包导入任务"""
    import shutil
    from pathlib import Path
    from app.core.database import async_session_maker
    from app.services.admin_division_import_service import AdminDivisionImportService
    from app.services.task_service import task_service

    temp_path = Path(temp_dir)
    archive_file = Path(archive_path)

    async def update_progress(progress: int):
        """使用独立会话更新进度，避免会话状态冲突"""
        try:
            async with async_session_maker() as progress_db:
                await task_service.update_task(progress_db, task_id, progress=progress)
        except Exception as e:
            logger.warning(f"[DataV上传导入] 更新进度失败: {e}")

    async with async_session_maker() as db:
        try:
            await task_service.update_task(db, task_id, status="running", progress=5)

            service = AdminDivisionImportService()

            def progress_callback(message: str, current: int, total: int):
                progress = 5 + int(90 * current / total) if total > 0 else 5
                asyncio.create_task(update_progress(progress))
                logger.info(f"[DataV上传导入] {message} ({current}/{total})")

            stats = await service.import_from_geojson_archive(
                db,
                archive_path=archive_file,
                progress_callback=progress_callback,
                force=force
            )

            result = f"导入完成: 省 {stats['provinces']}, 市 {stats['cities']}, 区县 {stats['areas']}, 文件 {stats['files']}"

            await task_service.update_task(
                db, task_id,
                status="completed",
                progress=100,
                result_path=result
            )
            logger.info(f"[DataV上传导入] 任务 {task_id} 完成: {result}")

        except Exception as e:
            logger.error(f"[DataV上传导入] 任务 {task_id} 失败: {e}")
            await task_service.update_task(
                db, task_id,
                status="failed",
                error_message=str(e)
            )

        finally:
            # 清理临时目录
            shutil.rmtree(temp_path, ignore_errors=True)


@router.get("/admin-divisions/import/progress/{task_id}")
async def get_admin_divisions_import_progress(
    task_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取行政区划导入任务进度（管理员）
    """
    from app.services.task_service import task_service

    task = await task_service.get_task(db, task_id)

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )

    # 只有管理员或任务创建者可以查看
    if task.user_id != current_admin.id and not current_admin.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此任务"
        )

    return {
        "id": task.id,
        "type": task.type,
        "status": task.status,
        "progress": task.progress,
        "result": task.result_path,
        "error": task.error_message,
        "created_at": task.created_at.isoformat(),
        "is_finished": task.is_finished,
    }


@router.get("/admin-divisions/provinces")
async def get_province_list(
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取省份列表（用于按省份导入选择）
    """
    from app.models.admin_division import AdminDivision

    result = await db.execute(
        select(AdminDivision.code, AdminDivision.name)
        .where(
            and_(
                AdminDivision.level == "province",
                AdminDivision.is_valid == True
            )
        )
        .order_by(AdminDivision.code)
    )

    provinces = [{"code": row[0], "name": row[1]} for row in result.fetchall()]

    # 如果数据库中没有省份数据，返回预设列表
    if not provinces:
        provinces = [
            {"code": "110000", "name": "北京市"},
            {"code": "120000", "name": "天津市"},
            {"code": "130000", "name": "河北省"},
            {"code": "140000", "name": "山西省"},
            {"code": "150000", "name": "内蒙古自治区"},
            {"code": "210000", "name": "辽宁省"},
            {"code": "220000", "name": "吉林省"},
            {"code": "230000", "name": "黑龙江省"},
            {"code": "310000", "name": "上海市"},
            {"code": "320000", "name": "江苏省"},
            {"code": "330000", "name": "浙江省"},
            {"code": "340000", "name": "安徽省"},
            {"code": "350000", "name": "福建省"},
            {"code": "360000", "name": "江西省"},
            {"code": "370000", "name": "山东省"},
            {"code": "410000", "name": "河南省"},
            {"code": "420000", "name": "湖北省"},
            {"code": "430000", "name": "湖南省"},
            {"code": "440000", "name": "广东省"},
            {"code": "450000", "name": "广西壮族自治区"},
            {"code": "460000", "name": "海南省"},
            {"code": "500000", "name": "重庆市"},
            {"code": "510000", "name": "四川省"},
            {"code": "520000", "name": "贵州省"},
            {"code": "530000", "name": "云南省"},
            {"code": "540000", "name": "西藏自治区"},
            {"code": "610000", "name": "陕西省"},
            {"code": "620000", "name": "甘肃省"},
            {"code": "630000", "name": "青海省"},
            {"code": "640000", "name": "宁夏回族自治区"},
            {"code": "650000", "name": "新疆维吾尔自治区"},
            {"code": "710000", "name": "台湾省"},
            {"code": "810000", "name": "香港特别行政区"},
            {"code": "820000", "name": "澳门特别行政区"},
        ]

    return {"provinces": provinces}


@router.get("/admin-divisions/postgis-status")
async def get_postgis_sync_status(
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取 PostGIS 几何数据同步状态（管理员）

    返回 geometry 字段和 PostGIS 空间表的数据对比。
    """
    from app.services.admin_division_import_service import AdminDivisionImportService

    service = AdminDivisionImportService()
    status = await service.get_postgis_sync_status(db)

    return status


@router.post("/admin-divisions/sync-postgis")
async def sync_postgis_geometry(
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    从 geometry 字段同步数据到 PostGIS 空间表（管理员）

    这是一个长时间运行的操作，会创建后台任务。
    返回 task_id 用于查询进度。
    """
    import asyncio
    from app.services.task_service import task_service
    from app.services.admin_division_import_service import AdminDivisionImportService

    # 检查是否为 PostgreSQL
    from app.core.config import settings
    if settings.DATABASE_TYPE != "postgresql":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PostGIS 同步仅支持 PostgreSQL 数据库"
        )

    # 创建后台任务
    task = await task_service.create_task(db, current_admin.id, "postgis_sync")
    logger.info(f"[PostGIS同步] 创建任务 {task.id}")

    # 在后台异步处理
    asyncio.create_task(
        _process_postgis_sync_task(task_id=task.id)
    )

    return {
        "message": "同步任务已创建，正在后台处理",
        "task_id": task.id
    }


async def _process_postgis_sync_task(task_id: int):
    """后台处理 PostGIS 同步任务"""
    from app.core.database import async_session_maker
    from app.services.admin_division_import_service import AdminDivisionImportService
    from app.services.task_service import task_service

    async def update_progress(progress: int):
        """使用独立会话更新进度"""
        try:
            async with async_session_maker() as progress_db:
                await task_service.update_task(progress_db, task_id, progress=progress)
        except Exception as e:
            logger.warning(f"[PostGIS同步] 更新进度失败: {e}")

    async with async_session_maker() as db:
        try:
            await task_service.update_task(db, task_id, status="running", progress=5)

            service = AdminDivisionImportService()

            def progress_callback(message: str, current: int, total: int):
                progress = 5 + int(90 * current / total) if total > 0 else 5
                asyncio.create_task(update_progress(progress))
                logger.info(f"[PostGIS同步] {message} ({current}/{total})")

            stats = await service.sync_postgis_from_geometry(
                db,
                progress_callback=progress_callback
            )

            result = f"同步完成: 成功={stats['success']}, 跳过={stats['skipped']}, 失败={stats['failed']}"

            await task_service.update_task(
                db, task_id,
                status="completed",
                progress=100,
                result_path=result
            )
            logger.info(f"[PostGIS同步] 任务 {task_id} 完成: {result}")

        except Exception as e:
            logger.error(f"[PostGIS同步] 任务 {task_id} 失败: {e}")
            await task_service.update_task(
                db, task_id,
                status="failed",
                error_message=str(e)
            )

