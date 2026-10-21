/**
 * 热力图共享配置与工具
 * 主页足迹热力图：各引擎共用的渐变色带与整体不透明度
 * （渲染与归一化见 heatmapCanvas.ts）
 */

// 各引擎共用的热力渐变色带（低 → 高：雾蓝 → 青绿 → 草绿 → 沙黄 → 杏 → 胭脂）
// 中等饱和度的柔和色（非荧光），配合 HEATMAP_OPACITY 叠在底图上不抢视觉
export const HEATMAP_GRADIENT: Record<string, string> = {
  0.2: '#8fc0dd',
  0.4: '#7cc6b8',
  0.6: '#c3d78f',
  0.75: '#ecd393',
  0.9: '#e9ab84',
  1.0: '#cd8f8f',
}

// 热力层整体不透明度（0-1）
export const HEATMAP_OPACITY = 0.5
