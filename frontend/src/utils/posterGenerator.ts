/**
 * 海报生成工具类
 * 用于将轨迹数据导出为高清图片
 */

import html2canvas from 'html2canvas'
import type { PosterConfig, PosterData, PosterProgress } from '@/types/poster'
import { POSTER_SIZE_PRESETS } from '@/types/poster'

export class PosterGenerator {
  private config: PosterConfig
  private progressCallback?: (progress: PosterProgress) => void

  constructor(config: PosterConfig, progressCallback?: (progress: PosterProgress) => void) {
    this.config = config
    this.progressCallback = progressCallback
  }

  private updateProgress(stage: PosterProgress['stage'], message: string, percent: number): void {
    this.progressCallback?.({ stage, message, percent })
  }

  /**
   * 捕获地图截图
   */
  async captureMap(mapElement: HTMLElement, scale: number = 2): Promise<string> {
    this.updateProgress('capturing', '正在捕获地图', 10)

    // 检测地图类型
    const hasLeaflet = mapElement.querySelector('.leaflet-container') !== null

    // 对于 Leaflet 地图，使用 html2canvas
    if (hasLeaflet) {
      return this.captureLeafletMap(mapElement, scale)
    }

    // 对于其他地图，尝试直接从 canvas 获取
    const canvasElements = mapElement.querySelectorAll('canvas')
    for (const canvas of Array.from(canvasElements)) {
      const htmlCanvas = canvas as HTMLCanvasElement
      try {
        const dataUrl = htmlCanvas.toDataURL('image/png')
        // 检查是否是有效的图片（不是空白）
        if (dataUrl && dataUrl.length > 1000) {
          this.updateProgress('capturing', '地图捕获成功', 30)
          return dataUrl
        }
      } catch {
        // 继续尝试下一个 canvas
      }
    }

    throw new Error('无法捕获地图，请切换到 Leaflet 地图（天地图/OSM）')
  }

  /**
   * 捕获 Leaflet 地图
   */
  private async captureLeafletMap(mapElement: HTMLElement, scale: number): Promise<string> {
    // 先隐藏所有控件
    const controls = mapElement.querySelectorAll(
      '.map-controls, .desktop-layer-selector, .mobile-layer-selector, ' +
      '.leaflet-control-zoom, .leaflet-control-scale, .leaflet-control-attribution, ' +
      '.live-update-time-btn, .clear-highlight-btn'
    )
    const originalDisplay: string[] = []
    controls.forEach((el, i) => {
      originalDisplay[i] = (el as HTMLElement).style.display
      ;(el as HTMLElement).style.display = 'none'
    })

    try {
      // 获取容器尺寸
      const rect = mapElement.getBoundingClientRect()
      const width = rect.width || 800
      const height = rect.height || 600

      // 配置 html2canvas
      const options: any = {
        scale,
        useCORS: true,
        allowTaint: true,
        backgroundColor: '#e8e8e8',
        logging: false,
        imageTimeout: 20000,
        width,
        height,
        windowWidth: width,
        windowHeight: height,
      }

      const canvas = await html2canvas(mapElement, options)
      this.updateProgress('capturing', '地图捕获成功', 30)
      return canvas.toDataURL('image/png')
    } finally {
      // 恢复控件显示
      controls.forEach((el, i) => {
        ;(el as HTMLElement).style.display = originalDisplay[i] || ''
      })
    }
  }

  /**
   * 生成海报
   */
  async generate(data: PosterData): Promise<HTMLCanvasElement> {
    this.updateProgress('drawing', '正在绘制海报', 40)

    const preset = POSTER_SIZE_PRESETS[this.config.sizePreset] || POSTER_SIZE_PRESETS.landscape_1080
    const width = this.config.customWidth || preset.width
    const height = this.config.customHeight || preset.height
    const scaleFactor = preset.scale

    const canvas = document.createElement('canvas')
    canvas.width = width * scaleFactor
    canvas.height = height * scaleFactor
    const ctx = canvas.getContext('2d')

    if (!ctx) {
      throw new Error('无法创建 Canvas 上下文')
    }

    ctx.scale(scaleFactor, scaleFactor)

    // 根据模板绘制
    switch (this.config.template) {
      case 'simple':
        await this.drawSimpleTemplate(ctx, data, width, height)
        break
      case 'rich':
        await this.drawRichTemplate(ctx, data, width, height)
        break
      case 'geo':
        await this.drawGeoTemplate(ctx, data, width, height)
        break
    }

    if (this.config.showWatermark) {
      this.drawWatermark(ctx, width, height)
    }

    this.updateProgress('done', '海报生成完成', 100)
    return canvas
  }

  private async drawSimpleTemplate(
    ctx: CanvasRenderingContext2D,
    data: PosterData,
    width: number,
    height: number
  ): Promise<void> {
    this.drawBackground(ctx, width, height, '#f5f7fa')

    const mapHeight = height * 0.6
    if (data.mapImage) {
      await this.drawImage(ctx, data.mapImage, 0, 0, width, mapHeight)
    }

    const cardY = mapHeight
    const cardHeight = height - mapHeight
    this.drawInfoCard(ctx, data, 20, cardY + 20, width - 40, cardHeight - 40, 'simple')
  }

  private async drawRichTemplate(
    ctx: CanvasRenderingContext2D,
    data: PosterData,
    width: number,
    height: number
  ): Promise<void> {
    const gradient = ctx.createLinearGradient(0, 0, width, height)
    gradient.addColorStop(0, '#667eea')
    gradient.addColorStop(1, '#764ba2')
    this.drawBackground(ctx, width, height, gradient)

    const mapWidth = width * 0.5
    if (data.mapImage) {
      await this.drawImage(ctx, data.mapImage, 20, 20, mapWidth - 40, height - 40)
    }

    const infoX = mapWidth
    const infoWidth = width - mapWidth
    this.drawInfoCard(ctx, data, infoX + 20, 20, infoWidth - 40, height - 40, 'rich')
  }

  private async drawGeoTemplate(
    ctx: CanvasRenderingContext2D,
    data: PosterData,
    width: number,
    height: number
  ): Promise<void> {
    this.drawBackground(ctx, width, height, '#f5f7fa')

    const mapHeight = height * 0.6
    if (data.mapImage) {
      await this.drawImage(ctx, data.mapImage, 0, 0, width, mapHeight)
    }

    const cardY = mapHeight
    const cardHeight = height - mapHeight
    this.drawInfoCard(ctx, data, 20, cardY + 20, width - 40, cardHeight - 40, 'geo')
  }

  private drawBackground(
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number,
    color: string | CanvasGradient
  ): void {
    ctx.fillStyle = color
    ctx.fillRect(0, 0, width, height)
  }

  private async drawImage(
    ctx: CanvasRenderingContext2D,
    src: string,
    x: number,
    y: number,
    width: number,
    height: number
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      const img = new Image()
      img.crossOrigin = 'anonymous'
      img.onload = () => {
        ctx.drawImage(img, x, y, width, height)
        resolve()
      }
      img.onerror = () => reject(new Error('图片加载失败'))
      img.src = src
    })
  }

  private drawInfoCard(
    ctx: CanvasRenderingContext2D,
    data: PosterData,
    x: number,
    y: number,
    width: number,
    height: number,
    template: 'simple' | 'rich' | 'geo'
  ): void {
    ctx.shadowColor = 'rgba(0, 0, 0, 0.1)'
    ctx.shadowBlur = 20
    ctx.shadowOffsetX = 0
    ctx.shadowOffsetY = 4
    ctx.fillStyle = '#ffffff'
    ctx.beginPath()
    this.roundRect(ctx, x, y, width, height, 16)
    ctx.fill()
    ctx.shadowColor = 'transparent'

    const padding = 24
    const contentX = x + padding
    const contentY = y + padding
    const contentWidth = width - padding * 2

    this.drawText(ctx, data.name, contentX, contentY, contentWidth, 32, '#1f2937', 'bold', 'left')
    this.drawText(ctx, data.date, contentX, contentY + 44, contentWidth, 16, '#6b7280', 'normal', 'left')

    if (template === 'simple') {
      this.drawSimpleStats(ctx, data, contentX, contentY + 80, contentWidth)
    } else if (template === 'rich') {
      this.drawRichStats(ctx, data, contentX, contentY + 80, contentWidth)
    } else if (template === 'geo') {
      this.drawGeoStats(ctx, data, contentX, contentY + 80, contentWidth)
    }
  }

  private roundRect(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    width: number,
    height: number,
    radius: number
  ): void {
    ctx.moveTo(x + radius, y)
    ctx.lineTo(x + width - radius, y)
    ctx.quadraticCurveTo(x + width, y, x + width, y + radius)
    ctx.lineTo(x + width, y + height - radius)
    ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height)
    ctx.lineTo(x + radius, y + height)
    ctx.quadraticCurveTo(x, y + height, x, y + height - radius)
    ctx.lineTo(x, y + radius)
    ctx.quadraticCurveTo(x, y, x + radius, y)
    ctx.closePath()
  }

  private drawSimpleStats(
    ctx: CanvasRenderingContext2D,
    data: PosterData,
    x: number,
    y: number,
    width: number
  ): void {
    const itemWidth = width / 2 - 12
    this.drawStatItem(ctx, '里程', this.formatDistance(data.distance), x, y, itemWidth)
    this.drawStatItem(ctx, '时长', this.formatDuration(data.duration), x + itemWidth + 24, y, itemWidth)
  }

  private drawRichStats(
    ctx: CanvasRenderingContext2D,
    data: PosterData,
    x: number,
    y: number,
    width: number
  ): void {
    const itemWidth = width / 2 - 12
    const itemHeight = 80

    this.drawStatItem(ctx, '里程', this.formatDistance(data.distance), x, y, itemWidth)
    this.drawStatItem(ctx, '时长', this.formatDuration(data.duration), x + itemWidth + 24, y, itemWidth)

    if (data.avgSpeed !== undefined) {
      this.drawStatItem(ctx, '平均速度', this.formatSpeed(data.avgSpeed), x, y + itemHeight, itemWidth)
    }
    if (data.maxSpeed !== undefined) {
      this.drawStatItem(ctx, '最高速度', this.formatSpeed(data.maxSpeed), x + itemWidth + 24, y + itemHeight, itemWidth)
    }

    this.drawStatItem(ctx, '爬升', `${Math.round(data.elevationGain)} m`, x, y + itemHeight * 2, itemWidth)
    this.drawStatItem(ctx, '下降', `${Math.round(data.elevationLoss)} m`, x + itemWidth + 24, y + itemHeight * 2, itemWidth)
  }

  private drawGeoStats(
    ctx: CanvasRenderingContext2D,
    data: PosterData,
    x: number,
    y: number,
    width: number
  ): void {
    const itemWidth = width / 2 - 12
    this.drawStatItem(ctx, '里程', this.formatDistance(data.distance), x, y, itemWidth)
    this.drawStatItem(ctx, '时长', this.formatDuration(data.duration), x + itemWidth + 24, y, itemWidth)

    if (data.regions && data.regions.length > 0) {
      const regionY = y + 80
      this.drawText(ctx, '经过区域', x, regionY, width, 14, '#6b7280', 'normal', 'left')
      const displayRegions = data.regions.slice(0, 5)
      const regionText = displayRegions.join(' · ') + (data.regions.length > 5 ? ' ...' : '')
      this.drawText(ctx, regionText, x, regionY + 24, width, 16, '#374151', 'normal', 'left')
    }
  }

  private drawStatItem(
    ctx: CanvasRenderingContext2D,
    label: string,
    value: string,
    x: number,
    y: number,
    width: number
  ): void {
    this.drawText(ctx, label, x, y, width, 14, '#6b7280', 'normal', 'left')
    this.drawText(ctx, value, x, y + 24, width, 24, '#1f2937', 'bold', 'left')
  }

  private drawText(
    ctx: CanvasRenderingContext2D,
    text: string,
    x: number,
    y: number,
    maxWidth: number,
    fontSize: number,
    color: string,
    fontWeight: 'normal' | 'bold',
    align: 'left' | 'center' | 'right'
  ): void {
    const displayText = text || '--'
    ctx.font = `${fontWeight} ${fontSize}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
    ctx.fillStyle = color
    ctx.textAlign = align
    const textX = align === 'center' ? x + maxWidth / 2 : align === 'right' ? x + maxWidth : x
    ctx.fillText(displayText, textX, y + fontSize)
  }

  private drawWatermark(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    ctx.save()
    ctx.translate(width / 2, height - 30)
    ctx.font = '12px -apple-system, sans-serif'
    ctx.fillStyle = 'rgba(0, 0, 0, 0.3)'
    ctx.textAlign = 'center'
    ctx.fillText('由 Vibe Route 生成', 0, 0)
    ctx.restore()
  }

  private formatDistance(meters: number): string {
    if (meters < 1000) {
      return `${Math.round(meters)} m`
    }
    const km = (meters / 1000).toFixed(2)
    return km.endsWith('.00') ? `${km.slice(0, -3)} km` : `${km} km`
  }

  private formatDuration(seconds: number): string {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    if (hours > 0) {
      return `${hours}h ${minutes}min`
    }
    return `${minutes}min`
  }

  private formatSpeed(speedMps: number): string {
    const kmh = speedMps * 3.6
    return `${kmh.toFixed(1)} km/h`
  }

  downloadPoster(canvas: HTMLCanvasElement, filename: string): void {
    const link = document.createElement('a')
    link.download = `${filename}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
  }
}

export { POSTER_SIZE_PRESETS }
