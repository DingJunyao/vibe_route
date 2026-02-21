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

| 功能 | 高德 | 百度 GL | 百度 Legacy | 腾讯 | Leaflet |
|------|------|---------|-------------|--------|---------|
| 坐标转像素 | `lngLatToContainer` | `pointToOverlayPixel` | `pointToPixel` | `projectToContainer` | `latLngToContainerPoint` |
| Zoom 范围 | 3-20 | 3-20 | 3-18 | 3-20 | 1-20 |
| 事件监听 | DOM 捕获 | addEventListener | addEventListener | DOM 容器 | 地图实例 |

## 百度地图特殊处理

1. InfoWindow 冲突: 先 `closeInfoWindow()` 再 `setTimeout(() => openInfoWindow(), 0)`
2. 海报生成: 强制使用后端 Playwright（前端 html2canvas 无法捕获 SVG 轨迹）

## 地图缩放（海报导出）

**公式**: `targetContentWidth = containerWidth * 0.9 / scale`

### 各地图缩放方式

- **高德/腾讯/百度 GL**: fitBounds → 延迟获取 zoom → 像素测量 → `Math.log2(targetWidth/currentWidth)` 调整
- **百度 Legacy**: 先 zoom=12 建立基准 → 测量 → 智能舍入（≥0.9 尝试+1 级验证）→ setZoom
- **Leaflet**: 直接地理范围计算，`targetZoom = Math.log2(40075km / (256 * kmPerPixel)) + offset`
