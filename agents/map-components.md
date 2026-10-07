# 地图组件

## Tooltip 定位（重要）

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

## 地图引擎差异

| 功能 | 高德 | 百度 GL | 百度 Legacy | 腾讯 | Google SDK | Leaflet |
|------|------|---------|-------------|--------|---------|---------|
| 坐标转像素 | `lngLatToContainer` | `pointToOverlayPixel` | `pointToPixel` | `projectToContainer` | OverlayView `fromLatLngToContainerPixel` | `latLngToContainerPoint` |
| Zoom 范围 | 3-20 | 3-20 | 3-18 | 3-20 | 3-20 | 1-20 |
| 事件监听 | DOM 捕获 | addEventListener | addEventListener | DOM 容器 | 地图实例 `addListener` | 地图实例 |
| 回放旋转 | `setRotation(-θ)` | `setHeading(θ)` | 不支持 | `setRotation(-θ)` | `setHeading(θ)` | leaflet-rotate `setBearing(-θ)` |

## 地图引擎切换（SDK / Leaflet）

- UniversalMap 图层按钮组旁有 **SDK / Leaflet 切换按钮组**，仅当前图层家族配置了 SDK 凭据时显示（amap/baidu/tencent/google 有 SDK；天地图仅有需 key 的 Leaflet 瓦片、OSM 无 SDK，均不显示）
- 同一 provider 家族（ID 前缀匹配，如 `amap`/`amap_satellite`）共用一个引擎偏好；存 localStorage `map_engine_preference`（[`mapLocalPreference.ts`](frontend/src/utils/mapLocalPreference.ts)），**默认 `sdk` 保持既有行为**；无凭据家族强制 leaflet
- 切换时保存/恢复地图视角（与跨引擎图层切换同机制）；`map_provider` 事件不变（坐标系字段选择不受引擎影响）
- 导出模式 URL `engine=sdk|leaflet` → `forceEngine` prop 覆盖本地偏好（见 features.md 轨迹回放）

## Google 地图

- **单一 `google` 图层**，与高德/腾讯相同的引擎选择模式：
  - 配置了 `api_key` → Google Maps JS API SDK 引擎（WGS84 坐标）
  - 未配置 `api_key` → Leaflet 瓦片（GCJ02 坐标，瓦片源 `www.google.cn`，大陆直连）
- `api_base_url` 可配置（大陆部署可指向自建反向代理），SDK 与 Leaflet 共用 `google` 图层配置
- SDK 坐标↔像素转换依赖 OverlayView 投影助手（地图 `projection` 就绪后可用）
- SDK 模式下海报生成、动画视频导出强制后端 Playwright（同百度 Legacy 原因：前端捕获 CORS/渲染限制）

## 百度地图特殊处理

1. InfoWindow 冲突: 先 `closeInfoWindow()` 再 `setTimeout(() => openInfoWindow(), 0)`
2. 海报生成: 强制使用后端 Playwright（前端 html2canvas 无法捕获 SVG 轨迹）

## 地图缩放（海报导出）

**公式**: `targetContentWidth = containerWidth * 0.9 / scale`

### 各地图缩放方式

- **高德/腾讯/百度 GL**: fitBounds → 延迟获取 zoom → 像素测量 → `Math.log2(targetWidth/currentWidth)` 调整
- **百度 Legacy**: 先 zoom=12 建立基准 → 测量 → 智能舍入（≥0.9 尝试+1 级验证）→ setZoom
- **Leaflet**: 直接地理范围计算，`targetZoom = Math.log2(40075km / (256 * kmPerPixel)) + offset`
