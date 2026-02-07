/**
 * 前端海报生成器
 * 使用 iframe + html2canvas 截取地图，然后用 Canvas 合成海报
 */

import html2canvas from 'html2canvas'

export interface PosterConfig {
  template: 'minimal' | 'simple' | 'rich' | 'geo'
  width: number
  height: number
  showWatermark: boolean
  mapScale: number
}

export interface TrackData {
  name: string
  distance: number
  duration: number
  elevation_gain: number
  elevation_loss: number
}

export interface PosterProgressCallback {
  (stage: string, message: string, percent: number): void
}

export class FrontendPosterGenerator {
  private config: PosterConfig
  private trackId: number
  private provider: string
  private posterSecret: string
  private trackData: TrackData
  private onProgress: PosterProgressCallback

  constructor(
    config: PosterConfig,
    trackId: number,
    provider: string,
    posterSecret: string,
    trackData: TrackData,
    onProgress: PosterProgressCallback
  ) {
    this.config = config
    this.trackId = trackId
    // 百度地图统一使用 Legacy 版本（非 WebGL，避免截图问题）
    this.provider = provider === 'baidu' ? 'baidu_legacy' : provider
    this.posterSecret = posterSecret
    this.trackData = trackData
    this.onProgress = onProgress
  }

  /**
   * 生成海报
   */
  async generate(): Promise<Blob> {
    this.onProgress('capturing', '正在加载地图...', 10)

    // 1. 创建隐藏的 iframe 加载地图页面
    const iframe = await this.loadMapInIframe()

    try {
      // 2. 等待地图就绪
      await this.waitForMapReady(iframe)

      // 3. 截取地图
      this.onProgress('capturing', '正在截取地图...', 30)
      const mapCanvas = await this.captureMap(iframe)

      // 4. 合成海报
      this.onProgress('drawing', '正在合成海报...', 60)
      const posterCanvas = await this.composePoster(mapCanvas)

      this.onProgress('done', '生成完成', 100)

      // 5. 转换为 Blob
      return new Promise((resolve) => {
        posterCanvas.toBlob((blob) => {
          resolve(blob!)
        }, 'image/png')
      })
    } finally {
      // 清理 iframe
      document.body.removeChild(iframe)
    }
  }

  /**
   * 创建隐藏的 iframe 加载地图页面
   */
  private async loadMapInIframe(): Promise<HTMLIFrameElement> {
    return new Promise((resolve, reject) => {
      const iframe = document.createElement('iframe')
      iframe.style.position = 'absolute'
      iframe.style.left = '0'
      iframe.style.top = '0'
      iframe.style.width = `${this.config.width}px`
      iframe.style.height = `${this.config.height}px`
      iframe.style.border = 'none'
      iframe.style.opacity = '0'
      iframe.style.pointerEvents = 'none'
      iframe.style.zIndex = '-1'

      // 构建 URL（provider 已在构造函数中转换）
      const url = `/tracks/${this.trackId}/map-only?provider=${this.provider}&secret=${this.posterSecret}&map_scale=${this.config.mapScale}&width=${this.config.width}&height=${this.config.height}`

      iframe.onload = () => resolve(iframe)
      iframe.onerror = reject

      iframe.src = url
      document.body.appendChild(iframe)
    })
  }

  /**
   * 等待地图就绪
   */
  private async waitForMapReady(iframe: HTMLIFrameElement): Promise<void> {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('等待地图就绪超时'))
      }, 60000)  // 增加超时时间到 60 秒

      const checkReady = () => {
        try {
          if ((iframe.contentWindow as any)?.mapReady === true) {
            clearTimeout(timeout)
            // mapReady 后，额外等待根据缩放比例计算的时间
            const baseWait = 1000
            const scaleWait = (this.config.mapScale - 100) * 50  // 每 1% 缩放增加 50ms
            const totalWait = baseWait + scaleWait
            console.log(`[FrontendPoster] mapReady，额外等待 ${totalWait}ms`)
            setTimeout(resolve, totalWait)
          } else {
            setTimeout(checkReady, 100)
          }
        } catch (e) {
          // 跨域错误，继续检查
          setTimeout(checkReady, 100)
        }
      }

      checkReady()
    })
  }

  /**
   * 使用 html2canvas 截取地图
   */
  private async captureMap(iframe: HTMLIFrameElement): Promise<HTMLCanvasElement> {
    const iframeDoc = iframe.contentDocument
    if (!iframeDoc) {
      throw new Error('无法访问 iframe 内容')
    }

    // 截取整个页面，包含缩放后的地图
    const mapElement = iframeDoc.querySelector('.map-only-page') as HTMLElement
    if (!mapElement) {
      throw new Error('找不到地图容器')
    }

    // 使用 html2canvas 截图
    const canvas = await html2canvas(mapElement, {
      useCORS: true,
      allowTaint: false,
      scale: 2, // 高分辨率
      logging: false,
      backgroundColor: '#e5e5e5',
      // 处理 Leaflet SVG 的特殊配置
      foreignObjectRendering: false,
      removeContainer: true,
      imageTimeout: 15000,
    })

    return canvas
  }

  /**
   * 合成海报（复刻后端 PIL 逻辑）
   */
  private async composePoster(mapCanvas: HTMLCanvasElement): Promise<HTMLCanvasElement> {
    console.log('[FrontendPoster] composePoster 开始', {
      configSize: `${this.config.width}x${this.config.height}`,
      mapCanvasSize: `${mapCanvas.width}x${mapCanvas.height}`,
      mapScale: this.config.mapScale
    })

    const canvas = document.createElement('canvas')
    canvas.width = this.config.width
    canvas.height = this.config.height
    const ctx = canvas.getContext('2d')

    if (!ctx) {
      throw new Error('无法创建 Canvas 上下文')
    }

    // 1. 绘制背景（后端使用 RGB(245, 245, 245)）
    ctx.fillStyle = '#f5f5f5'
    ctx.fillRect(0, 0, this.config.width, this.config.height)

    // 2. 绘制地图（居中）
    // 如果地图截图大于目标画布，需要缩放
    let drawWidth = mapCanvas.width
    let drawHeight = mapCanvas.height
    let mapX = (this.config.width - mapCanvas.width) / 2
    let mapY = (this.config.height - mapCanvas.height) / 2

    // 如果地图超出画布，缩放到合适大小
    if (mapCanvas.width > this.config.width || mapCanvas.height > this.config.height) {
      const scaleX = this.config.width / mapCanvas.width
      const scaleY = this.config.height / mapCanvas.height
      const scale = Math.min(scaleX, scaleY) * 0.95  // 留 5% 边距
      drawWidth = mapCanvas.width * scale
      drawHeight = mapCanvas.height * scale
      mapX = (this.config.width - drawWidth) / 2
      mapY = (this.config.height - drawHeight) / 2
      console.log('[FrontendPoster] 地图超出画布，缩放', { scale, drawWidth, drawHeight, mapX, mapY })
    }

    ctx.drawImage(mapCanvas, mapX, mapY, drawWidth, drawHeight)

    // 3. 根据模板添加信息
    if (this.config.template !== 'minimal') {
      this.drawTemplate(ctx)
    }

    // 4. 绘制水印
    if (this.config.showWatermark) {
      this.drawWatermark(ctx)
    }

    console.log('[FrontendPoster] composePoster 完成')
    return canvas
  }

  /**
   * 绘制模板信息
   */
  private drawTemplate(ctx: CanvasRenderingContext2D): void {
    if (this.config.template === 'simple' || this.config.template === 'rich') {
      this.drawSimpleTemplate(ctx)
    } else if (this.config.template === 'geo') {
      this.drawGeoTemplate(ctx)
    }
  }

  /**
   * 绘制简洁/丰富模板
   */
  private drawSimpleTemplate(ctx: CanvasRenderingContext2D): void {
    const overlayY = this.config.height - 200
    const overlayHeight = 200

    // 绘制半透明背景框（后端使用 RGBA(30, 30, 30, 200)）
    ctx.fillStyle = 'rgba(30, 30, 30, 0.78)'
    ctx.fillRect(0, overlayY, this.config.width, overlayHeight)

    // 设置字体
    const fontSizeLarge = 48
    const fontSizeMedium = 32
    const fontSizeSmall = 24

    // 绘制轨迹名称
    ctx.fillStyle = '#ffffff'
    ctx.font = `${fontSizeLarge}px "Microsoft YaHei", sans-serif`
    ctx.textBaseline = 'top'
    ctx.fillText(this.trackData.name, 30, overlayY + 20)

    // 绘制统计信息
    let infoY = overlayY + 80
    const infoX = 30
    const lineHeight = 40

    if (this.trackData.distance > 0) {
      ctx.font = `${fontSizeMedium}px "Microsoft YaHei", sans-serif`
      ctx.fillText(`距离: ${this.formatDistance(this.trackData.distance)}`, infoX, infoY)
      infoY += lineHeight
    }

    if (this.trackData.duration > 0) {
      ctx.fillText(`时长: ${this.formatDuration(this.trackData.duration)}`, infoX, infoY)
      infoY += lineHeight
    }

    if (this.trackData.elevation_gain > 0) {
      ctx.font = `${fontSizeSmall}px "Microsoft YaHei", sans-serif`
      ctx.fillText(`爬升: ${this.formatElevation(this.trackData.elevation_gain)}`, infoX, infoY)
    }
  }

  /**
   * 绘制地理模板
   */
  private drawGeoTemplate(ctx: CanvasRenderingContext2D): void {
    const overlayWidth = 400
    const overlayHeight = 180
    const overlayX = this.config.width - overlayWidth
    const overlayY = this.config.height - overlayHeight

    // 绘制半透明背景框（后端使用 RGBA(30, 30, 30, 220)）
    ctx.fillStyle = 'rgba(30, 30, 30, 0.86)'
    ctx.fillRect(overlayX, overlayY, overlayWidth, overlayHeight)

    // 设置字体
    const fontSizeMedium = 32
    const fontSizeSmall = 24

    let infoX = overlayX + 20
    let infoY = overlayY + 20

    // 绘制轨迹名称
    ctx.fillStyle = '#ffffff'
    ctx.font = `${fontSizeMedium}px "Microsoft YaHei", sans-serif`
    ctx.textBaseline = 'top'
    ctx.fillText(this.trackData.name, infoX, infoY)
    infoY += 50

    // 绘制统计信息
    ctx.font = `${fontSizeSmall}px "Microsoft YaHei", sans-serif`
    ctx.fillStyle = '#c8c8c8'
    const info = `${this.formatDistance(this.trackData.distance)} · ${this.formatDuration(this.trackData.duration)}`
    ctx.fillText(info, infoX, infoY)
  }

  /**
   * 绘制水印
   */
  private drawWatermark(ctx: CanvasRenderingContext2D): void {
    const fontSize = 20
    ctx.font = `${fontSize}px "Microsoft YaHei", sans-serif`
    ctx.fillStyle = '#969696'
    ctx.textBaseline = 'bottom'

    const watermarkText = 'Vibe Route'
    const textWidth = ctx.measureText(watermarkText).width

    ctx.fillText(watermarkText, this.config.width - textWidth - 20, this.config.height - 40)
  }

  /**
   * 格式化距离
   */
  private formatDistance(meters: number): string {
    if (meters >= 1000) {
      return `${(meters / 1000).toFixed(2)} km`
    }
    return `${Math.round(meters)} m`
  }

  /**
   * 格式化时长
   */
  private formatDuration(seconds: number): string {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    if (hours > 0) {
      return `${hours}h ${minutes}m`
    }
    return `${minutes}m`
  }

  /**
   * 格式化海拔
   */
  private formatElevation(meters: number): string {
    if (meters >= 1000) {
      return `${(meters / 1000).toFixed(1)} km`
    }
    return `${Math.round(meters)} m`
  }
}

/**
 * 生成海报的便捷函数
 */
export async function generateFrontendPoster(
  config: PosterConfig,
  trackId: number,
  provider: string,
  posterSecret: string,
  trackData: TrackData,
  onProgress: PosterProgressCallback
): Promise<Blob> {
  const generator = new FrontendPosterGenerator(
    config,
    trackId,
    provider,
    posterSecret,
    trackData,
    onProgress
  )
  return generator.generate()
}
