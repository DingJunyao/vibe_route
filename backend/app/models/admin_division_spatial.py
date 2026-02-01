"""
PostGIS 空间扩展模型

用于 PostgreSQL + PostGIS 环境，存储行政区划的几何数据。
"""
from sqlalchemy import Column, Integer, ForeignKey
from app.core.database import Base


class AdminDivisionSpatial(Base):
    """
    PostGIS 空间扩展表

    仅在 PostgreSQL + PostGIS 环境下使用。
    geom 字段在迁移脚本中创建。
    """
    __tablename__ = "admin_divisions_spatial"

    division_id = Column(
        Integer,
        ForeignKey("admin_divisions.id", ondelete="CASCADE"),
        primary_key=True
    )

    # geom 字段在迁移脚本中创建，类型为 GEOMETRY(POLYGON, 4326) 或 GEOGRAPHY(POLYGON, 4326)
    # geom = Column(Geometry('POLYGON', 4326))

    def __repr__(self):
        return f"<AdminDivisionSpatial(division_id={self.division_id})>"
