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

  /**
   * 更新进度
   */
  private updateProgress(stage: PosterProgress['stage'], message: string, percent: number): void {
    this.progressCallback?.({ stage, message, percent })
  }

  /**
   * 捕获地图截图
   * @param mapElement 地图 DOM 元素
   * @param scale 缩放倍数（2 或 4）
   * @returns Base64 格式的图片数据
   */
  async captureMap(mapElement: HTMLElement, scale: number = 2): Promise<string> {
    this.updateProgress('capturing', `正在捕获地图 (scale=${scale})`, 10)

    // 对于 4K 分辨率，先尝试降级到 2K 以避免内存问题
    const actualScale = scale === 4 ? 2 : scale

    // 尝试最多 3 次
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        const canvas = await this.captureWithTimeout(mapElement, actualScale, 30000)

        this.updateProgress('capturing', '地图捕获成功', 30)
        return canvas.toDataURL('image/png')
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : String(error)
        console.warn(`地图捕获失败 (尝试 ${attempt}/3):`, errorMsg)

        // 如果是内存错误或者超时，且当前是 scale=2，尝试降级到 scale=1
        if ((errorMsg.includes('RangeError') || errorMsg.includes('timeout') || errorMsg.includes('memory')) && actualScale === 2 && attempt === 2) {
          console.log('降级到低分辨率模式 (scale=1)')
          this.updateProgress('capturing', '降级到低分辨率', 15)
          return this.captureMap(mapElement, 1)
        }

        if (attempt === 3) {
          // 最后尝试使用 scale=1
          if (actualScale > 1) {
            this.updateProgress('capturing', '降级到低分辨率', 15)
            return this.captureMap(mapElement, 1)
          }
          throw new Error('地图捕获失败，请重试')
        }
        // 等待 1 秒后重试
        await new Promise(resolve => setTimeout(resolve, 1000))
      }
    }

    throw new Error('地图捕获失败')
  }

  /**
   * 带超时的捕获地图
   */
  private captureWithTimeout(
    mapElement: HTMLElement,
    scale: number,
    timeoutMs: number
  ): Promise<HTMLCanvasElement> {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        reject(new Error(`捕获超时 (${timeoutMs}ms)`))
      }, timeoutMs)

      html2canvas(mapElement, {
        scale,
        useCORS: true,
        allowTaint: false,
        backgroundColor: null,
        logging: false,
      })
        .then(canvas => {
          clearTimeout(timer)
          resolve(canvas)
        })
        .catch(error => {
          clearTimeout(timer)
          reject(error)
        })
    })
  }

  /**
   * 生成海报
   * @param data 海报数据
   * @returns HTMLCanvasElement
   */
  async generate(data: PosterData): Promise<HTMLCanvasElement> {
    this.updateProgress('drawing', '正在绘制海报', 40)

    // 计算尺寸
    const preset = POSTER_SIZE_PRESETS[this.config.sizePreset] || POSTER_SIZE_PRESETS.portrait_1080
    const width = this.config.customWidth || preset.width
    const height = this.config.customHeight || preset.height
    const scale = preset.scale

    // 创建 Canvas
    const canvas = document.createElement('canvas')
    canvas.width = width * scale
    canvas.height = height * scale
    const ctx = canvas.getContext('2d')

    if (!ctx) {
      throw new Error('无法创建 Canvas 上下文')
    }

    // 缩放上下文以匹配 scale
    ctx.scale(scale, scale)

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

    // 绘制水印
    if (this.config.showWatermark) {
      this.drawWatermark(ctx, width, height)
    }

    this.updateProgress('done', '海报生成完成', 100)
    return canvas
  }

  /**
   * 绘制简洁模板
   */
  private async drawSimpleTemplate(
    ctx: CanvasRenderingContext2D,
    data: PosterData,
    width: number,
    height: number
  ): Promise<void> {
    // 绘制背景
    this.drawBackground(ctx, width, height, '#f5f7fa')

    // 地图区域（60%）
    const mapHeight = height * 0.6
    if (data.mapImage) {
      await this.drawImage(ctx, data.mapImage, 0, 0, width, mapHeight)
    }

    // 信息卡片区域（40%）
    const cardY = mapHeight
    const cardHeight = height - mapHeight
    this.drawInfoCard(ctx, data, 20, cardY + 20, width - 40, cardHeight - 40, 'simple')
  }

  /**
   * 绘制丰富模板（横版布局）
   */
  private async drawRichTemplate(
    ctx: CanvasRenderingContext2D,
    data: PosterData,
    width: number,
    height: number
  ): Promise<void> {
    // 绘制渐变背景
    const gradient = ctx.createLinearGradient(0, 0, width, height)
    gradient.addColorStop(0, '#667eea')
    gradient.addColorStop(1, '#764ba2')
    this.drawBackground(ctx, width, height, gradient)

    // 左侧地图（50%）
    const mapWidth = width * 0.5
    if (data.mapImage) {
      await this.drawImage(ctx, data.mapImage, 20, 20, mapWidth - 40, height - 40)
    }

    // 右侧信息面板（50%）
    const infoX = mapWidth
    const infoWidth = width - mapWidth
    this.drawInfoCard(ctx, data, infoX + 20, 20, infoWidth - 40, height - 40, 'rich')
  }

  /**
   * 绘制地理模板
   */
  private async drawGeoTemplate(
    ctx: CanvasRenderingContext2D,
    data: PosterData,
    width: number,
    height: number
  ): Promise<void> {
    // 绘制背景
    this.drawBackground(ctx, width, height, '#f5f7fa')

    // 地图区域（60%）
    const mapHeight = height * 0.6
    if (data.mapImage) {
      await this.drawImage(ctx, data.mapImage, 0, 0, width, mapHeight)
    }

    // 信息卡片区域（40%）
    const cardY = mapHeight
    const cardHeight = height - mapHeight
    this.drawInfoCard(ctx, data, 20, cardY + 20, width - 40, cardHeight - 40, 'geo')
  }

  /**
   * 绘制背景
   */
  private drawBackground(
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number,
    color: string | CanvasGradient
  ): void {
    ctx.fillStyle = color
    ctx.fillRect(0, 0, width, height)
  }

  /**
   * 绘制图片
   */
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
      img.onload = () => {
        ctx.drawImage(img, x, y, width, height)
        resolve()
      }
      img.onerror = () => reject(new Error('图片加载失败'))
      img.src = src
    })
  }

  /**
   * 绘制信息卡片
   */
  private drawInfoCard(
    ctx: CanvasRenderingContext2D,
    data: PosterData,
    x: number,
    y: number,
    width: number,
    height: number,
    template: 'simple' | 'rich' | 'geo'
  ): void {
    // 绘制卡片背景（白色带阴影）
    ctx.shadowColor = 'rgba(0, 0, 0, 0.1)'
    ctx.shadowBlur = 20
    ctx.shadowOffsetX = 0
    ctx.shadowOffsetY = 4
    ctx.fillStyle = '#ffffff'
    ctx.beginPath()
    this.roundRect(ctx, x, y, width, height, 16)
    ctx.fill()
    ctx.shadowColor = 'transparent'

    // 卡片内边距
    const padding = 24
    const contentX = x + padding
    const contentY = y + padding
    const contentWidth = width - padding * 2

    // 绘制标题
    this.drawText(ctx, data.name, contentX, contentY, contentWidth, 32, '#1f2937', 'bold', 'left')

    // 绘制日期
    this.drawText(ctx, data.date, contentX, contentY + 44, contentWidth, 16, '#6b7280', 'normal', 'left')

    // 根据模板绘制不同内容
    if (template === 'simple') {
      this.drawSimpleStats(ctx, data, contentX, contentY + 80, contentWidth)
    } else if (template === 'rich') {
      this.drawRichStats(ctx, data, contentX, contentY + 80, contentWidth)
    } else if (template === 'geo') {
      this.drawGeoStats(ctx, data, contentX, contentY + 80, contentWidth)
    }
  }

  /**
   * 绘制圆角矩形
   */
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

  /**
   * 绘制简洁统计信息
   */
  private drawSimpleStats(
    ctx: CanvasRenderingContext2D,
    data: PosterData,
    x: number,
    y: number,
    width: number
  ): void {
    const itemWidth = width / 2 - 12

    // 里程
    this.drawStatItem(ctx, '里程', this.formatDistance(data.distance), x, y, itemWidth)
    // 时长
    this.drawStatItem(ctx, '时长', this.formatDuration(data.duration), x + itemWidth + 24, y, itemWidth)
  }

  /**
   * 绘制丰富统计信息
   */
  private drawRichStats(
    ctx: CanvasRenderingContext2D,
    data: PosterData,
    x: number,
    y: number,
    width: number
  ): void {
    const itemWidth = width / 2 - 12
    const itemHeight = 80

    // 第一行
    this.drawStatItem(ctx, '里程', this.formatDistance(data.distance), x, y, itemWidth)
    this.drawStatItem(ctx, '时长', this.formatDuration(data.duration), x + itemWidth + 24, y, itemWidth)

    // 第二行
    if (data.avgSpeed !== undefined) {
      this.drawStatItem(ctx, '平均速度', this.formatSpeed(data.avgSpeed), x, y + itemHeight, itemWidth)
    }
    if (data.maxSpeed !== undefined) {
      this.drawStatItem(ctx, '最高速度', this.formatSpeed(data.maxSpeed), x + itemWidth + 24, y + itemHeight, itemWidth)
    }

    // 第三行
    this.drawStatItem(ctx, '爬升', `${Math.round(data.elevationGain)} m`, x, y + itemHeight * 2, itemWidth)
    this.drawStatItem(ctx, '下降', `${Math.round(data.elevationLoss)} m`, x + itemWidth + 24, y + itemHeight * 2, itemWidth)
  }

  /**
   * 绘制地理统计信息
   */
  private drawGeoStats(
    ctx: CanvasRenderingContext2D,
    data: PosterData,
    x: number,
    y: number,
    width: number
  ): void {
    const itemWidth = width / 2 - 12

    // 里程和时长
    this.drawStatItem(ctx, '里程', this.formatDistance(data.distance), x, y, itemWidth)
    this.drawStatItem(ctx, '时长', this.formatDuration(data.duration), x + itemWidth + 24, y, itemWidth)

    // 经过区域
    if (data.regions && data.regions.length > 0) {
      const regionY = y + 80
      this.drawText(ctx, '经过区域', x, regionY, width, 14, '#6b7280', 'normal', 'left')

      const displayRegions = data.regions.slice(0, 5)
      const regionText = displayRegions.join(' · ') + (data.regions.length > 5 ? ' ...' : '')
      this.drawText(ctx, regionText, x, regionY + 24, width, 16, '#374151', 'normal', 'left')
    }
  }

  /**
   * 绘制统计项
   */
  private drawStatItem(
    ctx: CanvasRenderingContext2D,
    label: string,
    value: string,
    x: number,
    y: number,
    width: number
  ): void {
    // 标签
    this.drawText(ctx, label, x, y, width, 14, '#6b7280', 'normal', 'left')
    // 数值
    this.drawText(ctx, value, x, y + 24, width, 24, '#1f2937', 'bold', 'left')
  }

  /**
   * 绘制文本
   */
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
    // 如果文本为空，显示占位符
    const displayText = text || '--'

    ctx.font = `${fontWeight} ${fontSize}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`
    ctx.fillStyle = color
    ctx.textAlign = align

    const textX = align === 'center' ? x + maxWidth / 2 : align === 'right' ? x + maxWidth : x
    ctx.fillText(displayText, textX, y + fontSize)
  }

  /**
   * 绘制水印
   */
  private drawWatermark(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    ctx.save()
    ctx.translate(width / 2, height - 30)
    ctx.font = '12px -apple-system, sans-serif'
    ctx.fillStyle = 'rgba(0, 0, 0, 0.3)'
    ctx.textAlign = 'center'
    ctx.fillText('由 Vibe Route 生成', 0, 0)
    ctx.restore()
  }

  /**
   * 格式化距离
   */
  private formatDistance(meters: number): string {
    if (meters < 1000) {
      return `${Math.round(meters)} m`
    }
    const km = (meters / 1000).toFixed(2)
    return km.endsWith('.00') ? `${km.slice(0, -3)} km` : `${km} km`
  }

  /**
   * 格式化时长
   */
  private formatDuration(seconds: number): string {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)

    if (hours > 0) {
      return `${hours}h ${minutes}min`
    }
    return `${minutes}min`
  }

  /**
   * 格式化速度
   */
  private formatSpeed(speedMps: number): string {
    const kmh = speedMps * 3.6
    return `${kmh.toFixed(1)} km/h`
  }

  /**
   * 下载海报
   */
  downloadPoster(canvas: HTMLCanvasElement, filename: string): void {
    const link = document.createElement('a')
    link.download = `${filename}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
  }
}

export { POSTER_SIZE_PRESETS }
