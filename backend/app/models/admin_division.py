"""
行政区划模型

用于本地地理编码服务（GDF），存储省/市/区三级行政区划数据。
兼容 SQLite / MySQL / PostgreSQL，PostgreSQL 环境下可选使用 PostGIS。
"""
from sqlalchemy import Column, String, Integer, Float, Text

from app.models.base import AuditMixin
from app.core.database import Base


class AdminDivision(Base, AuditMixin):
    """
    行政区划表

    存储省/市/区三级行政区划，用于本地反向地理编码。
    """
    __tablename__ = "admin_divisions"

    # 主键
    id = Column(Integer, primary_key=True, index=True)

    # 行政区划代码（6位标准代码）
    code = Column(String(12), nullable=False, unique=True, index=True, comment="行政区划代码")

    # 名称
    name = Column(String(100), nullable=False, comment="中文名称")
    name_en = Column(String(200), nullable=True, comment="英文名称（拼音+后缀）")

    # 层级：province/city/area
    level = Column(String(10), nullable=False, index=True, comment="层级：province/city/area")

    # 父级代码
    parent_code = Column(String(12), nullable=True, index=True, comment="上级行政区划代码")

    # 边界框（用于快速过滤，坐标 * 1e6 存储为整数）
    min_lat = Column(Integer, nullable=True, comment="最小纬度 * 1e6")
    max_lat = Column(Integer, nullable=True, comment="最大纬度 * 1e6")
    min_lon = Column(Integer, nullable=True, comment="最小经度 * 1e6")
    max_lon = Column(Integer, nullable=True, comment="最大经度 * 1e6")

    # 中心点坐标（用于地图显示，原始浮点数）
    center_lon = Column(Float, nullable=True, comment="中心点经度")
    center_lat = Column(Float, nullable=True, comment="中心点纬度")

    # 子级数量（用于判断不设区地级市）
    children_num = Column(Integer, nullable=True, comment="子级行政区划数量")

    # 几何数据（GeoJSON 格式，用于 shapely 多边形包含判断）
    geometry = Column(Text, nullable=True, comment="GeoJSON 多边形几何")

    # 关联字段（用于查询优化）
    province_code = Column(String(12), nullable=True, index=True, comment="省代码")
    city_code = Column(String(12), nullable=True, index=True, comment="市代码")

    def __repr__(self):
        return f"<AdminDivision(code={self.code}, name={self.name}, level={self.level})>"
