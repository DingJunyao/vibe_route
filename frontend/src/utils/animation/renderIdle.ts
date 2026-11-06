// frontend/src/utils/animation/renderIdle.ts
// SDK 地图渲染收敛等待（逐帧导出用）。
//
// SDK 引擎没有「渲染完成」信号：AMap 无 renderComplete 事件、各家瓦片加载无 DOM
// 计数可查（pendingTileCount 只认 Leaflet）。此处移植 amap_remotion 的实测方案
// （TRACK-REPLAY-NOTES.md 第六节）：轮询地图主画布 64×64 缩略图 toDataURL，
// 连续两次采样不变（瓦片加载收敛）才放行截图；minMs 起判避免在 SDK 尚未开始
// 重绘时误判稳定，maxMs 兜底防止个别失败瓦片把导出永久卡死。
//
// 适配器 waitForIdle 的组合方式：先 race 引擎事件（如 AMap/BMap moveend、
// Google idle）给画布收敛留出起点，再调用本函数做实际等待。

export interface RenderIdleOptions {
  minMs?: number      // 最短判定时间（默认 350ms）
  maxMs?: number      // 兜底超时（默认 2500ms）
  pollMs?: number     // 轮询间隔（默认 120ms）
  stableNeed?: number // 需要连续一致的采样次数（默认 2）
}

const DEFAULTS: Required<RenderIdleOptions> = { minMs: 350, maxMs: 2500, pollMs: 120, stableNeed: 2 }

function nextPaint(): Promise<void> {
  // 双 rAF：确保 SDK 本帧的重绘任务被浏览器实际执行后再开始采样
  return new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/** 采集容器主画布的 64×64 缩略图签名；读取失败按 'err' 处理（视为稳定，交由兜底放行） */
function canvasSignature(container: HTMLElement): string {
  try {
    const src = container.querySelector('canvas') as HTMLCanvasElement | null
    if (!src) return 'no-canvas'
    const thumb = document.createElement('canvas')
    thumb.width = 64
    thumb.height = 64
    const ctx = thumb.getContext('2d')
    if (!ctx) return 'err'
    ctx.drawImage(src, 0, 0, 64, 64)
    return thumb.toDataURL('image/png')
  } catch {
    // 画布被污染 / WebGL 上下文丢失：按稳定处理，交由 maxMs 兜底
    return 'err'
  }
}

/** 容器内尚未加载完成的 <img> 数（DomRender 栅格瓦片走 img 元素，画布轮询看不到它们） */
function pendingImages(container: HTMLElement): number {
  let pending = 0
  const imgs = container.querySelectorAll('img')
  for (const img of imgs) {
    if (!img.complete) pending++
  }
  return pending
}

/**
 * 等待地图容器渲染收敛（画布内容连续采样不变且无加载中瓦片）。
 * 容器内无 canvas（DOM 渲染引擎，如百度 Legacy）时退化为固定延时。
 */
export async function waitForRenderIdle(
  container: HTMLElement | null,
  options: RenderIdleOptions = {}
): Promise<void> {
  const opts = { ...DEFAULTS, ...options }
  await nextPaint()
  if (!container || !container.querySelector('canvas')) {
    // DOM 渲染引擎没有可读回的画布，等待加载中的瓦片 img（若有）后固定延时兜底
    const start = performance.now()
    while (pendingImages(container ?? document.body) > 0 && performance.now() - start < opts.maxMs) {
      await sleep(opts.pollMs)
    }
    await sleep(opts.minMs)
    return
  }
  const start = performance.now()
  let last = ''
  let stable = 0
  for (;;) {
    const sig = canvasSignature(container)
    const pending = pendingImages(container)
    stable = sig === last && pending === 0 ? stable + 1 : 0
    last = sig
    const elapsed = performance.now() - start
    if ((stable >= opts.stableNeed && elapsed >= opts.minMs) || elapsed >= opts.maxMs) {
      return
    }
    await sleep(opts.pollMs)
  }
}
