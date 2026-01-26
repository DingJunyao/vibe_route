"""
道路标志相关 API
"""
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.models.road_sign import RoadSignCache
from app.services.road_sign_service import road_sign_service
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional

router = APIRouter(prefix="/road-signs", tags=["road-signs"])


class RoadSignRequest(BaseModel):
    """道路标志生成请求"""
    sign_type: str = Field(..., description="标志类型: way(普通道路) 或 expwy(高速)")
    code: str = Field(..., description="道路编号，如 G221, S221, G5, G4511")
    province: Optional[str] = Field(None, description="省份简称，如 '豫', '晋'（仅高速用）")
    name: Optional[str] = Field(None, description="道路名称（可选）")

    @field_validator('code')
    @classmethod
    def normalize_code(cls, v: str) -> str:
        """规范化道路编号：转大写"""
        return v.strip().upper()

    @model_validator(mode='after')
    def validate_road_sign(self) -> 'RoadSignRequest':
        """校验道路编号"""
        code = self.code
        sign_type = self.sign_type
        province = self.province

        if not code:
            raise ValueError("道路编号不能为空")

        if sign_type == 'way':
            # 普通道路：字母 + 三位数字
            if not re.match(r'^[A-Z]\d{3}$', code):
                raise ValueError("普通道路编号格式错误：应为字母 + 三位数字，如 G221、S221、X221")

        elif sign_type == 'expwy':
            # 高速公路：国家高速或省级高速
            if code.startswith('G'):
                # 国家高速：G + 1-4位数字
                if not re.match(r'^G\d{1,4}$', code):
                    raise ValueError("国家高速编号格式错误：应为 G + 1-4位数字，如 G5、G45、G4511")
            elif code.startswith('S'):
                # 省级高速：S + 纯数字(1-4位) 或 S + 字母 + 可选数字(0-3位)
                # 字母格式（第二位是字母）仅限四川省
                letter_format_match = re.match(r'^S([A-Z]\d{0,3})$', code)
                if letter_format_match:
                    # 字母格式，检查是否是四川省
                    if province != '川':
                        raise ValueError("字母格式的省级高速编号（如 SA、SC、SA1）仅限四川省使用，请使用纯数字编号（如 S1、S11）或选择四川省")
                elif not re.match(r'^S\d{1,4}$', code):
                    raise ValueError("省级高速编号格式错误：应为 S + 1-4位数字（如 S1、S11、S1111），或仅限四川省使用 S + 字母 + 可选数字（如 SA、SC、SA1）")
            else:
                raise ValueError("高速公路编号应以 G（国家高速）或 S（省级高速）开头")

        return self

    @field_validator('province')
    @classmethod
    def validate_province(cls, v: Optional[str], info) -> Optional[str]:
        """校验省份简称"""
        if v is None:
            return None

        province = v.strip()
        if not province:
            return None

        # 中国省份简称列表
        valid_provinces = {
            '京', '津', '冀', '晋', '蒙', '辽', '吉', '黑',
            '沪', '苏', '浙', '皖', '闽', '赣', '鲁', '豫',
            '鄂', '湘', '粤', '桂', '琼', '渝', '川', '贵',
            '云', '藏', '陕', '甘', '青', '宁', '新',
        }

        if province not in valid_provinces:
            raise ValueError(f"无效的省份简称：{v}。应为标准省份简称，如'京'、'津'、'冀'等")

        return province


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
        - 普通道路: 字母 + 三位数字，如 G221(国道-红), S221(省道-黄), X221(县道-白)
        - 高速公路:
          - 国家高速: G + 1-4位数字，如 G5, G45, G4511
          - 省级高速: S + 纯数字(1-4位) 或 S + 字母 + 可选数字
            如 S1, S11, S111, S1111 或 SA, SC, SA1, SA12（四川格式）
    - **province**: 省份简称，仅省级高速需要（如'京'、'津'、'冀'等）
    - **name**: 道路名称，可选

    注：编号自动转换为大写，如输入 g221 会自动转为 G221
    """
    if request.sign_type not in ('way', 'expwy'):
        raise HTTPException(status_code=400, detail="sign_type 必须是 'way' 或 'expwy'")

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
