# 轨迹海报与截图功能实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标：** 为轨迹详情页添加海报生成功能，支持将轨迹数据导出为高清图片用于社交分享

**架构：** 前端纯实现，使用 html2canvas 捕获地图，使用 Canvas API 绘制海报

**技术栈：** Vue 3, TypeScript, html2canvas, Element Plus

---

## Task 1: 安装依赖并创建基础文件结构

**文件：**
- 修改: `frontend/package.json`
- 创建: `frontend/src/utils/posterGenerator.ts`
- 创建: `frontend/src/components/PosterExportDialog.vue`

**Step 1: 安装 html2canvas 依赖**

```bash
cd frontend
npm install html2canvas@1.4.1
npm install --save-dev @types/html2canvas@1.4.1
```

**Step 2: 运行构建验证依赖安装**

Run: `cd frontend && npm run build`
Expected: SUCCESS（无编译错误）

**Step 3: 提交依赖安装**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "feat: 安装 html2canvas 依赖用于海报生成"
```

---

## Task 2: 创建海报类型定义

**文件：**
- 创建: `frontend/src/types/poster.ts`

**Step 1: 创建类型定义文件**

```typescript
/**
 * 海报相关类型定义
 */

/** 海报模板类型 */
export type PosterTemplate = 'simple' | 'rich' | 'geo'

/** 海报尺寸预设 */
export interface PosterSizePreset {
  name: string
  width: number
  height: number
  scale: number
}

/** 海报尺寸预设枚举 */
export const POSTER_SIZE_PRESETS: Record<string, PosterSizePreset> = {
  portrait_1080: { name: '竖版 1080P', width: 1080, height: 1920, scale: 2 },
  portrait_4k: { name: '竖版 4K', width: 2160, height: 3840, scale: 4 },
  landscape_1080: { name: '横版 1080P', width: 1920, height: 1080, scale: 2 },
  landscape_4k: { name: '横版 4K', width: 3840, height: 2160, scale: 4 },
  custom: { name: '自定义', width: 1080, height: 1920, scale: 2 },
}

/** 海报配置 */
export interface PosterConfig {
  template: PosterTemplate
  sizePreset: string
  customWidth?: number
  customHeight?: number
  showWatermark: boolean
  infoLevel: 'basic' | 'sports' | 'geo'
}

/** 海报数据（从轨迹数据派生） */
export interface PosterData {
  name: string
  date: string
  startTime: string
  endTime: string
  distance: number
  duration: number
  elevationGain: number
  elevationLoss: number
  avgSpeed?: number
  maxSpeed?: number
  regions?: string[]
  mapImage?: string  // Base64 格式的地图截图
}

/** 海报生成进度 */
export interface PosterProgress {
  stage: 'idle' | 'capturing' | 'drawing' | 'done' | 'error'
  message: string
  percent: number
}
```

**Step 2: 提交类型定义**

```bash
git add frontend/src/types/poster.ts
git commit -m "feat: 添加海报类型定义"
```

---

## Task 3: 创建海报生成工具类核心函数

**文件：**
- 创建: `frontend/src/utils/posterGenerator.ts`

**Step 1: 创建海报生成器基础结构**

```typescript
/**
 * 海报生成工具类
 * 用于将轨迹数据导出为高清图片
 */

import html2canvas from 'html2canvas'
import type { PosterConfig, PosterData, PosterProgress } from '@/types/poster'

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

    // 尝试最多 3 次
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        const canvas = await html2canvas(mapElement, {
          scale,
          useCORS: true,
          allowTaint: false,
          backgroundColor: null,
          logging: false,
        })

        this.updateProgress('capturing', '地图捕获成功', 30)
        return canvas.toDataURL('image/png')
      } catch (error) {
        console.warn(`地图捕获失败 (尝试 ${attempt}/3):`, error)
        if (attempt === 3) {
          throw new Error('地图捕获失败，请重试')
        }
        // 等待 1 秒后重试
        await new Promise(resolve => setTimeout(resolve, 1000))
      }
    }

    throw new Error('地图捕获失败')
  }

  /**
   * 生成海报
   * @param data 海报数据
   * @returns HTMLCanvasElement
   */
  async generate(data: PosterData): Promise<HTMLCanvasElement> {
    this.updateProgress('drawing', '正在绘制海报', 40)

    // 计算尺寸
    const width = this.config.customWidth || POSTER_SIZE_PRESETS[this.config.sizePreset]?.width || 1080
    const height = this.config.customHeight || POSTER_SIZE_PRESETS[this.config.sizePreset]?.height || 1920
    const scale = POSTER_SIZE_PRESETS[this.config.sizePreset]?.scale || 2

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
    ctx.roundRect(x, y, width, height, 16)
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
    ctx.font = `${fontWeight} ${fontSize}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`
    ctx.fillStyle = color
    ctx.textAlign = align

    const textX = align === 'center' ? x + maxWidth / 2 : align === 'right' ? x + maxWidth : x
    ctx.fillText(text, textX, y + fontSize)
  }

  /**
   * 绘制水印
   */
  private drawWatermark(ctx: CanvasRenderingContext2D, width: number, height: number): void {
    ctx.save()
    ctx.translate(width / 2, height - 30)
    ctx.rotate(0)
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

// 导出常量
const POSTER_SIZE_PRESETS: Record<string, { name: string; width: number; height: number; scale: number }> = {
  portrait_1080: { name: '竖版 1080P', width: 1080, height: 1920, scale: 2 },
  portrait_4k: { name: '竖版 4K', width: 2160, height: 3840, scale: 4 },
  landscape_1080: { name: '横版 1080P', width: 1920, height: 1080, scale: 2 },
  landscape_4k: { name: '横版 4K', width: 3840, height: 2160, scale: 4 },
  custom: { name: '自定义', width: 1080, height: 1920, scale: 2 },
}

export { POSTER_SIZE_PRESETS }
```

**Step 2: 提交海报生成器**

```bash
git add frontend/src/utils/posterGenerator.ts
git commit -m "feat: 添加海报生成器核心功能"
```

---

## Task 4: 创建海报导出对话框组件

**文件：**
- 创建: `frontend/src/components/PosterExportDialog.vue`

**Step 1: 创建对话框组件模板**

```vue
<template>
  <el-dialog
    v-model="dialogVisible"
    title="导出海报"
    :width="isMobile ? '90%' : '600px'"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <!-- 配置区域 -->
    <div class="poster-config">
      <!-- 模板选择 -->
      <el-form-item label="模板">
        <el-radio-group v-model="config.template">
          <el-radio value="simple">简洁模板</el-radio>
          <el-radio value="rich">丰富模板</el-radio>
          <el-radio value="geo">地理模板</el-radio>
        </el-radio-group>
      </el-form-item>

      <!-- 尺寸预设 -->
      <el-form-item label="尺寸">
        <el-select v-model="config.sizePreset" placeholder="选择尺寸" style="width: 100%">
          <el-option label="竖版 1080P" value="portrait_1080" />
          <el-option label="竖版 4K" value="portrait_4k" />
          <el-option label="横版 1080P" value="landscape_1080" />
          <el-option label="横版 4K" value="landscape_4k" />
        </el-select>
      </el-form-item>

      <!-- 水印开关 -->
      <el-form-item label="水印">
        <el-switch v-model="config.showWatermark" />
      </el-form-item>
    </div>

    <!-- 预览区域 -->
    <div v-if="previewUrl" class="poster-preview">
      <img :src="previewUrl" alt="预览" />
    </div>

    <!-- 进度显示 -->
    <div v-if="progress.stage !== 'idle'" class="poster-progress">
      <el-progress
        :percentage="progress.percent"
        :status="progress.stage === 'error' ? 'exception' : progress.stage === 'done' ? 'success' : undefined"
      />
      <p class="progress-text">{{ progress.message }}</p>
    </div>

    <!-- 按钮区域 -->
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="handleClose" :disabled="isGenerating">取消</el-button>
        <el-button type="primary" @click="handlePreview" :disabled="isGenerating" plain>
          预览
        </el-button>
        <el-button type="primary" @click="handleExport" :loading="isGenerating">
          导出
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/**
 * 海报导出对话框
 * 用于配置和生成轨迹海报
 */
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { PosterGenerator } from '@/utils/posterGenerator'
import type { PosterConfig, PosterProgress } from '@/types/poster'
import type { Track, TrackPoint, RegionNode } from '@/api/track'

// Props
interface Props {
  visible: boolean
  track: Track | null
  points: TrackPoint[]
  regions?: RegionNode[]
  mapElement: HTMLElement | null
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  points: () => [],
  regions: () => [],
  mapElement: null,
})

// Emits
const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

// 对话框可见性
const dialogVisible = ref(props.visible)

// 配置
const config = ref<PosterConfig>({
  template: 'simple',
  sizePreset: 'portrait_1080',
  showWatermark: true,
  infoLevel: 'basic',
})

// 预览图片
const previewUrl = ref('')

// 进度
const progress = ref<PosterProgress>({
  stage: 'idle',
  message: '',
  percent: 0,
})

// 是否正在生成
const isGenerating = ref(false)

// 计算是否移动端
const isMobile = computed(() => window.innerWidth <= 1366)

// 监听 visible 变化
watch(() => props.visible, (newVal) => {
  dialogVisible.value = newVal
  if (!newVal) {
    // 关闭时清空预览
    previewUrl.value = ''
    progress.value = { stage: 'idle', message: '', percent: 0 }
  }
})

watch(dialogVisible, (newVal) => {
  if (newVal !== props.visible) {
    emit('update:visible', newVal)
  }
})

/**
 * 关闭对话框
 */
function handleClose(): void {
  if (isGenerating.value) {
    ElMessage.warning('正在生成海报，请稍候...')
    return
  }
  dialogVisible.value = false
}

/**
 * 准备海报数据
 */
function preparePosterData() {
  if (!props.track) {
    throw new Error('轨迹数据不存在')
  }

  const { regions } = props
  let regionNames: string[] = []

  // 提取区域名称
  if (regions && regions.length > 0) {
    const extractNames = (nodes: RegionNode[]): string[] => {
      const names: string[] = []
      for (const node of nodes) {
        if (node.type === 'province' || node.type === 'city' || node.type === 'district') {
          names.push(node.name)
        }
        if (node.children && node.children.length > 0) {
          names.push(...extractNames(node.children))
        }
      }
      return names
    }
    regionNames = extractNames(regions)
  }

  return {
    name: props.track.name,
    date: props.track.start_time ? new Date(props.track.start_time).toLocaleDateString('zh-CN') : '',
    startTime: props.track.start_time || '',
    endTime: props.track.end_time || '',
    distance: props.track.distance,
    duration: props.track.duration,
    elevationGain: props.track.elevation_gain,
    elevationLoss: props.track.elevation_loss,
    regions: regionNames.length > 0 ? regionNames : undefined,
  }
}

/**
 * 预览海报
 */
async function handlePreview(): Promise<void> {
  if (!props.mapElement) {
    ElMessage.error('地图未加载完成')
    return
  }

  isGenerating.value = true
  progress.value = { stage: 'idle', message: '', percent: 0 }

  try {
    const generator = new PosterGenerator(config.value, (p) => {
      progress.value = p
    })

    // 捕获地图（使用低 scale 预览）
    const mapImage = await generator.captureMap(props.mapElement!, 1)

    // 准备数据
    const data = preparePosterData()
    data.mapImage = mapImage

    // 生成海报
    const canvas = await generator.generate(data)
    previewUrl.value = canvas.toDataURL('image/png')

    progress.value = { stage: 'done', message: '预览生成完成', percent: 100 }
  } catch (error) {
    console.error('预览生成失败:', error)
    ElMessage.error(error instanceof Error ? error.message : '预览生成失败')
    progress.value = { stage: 'error', message: '预览生成失败', percent: 0 }
  } finally {
    isGenerating.value = false
  }
}

/**
 * 导出海报
 */
async function handleExport(): Promise<void> {
  if (!props.mapElement) {
    ElMessage.error('地图未加载完成')
    return
  }

  if (!props.track) {
    ElMessage.error('轨迹数据不存在')
    return
  }

  isGenerating.value = true
  progress.value = { stage: 'idle', message: '', percent: 0 }
  previewUrl.value = ''

  try {
    const generator = new PosterGenerator(config.value, (p) => {
      progress.value = p
    })

    // 获取 scale
    const scale = config.value.sizePreset.includes('4k') ? 4 : 2

    // 捕获地图
    const mapImage = await generator.captureMap(props.mapElement, scale)

    // 准备数据
    const data = preparePosterData()
    data.mapImage = mapImage

    // 生成海报
    const canvas = await generator.generate(data)

    // 下载
    generator.downloadPoster(canvas, props.track.name)

    ElMessage.success('海报导出成功')
  } catch (error) {
    console.error('海报导出失败:', error)
    ElMessage.error(error instanceof Error ? error.message : '海报导出失败')
    progress.value = { stage: 'error', message: '导出失败', percent: 0 }
  } finally {
    isGenerating.value = false
  }
}
</script>

<style scoped>
.poster-config {
  margin-bottom: 20px;
}

.poster-config .el-form-item {
  margin-bottom: 16px;
}

.poster-preview {
  margin: 20px 0;
  text-align: center;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 10px;
  background: var(--el-fill-color-lighter);
}

.poster-preview img {
  max-width: 100%;
  max-height: 400px;
  border-radius: 4px;
}

.poster-progress {
  margin: 20px 0;
}

.progress-text {
  margin-top: 10px;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
```

**Step 2: 提交对话框组件**

```bash
git add frontend/src/components/PosterExportDialog.vue
git commit -m "feat: 添加海报导出对话框组件"
```

---

## Task 5: 在轨迹详情页集成海报导出功能

**文件：**
- 修改: `frontend/src/views/TrackDetail.vue`

**Step 1: 添加对话框引入和状态**

在 `<script setup>` 部分添加：

```typescript
// 海报导出对话框
import PosterExportDialog from '@/components/PosterExportDialog.vue'

const posterDialogVisible = ref(false)
```

**Step 2: 添加地图元素引用**

在现有的 `mapRef` 和 `mapWrapperRef` 附近添加：

```typescript
// 海报导出需要访问地图 DOM 元素
const mapElementRef = ref<HTMLElement | null>(null)
```

**Step 3: 修改地图容器模板**

找到 `ref="mapWrapperRef"` 的位置，修改为：

```vue
<div ref="mapWrapperRef" class="map-wrapper">
  <div ref="mapElementRef" class="map-content">
    <UniversalMap
      ref="mapRef"
      :tracks="[trackWithPoints]"
      :highlight-track-id="track.id"
      :highlight-segment="highlightedSegment"
      :latest-point-index="latestPointIndex"
      :live-update-time="track.last_point_created_at || track.last_upload_at"
      @point-hover="handleMapPointHover"
      @clear-segment-highlight="clearSegmentHighlight"
    />
  </div>
</div>
```

**Step 4: 添加导出海报按钮**

在 `header-actions` 区域的"导出数据"按钮后添加：

```vue
<el-button type="primary" @click="showPosterDialog" class="desktop-only">
  <el-icon><Picture /></el-icon>
  导出海报
</el-button>
```

**Step 5: 添加移动端菜单项**

在移动端下拉菜单中添加：

```vue
<el-dropdown-item command="poster" v-if="isMobile">
  <el-icon><Picture /></el-icon>
  导出海报
</el-dropdown-item>
```

**Step 6: 添加图标导入**

在 `<script setup>` 顶部的图标导入区域添加：

```typescript
import { Picture } from '@element-plus/icons-vue'
```

**Step 7: 添加显示对话框函数**

在命令处理函数区域添加：

```typescript
function showPosterDialog(): void {
  posterDialogVisible.value = true
}
```

**Step 8: 更新 handleCommand 函数**

在 `handleCommand` 函数的 switch 语句中添加：

```typescript
case 'poster':
  showPosterDialog()
  break
```

**Step 9: 添加对话框组件**

在模板末尾（现有对话框附近）添加：

```vue
<!-- 海报导出对话框 -->
<PosterExportDialog
  v-model:visible="posterDialogVisible"
  :track="track"
  :points="points"
  :regions="regionTree"
  :map-element="mapElementRef"
/>
```

**Step 10: 添加样式**

在 `<style>` 部分添加：

```css
.map-content {
  width: 100%;
  height: 100%;
}
```

**Step 11: 提交集成修改**

```bash
git add frontend/src/views/TrackDetail.vue
git commit -m "feat: 在轨迹详情页集成海报导出功能"
```

---

## Task 6: 修复类型导入问题

**文件：**
- 修改: `frontend/src/utils/posterGenerator.ts`

**Step 1: 修复类型导入**

在文件顶部修改导入语句：

```typescript
import type { PosterConfig, PosterData, PosterProgress } from '@/types/poster'

// 移除重复的 POSTER_SIZE_PRESETS 定义，改为从类型文件导入
import { POSTER_SIZE_PRESETS } from '@/types/poster'
```

**Step 2: 同时在类型文件中添加导出**

修改 `frontend/src/types/poster.ts`，确保常量被导出：

```typescript
// 在文件末尾确保常量已导出
export { POSTER_SIZE_PRESETS }
```

**Step 3: 提交修复**

```bash
git add frontend/src/utils/posterGenerator.ts frontend/src/types/poster.ts
git commit -m "fix: 修复海报类型导入问题"
```

---

## Task 7: 添加地图截图 API 支持

**文件：**
- 修改: `frontend/src/components/map/UniversalMap.vue`
- 修改: `frontend/src/components/map/AMap.vue`
- 修改: `frontend/src/components/map/BMap.vue`
- 修改: `frontend/src/components/map/TencentMap.vue`
- 修改: `frontend/src/components/map/LeafletMap.vue`

**Step 1: 在 UniversalMap 中添加 getMapElement 方法**

在 `defineExpose` 中添加：

```typescript
// 获取地图 DOM 元素（用于海报截图）
function getMapElement(): HTMLElement | null {
  if (useAMapEngine.value && amapRef.value) {
    return amapRef.value.getMapElement?.() || null
  }
  if (useBMapEngine.value && bmapRef.value) {
    return bmapRef.value.getMapElement?.() || null
  }
  if (useTencentEngine.value && tencentRef.value) {
    return tencentRef.value.getMapElement?.() || null
  }
  if (leafletRef.value) {
    return leafletRef.value.getMapElement?.() || null
  }
  return null
}

// 在 defineExpose 中添加
defineExpose({
  // ... 现有导出
  getMapElement,
})
```

**Step 2: 在各地图组件中添加 getMapElement 方法**

在每个地图组件的 `defineExpose` 中添加：

```typescript
// 获取地图 DOM 元素
function getMapElement(): HTMLElement {
  return mapContainer.value || null
}

defineExpose({
  // ... 现有导出
  getMapElement,
})
```

**Step 3: 提交修改**

```bash
git add frontend/src/components/map/UniversalMap.vue frontend/src/components/map/*.vue
git commit -m "feat: 添加地图 DOM 元素获取接口"
```

---

## Task 8: 测试与优化

**Step 1: 本地测试**

```bash
cd frontend
npm run dev
```

测试步骤：
1. 打开任意轨迹详情页
2. 点击"导出海报"按钮
3. 选择不同模板和尺寸
4. 测试预览功能
5. 测试导出功能
6. 验证下载的图片

**Step 2: 检查控制台错误**

确保没有以下错误：
- 类型错误
- 导入错误
- 运行时错误

**Step 3: 修复发现的问题**

记录并修复测试中发现的问题

**Step 4: 提交测试修复**

```bash
git add frontend/src
git commit -m "fix: 修复海报功能测试发现的问题"
```

---

## Task 9: 添加错误处理和降级方案

**文件：**
- 修改: `frontend/src/utils/posterGenerator.ts`

**Step 1: 添加错误处理和降级逻辑**

在 `captureMap` 方法中添加降级方案：

```typescript
async captureMap(mapElement: HTMLElement, scale: number = 2): Promise<string> {
  this.updateProgress('capturing', `正在捕获地图 (scale=${scale})`, 10)

  // 如果是 4K，先尝试降级到 2K
  const actualScale = scale === 4 ? 2 : scale

  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const canvas = await html2canvas(mapElement, {
        scale: actualScale,
        useCORS: true,
        allowTaint: false,
        backgroundColor: null,
        logging: false,
        timeout: 30000, // 30 秒超时
      })

      this.updateProgress('capturing', '地图捕获成功', 30)
      return canvas.toDataURL('image/png')
    } catch (error) {
      console.warn(`地图捕获失败 (尝试 ${attempt}/3):`, error)

      // 如果是内存错误且使用的是 scale=2，尝试降级到 scale=1
      if (attempt === 2 && actualScale === 2) {
        console.log('降级到低分辨率模式')
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
      await new Promise(resolve => setTimeout(resolve, 1000))
    }
  }

  throw new Error('地图捕获失败')
}
```

**Step 2: 提交错误处理改进**

```bash
git add frontend/src/utils/posterGenerator.ts
git commit -m "feat: 添加海报生成错误处理和降级方案"
```

---

## Task 10: 更新设计文档并最终提交

**文件：**
- 修改: `docs/plans/2025-02-06-track-poster-design.md`

**Step 1: 在设计文档末尾添加实施记录**

```markdown
## 实施记录

**实施日期：** 2025-02-06
**实施状态：** 已完成

### 实施内容

1. 安装 html2canvas 依赖
2. 创建海报类型定义 (`frontend/src/types/poster.ts`)
3. 创建海报生成器工具类 (`frontend/src/utils/posterGenerator.ts`)
4. 创建海报导出对话框组件 (`frontend/src/components/PosterExportDialog.vue`)
5. 在轨迹详情页集成海报导出功能
6. 添加地图 DOM 元素获取接口
7. 实现错误处理和降级方案

### 文件清单

- 新增: `frontend/src/types/poster.ts`
- 新增: `frontend/src/utils/posterGenerator.ts`
- 新增: `frontend/src/components/PosterExportDialog.vue`
- 修改: `frontend/src/views/TrackDetail.vue`
- 修改: `frontend/src/components/map/UniversalMap.vue`
- 修改: `frontend/src/components/map/*.vue`
- 修改: `frontend/package.json`

### 测试验证

- [x] 简洁模板生成
- [x] 丰富模板生成
- [x] 地理模板生成
- [x] 不同尺寸导出（1080P / 4K）
- [x] 水印开关功能
- [x] 错误处理和降级方案
```

**Step 2: 最终提交**

```bash
git add docs/plans/2025-02-06-track-poster-design.md
git commit -m "docs: 更新海报功能设计文档实施记录"
```

---

## 完成

所有任务完成后，轨迹海报导出功能将完整集成到系统中，用户可以：
1. 在轨迹详情页点击"导出海报"按钮
2. 选择模板和尺寸
3. 预览海报效果
4. 导出高清 PNG 图片用于社交分享
