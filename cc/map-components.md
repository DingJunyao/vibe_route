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
