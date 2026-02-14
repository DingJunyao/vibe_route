# 轨迹分享功能设计文档

**创建时间**: 2026-02-06
**作者**: Claude
**状态**: 设计阶段

## 1. 功能概述

### 1.1 核心功能

1. **生成分享链接**：用户可以为轨迹生成永久分享链接
2. **公开访问**：无需登录即可查看分享的轨迹
3. **iframe 嵌入**：支持将轨迹地图嵌入到第三方网站
4. **用户自定义地图配置**：用户可配置自己的地图 API Key

### 1.2 分享控制

- **默认状态**：关闭（`is_shared = false`）
- **首次开启**：生成 `share_token`，设置 `is_shared = true`
- **关闭分享**：仅设置 `is_shared = false`，不删除 `share_token`
- **再次开启**：使用原 `share_token`，设置 `is_shared = true`

## 2. 数据模型

### 2.1 UserConfig 模型

```python
# backend/app/models/user_config.py
class UserConfig(Base):
    id: int
    user_id: int  # 关联 User，唯一约束
    map_provider: Optional[str] = None  # 默认地图提供商
    map_layers: Optional[JSON] = None  # 地图层配置（与系统格式相同）
    created_at: datetime
    updated_at: datetime
```

**配置优先级**：用户配置 > 系统配置

### 2.2 Track 模型扩展

```python
# backend/app/models/track.py
class Track(Base):
    # ... 现有字段 ...
    share_token: Optional[str] = None  # UUID 唯一令牌
    is_shared: bool = False  # 分享开关
```

## 3. API 端点

### 3.1 用户配置相关

| 端点 | 方法 | 功能 | 权限 |
|------|------|------|------|
| `/api/user/config` | GET | 获取用户配置 | 登录用户 |
| `/api/user/config` | PUT | 更新用户配置 | 登录用户 |
| `/api/user/config/reset` | POST | 重置为系统默认 | 登录用户 |

### 3.2 分享相关

| 端点 | 方法 | 功能 | 权限 |
|------|------|------|------|
| `/api/tracks/{id}/share` | POST | 启用分享 | 轨迹所有者 |
| `/api/tracks/{id}/share` | GET | 获取分享状态 | 轨迹所有者 |
| `/api/tracks/{id}/share` | DELETE | 停用分享 | 轨迹所有者 |
| `/api/shared/{token}` | GET | 获取分享轨迹数据 | 无 |
| `/api/shared/{token}/config` | GET | 获取分享者地图配置 | 无 |

### 3.3 API 响应示例

**`GET /api/shared/{token}`**:
```json
{
  "track": {
    "id": 123,
    "name": "周末骑行",
    "created_at": "2026-01-01T10:00:00",
    "distance": 25600,
    "duration": 7200,
    "ascent": 350,
    "descent": 340
  },
  "points": [
    { "latitude_wgs84": 39.9, "longitude_wgs84": 116.4, "elevation": 50, "time": "..." }
  ]
}
```

**`GET /api/shared/{token}/config`**:
```json
{
  "map_provider": "amap",
  "map_layers": { ... }
}
```

## 4. 前端设计

### 4.1 新增页面

| 页面 | 路由 | 组件 | 说明 |
|------|------|------|------|
| 用户设置 | `/settings` | `Settings.vue` | 用户信息 + 地图配置 |
| 分享页面 | `/s/:token` | `SharedTrack.vue` | 公开分享页面 |

### 4.2 新增组件

| 组件 | 位置 | 说明 |
|------|------|------|
| 分享对话框 | `ShareDialog.vue` | 生成分享链接和嵌入代码 |

### 4.3 新增 Store

| Store | 文件 | 说明 |
|-------|------|------|
| userConfig | `stores/userConfig.ts` | 用户配置管理 |

### 4.4 用户设置页面结构

```
Settings.vue
├── 选项卡1: 用户信息
│   ├── 用户名（只读）
│   ├── 邮箱（只读）
│   ├── 角色（只读）
│   └── 创建时间（只读）
└── 选项卡2: 地图设置
    ├── 说明文字
    ├── 地图层列表（拖拽排序）
    │   ├── 天地图: tk 输入
    │   ├── 高德: api_key + security_js_code
    │   ├── 腾讯: api_key
    │   └── 百度: api_key
    └── 操作按钮: 重置/保存
```

### 4.5 分享对话框内容

- 启用/禁用开关
- 分享链接（复制按钮）
- 嵌入代码（textarea + 复制按钮）
- 提示信息（API Key 白名单说明）

### 4.6 嵌入模式

**URL 参数**：`?embed=true`

**嵌入模式特点**：
- 隐藏头部
- 隐藏统计卡片
- 隐藏地图层选择器
- 无页面边距

**嵌入代码示例**：
```html
<iframe
  src="https://route.a4ding.com/s/{token}?embed=true"
  width="100%"
  height="500"
  frameborder="0"
  scrolling="no">
</iframe>
```

## 5. 配置优先级逻辑

### 5.1 前端配置获取流程

```
1. 加载系统配置 (/api/auth/config)
2. 尝试加载用户配置 (/api/user/config)
3. 合并：用户配置覆盖系统配置
4. 初始化地图组件
```

### 5.2 分享页面配置加载

```
1. 加载系统配置（后备）
2. 加载分享者配置 (/api/shared/{token}/config)
3. 合并配置
4. 渲染地图
```

### 5.3 configStore 扩展

新增计算属性：
- `effectiveMapProvider`: 有效地图提供商
- `effectiveMapLayers`: 有效地图层列表
- `getMapLayerById()`: 优先返回用户配置

## 6. 数据库迁移

### 6.1 SQLite

```sql
CREATE TABLE user_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    map_provider VARCHAR(50),
    map_layers TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_user_configs_user_id ON user_configs(user_id);

ALTER TABLE tracks ADD COLUMN share_token VARCHAR(36) UNIQUE;
ALTER TABLE tracks ADD COLUMN is_shared BOOLEAN DEFAULT 0;
CREATE INDEX idx_tracks_share_token ON tracks(share_token);
```

### 6.2 MySQL

```sql
CREATE TABLE user_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    map_provider VARCHAR(50),
    map_layers JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_user_configs_user_id ON user_configs(user_id);

ALTER TABLE tracks ADD COLUMN share_token VARCHAR(36) UNIQUE;
ALTER TABLE tracks ADD COLUMN is_shared BOOLEAN DEFAULT FALSE;
CREATE INDEX idx_tracks_share_token ON tracks(share_token);
```

### 6.3 PostgreSQL

```sql
CREATE TABLE user_configs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    map_provider VARCHAR(50),
    map_layers JSONB,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_user_configs_user_id ON user_configs(user_id);

ALTER TABLE tracks ADD COLUMN share_token VARCHAR(36) UNIQUE;
ALTER TABLE tracks ADD COLUMN is_shared BOOLEAN DEFAULT FALSE;
CREATE INDEX idx_tracks_share_token ON tracks(share_token);
```

## 7. 实现文件清单

### 7.1 后端

| 文件 | 说明 |
|------|------|
| `backend/app/models/user_config.py` | UserConfig 模型 |
| `backend/app/schemas/user_config.py` | Pydantic schemas |
| `backend/app/api/user_config.py` | API 路由 |
| `backend/app/services/user_config_service.py` | 业务逻辑 |
| `backend/app/api/shared.py` | 分享页面 API |
| `backend/app/services/share_service.py` | 分享业务逻辑 |
| `backend/app/models/track.py` | 添加 share_token, is_shared |
| `backend/app/schemas/track.py` | 添加分享相关 schema |
| `backend/app/api/tracks.py` | 添加分享 API 端点 |

### 7.2 前端

| 文件 | 说明 |
|------|------|
| `frontend/src/views/Settings.vue` | 用户设置页面 |
| `frontend/src/views/SharedTrack.vue` | 分享页面 |
| `frontend/src/components/ShareDialog.vue` | 分享对话框 |
| `frontend/src/stores/userConfig.ts` | 用户配置 store |
| `frontend/src/api/userConfig.ts` | 用户配置 API |
| `frontend/src/api/shared.ts` | 分享页面 API |
| `frontend/src/api/track.ts` | 添加分享相关 API |
| `frontend/src/stores/config.ts` | 扩展配置优先级逻辑 |
| `frontend/src/router/index.ts` | 添加新路由 |

## 8. 安全考虑

1. **分享令牌**：使用 UUID，确保不可猜测
2. **访问控制**：`is_shared = false` 时返回 404
3. **敏感信息**：分享页面不暴露用户隐私信息
4. **API Key**：用户配置的 Key 仅用于分享者自己的轨迹

## 9. 参考资料

- 现有后台管理页面地图设置实现
- `leaflet.chinatmsproviders` 插件使用
- 用户认证和权限控制机制
