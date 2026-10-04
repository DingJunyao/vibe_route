# 开发规范

## 文件结构

```
backend/app/
├── api/              # API 路由
├── core/             # 配置、依赖注入、安全
├── models/           # SQLAlchemy 模型
├── schemas/          # Pydantic schemas
├── services/         # 业务逻辑
└── gpxutil_wrapper/  # gpxutil 集成

frontend/src/
├── api/              # API 客户端
├── components/map/   # 地图组件
├── stores/           # Pinia stores
├── utils/            # 工具函数
└── views/            # 页面组件
```

## 常用模式

### 添加 API 端点

1. [`backend/app/api/`](backend/app/api/) 创建路由
2. 依赖注入: `current_user: User = Depends(get_current_user)`
3. 管理员: `current_user: User = Depends(get_current_admin_user)`
4. [`main.py`](backend/app/main.py) 注册路由

### 添加前端页面

1. [`frontend/src/views/`](frontend/src/views/) 创建组件
2. [`router/index.ts`](frontend/src/router/index.ts) 添加路由
3. `meta: { requiresAuth: true }` 或 `requiresAdmin: true }`

### Pinia Store

- Composition API 风格
- `ref()` state, `computed()` getters
- token 同步 localStorage

## UI 规范

### Header

- 默认高度: `60px`（不显式定义）
- 导航按钮: `padding: 8px`

### 图标

- 上传: `Plus`
- 后退: `ArrowLeft`
- 主页: `HomeFilled`

### 下拉菜单顺序

**主页移动端**: 轨迹列表 > 上传 > 实时记录 > 道路标志 > ── > 后台管理 > 退出
**轨迹列表移动端**: 上传 > 实时记录 > ── > 后台管理 > 退出
**轨迹详情移动端**: 配置 > 编辑 > 导入 > 导出 > ── > 后台管理 > 退出

### 分割线

```vue
<el-dropdown-item class="dropdown-divider" :disabled="true" />
```

```css
.dropdown-divider { margin: 4px 0; height: 1px; background-color: var(--el-border-color-lighter); }
```

## 重要提醒

1. **密码**: 前端 `hashPassword()` → 后端 bcrypt
2. **配置**: 普通用户 `/auth/config`，管理员 `/admin/config`
3. **CORS**: 开发环境允许所有来源
4. **首用户**: 自动成为管理员
5. **Viewport**: `maximum-scale=1.0, user-scalable=no`
6. **Git**: 临时修改用 `git update-index --skip-worktree <file>`
