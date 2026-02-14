# PostGIS 几何导入与统计排除修复

**日期**: 2026-02-02

## 问题描述

1. **PostGIS 几何问题**：对于启用 PostGIS 的数据库，在线导入行政区划数据时没有建立 PostGIS 几何
2. **统计排除问题**：行政区划统计中"缺少关联代码的区县记录"包含了正常情况（直辖市区县、省辖县级单位）

## 设计方案

### 问题 1：PostGIS 几何导入

#### 根本原因

`import_from_datav_online()` 只将基本信息保存到 `admin_divisions` 表，GeoJSON 中的 geometry 数据被丢弃，没有保存到 `admin_divisions_spatial` 表。

#### 解决方案

在 `_import_datav_feature()` 中同时保存几何到 PostGIS 表。

#### 实现细节

1. **PostGIS 可用性检测** (`_is_postgis_available`)
   - 检查 `settings.DATABASE_TYPE == "postgresql"`
   - 查询 `pg_extension` 表确认 postgis 扩展存在
   - **自动补全空间表结构** (`_ensure_spatial_table`)：
     - 如果 `admin_divisions_spatial` 表不存在，自动创建
     - 如果表存在但 `geom` 字段不存在，自动添加
     - 自动创建 GIST 空间索引

2. **几何坐标转换** (`DataVGeoService.convert_geometry_to_wgs84`)
   - DataV 在线数据使用 GCJ02 坐标系
   - 转换为 WGS84 存储
   - 支持 Polygon 和 MultiPolygon 类型

3. **修改 `_import_datav_feature()`**
   - 新增 `save_postgis` 参数
   - 保存记录后，如果 PostGIS 可用，插入几何到空间表

4. **修改 `import_from_datav_online()`**
   - 开始前检测 PostGIS 可用性
   - 传递 `save_postgis` 参数

### 问题 2：统计排除逻辑

#### 根本原因

以下情况 `city_code` 为空是正常的，不应显示为"缺少关联代码"：
- 直辖市区县：`province_code[:2]` 在 `['11', '12', '31', '50']`
- 省辖县级单位：`parent_code` 以 `0000` 结尾

#### 解决方案

修改 `get_admin_division_stats()` 查询，排除这些正常情况。

### 问题 3：本地地理编码 PostGIS 回退

#### 根本原因

`LocalGeocodingService` 在初始化时根据数据库类型判断是否使用 PostGIS，但没有检测 PostGIS 空间表是否有数据。如果表为空，查询会返回空结果。

#### 解决方案

在 `LocalGeocodingService` 中添加 PostGIS 可用性检测（`_check_postgis_available`）：
- 检查 PostGIS 扩展是否安装
- 检查 `admin_divisions_spatial` 表是否有数据
- 如果不可用，自动回退到边界框查询

## 注意事项

**后启用 PostGIS 的情况**：如果在未启用 PostGIS 的 PostgreSQL 环境下初始化并导入了行政区划数据，后来启用了 PostGIS，需要**重新导入行政区划数据**才能使用 PostGIS 空间查询。因为之前导入的数据没有保存几何信息到 `admin_divisions_spatial` 表。

## 涉及文件

1. `backend/app/services/admin_division_import_service.py`
2. `backend/app/services/datav_geo_service.py`
3. `backend/app/api/admin.py`
4. `backend/app/gpxutil_wrapper/local_geocoding.py`
