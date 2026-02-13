# CLAUDE.md

Vibe Route - 全栈 Web 轨迹管理系统

## 项目概述

基于 [gpxutil](https://github.com/DingJunyao/gpxutil) 构建。用户上传 GPX 文件，系统解析轨迹、坐标转换（WGS84/GCJ02/BD09）、地理编码填充、地图可视化。

## 开发环境

**Python**: Anaconda 环境 `vibe_route`，所有 Python 操作需切换到此环境。
**数据库**: 查看 `backend/.env` 确定。
**浏览器**: Edge（开发者），需远程调试时运行：

```powershell
Stop-Process -Name msedge -Force; Start-Sleep -Milliseconds 500; Start-Process "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" -ArgumentList "--remote-debugging-port=9222"
```

**开发服务**: 前后端热重载已开启，任务中不再启动/关闭服务。

## 工作流规范

### 1. 问题诊断流程
- 优先使用 Chrome DevTools MCP 分析：控制台错误、网络请求、DOM 结构
- 难以描述时添加调试日志，通过 MCP 或用户提供结果分析
- 检查数据库状态（使用 MCP 或 SQL 查询）
- 检查前端显示效果（使用 MCP 截图）

### 2. 代码修改验证
- 所有代码更改必须编译通过
- 运行相关测试确保功能正常
- 前端: `npm run build`，后端: Python 语法检查

### 3. 任务完成标准
- 编译通过，测试通过
- 大任务完成后整理要点到本文件
- 保持文件大小 < 40KB（压缩历史版本到独立文件）

### tips

For map coordinate conversions, always use the MapService.covert_coords method with provider-specific transformations. AMap/Tencent use GCJ-02, Baidu uses BD-09, Leaflet uses WGS-84.

For text alignment and wrapping features: always test justify overflow, control point positioning when toggling wrap mode, and width adjustment in non-wrap mode before considering implementation complete.

When handling Chinese characters in font uploads or text display, always use UTF-8 encoding and check for full-width vs single-width quote/comparison operator issues.

For undo/redo implementation: always debounce state recording during drag operations, avoid naming conflicts with browser 'history' object, and test multi-step undo jumps.

For control handles on bounding boxes: use shouldShowHandle function instead of hasLineHeight in v-if conditions, align handles to bounding box edges, and display N/S handles when acting as anchors even without line wrapping.

Before fixing any UI bug, first use chrome-devtools to take a snapshot and inspect the computed CSS styles, Vue component state, and actual rendered DOM. Then identify the root cause before editing code.

After implementing any text alignment or control point feature, test: (1) justify mode overflow, (2) wrap mode toggle detaching controls, (3) width adjustment when wrap disabled, (4) coordinate switching across AMap/Baidu/Tencent/Leaflet, (5) control point display after provider switch. Only consider complete when all pass.

For any coordinate or marker-related fix: (1) Test coordinate conversion works for all four providers (AMap=GCJ-02, Baidu=BD-09, Tencent=GCJ-02, Leaflet=WGS-84), (2) Verify green latest-point markers display correctly on each, (3) Switch between providers and confirm control points still render, (4) Use MapService.convert_coords consistently, never manually transform coordinates.

## 快速命令

```bash
# 后端
cd backend && uvicorn app.main:app --reload

# 前端
cd frontend && npm run dev

# 数据库迁移
cd backend && alembic upgrade head
```

## 架构核心

### 认证
- 前端 SHA256 加密 → 后端 bcrypt 二次哈希
- 公开配置 `/api/auth/config` vs 管理员 `/admin/config`

### 多坐标系
- WGS84（GPS 原始）、GCJ02（高德/腾讯）、BD09（百度）
- 地图组件自动切换对应坐标

### 用户状态
- `is_valid`: 软删除标记
- `is_active`: 账户启用状态
- 创建时复用已删除用户记录

### 路由守卫
- `guest`: 未登录可访问
- `requiresAuth`: 需登录
- `requiresAdmin`: 需管理员

## 响应式设计

- 移动端断点: `screenWidth <= 1366px`
- 高度单位: `vh` 实现，如 `height: calc(100vh - 60px)`
- 地图重绘: `ResizeObserver` 监听容器变化

### 布局规则
| 页面 | 桌面端 (height>=800px) | 桌面端 (height<800px) | 移动端 |
|------|------------------------|----------------------|--------|
| 首页 | 统计固定 + 地图填充 | 独立滚动 | 单列流式 |
| 详情页 | 左侧固定 + 右侧滚动 | 地图 40vh + 图表 22vh | 地图 30vh + 图表 20vh |

## 地图组件

### Tooltip 定位（重要）
- **问题**: AMap 内部元素阻止事件冒泡
- **解决**: document 级别监听 mousemove，检查鼠标是否在容器内
- **关键代码** ([`AMap.vue`](frontend/src/components/map/AMap.vue)):
  ```typescript
  documentMouseMoveHandler = (e: MouseEvent) => {
    // 图表容器检测 - 避免与图表 tooltip 冲突
    const chartContainer = document.querySelector('.chart')
    if (chartContainer?.contains(e.target)) return

    // 容器边界检测
    const rect = mapContainer.value.getBoundingClientRect()
    if (x < 0 || x > rect.width || y < 0 || y > rect.height) {
      hideMarker()
      return
    }
    // 坐标转换处理...
  }
  ```

### 地图引擎差异
| 功能 | 高德 | 百度 GL | 百度 Legacy | 腾讯 | Leaflet |
|------|------|---------|-------------|--------|---------|
| 坐标转像素 | `lngLatToContainer` | `pointToOverlayPixel` | `pointToPixel` | `projectToContainer` | `latLngToContainerPoint` |
| Zoom 范围 | 3-20 | 3-20 | 3-18 | 3-20 | 1-20 |
| 事件监听 | DOM 捕获 | addEventListener | addEventListener | DOM 容器 | 地图实例 |

### 百度地图特殊处理
1. InfoWindow 冲突: 先 `closeInfoWindow()` 再 `setTimeout(() => openInfoWindow(), 0)`
2. 海报生成: 强制使用后端 Playwright（前端 html2canvas 无法捕获 SVG 轨迹）

## 地图缩放（海报导出）

**公式**: `targetContentWidth = containerWidth * 0.9 / scale`

### 各地图缩放方式
- **高德/腾讯/百度 GL**: fitBounds → 延迟获取 zoom → 像素测量 → `Math.log2(targetWidth/currentWidth)` 调整
- **百度 Legacy**: 先 zoom=12 建立基准 → 测量 → 智能舍入（≥0.9 尝试+1 级验证）→ setZoom
- **Leaflet**: 直接地理范围计算，`targetZoom = Math.log2(40075km / (256 * kmPerPixel)) + offset`

## 实时记录

### 时间字段规范
| 字段 | 含义 | 用途 |
|------|------|------|
| `last_upload_at` | LiveRecording 上传时间 | 备用 |
| `last_point_time` | GPS 时间 | 对话框"轨迹点时间" |
| `last_point_created_at` | 服务器接收时间 | **"最近更新"统一使用此字段** |

### 核心逻辑
- **乱序处理**: 前端接收新点后按 `time` 排序
- **point_index**: 实时记录期间可能不准，停止时自动修复
- **查询排序**: 始终使用 `.order_by(TrackPoint.time.asc(), TrackPoint.created_at.asc())`

### WebSocket
- 连接: `/api/ws/live-recording/{recording_id}?token={TOKEN}`
- 自动重连: 3 秒间隔
- 地址动态适配: [`origin.ts`](frontend/src/utils/origin.ts) 根据访问地址判断

## 地理编码

### 本地反向编码
- **边界框过滤**: 快速获取候选区域
- **Shapely 精确匹配**: `polygon.contains(point)` 判断
- **无 geometry**: 跳过（不回退到边界框）

### DataV 导入
- **在线数据**: GCJ02 坐标，导入时转 WGS84
- **压缩包**: 假设 WGS84
- **特殊行政区划**:
  - 直辖市 (110000/120000/310000/500000): 区县直属省级
  - 不设区地级市 (东莞/中山/儋州/嘉峪关): 保留市级，无镇级
  - 省辖县级 (仙桃/潜江/天门/济源): 分类为 `area` 级别

## PostGIS

### 架构
- `admin_divisions.geometry`: GeoJSON 多边形（shapely 用）
- `admin_divisions_spatial.geom`: PostGIS 几何（空间查询用）
- **手动同步**: 后台管理提供同步功能

## 地理信息编辑器

### 撤销/重做
- 快捷键: Ctrl+Z 撤销, Ctrl+Y 重做
- 历史结构: `history[i].after` 是撤销后应恢复的状态
- 类型扩展: `'edit' | 'resize' | 'move'`

### 刻度条
- 边界扩展: 基于可视区域点时间扩展
- 点索引定位: `findPointIndexByTime` 确保刻度与点一致
- 级别去重: 主刻度 5%, 次刻度 1%, 三级 0.2%

## 轨迹插值

### 三阶段流程
1. **选择区段**: 表格展示可插值区段（间隔 ≥ 最小间隔）
2. **绘制路径**: 地图点击添加控制点，支持拖拽、撤销/重做
3. **预览结果**: 禁用编辑，确认后保存

### 控制点手柄
- `handlesLocked = true`: 拖拽一个手柄，另一个对称移动
- `handlesLocked = false`: 手柄独立移动

## 覆盖层模板编辑器

### 坐标系统规范
| 数据 | 单位 | 范围 |
|------|------|------|
| `position.x/y` | 画布比例 | -0.5 到 0.5 |
| `layout.width/height` | 画布比例 | 0 到 1 |
| `style.font_size` | 画布比例 | 正数 |

### 转换公式
```javascript
// 画布比例 → 画布像素
offsetX = element.position.x * canvasWidth

// 画布像素 → 预览百分比 (0-100)
leftPct = (elemX * scaleToPreviewX) / previewBaseWidth * 100

// 预览百分比 → 画布比例
deltaCanvasPct = deltaPreviewPct / 100
```

### 容器锚点
- **始终相对于画布计算**，不受 `use_safe_area` 影响
- 公式: `final_x = container_x + offset_x - elem_anchor_x`

### 空格键拖动
- 滚动区域: 容器尺寸 150%
- 拖动时: 禁用滚动条 (`overflow: hidden !important`)
- 初始居中: `(wrapperWidth - containerWidth) / 2`

## 海报生成

### 前端生成
- iframe 加载 [`TrackMapOnly.vue`](frontend/src/views/TrackMapOnly.vue)
- 等待 `window.mapReady === true`
- html2canvas 截取 `.map-only-page`（不截 `.map-wrapper-container`）

### 后端生成
- Playwright 访问 `/tracks/{id}/map-only`
- 等待 `window.mapReady === true`
- 使用 `clip` 参数截取

### 百度地图
- **强制后端生成**: Legacy 版本 DOM 渲染，html2canvas 无法正确捕获

### 缩放等待时间
- 动态: `baseWait + (mapScale - 100) * multiplier`

## 分享嵌入模式

- URL: `/s/{token}?embed=true`
- 只显示地图，隐藏其他元素
- "查看轨迹详情"按钮跳转完整分享页

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

## 变更历史

详细历史版本已归档到 `ref/CLAUDE_ARCHIVE.md`，以下是简要记录：

### 2026-01
- DateTime 时区统一为 timezone-naive UTC
- 地理编码失败跟踪
- PostGIS 空间计算支持
- 实时记录架构改进（一对一 Track）
- 地理编码服务配置缓存

### 2026-02

- 多边形几何字段 + Shapely 精确匹配
- 省辖县级行政单位分类修复
- 地理信息编辑器（刻度条、撤销/重做、空块操作）
- 地图缩放（海报导出）
- 分享嵌入模式
- 轨迹插值功能
- 覆盖层模板编辑器（空格键拖动、坐标系统重构）
- **文本对齐功能完善**：
  - 添加垂直对齐控制（上/中/下）
  - 两端对齐对所有行生效
  - 添加"自定义文本"数据源选项
  - 示例文本支持多行输入
  - 修正文本整体高度计算（排除最后一行下方空间）
- **GB 5765 字体支持**：
  - 后端启动时预转换为 WOFF2 格式（`_convert_gb5765_fonts_to_woff2()`）
  - 删除问题表（VDMX、GASP、GDEF、GPOS、GSUB、gasp、gvar、fvar、STAT、trak、kern、vhea、vmtx）
  - 重建最小化 post 表（format 3.0）
  - WOFF2 缓存机制（`backend/data/fonts/woff2_cache/`）
  - 前端动态加载字体（`user_font_${fontId}` 命名）
  - `OverlayTemplateEditor.getFontFamilyName()` 支持用户字体映射
  - `FontSelector` 为 GB 5765 字体添加时间戳绕过浏览器缓存
- **覆盖层模板编辑器 UI 完善**：
  - 安全区输入框宽度统一（使用 visibility: hidden 占位）
  - 前缀后缀输入框支持多行文本（textarea, 2 行）
  - 示例文本输入框高度与描述输入框一致（2 行）
  - 画布宽高输入框和字体下拉框宽度延伸到右边（100%）
  - 画布渲染支持用户/管理员上传字体
