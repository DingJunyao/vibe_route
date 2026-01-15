"""
道路标志相关 API
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.models.road_sign import RoadSignCache
from app.services.road_sign_service import road_sign_service
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter(prefix="/api/road-signs", tags=["road-signs"])


class RoadSignRequest(BaseModel):
    """道路标志生成请求"""
    sign_type: str = Field(..., description="标志类型: way(普通道路) 或 expwy(高速)")
    code: str = Field(..., description="道路编号，如 G221, S221, G5, G4511")
    province: Optional[str] = Field(None, description="省份简称，如 '豫', '晋'（仅高速用）")
    name: Optional[str] = Field(None, description="道路名称（可选）")


class RoadSignResponse(BaseModel):
    """道路标志响应"""
    svg: str
    cached: bool
    sign_type: str
    code: str
    province: Optional[str] = None
    name: Optional[str] = None


@router.post("/generate", response_model=RoadSignResponse)
async def generate_road_sign(
    request: RoadSignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    生成道路标志 SVG

    - **sign_type**: way (普通道路) 或 expwy (高速)
    - **code**: 道路编号
        - 普通道路: G221(国道-红), S221(省道-黄), X221(县道-白)
        - 高速: G5, G45, S21, S0211 等
    - **province**: 省份简称，仅省级高速需要
    - **name**: 道路名称，可选
    """
    if request.sign_type not in ('way', 'expwy'):
        raise HTTPException(status_code=400, detail="sign_type 必须是 'way' 或 'expwy'")

    if not request.code or len(request.code) < 2:
        raise HTTPException(status_code=400, detail="道路编号格式错误")

    try:
        svg_content, cached = await road_sign_service.get_or_create_sign(
            db=db,
            sign_type=request.sign_type,
            code=request.code,
            province=request.province,
            name=request.name,
        )

        return RoadSignResponse(
            svg=svg_content,
            cached=cached,
            sign_type=request.sign_type,
            code=request.code,
            province=request.province,
            name=request.name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


class RoadSignListItem(BaseModel):
    """道路标志列表项"""
    id: str
    code: str
    province: Optional[str] = None
    name: Optional[str] = None
    sign_type: str


@router.get("/list", response_model=list[RoadSignListItem])
async def list_road_signs(
    sign_type: Optional[str] = Query(None, description="筛选标志类型"),
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取已生成的道路标志列表
    """
    caches = await road_sign_service.get_list(db, sign_type, limit)

    # 判断标志类型
    result = []
    for cache in caches:
        # 根据代码和属性判断类型
        if cache.province or cache.name or (cache.code and len(cache.code) >= 3):
            st = 'expwy'
        else:
            st = 'way'

        result.append(RoadSignListItem(
            id=cache.id,
            code=cache.code,
            province=cache.province,
            name=cache.name,
            sign_type=st,
        ))

    return result


class ClearCacheResponse(BaseModel):
    """清除缓存响应"""
    count: int


@router.post("/clear-cache", response_model=ClearCacheResponse)
async def clear_road_sign_cache(
    sign_type: Optional[str] = Query(None, description="筛选标志类型"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    清除道路标志缓存
    """
    count = await road_sign_service.clear_cache(db, sign_type)
    return ClearCacheResponse(count=count)
