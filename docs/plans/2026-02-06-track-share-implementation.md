# 轨迹分享功能实现计划

**设计文档**: [2026-02-06-track-share-feature-design.md](./2026-02-06-track-share-feature-design.md)
**创建时间**: 2026-02-06

## 实现阶段

### 阶段 1: 后端基础设施

#### 1.1 数据库迁移

- [ ] 创建 `013_add_user_configs_and_share.*.{sqlite,mysql,postgresql}`
- [ ] 创建 `user_configs` 表
- [ ] 为 `tracks` 表添加 `share_token` 和 `is_shared` 字段
- [ ] 运行迁移测试

#### 1.2 模型和 Schema

- [ ] 创建 `backend/app/models/user_config.py`
  - [ ] `UserConfig` 模型
- [ ] 修改 `backend/app/models/track.py`
  - [ ] 添加 `share_token` 字段
  - [ ] 添加 `is_shared` 字段
- [ ] 创建 `backend/app/schemas/user_config.py`
  - [ ] `UserConfigResponse`
  - [ ] `UserConfigUpdate`
- [ ] 修改 `backend/app/schemas/track.py`
  - [ ] 添加分享相关字段到响应 schema

#### 1.3 服务层

- [ ] 创建 `backend/app/services/user_config_service.py`
  - [ ] `get_user_config(user_id)`
  - [ ] `update_user_config(user_id, data)`
  - [ ] `reset_user_config(user_id)`
- [ ] 创建 `backend/app/services/share_service.py`
  - [ ] `create_share(track_id)` - 生成 token
  - [ ] `enable_share(track_id)` - 设置 is_shared=true
  - [ ] `disable_share(track_id)` - 设置 is_shared=false
  - [ ] `get_shared_track(token)` - 获取分享数据
  - [ ] `get_shared_user_config(token)` - 获取分享者配置

#### 1.4 API 路由

- [ ] 创建 `backend/app/api/user_config.py`
  - [ ] `GET /api/user/config`
  - [ ] `PUT /api/user/config`
  - [ ] `POST /api/user/config/reset`
- [ ] 创建 `backend/app/api/shared.py`
  - [ ] `GET /api/shared/{token}`
  - [ ] `GET /api/shared/{token}/config`
- [ ] 修改 `backend/app/api/tracks.py`
  - [ ] `POST /api/tracks/{id}/share`
  - [ ] `GET /api/tracks/{id}/share`
  - [ ] `DELETE /api/tracks/{id}/share`
- [ ] 在 `backend/app/main.py` 中注册新路由

### 阶段 2: 前端基础设施

#### 2.1 API 客户端

- [ ] 创建 `frontend/src/api/userConfig.ts`
  - [ ] `getUserConfig()`
  - [ ] `updateUserConfig(data)`
  - [ ] `resetUserConfig()`
- [ ] 创建 `frontend/src/api/shared.ts`
  - [ ] `getSharedTrack(token)`
  - [ ] `getSharedConfig(token)`
- [ ] 修改 `frontend/src/api/track.ts`
  - [ ] `createShare(trackId)`
  - [ ] `getShareStatus(trackId)`
  - [ ] `deleteShare(trackId)`

#### 2.2 Store

- [ ] 创建 `frontend/src/stores/userConfig.ts`
  - [ ] `config` 状态
  - [ ] `fetchConfig()`
  - [ ] `updateConfig(data)`
  - [ ] `resetConfig()`
  - [ ] `fetchSharedConfig(token)`
  - [ ] `getEffectiveProvider()` 计算属性
  - [ ] `getEffectiveLayers()` 计算属性

#### 2.3 配置优先级

- [ ] 修改 `frontend/src/stores/config.ts`
  - [ ] 导入 `userConfigStore`
  - [ ] 实现 `getMapLayerById()` 优先用户配置
  - [ ] 更新 `getMapLayers()` 使用用户配置覆盖

### 阶段 3: 用户设置页面

#### 3.1 页面组件

- [ ] 创建 `frontend/src/views/Settings.vue`
  - [ ] 布局结构（container + header + main + tabs）
  - [ ] 用户信息选项卡（只读表单）
  - [ ] 地图设置选项卡（复用 Admin.vue 的地图设置 UI）
  - [ ] 响应式样式（桌面/移动端）

#### 3.2 地图设置功能

- [ ] 拖拽排序（draggable）
- [ ] 移动端上下按钮排序
- [ ] 启用/禁用开关
- [ ] 默认地图单选
- [ ] API Key 输入框（天地图、高德、腾讯、百度）
- [ ] 保存功能
- [ ] 重置功能

#### 3.3 路由和导航

- [ ] 添加 `/settings` 路由
- [ ] 在各页面用户菜单添加"设置"选项

### 阶段 4: 分享功能

#### 4.1 分享对话框

- [ ] 创建 `frontend/src/components/ShareDialog.vue`
  - [ ] 启用/禁用开关
  - [ ] 分享链接显示和复制
  - [ ] 嵌入代码生成和复制
  - [ ] 提示信息

#### 4.2 轨迹详情页集成

- [ ] 修改 `frontend/src/views/TrackDetail.vue`
  - [ ] 添加分享按钮
  - [ ] 集成 ShareDialog
  - [ ] 处理分享状态

### 阶段 5: 分享页面

#### 5.1 页面组件

- [ ] 创建 `frontend/src/views/SharedTrack.vue`
  - [ ] 布局（简化版头部）
  - [ ] 统计卡片
  - [ ] 地图组件
  - [ ] 嵌入模式检测和样式

#### 5.2 嵌入模式

- [ ] URL 参数 `?embed=true` 检测
- [ ] 嵌入模式样式（隐藏头部、无边距）
- [ ] 响应式适配

#### 5.3 配置加载

- [ ] 分享者配置加载
- [ ] 配置合并（用户配置 > 系统配置）
- [ ] 地图初始化

#### 5.4 路由

- [ ] 添加 `/s/:token` 路由（无需登录）

### 阶段 6: 测试和优化

#### 6.1 功能测试

- [ ] 用户配置 CRUD
- [ ] 分享链接生成
- [ ] 分享启用/禁用
- [ ] 分享页面访问
- [ ] iframe 嵌入
- [ ] 配置优先级

#### 6.2 边界测试

- [ ] 未登录访问分享页面
- [ ] 无效 token 访问
- [ ] 已禁用分享的链接
- [ ] 无 API Key 时的回退

#### 6.3 性能优化

- [ ] 分享页面加载优化
- [ ] 配置缓存

## 文件清单

### 后端 (14 个文件)

| 文件 | 操作 | 说明 |
|------|------|------|
| `alembic/versions/013_*.py` | 新建 | 数据库迁移 |
| `backend/app/models/user_config.py` | 新建 | UserConfig 模型 |
| `backend/app/models/track.py` | 修改 | 添加分享字段 |
| `backend/app/schemas/user_config.py` | 新建 | UserConfig schemas |
| `backend/app/schemas/track.py` | 修改 | 分享相关 schema |
| `backend/app/services/user_config_service.py` | 新建 | 用户配置服务 |
| `backend/app/services/share_service.py` | 新建 | 分享服务 |
| `backend/app/api/user_config.py` | 新建 | 用户配置 API |
| `backend/app/api/shared.py` | 新建 | 分享页面 API |
| `backend/app/api/tracks.py` | 修改 | 添加分享端点 |
| `backend/app/main.py` | 修改 | 注册路由 |

### 前端 (12 个文件)

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/api/userConfig.ts` | 新建 | 用户配置 API |
| `frontend/src/api/shared.ts` | 新建 | 分享页面 API |
| `frontend/src/api/track.ts` | 修改 | 添加分享 API |
| `frontend/src/stores/userConfig.ts` | 新建 | 用户配置 store |
| `frontend/src/stores/config.ts` | 修改 | 配置优先级 |
| `frontend/src/views/Settings.vue` | 新建 | 用户设置页 |
| `frontend/src/views/SharedTrack.vue` | 新建 | 分享页面 |
| `frontend/src/components/ShareDialog.vue` | 新建 | 分享对话框 |
| `frontend/src/views/TrackDetail.vue` | 修改 | 添加分享按钮 |
| `frontend/src/router/index.ts` | 修改 | 添加路由 |

## 预估工作量

| 阶段 | 预估时间 |
|------|---------|
| 阶段 1: 后端基础设施 | 4-6 小时 |
| 阶段 2: 前端基础设施 | 2-3 小时 |
| 阶段 3: 用户设置页面 | 3-4 小时 |
| 阶段 4: 分享功能 | 2-3 小时 |
| 阶段 5: 分享页面 | 3-4 小时 |
| 阶段 6: 测试和优化 | 2-3 小时 |
| **总计** | **16-23 小时** |
