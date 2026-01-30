# 常见问题

本文档收集了 Vibe Route 轨迹管理系统的常见问题及其解决方案。

## 目录

- [安装与部署](#安装与部署)
- [登录与认证](#登录与认证)
- [轨迹上传与处理](#轨迹上传与处理)
- [地图与可视化](#地图与可视化)
- [实时记录](#实时记录)
- [性能与优化](#性能与优化)
- [其他问题](#其他问题)

---

## 安装与部署

### Q: 后端启动失败，提示 "ModuleNotFoundError"

**A**: 确保已安装所有依赖：

```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Q: 数据库迁移失败

**A**: 检查以下几点：

1. 数据库服务是否运行
2. `backend/.env` 中的数据库配置是否正确
3. 数据库用户是否有足够权限

手动重置数据库：

```bash
# 删除现有数据库
rm backend/data/vibe_route.db

# 重新运行迁移
alembic upgrade head
```

### Q: 前端构建后访问空白

**A**: 检查以下几点：

1. API 地址配置是否正确（`frontend/.env.local`）
2. 后端服务是否运行
3. 浏览器控制台是否有错误信息

### Q: Docker 容器无法启动

**A**: 检查以下几点：

1. Docker 和 Docker Compose 是否安装
2. 端口是否被占用
3. 查看容器日志：

```bash
docker-compose logs -f
```

### Q: Nginx 502 Bad Gateway

**A**: 检查以下几点：

1. 后端服务是否运行
2. Nginx 配置中的 upstream 地址是否正确
3. 查看后端和 Nginx 日志

---

## 登录与认证

### Q: 忘记密码怎么办？

**A**: 目前系统不支持自助找回密码，需要联系管理员重置密码。

如果自己是管理员，可以重置其他用户的密码。

### Q: 首位注册用户为什么没有成为管理员？

**A**: 检查后端配置：

```env
FIRST_USER_IS_ADMIN=true
```

如果配置正确，可能是数据库中已有用户。检查数据库中的用户记录。

### Q: 如何查看当前用户是否是管理员？

**A**: 登录后，如果顶部导航栏有"后台管理"按钮，说明当前用户是管理员。

### Q: Token 过期怎么办？

**A**: Token 过期后会自动跳转到登录页，重新登录即可。

默认配置：
- 访问令牌：60 分钟
- 刷新令牌：7 天

---

## 轨迹上传与处理

### Q: 上传文件后没有反应

**A**: 检查以下几点：

1. 文件大小是否超过限制（默认 100 MB）
2. 文件格式是否支持（GPX/CSV/XLSX/KML/KMZ）
3. 查看浏览器控制台是否有错误
4. 检查后端日志

### Q: CSV 上传后没有数据

**A**: 确保 CSV 格式正确：

- 包含必需的列：`lat`（纬度）、`lon`（经度）
- 使用 UTF-8 编码
- 逗号分隔

如果使用自定义格式，需要在上传时指定列名映射。

### Q: 轨迹解析后位置偏移

**A**: 检查原始坐标系设置是否正确：

- **WGS84**：GPS 原始坐标，海外使用
- **GCJ02**：中国火星坐标系，高德/腾讯/天地图
- **BD09**：百度坐标系

如果不确定，可以尝试 WGS84。

### Q: 异步任务一直处于"处理中"

**A**: 可能的原因：

1. 文件过大，处理需要时间
2. 后端资源不足
3. 任务卡死

可以：
1. 刷新页面查看最新状态
2. 取消任务后重新上传
3. 检查后端日志

### Q: 地理编码填充失败

**A**: 可能的原因：

1. 坐标超出中国范围
2. 网络问题
3. 地理编码服务异常

可以在任务完成后，使用"导入数据"功能手动填充。

---

## 地图与可视化

### Q: 地图不显示

**A**: 检查以下几点：

1. 网络连接是否正常
2. 是否配置了正确的 API Key（百度/腾讯地图需要）
3. 浏览器控制台是否有错误
4. 尝试切换不同的底图

### Q: 地图显示位置偏移

**A**: 这是正常的，因为不同地图使用不同的坐标系：

- 高德/腾讯/天地图：GCJ02
- 百度地图：BD09
- OpenStreetMap：WGS84

系统会自动转换坐标，但可能有微小误差。

### Q: 海拔图/速度图不显示

**A**: 可能的原因：

1. 轨迹点没有海拔/速度数据
2. 数据格式不正确
3. 浏览器兼容性问题

### Q: 地图与图表不同步

**A**: 检查以下几点：

1. 使用推荐的浏览器（Chrome/Firefox）
2. 刷新页面
3. 检查浏览器控制台是否有 JavaScript 错误

### Q: "经过区域"为空

**A**: 可能的原因：

1. 地理编码填充失败
2. 轨迹在中国境外
3. 坐标系设置错误

可以尝试：
1. 修改原始坐标系后重新解析
2. 使用"导入数据"功能手动填充

---

## 实时记录

### Q: GPS Logger 上传失败

**A**: 检查以下几点：

1. 上传 URL 是否正确复制
2. Token 是否有效
3. 设备网络连接是否正常
4. 查看后端日志

### Q: 实时记录不更新

**A**: 可能的原因：

1. WebSocket 连接断开
2. 设备停止上传数据
3. 浏览器长时间待机

尝试：
1. 刷新页面
2. 检查设备 GPS Logger 应用
3. 查看浏览器控制台

### Q: 状态显示黄色（有故障）

**A**: 说明 WebSocket 连接断开，可能原因：

1. 网络问题
2. 服务器重启
3. 长时间待机

系统会自动尝试重连（3 秒间隔）。

### Q: 结束实时记录后轨迹消失

**A**: 这是正常行为，实时记录结束后会转换为普通轨迹。在轨迹列表中可以找到。

---

## 性能与优化

### Q: 大文件上传很慢

**A**: 优化建议：

1. 使用异步任务处理
2. 增加上传文件大小限制
3. 检查网络带宽
4. 考虑使用更小的文件（分割轨迹）

### Q: 页面加载缓慢

**A**: 优化建议：

1. 清理浏览器缓存
2. 减少同时显示的轨迹数量
3. 使用分页浏览
4. 检查服务器资源

### Q: 地图操作卡顿

**A**: 可能的原因：

1. 轨迹点数量过多
2. 浏览器性能不足
3. 网络问题

优化建议：
1. 简化轨迹（减少点数）
2. 使用更简单的底图
3. 关闭不必要的浏览器标签

### Q: 如何启用 PostGIS 提升性能？

**A**: 如果使用 PostgreSQL，启用 PostGIS 扩展可以显著提升空间查询性能（如附近轨迹搜索）。

#### 现有数据迁移

**可以**为已有数据启用 PostGIS。项目使用独立的空间扩展表，不影响主表数据：

**方式一：使用 Alembic 迁移**

```bash
# 1. 在 PostgreSQL 中启用 PostGIS 扩展
psql -U vibe_route -d vibe_route -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# 2. 运行迁移（会自动为现有数据创建空间索引）
cd backend
alembic upgrade head

# 3. 在后台管理中设置：空间计算后端 → PostGIS
```

**方式二：手动执行 SQL（适用于已有数据库）**

如果 Alembic 迁移记录已过时，可以直接执行 SQL：

```sql
-- 启用 PostGIS 扩展
CREATE EXTENSION IF NOT EXISTS postgis;

-- 删除旧表（如果存在且结构不对）
DROP TABLE IF EXISTS track_points_spatial CASCADE;

-- 创建空间扩展表
CREATE TABLE track_points_spatial (
    point_id INTEGER PRIMARY KEY REFERENCES track_points(id) ON DELETE CASCADE,
    geom GEOGRAPHY(POINT, 4326) NOT NULL
);

-- 为现有数据创建 geometry 记录
INSERT INTO track_points_spatial (point_id, geom)
SELECT id, ST_MakePoint(longitude_wgs84, latitude_wgs84)::geography
FROM track_points;

-- 创建空间索引
CREATE INDEX idx_track_points_spatial_geom
    ON track_points_spatial USING GIST(geom);

-- 验证
SELECT COUNT(*) AS spatial_count FROM track_points_spatial;
SELECT COUNT(*) AS main_count FROM track_points;
```

执行完成后，在**后台管理 → 空间计算设置**中选择 **PostGIS**。

#### 性能对比

| 操作 | Python 实现 | PostGIS |
|-----|------------|---------|
| 点到点距离计算 | O(n) 逐点计算 | O(1) 空间函数 |
| 附近点查询 | 全表扫描 | 空间索引查询 |
| 轨迹长度计算 | Python 循环 | SQL 聚合函数 |

---

## 其他问题

### Q: 如何备份数据？

**A**: 参考部署指南中的备份章节：

```bash
# 备份数据库
mysqldump -u vibe_route -p vibe_route > backup.sql

# 备份上传文件
rsync -av backend/data/uploads/ backup/uploads/
```

### Q: 如何更新系统？

**A**:

1. 拉取最新代码：

```bash
git pull
```

2. 更新后端依赖：

```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

3. 更新前端依赖：

```bash
cd frontend
npm install
npm run build
```

4. 重启服务

### Q: 如何查看日志？

**A**: 根据部署方式不同：

- **Systemd**：`journalctl -u vibe-route-backend -f`
- **PM2**：`pm2 logs`
- **Docker**：`docker-compose logs -f`
- **远程日志**：访问 `/log-viewer`

### Q: 如何联系技术支持？

**A**:

1. 查看 GitHub Issues
2. 提交新的 Issue
3. 联系系统管理员

### Q: 系统支持多语言吗？

**A**: 目前系统仅支持中文，多语言支持计划中。

### Q: 可以自部署吗？

**A**: 可以，系统完全开源，可以自由部署。参考部署指南。

### Q: 商业使用需要授权吗？

**A**: 系统使用 MIT 许可证，可以自由使用、修改和分发。

---

## 获取帮助

如果以上 FAQ 无法解决你的问题：

1. 查看 [部署指南](deployment.md)
2. 查看 [使用指南](usage.md)
3. 查看 [配置指南](configuration.md)
4. 在 GitHub 提交 Issue
5. 联系技术支持
