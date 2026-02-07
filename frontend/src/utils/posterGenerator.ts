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
    console.log(`[PosterGenerator] ${stage}: ${message} (${percent}%)`)
  }

  async captureMap(mapElement: HTMLElement, scale: number = 2): Promise<string> {
    this.updateProgress('capturing', '正在捕获地图', 10)

    // 先隐藏所有控件
    const controls = mapElement.querySelectorAll(
      '.map-controls, .desktop-layer-selector, .mobile-layer-selector, ' +
      '.leaflet-control-zoom, .leaflet-control-scale, .leaflet-control-attribution, ' +
      '.live-update-time-btn, .clear-highlight-btn'
    )

    const originalDisplay: string[] = []
    for (let i = 0; i < controls.length; i++) {
      const el = controls[i] as HTMLElement
      originalDisplay[i] = el.style.display
      el.style.display = 'none'
    }

    try {
      // 获取容器尺寸
      const rect = mapElement.getBoundingClientRect()
      const width = rect.width || 800
      const height = rect.height || 600

      // 使用更高的分辨率捕获地图（2倍或3倍）
      // 这样放大后不会模糊
      const captureScale = Math.max(scale, 2)
      const result = await this.drawMapToCanvas(mapElement, width, height, captureScale)

      this.updateProgress('capturing', '地图捕获成功', 30)
      return result
    } finally {
      // 恢复控件显示
      for (let i = 0; i < controls.length; i++) {
        const el = controls[i] as HTMLElement
        el.style.display = originalDisplay[i] || ''
      }
    }
  }

  /**
   * 使用 canvas 直接捕获 WebGL 地图（高德/百度/腾讯）
   * 这些地图使用 Canvas2D/WebGL 渲染，可以直接绘制到新的 canvas
   */
  private async captureWebGLMap(mapElement: HTMLElement, scale: number): Promise<string> {
    console.log('[PosterGenerator] captureWebGLMap:', { scale })

    // 查找实际的地图 canvas
    const canvas = mapElement.querySelector('canvas') as HTMLCanvasElement
    if (!canvas) {
      throw new Error('找不到地图 canvas 元素')
    }

    // 获取 canvas 尺寸
    const canvasWidth = canvas.width || canvas.clientWidth
    const canvasHeight = canvas.height || canvas.clientHeight

    console.log('[PosterGenerator] WebGL canvas size:', `${canvasWidth} x ${canvasHeight}`)

    // 创建高分辨率 canvas
    const scaledWidth = Math.round(canvasWidth * scale)
    const scaledHeight = Math.round(canvasHeight * scale)

    const outputCanvas = document.createElement('canvas')
    outputCanvas.width = scaledWidth
    outputCanvas.height = scaledHeight
    const ctx = outputCanvas.getContext('2d')
    if (!ctx) throw new Error('无法创建输出 Canvas')

    // 启用图像平滑以获得更好的缩放效果
    ctx.imageSmoothingEnabled = true
    ctx.imageSmoothingQuality = 'high'

    // 直接绘制 canvas 内容并缩放
    ctx.drawImage(canvas, 0, 0, canvasWidth, canvasHeight, 0, 0, scaledWidth, scaledHeight)

    console.log('[PosterGenerator] WebGL capture complete:', `${scaledWidth} x ${scaledHeight}`)

    // 检查结果是否为空白
    const imageData = ctx.getImageData(0, 0, Math.min(100, scaledWidth), Math.min(100, scaledHeight))
    const data = imageData.data
    let hasContent = false
    for (let i = 0; i < data.length; i += 4) {
      const a = data[i + 3]
      if (a > 10) {
        const r = data[i]
        const g = data[i + 1]
        const b = data[i + 2]
        if (r < 240 || g < 240 || b < 240) {
          hasContent = true
          break
        }
      }
    }

    if (!hasContent) {
      console.warn('[PosterGenerator] WebGL capture resulted in blank image')
      throw new Error('WebGL 捕获结果为空白')
    }

    return outputCanvas.toDataURL('image/png')
  }

  /**
   * 直接在 canvas 上绘制地图瓦片和轨迹
   * 绕过 html2canvas 的 CORS 限制
   */
  private async drawMapToCanvas(
    mapElement: HTMLElement,
    width: number,
    height: number,
    scale: number
  ): Promise<string> {
    console.log('[PosterGenerator] drawMapToCanvas:', { width, height, scale })

    // 创建 canvas（使用缩放后的尺寸以获得更高分辨率）
    const scaledWidth = Math.round(width * scale)
    const scaledHeight = Math.round(height * scale)

    const canvas = document.createElement('canvas')
    canvas.width = scaledWidth
    canvas.height = scaledHeight
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('无法创建 Canvas 上下文')

    // 填充背景色
    ctx.fillStyle = '#e5e5e5'
    ctx.fillRect(0, 0, scaledWidth, scaledHeight)

    // 获取地图容器位置
    const mapRect = mapElement.getBoundingClientRect()
    console.log('[PosterGenerator] mapElement:', {
      className: mapElement.className,
      rect: `left=${mapRect.left.toFixed(1)}, top=${mapRect.top.toFixed(1)}, w=${mapRect.width.toFixed(1)}, h=${mapRect.height.toFixed(1)}`,
    })

    // 获取实际的地图容器（.leaflet-map-container 或 .map）
    let actualMapContainer = mapElement.querySelector('.map') as HTMLElement
    if (!actualMapContainer) {
      actualMapContainer = mapElement
    }
    const actualRect = actualMapContainer.getBoundingClientRect()
    console.log('[PosterGenerator] actualMapContainer:', {
      className: actualMapContainer.className,
      rect: `left=${actualRect.left.toFixed(1)}, top=${actualRect.top.toFixed(1)}, w=${actualRect.width.toFixed(1)}, h=${actualRect.height.toFixed(1)}`,
    })
    console.log('[PosterGenerator] canvas size:', `${scaledWidth} x ${scaledHeight} (scale: ${scale})`)

    // 获取所有瓦片图片
    const tilePane = mapElement.querySelector('.leaflet-tile-pane') as HTMLElement
    if (!tilePane) {
      // 不是 Leaflet 瓦片地图，尝试使用 WebGL/Canvas2D 捕获
      console.log('[PosterGenerator] Not a Leaflet tile map, trying WebGL capture')
      return await this.captureWebGLMap(mapElement, scale)
    }

    let tileImages = Array.from(tilePane.querySelectorAll('img')) as HTMLImageElement[]

    // 天地图可能有多个 tile container（底图+注记）
    if (tileImages.length === 0) {
      const allContainers = mapElement.querySelectorAll('.leaflet-tile-pane, .leaflet-tile-container')
      allContainers.forEach((container: HTMLElement) => {
        const imgs = Array.from(container.querySelectorAll('img')) as HTMLImageElement[]
        tileImages.push(...imgs)
      })
    }

    console.log('[PosterGenerator] found tiles:', tileImages.length)

    // 打印前3个瓦片的位置信息用于调试
    for (let i = 0; i < Math.min(3, tileImages.length); i++) {
      const img = tileImages[i]
      const imgRect = img.getBoundingClientRect()
      const x1 = imgRect.left - mapRect.left
      const y1 = imgRect.top - mapRect.top
      const x2 = imgRect.left - actualRect.left
      const y2 = imgRect.top - actualRect.top
      console.log(`[PosterGenerator] tile ${i}:`, {
        imgRect: `left=${imgRect.left.toFixed(1)}, top=${imgRect.top.toFixed(1)}, w=${imgRect.width.toFixed(1)}, h=${imgRect.height.toFixed(1)}`,
        naturalSize: `${img.naturalWidth}x${img.naturalHeight}`,
        pos1: `x=${x1.toFixed(1)}, y=${y1.toFixed(1)}`,
        pos2: `x=${x2.toFixed(1)}, y=${y2.toFixed(1)}`,
      })
    }

    // 绘制每个瓦片
    let tilesDrawn = 0
    const tilePromises: Promise<void>[] = []

    // 获取 tile pane 的位置（用于计算正确的偏移）
    const tilePaneRect = tilePane.getBoundingClientRect()
    let tilePaneOffsetX = tilePaneRect.left - actualRect.left
    let tilePaneOffsetY = tilePaneRect.top - actualRect.top

    // 如果 tile pane 大小为 0，使用第一个瓦片的位置作为参考
    if (tilePaneRect.width === 0 || tilePaneRect.height === 0) {
      if (tileImages.length > 0) {
        const firstImgRect = tileImages[0].getBoundingClientRect()
        tilePaneOffsetX = firstImgRect.left - actualRect.left
        tilePaneOffsetY = firstImgRect.top - actualRect.top
        console.log('[PosterGenerator] Using first tile position as reference')
      }
    }

    console.log('[PosterGenerator] tilePane:', {
      rect: `left=${tilePaneRect.left.toFixed(1)}, top=${tilePaneRect.top.toFixed(1)}, w=${tilePaneRect.width.toFixed(1)}, h=${tilePaneRect.height.toFixed(1)}`,
      offset: `x=${tilePaneOffsetX.toFixed(1)}, y=${tilePaneOffsetY.toFixed(1)}`,
      actualMapContainer: `w=${actualRect.width.toFixed(1)}, h=${actualRect.height.toFixed(1)}`,
    })

    for (const img of tileImages) {
      if (img.complete && img.naturalWidth > 0) {
        // 获取瓦片相对于 tile pane 的位置（而不是相对于视口）
        const imgRect = img.getBoundingClientRect()
        const x = imgRect.left - tilePaneRect.left
        const y = imgRect.top - tilePaneRect.top

        // 修正：如果 tile pane 大小为 0，直接使用相对于容器的位置
        let finalX: number
        let finalY: number
        if (tilePaneRect.width === 0 || tilePaneRect.height === 0) {
          finalX = (imgRect.left - actualRect.left) * scale
          finalY = (imgRect.top - actualRect.top) * scale
        } else {
          finalX = (x + tilePaneOffsetX) * scale
          finalY = (y + tilePaneOffsetY) * scale
        }

        // 使用自然尺寸并应用 scale
        const w = img.naturalWidth * scale
        const h = img.naturalHeight * scale

        // 只绘制在 canvas 范围内的瓦片（部分可见的也绘制）
        if (finalX + w > 0 && finalY + h > 0 && finalX < scaledWidth && finalY < scaledHeight) {
          // 检查瓦片是否有 crossOrigin，如果没有则重新加载
          if (!img.crossOrigin || img.crossOrigin === '') {
            console.log('[PosterGenerator] Reloading tile without crossOrigin:', img.src?.substring(0, 60))
            const success = await this.loadAndDrawTile(ctx, img.src, finalX, finalY, w, h)
            if (success) tilesDrawn++
          } else {
            // 先在临时 canvas 上测试，避免污染主 canvas
            const tempCanvas = document.createElement('canvas')
            tempCanvas.width = 1
            tempCanvas.height = 1
            const tempCtx = tempCanvas.getContext('2d')
            let canDrawSafely = false
            if (tempCtx) {
              try {
                tempCtx.drawImage(img, 0, 0, 1, 1)
                canDrawSafely = true
              } catch {
                console.warn('[PosterGenerator] Tile would taint canvas, skipping')
              }
            }

            if (canDrawSafely) {
              try {
                ctx.drawImage(img, finalX, finalY, w, h)
                tilesDrawn++
              } catch (e) {
                // 跨域错误，尝试重新加载
                console.warn('[PosterGenerator] CORS error for tile, attempting reload:', img.src?.substring(0, 50))
                const promise = this.loadAndDrawTile(ctx, img.src, finalX, finalY, w, h)
                tilePromises.push(promise)
              }
            } else {
              // 瓦片不安全，尝试重新加载
              console.log('[PosterGenerator] Tile unsafe, attempting reload')
              const promise = this.loadAndDrawTile(ctx, img.src, finalX, finalY, w, h)
              tilePromises.push(promise)
            }
          }
        }
      }
    }

    console.log('[PosterGenerator] tiles drawn:', tilesDrawn, 'pending reload:', tilePromises.length)

    // 等待所有需要重新加载的瓦片
    if (tilePromises.length > 0) {
      await Promise.race([
        Promise.all(tilePromises),
        new Promise(resolve => setTimeout(resolve, 3000))
      ])
    }

    // 绘制轨迹线（SVG）- 使用相同的参考点和缩放
    const overlayPane = mapElement.querySelector('.leaflet-overlay-pane') as HTMLElement
    if (overlayPane) {
      await this.drawSvgToCanvas(ctx, overlayPane, actualRect, scale)
    }

    const dataUrl = canvas.toDataURL('image/png')
    console.log('[PosterGenerator] final dataURL length:', dataUrl.length)

    // 检查结果
    const expectedMinSize = canvas.width * canvas.height * 0.05
    if (dataUrl.length < expectedMinSize && tilesDrawn === 0) {
      throw new Error(`地图捕获失败：生成的图片太小 (${dataUrl.length} bytes)，可能是瓦片加载失败`)
    }

    return dataUrl
  }

  /**
   * 重新加载瓦片并绘制到 canvas
   */
  private async loadAndDrawTile(
    ctx: CanvasRenderingContext2D,
    src: string | undefined,
    x: number,
    y: number,
    w: number,
    h: number
  ): Promise<boolean> {
    if (!src) return false

    return new Promise((resolve) => {
      const img = new Image()
      img.crossOrigin = 'anonymous'
      img.onload = () => {
        try {
          ctx.drawImage(img, x, y, w, h)
          resolve(true)
        } catch (e) {
          console.warn('[PosterGenerator] Failed to draw reloaded tile:', e)
          resolve(false)
        }
      }
      img.onerror = () => {
        console.warn('[PosterGenerator] Failed to load tile with CORS:', src?.substring(0, 60))
        resolve(false)
      }
      // 添加时间戳避免缓存
      const separator = src.includes('?') ? '&' : '?'
      img.src = src + separator + 't=' + Date.now()
    })
  }

  /**
   * 将 SVG 轨迹绘制到 canvas
   */
  private async drawSvgToCanvas(
    ctx: CanvasRenderingContext2D,
    overlayPane: HTMLElement,
    mapRect: DOMRect,
    scale: number = 1
  ): Promise<void> {
    const svgs = Array.from(overlayPane.querySelectorAll('svg'))
    console.log('[PosterGenerator] found SVGs:', svgs.length)

    for (const svg of svgs) {
      const svgRect = svg.getBoundingClientRect()
      const x = svgRect.left - mapRect.left
      const y = svgRect.top - mapRect.top

      console.log('[PosterGenerator] SVG rect:', {
        svgRect: `left=${svgRect.left.toFixed(1)}, top=${svgRect.top.toFixed(1)}, w=${svgRect.width.toFixed(1)}, h=${svgRect.height.toFixed(1)}`,
        mapRect: `left=${mapRect.left.toFixed(1)}, top=${mapRect.top.toFixed(1)}`,
        calculatedPos: `x=${x.toFixed(1)}, y=${y.toFixed(1)}`,
        viewBox: svg.getAttribute('viewBox'),
      })

      // 查找 SVG 内的 path 元素并直接绘制到 canvas
      const paths = Array.from(svg.querySelectorAll('path'))
      console.log('[PosterGenerator] found paths in SVG:', paths.length)

      // 解析 viewBox
      const viewBoxAttr = svg.getAttribute('viewBox')
      let viewBoxOffsetX = 0
      let viewBoxOffsetY = 0
      if (viewBoxAttr) {
        const parts = viewBoxAttr.split(/\s+/).map(parseFloat)
        if (parts.length >= 4) {
          viewBoxOffsetX = parts[0]
          viewBoxOffsetY = parts[1]
          console.log('[PosterGenerator] viewBox offset:', `x=${viewBoxOffsetX}, y=${viewBoxOffsetY}`)
        }
      }

      for (const path of paths) {
        const stroke = path.getAttribute('stroke') || '#ff0000'
        const strokeWidth = parseFloat(path.getAttribute('stroke-width') || '3')
        const d = path.getAttribute('d')

        if (d) {
          // 解析 path 数据并绘制
          ctx.strokeStyle = stroke
          ctx.lineWidth = strokeWidth * scale  // 缩放线条宽度
          ctx.lineCap = 'round'
          ctx.lineJoin = 'round'

          // 创建一个临时的 SVG path 元素来获取点坐标
          const tempPath = document.createElementNS('http://www.w3.org/2000/svg', 'path')
          tempPath.setAttribute('d', d)
          const svgElement = svg as SVGSVGElement
          const totalLength = tempPath.getTotalLength()

          ctx.beginPath()
          let firstPoint = true
          for (let i = 0; i <= totalLength; i += Math.min(5, totalLength / 1000)) {
            const point = tempPath.getPointAtLength(i)
            // SVG 坐标需要转换到 canvas 坐标，并应用缩放
            const canvasX = (x - viewBoxOffsetX + point.x) * scale
            const canvasY = (y - viewBoxOffsetY + point.y) * scale
            if (firstPoint) {
              console.log('[PosterGenerator] first point:', {
                svgPoint: `x=${point.x.toFixed(1)}, y=${point.y.toFixed(1)}`,
                svgPos: `x=${x.toFixed(1)}, y=${y.toFixed(1)}`,
                viewBoxOffset: `x=${viewBoxOffsetX}, y=${viewBoxOffsetY}`,
                canvasPos: `x=${canvasX.toFixed(1)}, y=${canvasY.toFixed(1)}`,
              })
              firstPoint = false
              ctx.moveTo(canvasX, canvasY)
            } else {
              ctx.lineTo(canvasX, canvasY)
            }
          }
          ctx.stroke()
          console.log('[PosterGenerator] path drawn')
        }
      }
    }
  }

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
      case 'minimal':
        await this.drawMinimalTemplate(ctx, data, width, height)
        break
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

  /**
   * 极简模板：只显示地图和轨迹，无文字信息
   */
  private async drawMinimalTemplate(
    ctx: CanvasRenderingContext2D,
    data: PosterData,
    width: number,
    height: number
  ): Promise<void> {
    // 地图铺满整张海报
    if (data.mapImage) {
      const img = new Image()
      await new Promise<void>((resolve) => {
        img.onload = () => resolve()
        img.onerror = () => resolve()
        img.src = data.mapImage!
      })

      const imgAspectRatio = img.width / img.height
      const targetAspectRatio = width / height

      let drawWidth: number
      let drawHeight: number
      let drawX: number
      let drawY: number

      if (imgAspectRatio > targetAspectRatio) {
        drawHeight = height
        drawWidth = height * imgAspectRatio
        drawX = (width - drawWidth) / 2
        drawY = 0
      } else {
        drawWidth = width
        drawHeight = width / imgAspectRatio
        drawX = 0
        drawY = (height - drawHeight) / 2
      }

      await this.drawImage(ctx, data.mapImage, drawX, drawY, drawWidth, drawHeight)
    }
    // 极简模板无文字信息
  }

  private async drawSimpleTemplate(
    ctx: CanvasRenderingContext2D,
    data: PosterData,
    width: number,
    height: number
  ): Promise<void> {
    // 地图铺满整张海报
    if (data.mapImage) {
      // 使用 object-fit: cover 的逻辑裁剪地图
      const img = new Image()
      await new Promise<void>((resolve) => {
        img.onload = () => resolve()
        img.onerror = () => resolve()
        img.src = data.mapImage!
      })

      const imgAspectRatio = img.width / img.height
      const targetAspectRatio = width / height

      let drawWidth: number
      let drawHeight: number
      let drawX: number
      let drawY: number

      if (imgAspectRatio > targetAspectRatio) {
        // 地图更宽，以高度为准裁剪
        drawHeight = height
        drawWidth = height * imgAspectRatio
        drawX = (width - drawWidth) / 2
        drawY = 0
      } else {
        // 地图更高，以宽度为准裁剪
        drawWidth = width
        drawHeight = width / imgAspectRatio
        drawX = 0
        drawY = (height - drawHeight) / 2
      }

      await this.drawImage(ctx, data.mapImage, drawX, drawY, drawWidth, drawHeight)
    } else {
      // 降级：填充背景色
      this.drawBackground(ctx, width, height, '#e5e5e5')
    }

    // 信息卡片放在底部，使用半透明背景
    const cardHeight = 140
    const cardY = height - cardHeight - 20
    this.drawInfoCard(ctx, data, 20, cardY, width - 40, cardHeight, 'simple')
  }

  private async drawRichTemplate(
    ctx: CanvasRenderingContext2D,
    data: PosterData,
    width: number,
    height: number
  ): Promise<void> {
    // 地图铺满整张海报作为背景
    if (data.mapImage) {
      const img = new Image()
      await new Promise<void>((resolve) => {
        img.onload = () => resolve()
        img.onerror = () => resolve()
        img.src = data.mapImage!
      })

      const imgAspectRatio = img.width / img.height
      const targetAspectRatio = width / height

      let drawWidth: number
      let drawHeight: number
      let drawX: number
      let drawY: number

      if (imgAspectRatio > targetAspectRatio) {
        drawHeight = height
        drawWidth = height * imgAspectRatio
        drawX = (width - drawWidth) / 2
        drawY = 0
      } else {
        drawWidth = width
        drawHeight = width / imgAspectRatio
        drawX = 0
        drawY = (height - drawHeight) / 2
      }

      await this.drawImage(ctx, data.mapImage, drawX, drawY, drawWidth, drawHeight)
    }

    // 信息卡片放在右侧
    const cardWidth = Math.min(400, width * 0.4)
    const cardHeight = Math.min(300, height * 0.5)
    const cardX = width - cardWidth - 20
    const cardY = height - cardHeight - 20
    this.drawInfoCard(ctx, data, cardX, cardY, cardWidth, cardHeight, 'rich')
  }

  private async drawGeoTemplate(
    ctx: CanvasRenderingContext2D,
    data: PosterData,
    width: number,
    height: number
  ): Promise<void> {
    // 地图铺满整张海报
    if (data.mapImage) {
      const img = new Image()
      await new Promise<void>((resolve) => {
        img.onload = () => resolve()
        img.onerror = () => resolve()
        img.src = data.mapImage!
      })

      const imgAspectRatio = img.width / img.height
      const targetAspectRatio = width / height

      let drawWidth: number
      let drawHeight: number
      let drawX: number
      let drawY: number

      if (imgAspectRatio > targetAspectRatio) {
        drawHeight = height
        drawWidth = height * imgAspectRatio
        drawX = (width - drawWidth) / 2
        drawY = 0
      } else {
        drawWidth = width
        drawHeight = width / imgAspectRatio
        drawX = 0
        drawY = (height - drawHeight) / 2
      }

      await this.drawImage(ctx, data.mapImage, drawX, drawY, drawWidth, drawHeight)
    } else {
      this.drawBackground(ctx, width, height, '#e5e5e5')
    }

    // 信息卡片放在底部，使用半透明背景
    const cardHeight = 140
    const cardY = height - cardHeight - 20
    this.drawInfoCard(ctx, data, 20, cardY, width - 40, cardHeight, 'geo')
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
    // 使用半透明背景，让地图能透过来
    ctx.shadowColor = 'rgba(0, 0, 0, 0.2)'
    ctx.shadowBlur = 20
    ctx.shadowOffsetX = 0
    ctx.shadowOffsetY = 4

    // 半透明白色背景
    ctx.fillStyle = 'rgba(255, 255, 255, 0.85)'
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
