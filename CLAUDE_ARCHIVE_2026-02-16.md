# CLAUDE.md 变更历史 - 2026-02-16

## 腾讯地图动画标记和 HUD 控制修复

### 问题
- 动画标记显示默认样式，没有使用系统提供的图标
- 回放控制浮窗（HUD）无法响应点击，操作直接映射到地图

### 根本原因
1. `TMap.DOMOverlay.extend` 不是一个函数，无法通过 DOM 操作添加自定义 HTML 内容
2. 点击事件监听使用了 `useCapture: true`，事件在捕获阶段被地图容器拦截
3. `TMap.MultiMarker` 没有 `updateStyles` 方法
4. 腾讯地图的控件层（`z-index: 1000`）覆盖了整个页面，包括 HUD

### 解决方案
1. **动画标记**：使用 Canvas 绘制旋转后的图标，转换为 data URL，在 `TMap.MarkerStyle` 中设置 `src` 属性
2. **HUD 点击响应**：将 `useCapture` 参数改为 `false`，让事件在冒泡阶段处理
3. **样式更新**：使用 `setStyles` 方法替代 `updateStyles`，添加 try-catch 处理失败情况
4. **HUD 遮挡**：将 HUD 的 `z-index` 从 `1000` 提高到 `10000`

### 修改文件
- [frontend/src/components/map/TencentMap.vue](../frontend/src/components/map/TencentMap.vue)
  - 重写 `generateRotatedMarkerIcon` 函数，使用 Canvas 绘制旋转图标
  - 修改 `setMarkerPosition` 函数，使用 data URL 设置标记
  - 修改点击事件监听，改为冒泡阶段
- [frontend/src/components/animation/AnimationHUD.vue](../frontend/src/components/animation/AnimationHUD.vue)
  - 将 `.animation-hud` 的 `z-index` 从 `1000` 改为 `10000`

### 结果
- 腾讯地图的动画标记正确显示并旋转
- HUD 控制面板的按钮可以正常点击和交互
