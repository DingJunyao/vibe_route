<template>
  <div class="overlay-template-editor">
    <!-- Header -->
    <el-header>
      <div class="header-left">
        <el-button @click="handleBack" :icon="ArrowLeft" class="nav-btn" />
        <el-button @click="goHome" :icon="HomeFilled" class="nav-btn home-nav-btn" />
        <h1>{{ isNew ? '新建模板' : template?.name || '编辑模板' }}</h1>
      </div>
      <div class="header-right">
        <el-button @click="saveTemplate" type="primary" :loading="isSaving" class="desktop-only">
          <el-icon><Check /></el-icon>
          保存
        </el-button>
        <el-dropdown @command="handleCommand">
          <span class="user-info">
            <el-icon><User /></el-icon>
            <span class="username">{{ authStore.user?.username }}</span>
            <el-icon class="el-icon--right"><arrow-down /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="settings">
                <el-icon><Setting /></el-icon>
                设置
              </el-dropdown-item>
              <el-dropdown-item command="admin" v-if="authStore.user?.is_admin">
                <el-icon><Setting /></el-icon>
                后台管理
              </el-dropdown-item>
              <el-dropdown-item command="logout">
                <el-icon><SwitchButton /></el-icon>
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>

    <!-- 主内容区 -->
    <el-main class="editor-main">
      <div class="editor-layout">
        <!-- 左侧：预览区 -->
        <div class="preview-panel">
          <div class="preview-toolbar">
            <!-- 缩放控制 -->
            <el-button-group size="small">
              <el-button @click="zoomOut" :disabled="zoomLevel <= 10">
                <el-icon><Minus /></el-icon>
              </el-button>
              <el-button class="zoom-level-button" @click="resetZoom">
                {{ Math.round(zoomLevel) }}%
              </el-button>
              <el-button @click="zoomIn" :disabled="zoomLevel >= 500">
                <el-icon><Plus /></el-icon>
              </el-button>
              <el-button @click="fitToContainer">
                适配
              </el-button>
            </el-button-group>

            <el-button-group size="small">
              <el-button :type="showSafeArea ? 'primary' : ''" @click="showSafeArea = !showSafeArea">
                安全区
              </el-button>
              <el-button @click="refreshPreview" :loading="isLoadingPreview">
                刷新
              </el-button>
            </el-button-group>

            <!-- 参考图控制 -->
            <el-button-group size="small">
              <el-button @click="triggerFileInput">
                <el-icon><Picture /></el-icon>
                参考图
              </el-button>
              <el-button v-if="referenceImage" @click="clearReferenceImage">
                <el-icon><Close /></el-icon>
              </el-button>
            </el-button-group>

            <!-- 参考图透明度 -->
            <div v-if="referenceImage" class="opacity-control">
              <span class="opacity-label">透明度</span>
              <el-slider v-model="referenceOpacity" :min="0" :max="100" style="width: 80px" />
              <span class="opacity-value">{{ referenceOpacity }}%</span>
            </div>

            <!-- 隐藏的文件输入 -->
            <input
              ref="fileInputRef"
              type="file"
              accept="image/*"
              style="display: none"
              @change="handleFileChange"
            />
          </div>

          <!-- 预览容器 -->
          <div
            class="preview-container"
            :class="{ 'space-pressed': isSpacePressed, 'is-panning': isPanning }"
            ref="previewContainerRef"
            tabindex="0"
            @wheel="handleWheel"
            @mousedown="handleCanvasMouseDown"
            @touchstart="handleCanvasTouchStart"
            @touchmove="handleCanvasTouchMove"
            @touchend="handleCanvasTouchEnd"
            @keydown="handleKeydown"
            @keyup="handleKeyup"
          >
            <!-- 滚动包装器 - 提供正确的滚动区域 -->
            <div class="preview-scroll-wrapper" :style="previewScrollWrapperStyle">
              <!-- 预览内容包装器 -->
              <div class="preview-content" :style="previewContentStyle" ref="previewCanvasRef" @click="handleContentClick">
              <!-- 屏幕边框（外层框架） -->
              <div class="screen-frame" v-if="showSafeArea"></div>

              <!-- 安全区外边界 -->
              <template v-if="showSafeArea">
                <div class="safe-margin top" :style="safeMarginStyles.top"></div>
                <div class="safe-margin bottom" :style="safeMarginStyles.bottom"></div>
                <div class="safe-margin left" :style="safeMarginStyles.left"></div>
                <div class="safe-margin right" :style="safeMarginStyles.right"></div>
              </template>

              <!-- 参考图（最底层） -->
              <img
                v-if="referenceImage"
                :src="referenceImage"
                class="reference-image"
                :style="{ opacity: referenceOpacity / 100 }"
              />

              <!-- 实时 Canvas 预览 -->
              <canvas
                ref="overlayCanvasRef"
                class="overlay-canvas"
                :width="templateConfig.canvas.width"
                :height="templateConfig.canvas.height"
              />

              <!-- 安全区内容区域指示 -->
              <div v-if="showSafeArea" class="safe-area-content" :style="safeAreaStyle"></div>

              <!-- 元素选中框（最顶层） -->
              <div
                v-for="el in templateConfig.elements"
                :key="el.id"
                class="element-outline"
                :class="{ selected: selectedElementId === el.id, dragging: isDragging && selectedElementId === el.id }"
                :style="getElementOutlineStyle(el)"
                @mousedown.stop="handleElementMouseDown($event, el)"
              >
              </div>

              <!-- 控制点覆盖层（与 element-outline 同级，在同一缩放容器内） -->
              <!-- 拖动时隐藏控制点以提高性能 -->
              <div class="resize-handles-overlay" v-if="selectedElement && !isDragging">
                <!-- 四角：调整字号 -->
                <div :class="getHandlePosition('nw').class" @mousedown.stop="handleResizeStart($event, selectedElement, 'nw')" title="调整字号" :style="getHandlePosition('nw')"></div>
                <div :class="getHandlePosition('ne').class" @mousedown.stop="handleResizeStart($event, selectedElement, 'ne')" title="调整字号" :style="getHandlePosition('ne')"></div>
                <div :class="getHandlePosition('sw').class" @mousedown.stop="handleResizeStart($event, selectedElement, 'sw')" title="调整字号" :style="getHandlePosition('sw')"></div>
                <div :class="getHandlePosition('se').class" @mousedown.stop="handleResizeStart($event, selectedElement, 'se')" title="调整字号" :style="getHandlePosition('se')"></div>
                <!-- 四边中点：调整宽度/高度 -->
                <div v-if="shouldShowHandle('n')" :class="getHandlePosition('n').class" @mousedown.stop="handleResizeStart($event, selectedElement, 'n')" title="调整行高" :style="getHandlePosition('n')"></div>
                <div v-if="shouldShowHandle('e')" :class="getHandlePosition('e').class" @mousedown.stop="handleResizeStart($event, selectedElement, 'e')" title="调整宽度" :style="getHandlePosition('e')"></div>
                <div v-if="shouldShowHandle('s')" :class="getHandlePosition('s').class" @mousedown.stop="handleResizeStart($event, selectedElement, 's')" title="调整行高" :style="getHandlePosition('s')"></div>
                <div v-if="shouldShowHandle('w')" :class="getHandlePosition('w').class" @mousedown.stop="handleResizeStart($event, selectedElement, 'w')" title="调整宽度" :style="getHandlePosition('w')"></div>
                <!-- 居中锚点标记：只在锚点是 center 时显示 -->
                <div v-if="selectedElement && selectedElement.position.element_anchor === 'center'" :class="getHandlePosition('center-marker').class" @mousedown.stop="handleResizeStart($event, selectedElement, 'center-marker')" title="居中锚点" :style="getHandlePosition('center-marker')"></div>
              </div>
            </div>
          </div>
          </div>
        </div>

        <!-- 右侧：配置面板 -->
        <div class="config-panel">
          <!-- 模板基本信息 -->
          <div class="config-section">
            <h3>模板信息</h3>
            <el-form :model="templateInfo" label-width="80px" size="small">
              <el-form-item label="名称">
                <el-input v-model="templateInfo.name" placeholder="模板名称" />
              </el-form-item>
              <el-form-item label="描述">
                <el-input v-model="templateInfo.description" type="textarea" :rows="2" />
              </el-form-item>
            </el-form>
          </div>

          <!-- 画布配置 -->
          <div class="config-section">
            <h3>画布配置</h3>
            <el-form label-width="80px" size="small">
              <el-form-item label="宽度">
                <el-input-number
                  v-model="templateConfig.canvas.width"
                  :min="100"
                  :max="7680"
                  :step="10"
                  controls-position="right"
                  @change="fitToContainer"
                />
              </el-form-item>
              <el-form-item label="高度">
                <el-input-number
                  v-model="templateConfig.canvas.height"
                  :min="100"
                  :max="4320"
                  :step="10"
                  controls-position="right"
                  @change="fitToContainer"
                />
              </el-form-item>
              <el-row>
                <el-col :span="24">
                  <div class="preset-buttons">
                    <el-button size="small" @click="setCanvasSize(1920, 1080)">1080p (16:9)</el-button>
                    <el-button size="small" @click="setCanvasSize(2560, 1440)">2K (16:9)</el-button>
                    <el-button size="small" @click="setCanvasSize(3840, 2160)">4K (16:9)</el-button>
                    <el-button size="small" @click="setCanvasSize(1080, 1920)">竖屏 1080p (9:16)</el-button>
                    <el-button size="small" @click="setCanvasSize(1080, 1080)">方形 (1:1)</el-button>
                  </div>
                </el-col>
              </el-row>
            </el-form>
          </div>

          <!-- 安全区配置 -->
          <div class="config-section">
            <h3>安全区配置</h3>
            <el-form label-width="80px" size="small">
              <el-form-item label="顶部">
                <el-input-number
                  v-model="templateConfig.safe_area.top"
                  :min="0" :max="0.2" :step="0.001"
                  controls-position="right"
                  :precision="3"
                />
              </el-form-item>
              <el-form-item label="底部">
                <el-input-number
                  v-model="templateConfig.safe_area.bottom"
                  :min="0" :max="0.2" :step="0.001"
                  controls-position="right"
                  :precision="3"
                />
              </el-form-item>
              <el-form-item label="左侧">
                <el-input-number
                  v-model="templateConfig.safe_area.left"
                  :min="0" :max="0.2" :step="0.001"
                  controls-position="right"
                  :precision="3"
                />
              </el-form-item>
              <el-form-item label="右侧">
                <el-input-number
                  v-model="templateConfig.safe_area.right"
                  :min="0" :max="0.2" :step="0.001"
                  controls-position="right"
                  :precision="3"
                />
              </el-form-item>
            </el-form>
          </div>

          <!-- 元素列表 -->
          <div class="config-section">
            <div class="section-header">
              <h3>元素列表</h3>
              <el-button-group size="small">
                <el-button @click="addTextElement">
                  <el-icon><Document /></el-icon>
                  文本
                </el-button>
              </el-button-group>
            </div>

            <draggable
              v-model="templateConfig.elements"
              item-key="id"
              handle=".drag-handle"
              class="element-list"
            >
              <template #item="{ element: el }">
                <div
                  class="element-item"
                  :class="{ active: selectedElementId === el.id }"
                >
                  <el-icon class="drag-handle"><Rank /></el-icon>
                  <el-icon v-if="el.type === 'text'"><Document /></el-icon>
                  <el-input
                    v-model="el.name"
                    size="small"
                    class="element-name-input"
                    placeholder="元素名称"
                    @click.stop="selectElement(el.id)"
                    @focus="selectElement(el.id)"
                  />
                  <el-button
                    type="danger"
                    size="small"
                    text
                    @click.stop="deleteElement(el.id)"
                  >
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </div>
              </template>
            </draggable>
          </div>

          <!-- 元素属性 -->
          <div v-if="selectedElement" class="config-section">
            <h3>{{ selectedElement.name }} - 属性</h3>

            <!-- 定位 -->
            <el-divider>定位</el-divider>
            <el-form label-width="80px" size="small">
              <el-form-item label="容器锚点">
                <anchor-selector v-model="selectedElement.position.container_anchor" />
              </el-form-item>
              <el-form-item label="元素锚点">
                <anchor-selector v-model="selectedElement.position.element_anchor" />
              </el-form-item>
              <el-form-item label="X 偏移">
                <el-input-number
                  v-model="selectedElement.position.x"
                  :step="0.001"
                  controls-position="right"
                  :precision="4"
                  style="width: 100%"
                />
              </el-form-item>
              <el-form-item label="Y 偏移">
                <el-input-number
                  v-model="selectedElement.position.y"
                  :step="0.001"
                  controls-position="right"
                  :precision="4"
                  style="width: 100%"
                />
              </el-form-item>
              <el-form-item label="使用安全区">
                <el-switch v-model="selectedElement.position.use_safe_area" />
              </el-form-item>
            </el-form>

            <!-- 文本内容 -->
            <template v-if="selectedElement.type === 'text'">
              <el-divider>内容</el-divider>
              <el-form label-width="90px" size="small">
                <el-form-item label="数据源">
                  <data-source-selector v-model="selectedElement.content.source" />
                </el-form-item>
                <el-form-item label="前缀后缀" v-if="selectedElement.content.source !== 'none'">
                  <el-input
                    v-model="selectedElement.content.format"
                    placeholder="{}"
                  />
                  <div class="form-hint">
                    使用 <code>{}</code> 作为数据占位符，可添加前后缀。
                    <br>示例：<code>速度: {} km/h</code>、<code>海拔: {}m</code>、<code>{}</code>
                  </div>
                </el-form-item>
                <el-form-item label="小数位数" v-if="isNumericSource">
                  <el-input-number
                    v-model="decimalPlaces"
                    :min="0" :max="10"
                    :step="1"
                    placeholder="自动"
                    controls-position="right"
                    style="width: 100%"
                  />
                  <div class="form-hint">留空则不进行小数位处理。适用于速度、海拔、经纬度等数值。</div>
                </el-form-item>
                <el-form-item label="示例文本">
                  <el-input
                    v-model="selectedElement.content.sample_text"
                    :placeholder="defaultSampleText"
                    type="textarea"
                    :rows="selectedElement.content.source === 'none' ? 3 : 1"
                    resize="horizontal"
                  />
                  <div class="form-hint">
                    <template v-if="selectedElement.content.source === 'none'">
                      自定义文本模式下必填，显示的固定文本内容（支持多行）
                    </template>
                    <template v-else>
                      预览时显示的自定义文本，留空则根据数据源生成默认示例
                    </template>
                  </div>
                </el-form-item>
              </el-form>
            </template>

            <!-- 样式 -->
            <el-divider>样式</el-divider>
            <el-form label-width="80px" size="small">
              <el-form-item label="字体">
                <font-selector v-model="selectedElement.style.font_family" />
              </el-form-item>
              <el-form-item label="字号%">
                <el-input-number
                  v-model="selectedElement.style.font_size"
                  :step="0.001"
                  :precision="4"
                  controls-position="right"
                  style="width: 100%"
                />
              </el-form-item>
              <el-form-item label="颜色">
                <el-color-picker v-model="selectedElement.style.color" />
              </el-form-item>
            </el-form>

            <!-- 文本布局 -->
            <template v-if="selectedElement.type === 'text'">
              <el-divider>文本布局</el-divider>
              <el-form label-width="80px" size="small">
                <el-form-item label="宽度%">
                  <el-input-number
                    v-model="selectedElement.layout.width"
                    :step="0.01"
                    :precision="3"
                    :min="0"
                    :max="1"
                    controls-position="right"
                    placeholder="自动"
                    style="width: 100%"
                  />
                </el-form-item>
                <el-form-item label="水平对齐">
                  <el-radio-group v-model="selectedElement.layout.horizontal_align">
                    <el-radio-button value="left">左</el-radio-button>
                    <el-radio-button value="center">中</el-radio-button>
                    <el-radio-button value="right">右</el-radio-button>
                    <el-radio-button value="justify">两端</el-radio-button>
                  </el-radio-group>
                </el-form-item>
                <el-form-item label="垂直对齐">
                  <el-radio-group v-model="selectedElement.layout.vertical_align">
                    <el-radio-button value="top">上</el-radio-button>
                    <el-radio-button value="middle">中</el-radio-button>
                    <el-radio-button value="bottom">下</el-radio-button>
                  </el-radio-group>
                </el-form-item>
                <el-form-item label="高度">
                  <el-input-number
                    v-model="selectedElement.layout.height"
                    :step="0.01"
                    :precision="3"
                    :min="0"
                    :max="1"
                    controls-position="right"
                    placeholder="自动"
                    style="width: 100%"
                  />
                </el-form-item>
                <el-form-item label="折行">
                  <el-switch v-model="selectedElement.layout.wrap" />
                </el-form-item>
                <el-form-item label="行高">
                  <el-input-number
                    v-model="selectedElement.layout.line_height"
                    :step="0.1"
                    :precision="2"
                    controls-position="right"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-form>
            </template>
          </div>
        </div>
      </div>
    </el-main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import draggable from 'vuedraggable'
import {
  ArrowLeft, HomeFilled, Check, Picture, Close, Document,
  Rank, Delete, User, Setting, SwitchButton, ArrowDown, Plus, Minus
} from '@element-plus/icons-vue'
import {
  overlayTemplateApi,
  type OverlayTemplate,
  type OverlayTemplateConfig,
  type OverlayElement,
  type ContainerAnchor,
  type DataSource
} from '@/api/overlayTemplate'
import { useAuthStore } from '@/stores/auth'

// 组件
import AnchorSelector from '@/components/overlay-editor/AnchorSelector.vue'
import DataSourceSelector from '@/components/overlay-editor/DataSourceSelector.vue'
import FontSelector from '@/components/overlay-editor/FontSelector.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// 状态
const isNew = computed(() => route.params.id === 'new')
const templateId = computed(() => {
  // 修复：直接使用 route.params.id，避免 computed 值为 NaN
  const id = Number(route.params.id)
  return isNaN(id) ? 0 : id
})
const template = ref<OverlayTemplate | null>(null)
const isSaving = ref(false)
const isLoadingPreview = ref(false)
const previewImageUrl = ref('')
const showSafeArea = ref(true)

// 缩放控制
const zoomLevel = ref(100)
const previewContainerRef = ref<HTMLElement>()
const previewCanvasRef = ref<HTMLElement>()
const overlayCanvasRef = ref<HTMLCanvasElement>()
let resizeObserver: ResizeObserver | null = null
const isUserZoomed = ref(false)  // 标记用户是否手动调整过缩放

// 空格键拖动画布
const isSpacePressed = ref(false)
const isPanning = ref(false)
const panStartPos = ref({ x: 0, y: 0 })
const panStartScroll = ref({ x: 0, y: 0 })
const isMouseDownOnCanvas = ref(false)  // 跟踪鼠标是否在画布上按下
const lastMousePos = ref({ x: 0, y: 0 })  // 记录最后的鼠标位置
const shouldLockScroll = ref(false)  // 滚动锁定标志

// 参考图
const referenceImage = ref<string | null>(null)
const referenceOpacity = ref(50)
const fileInputRef = ref<HTMLInputElement>()

// 元素拖动和缩放状态
const isDragging = ref(false)
const isResizing = ref(false)
const resizeHandle = ref<string | null>(null)  // 'nw', 'ne', 'sw', 'se', 'n', 's', 'e', 'w'
const dragStartPos = ref({ x: 0, y: 0 })
// 元素起始位置：包含锚点位置和边界位置（用于调整大小）
const elementStartPos = ref<{
  x: number
  y: number
  left: number   // 元素左边（预览内容百分比）
  top: number    // 元素上边（预览内容百分比）
  right: number  // 元素右边（预览内容百分比）
  bottom: number // 元素下边（预览内容百分比）
  width: number  // 初始宽度（百分比）
  height: number // 初始高度（百分比）
  fontSize: number
  centerDistance?: number  // 四角缩放时：拖动开始时鼠标到元素中心的距离（预览内容百分比）
}>({ x: 0, y: 0, left: 0, top: 0, right: 0, bottom: 0, width: 0, height: 0, fontSize: 0.025 })

// 模板信息
const templateInfo = ref({
  name: '',
  description: ''
})

// 模板配置（带默认值）
const templateConfig = ref<OverlayTemplateConfig>({
  canvas: {
    width: 1920,
    height: 1080
  },
  safe_area: {
    top: 0.05,
    bottom: 0.05,
    left: 0.05,
    right: 0.05
  },
  background: {
    color: '#000000',
    opacity: 0
  },
  elements: []
})

// 选中的元素
const selectedElementId = ref<string | null>(null)

// 元素轮廓样式版本号（用于强制刷新）
const elementStyleVersion = ref(0)

const selectedElement = computed(() => {
  if (!selectedElementId.value) return null
  return templateConfig.value.elements.find(el => el.id === selectedElementId.value) || null
})

// 数值型数据源列表
const numericSources = new Set([
  'speed', 'elevation', 'compass_angle',
  'elapsed_distance', 'elapsed_time',
  'remain_distance', 'remain_time',
  'latitude', 'longitude'
])

// 各数据源的极端示例文本（使用最长可能的值）
const SAMPLE_TEXTS: Record<string, string> = {
  // 区域信息 - 使用最长的行政区划名称
  province: '新疆维吾尔自治区',
  city: '黔东南苗族侗族自治州',
  district: '双江拉祜族佤族布朗族傣族自治县',
  province_en: 'Xinjiang Uygur Autonomous Region',
  city_en: 'Xishuangbanna Dai Autonomous Prefecture',
  district_en: 'Zhalantun Chengisi Mongol Ethnic Township',
  // 区域组合
  region: '新疆维吾尔自治区 伊犁哈萨克自治州 霍城县',
  region_en: 'Zhalantun Chengisi Mongol Ethnic Township, Xilin Gol League, Inner Mongolia Autonomous Region',
  // 道路信息
  road_number: 'G0451',  // 最长的国家高速编号
  road_name: '新疆独山子库车公路',
  road_name_en: 'Dushanzi-Kuqa Highway in Xinjiang',
  // 运动数据 - 使用极端值
  speed: '299.999',
  elevation: '8848.86',
  compass_angle: '359.99',
  // 时间距离
  elapsed_distance: '9999.99',
  elapsed_time: '239:59:59',
  remain_distance: '9999.99',
  remain_time: '239:59:59',
  // 坐标时间
  current_time: '2025-12-31 23:59:59',
  latitude: '89.99999999',
  longitude: '179.99999999',
}

// 当前数据源是否为数值类型
const isNumericSource = computed(() => {
  if (!selectedElement.value?.content?.source) return false
  return numericSources.has(selectedElement.value.content.source)
})

// 默认示例文本（根据数据源）
const defaultSampleText = computed((): string => {
  const source = selectedElement.value?.content?.source
  if (source === 'none') {
    return '自定义文本'
  }
  return source ? (SAMPLE_TEXTS[source] || '') : ''
})

// 小数位数（使用计算属性实现双向绑定）
const decimalPlaces = computed({
  get: () => {
    return selectedElement.value?.content?.decimal_places ?? undefined
  },
  set: (value: number | undefined) => {
    if (selectedElement.value?.content) {
      selectedElement.value.content.decimal_places = value
    }
  }
})

// 预览内容的基准尺寸（用于计算缩放）
const BASE_PREVIEW_SIZE = 1000 // 预览内容的基准宽度（像素）

// 预览滚动包装器样式 - 提供正确的滚动区域尺寸（超出画布 50%）
const previewScrollWrapperStyle = computed(() => {
  // 使用原始画布尺寸计算滚动区域（不随缩放变化）
  const canvas = templateConfig.value.canvas
  const scale = zoomLevel.value / 100

  // 原始画布尺寸（基准尺寸）
  const baseCanvasWidth = BASE_PREVIEW_SIZE
  const baseCanvasHeight = BASE_PREVIEW_SIZE / (canvas.width / canvas.height)

  // 滚动区域为原始画布尺寸的 150%，确保可以滚动超出画布边缘 50%
  const scrollAreaWidth = baseCanvasWidth * 1.5
  const scrollAreaHeight = baseCanvasHeight * 1.5

  // 确保滚动区域不小于容器（否则会出现滚动条但无法滚动的情况）
  const container = previewContainerRef.value
  if (container) {
    const containerRect = container.getBoundingClientRect()
    const finalWidth = Math.max(scrollAreaWidth, containerRect.width)
    const finalHeight = Math.max(scrollAreaHeight, containerRect.height)

    return {
      width: `${finalWidth}px`,
      height: `${finalHeight}px`,
      minWidth: `${finalWidth}px`,
      minHeight: `${finalHeight}px`
    }
  }

  return {
    width: `${scrollAreaWidth}px`,
    height: `${scrollAreaHeight}px`,
    minWidth: `${scrollAreaWidth}px`,
    minHeight: `${scrollAreaHeight}px`
  }
})

// 预览内容样式（包含缩放）
const previewContentStyle = computed(() => {
  const canvas = templateConfig.value.canvas
  const aspectRatio = canvas.width / canvas.height
  const scale = zoomLevel.value / 100

  // CSS 尺寸（transform 之前）
  const cssWidth = BASE_PREVIEW_SIZE
  const cssHeight = BASE_PREVIEW_SIZE / aspectRatio

  // flexbox 会自动居中，只需要设置尺寸和缩放
  return {
    width: `${cssWidth}px`,
    height: `${cssHeight}px`,
    transform: `scale(${scale})`,
    transformOrigin: 'center center',
    '--preview-scale': scale.toString()
  }
})

// 计算合适的缩放级别以适配容器
const calculateFitZoom = (): number => {
  const canvas = templateConfig.value.canvas
  const canvasAspectRatio = canvas.width / canvas.height

  // 获取容器的实际尺寸
  const container = previewContainerRef.value
  if (!container) {
    // 容器还没挂载，使用默认值
    return 100
  }

  const containerRect = container.getBoundingClientRect()
  const containerWidth = containerRect.width
  const containerHeight = containerRect.height

  // 预览内容的实际尺寸（缩放前）
  const previewContentWidth = BASE_PREVIEW_SIZE
  const previewContentHeight = BASE_PREVIEW_SIZE / (canvas.width / canvas.height)

  // 计算容器中可用的空间（减去边距和滚动条）
  const availableWidth = containerWidth - 40
  const availableHeight = containerHeight - 40

  // 计算缩放比例，使预览内容适应可用空间
  const scaleX = availableWidth / previewContentWidth
  const scaleY = availableHeight / previewContentHeight
  const scale = Math.min(scaleX, scaleY) * 100  // 转换为百分比

  return Math.max(10, Math.min(500, Math.round(scale)))
}

// 安全区样式
const safeAreaStyle = computed(() => {
  const safeArea = templateConfig.value.safe_area
  return {
    top: `${safeArea.top * 100}%`,
    left: `${safeArea.left * 100}%`,
    right: `${safeArea.right * 100}%`,
    bottom: `${safeArea.bottom * 100}%`,
    width: `calc(100% - ${(safeArea.left + safeArea.right) * 100}%)`,
    height: `calc(100% - ${(safeArea.top + safeArea.bottom) * 100}%)`
  }
})

// 安全区边距遮罩样式
const safeMarginStyles = computed(() => {
  const safeArea = templateConfig.value.safe_area
  return {
    top: { height: `${safeArea.top * 100}%` },
    bottom: { height: `${safeArea.bottom * 100}%` },
    left: {
      top: `${safeArea.top * 100}%`,
      bottom: `${safeArea.bottom * 100}%`,
      width: `${safeArea.left * 100}%`
    },
    right: {
      top: `${safeArea.top * 100}%`,
      bottom: `${safeArea.bottom * 100}%`,
      width: `${safeArea.right * 100}%`
    }
  }
})

// 加载模板
const loadTemplate = async () => {
  if (route.params.id === 'new' || isNew.value) return

  const id = templateId.value
  if (!id || isNaN(id)) {
    console.warn('Invalid templateId:', templateId.value)
    return
  }

  try {
    template.value = await overlayTemplateApi.get(id)
    templateInfo.value = {
      name: template.value.name,
      description: template.value.description || ''
    }
    templateConfig.value = template.value.config
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '加载模板失败')
  }
}

// 保存模板
const saveTemplate = async () => {
  if (!templateInfo.value.name) {
    ElMessage.warning('请输入模板名称')
    return
  }

  isSaving.value = true
  try {
    const data = {
      name: templateInfo.value.name,
      description: templateInfo.value.description,
      config: templateConfig.value
    }

    // 双重检查：确保新建时使用 create API
    if (isNew.value || route.params.id === 'new' || templateId.value === 0) {
      await overlayTemplateApi.create(data)
    } else {
      await overlayTemplateApi.update(templateId.value, data)
    }

    ElMessage.success('保存成功')
    router.push('/overlay-templates')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    isSaving.value = false
  }
}

// 缩放方法
const zoomIn = () => {
  zoomLevel.value = Math.min(500, zoomLevel.value + 25)
  isUserZoomed.value = true
}

const zoomOut = () => {
  zoomLevel.value = Math.max(10, zoomLevel.value - 25)
  isUserZoomed.value = true
}

const resetZoom = () => {
  zoomLevel.value = 100
  isUserZoomed.value = true
}

const fitToContainer = () => {
  zoomLevel.value = calculateFitZoom()
  isUserZoomed.value = false  // 重置为自动适配模式

  // flexbox 会自动居中画布内容
  // 但滚动位置需要手动居中（对于 wrapper 大于容器的情况）
  nextTick(() => {
    if (previewContainerRef.value) {
      const container = previewContainerRef.value
      const scrollWrapper = container.querySelector('.preview-scroll-wrapper') as HTMLElement

      if (scrollWrapper) {
        const wrapperWidth = scrollWrapper.offsetWidth
        const wrapperHeight = scrollWrapper.offsetHeight
        const containerWidth = container.clientWidth
        const containerHeight = container.clientHeight

        // 将滚动位置居中
        // 当 wrapper 大于容器时，可以滚动出额外的空间
        const targetScrollLeft = (wrapperWidth - containerWidth) / 2
        const targetScrollTop = (wrapperHeight - containerHeight) / 2

        container.scrollLeft = targetScrollLeft
        container.scrollTop = targetScrollTop
      }
    }
  })
}

// 处理鼠标滚轮缩放
const handleWheel = (e: WheelEvent) => {
  if (e.ctrlKey || e.metaKey) {
    // Ctrl + 滚轮：缩放
    e.preventDefault()
    const delta = e.deltaY > 0 ? -25 : 25
    zoomAtPoint(e.clientX, e.clientY, delta)
  } else if (e.altKey) {
    // Alt + 滚轮：更精细的缩放
    e.preventDefault()
    const delta = e.deltaY > 0 ? -5 : 5
    zoomAtPoint(e.clientX, e.clientY, delta)
  }
  // 否则正常滚动
}

// 在指定点为中心进行缩放
const zoomAtPoint = (clientX: number, clientY: number, delta: number) => {
  const container = previewContainerRef.value
  if (!container) {
    zoomLevel.value = Math.max(10, Math.min(500, zoomLevel.value + delta))
    isUserZoomed.value = true
    return
  }

  // 计算新的缩放级别
  const newZoomLevel = Math.max(10, Math.min(500, zoomLevel.value + delta))

  // 获取鼠标在容器中的相对位置
  const rect = container.getBoundingClientRect()
  const mouseX = clientX - rect.left
  const mouseY = clientY - rect.top

  // 计算鼠标相对于滚动位置的偏移比例
  // 当前滚动位置 + 鼠标位置 = 鼠标在内容中的绝对位置
  const currentScrollLeft = container.scrollLeft
  const currentScrollTop = container.scrollTop

  // 计算缩放比例
  const zoomRatio = newZoomLevel / zoomLevel.value

  // 调整滚动位置，使鼠标下的内容点保持在同一位置
  const newScrollLeft = currentScrollLeft + mouseX * (zoomRatio - 1)
  const newScrollTop = currentScrollTop + mouseY * (zoomRatio - 1)

  // 更新缩放级别
  zoomLevel.value = newZoomLevel
  isUserZoomed.value = true

  // 使用 nextTick 等待 DOM 更新后调整滚动位置
  nextTick(() => {
    if (previewContainerRef.value) {
      previewContainerRef.value.scrollLeft = newScrollLeft
      previewContainerRef.value.scrollTop = newScrollTop
    }
  })
}

// 前端 Canvas 实时渲染
const renderOverlayCanvas = () => {
  const canvas = overlayCanvasRef.value
  if (!canvas) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const config = templateConfig.value
  const width = config.canvas.width
  const height = config.canvas.height

  // 清空画布
  ctx.clearRect(0, 0, width, height)

  // 绘制背景（如果有）
  if (config.background?.color && config.background.opacity > 0) {
    ctx.fillStyle = config.background.color
    ctx.globalAlpha = config.background.opacity
    ctx.fillRect(0, 0, width, height)
    ctx.globalAlpha = 1
  }

  // 计算安全区
  const safeArea = config.safe_area
  const safeAreaLeft = width * safeArea.left
  const safeAreaTop = height * safeArea.top
  const safeAreaRight = width * safeArea.right
  const safeAreaBottom = height * safeArea.bottom
  const safeAreaWidth = width - safeAreaLeft - safeAreaRight
  const safeAreaHeight = height - safeAreaTop - safeAreaBottom

  // 示例数据
  const sampleData = getSampleData()

  // 锚点位置映射
  const anchorPositions: Record<string, { x: number; y: number }> = {
    'top-left': { x: 0, y: 0 },
    'top': { x: 0.5, y: 0 },
    'top-right': { x: 1, y: 0 },
    'left': { x: 0, y: 0.5 },
    'center': { x: 0.5, y: 0.5 },
    'right': { x: 1, y: 0.5 },
    'bottom-left': { x: 0, y: 1 },
    'bottom': { x: 0.5, y: 1 },
    'bottom-right': { x: 1, y: 1 }
  }

  // 绘制每个文本元素
  for (const element of config.elements) {
    if (element.type !== 'text' || !element.visible) continue

    const content = element.content
    if (!content) continue

    // 获取文本内容
    let text = getSampleText(content.source, content.sample_text)

    // 如果是数值型数据源，应用小数位数格式化
    if (numericSources.has(content.source)) {
      text = formatNumericValue(text, content.decimal_places)
    }

    // 使用 format 字段应用前缀后缀
    const formatStr = content.format || '{}'
    try {
      text = formatStr.replace('{}', text)
    } catch {
      text = text
    }

    if (!text) continue

    // 容器锚点始终相对于画布计算（不受 use_safe_area 影响）
    const contentArea = { x: 0, y: 0, width, height }

    // 容器锚点
    const containerAnchor = anchorPositions[element.position.container_anchor] || anchorPositions['top-left']
    const anchorX = contentArea.x + contentArea.width * containerAnchor.x
    const anchorY = contentArea.y + contentArea.height * containerAnchor.y

    // 元素偏移（相对于整个画布）
    // position.x/y 的单位是比例（0-1），范围 -0.5 到 0.5
    const offsetX = element.position.x * width
    const offsetY = element.position.y * height

    // 字体大小
    const fontSize = (element.style?.font_size || 0.025) * height

    // 设置字体
    const fontFamily = getFontFamilyName(element.style?.font_family || 'system_msyh')
    ctx.font = `${fontSize}px ${fontFamily}`
    ctx.fillStyle = element.style?.color || '#FFFFFF'

    // 获取布局配置
    const layout = element.layout || {}
    const horizontalAlign = layout.horizontal_align || 'left'
    const verticalAlign = layout.vertical_align || 'top'
    const wrapEnabled = layout.wrap === true
    const lineHeight = (layout.line_height || 1.2) * fontSize

    // 测量自然文本宽度
    const metrics = ctx.measureText(text)
    const naturalTextWidth = metrics.width

    // 获取文字的实际垂直边界
    const ascent = metrics.actualBoundingBoxAscent || fontSize * 0.8
    const descent = metrics.actualBoundingBoxDescent || fontSize * 0.2
    const singleLineHeight = ascent + descent

    // 计算实际使用的文本宽度和高度
    let textWidth = naturalTextWidth
    let boxWidth = naturalTextWidth

    // 如果设置了固定宽度，使用固定宽度
    if (layout.width !== undefined && layout.width !== null) {
      boxWidth = layout.width * width
      textWidth = boxWidth
    }

    // 先计算是否需要折行，以确定内容高度
    let totalTextHeight: number
    let lines: string[] = []

    if (wrapEnabled) {
      lines = wrapText(text, boxWidth, ctx, layout.max_lines)
      totalTextHeight = lines.length * lineHeight
    } else {
      totalTextHeight = singleLineHeight
    }

    // 计算定界框高度：如果有固定高度则使用，否则使用内容高度
    let boxHeight = totalTextHeight
    if (layout.height !== undefined && layout.height !== null) {
      boxHeight = layout.height * height
    }

    // 元素锚点偏移
    const elementAnchor = anchorPositions[element.position.element_anchor] || anchorPositions['top-left']

    // 计算文本框左上角位置（与后端 PIL 逻辑一致）
    // 后端: final_x = container_x + offset_x - elem_anchor_x
    //      final_y = container_y + offset_y - elem_anchor_y
    // Canvas: fillText 的 y 是基线位置，需要加上 ascent 才能得到顶部位置
    const elemAnchorOffsetX = boxWidth * elementAnchor.x
    const elemAnchorOffsetY = boxHeight * elementAnchor.y

    // 文本框左上角位置
    const boxLeftTopX = anchorX + offsetX - elemAnchorOffsetX
    const boxLeftTopY = anchorY + offsetY - elemAnchorOffsetY

    // 折行处理
    if (wrapEnabled) {
      // 需要折行：拆分文本为多行
      const lines = wrapText(text, boxWidth, ctx, layout.max_lines)

      // 计算文本实际高度（不包含最后一行下方的行高空间）
      // 文本实际高度 = (行数 - 1) * 行高 + 最后一行文本高度
      const lastLineMetrics = ctx.measureText(lines[lines.length - 1] || text)
      const lastLineAscent = lastLineMetrics.actualBoundingBoxAscent || fontSize * 0.8
      const lastLineDescent = lastLineMetrics.actualBoundingBoxDescent || fontSize * 0.2
      const totalTextHeight = (lines.length - 1) * lineHeight + lastLineAscent + lastLineDescent

      // 根据垂直对齐计算第一行的 y 坐标
      let firstLineY = boxLeftTopY
      if (verticalAlign === 'middle') {
        firstLineY = boxLeftTopY + (boxHeight - totalTextHeight) / 2
      } else if (verticalAlign === 'bottom') {
        firstLineY = boxLeftTopY + boxHeight - totalTextHeight
      }
      // top 对齐：默认为 boxLeftTopY

      // 绘制每一行
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i]
        const lineMetrics = ctx.measureText(line)
        const lineWidth = lineMetrics.width
        const lineAscent = lineMetrics.actualBoundingBoxAscent || fontSize * 0.8

        // 计算行的 y 坐标
        const lineY = firstLineY + i * lineHeight

        // 计算行的 x 坐标（根据水平对齐方式）
        let lineX = boxLeftTopX
        if (horizontalAlign === 'center') {
          // 居中：文本相对于文本框居中
          lineX = boxLeftTopX + (boxWidth - lineWidth) / 2
        } else if (horizontalAlign === 'right') {
          // 右对齐
          lineX = boxLeftTopX + boxWidth - lineWidth
        }
        // 左对齐和两端对齐：默认从左边缘开始

        // 绘制行文本
        const fillTextY = lineY + lineAscent

        // 两端对齐处理：所有行都两端对齐（单行文本也支持）
        if (horizontalAlign === 'justify' && line.length > 1) {
          // 两端对齐：在固定宽度内均匀分布字符
          const totalCharWidth = lineWidth
          const availableWidth = boxWidth
          const totalSpace = availableWidth - totalCharWidth
          const spacePerChar = totalSpace / (line.length - 1)

          let currentX = boxLeftTopX  // 从左边缘开始
          for (let j = 0; j < line.length; j++) {
            const char = line[j]
            const charMetrics = ctx.measureText(char)
            const charWidth = charMetrics.width

            // 绘制字符
            ctx.fillText(char, currentX, fillTextY)

            // 移动到下一个字符位置（字符宽度 + 均匀间距）
            currentX += charWidth + spacePerChar
          }
        } else {
          // 普通绘制：左、中、右对齐，或最后一行
          ctx.fillText(line, lineX, fillTextY)
        }
      }
    } else {
      // 单行文本
      // 根据垂直对齐计算 fillText 的 y 坐标（fillText 的 y 是基线位置）
      // 文本实际垂直范围：[fillTextY - ascent, fillTextY + descent]
      let fillTextY = boxLeftTopY + ascent  // 上对齐：文本顶端在 boxLeftTopY
      if (verticalAlign === 'middle') {
        // 中对齐：文本中心在定界框中心
        // 文本中心 = (fillTextY - ascent + fillTextY + descent) / 2 = fillTextY + (descent - ascent) / 2
        // 定界框中心 = boxLeftTopY + boxHeight / 2
        // 所以：fillTextY = boxLeftTopY + boxHeight / 2 + (ascent - descent) / 2
        fillTextY = boxLeftTopY + boxHeight / 2 + (ascent - descent) / 2
      } else if (verticalAlign === 'bottom') {
        // 下对齐：文本底端在定界框底部
        // fillTextY + descent = boxLeftTopY + boxHeight
        fillTextY = boxLeftTopY + boxHeight - descent
      }

      // 根据水平对齐计算 fillText 的 x 坐标
      let fillTextX = boxLeftTopX
      if (horizontalAlign === 'center') {
        // 居中：文本相对于文本框居中
        fillTextX = boxLeftTopX + (boxWidth - naturalTextWidth) / 2
      } else if (horizontalAlign === 'right') {
        // 右对齐
        fillTextX = boxLeftTopX + boxWidth - naturalTextWidth
      }
      // 左对齐：默认为 boxLeftTopX
      // justify：从 boxLeftTopX 开始绘制，通过字符间距实现两端对齐

      // 两端对齐单行文本：计算字符间距并绘制
      if (horizontalAlign === 'justify' && layout.width && text.length > 1) {
        // 两端对齐：在固定宽度内均匀分布字符
        // 从文本框左边缘开始绘制
        const totalCharWidth = naturalTextWidth
        const availableWidth = boxWidth
        const totalSpace = availableWidth - totalCharWidth
        const spacePerChar = totalSpace / (text.length - 1)

        let currentX = boxLeftTopX  // 从左边缘开始
        for (let i = 0; i < text.length; i++) {
          const char = text[i]
          const charMetrics = ctx.measureText(char)
          const charWidth = charMetrics.width

          // 绘制字符
          ctx.fillText(char, currentX, fillTextY)

          // 移动到下一个字符位置（字符宽度 + 均匀间距）
          currentX += charWidth + spacePerChar
        }
      } else {
        // 普通绘制：左、中、右对齐
        ctx.fillText(text, fillTextX, fillTextY)
      }
    }
  }
}

// 文本折行函数
const wrapText = (text: string, maxWidth: number, ctx: CanvasRenderingContext2D, maxLines?: number): string[] => {
  if (!text) return []
  if (maxWidth <= 0) return [text]

  const lines: string[] = []
  let currentLine = ''

  for (let i = 0; i < text.length; i++) {
    const char = text[i]
    const testLine = currentLine + char

    // 测试添加这个字符后是否超出最大宽度
    const metrics = ctx.measureText(testLine)
    if (metrics.width <= maxWidth) {
      currentLine = testLine
    } else {
      // 超出宽度，开始新行
      if (currentLine) {
        lines.push(currentLine)
      }
      currentLine = char
    }
  }

  // 添加最后一行
  if (currentLine) {
    lines.push(currentLine)
  }

  // 处理最大行数限制
  if (maxLines && lines.length > maxLines) {
    const result = lines.slice(0, maxLines)
    if (maxLines > 0) {
      // 在最后一行添加省略号
      const lastLine = result[result.length - 1]
      if (lastLine && lastLine.length > 3) {
        result[result.length - 1] = lastLine.slice(0, -3) + '...'
      }
    }
    return result
  }

  return lines
}

// 获取示例数据
const getSampleData = () => ({
  province: '河南省',
  city: '郑州市',
  district: '中原区',
  road_number: 'G221',
  road_name: '建设路',
  road_name_en: 'Jianshe Road',
  speed: 65.5,
  elevation: 120,
  compass_angle: 45,
  elapsed_distance: '125.6 km',
  elapsed_time: '02:35:12',
  remain_distance: '74.4 km',
  remain_time: '01:15:30',
  current_time: '14:32:45',
  latitude: 34.747,
  longitude: 113.625
})

// 根据数据源获取示例文本
const getSampleText = (source: string, customSample?: string): string => {
  // 如果是自定义文本数据源，使用自定义示例文本（如果没有则返回空）
  if (source === 'none') {
    return customSample || ''
  }

  // 如果有自定义示例文本，使用它
  if (customSample) return customSample

  // 使用 SAMPLE_TEXTS 常量中的极端值作为示例文本
  return SAMPLE_TEXTS[source] || ''
}

// 格式化数值（应用小数位数）
const formatNumericValue = (value: string, decimalPlaces?: number): string => {
  // 如果没有指定小数位数，返回原值
  if (decimalPlaces === undefined || decimalPlaces === null) return value

  // 尝试解析为数字
  const num = parseFloat(value)
  if (isNaN(num)) return value

  // 格式化为指定小数位数
  return num.toFixed(decimalPlaces)
}

// 获取字体族名称
const getFontFamilyName = (fontId: string): string => {
  const fontMap: Record<string, string> = {
    'system_msyh': 'Microsoft YaHei',
    'system_simhei': 'SimHei',
    'system_simsun': 'SimSun',
    'system_arial': 'Arial',
    'system_times': 'Times New Roman',
    'system_courier': 'Courier New'
  }
  return fontMap[fontId] || 'sans-serif'
}

// 监听模板配置变化，实时重新渲染
watch(
  () => templateConfig.value,
  () => {
    nextTick(() => {
      renderOverlayCanvas()
    })
  },
  { deep: true }
)

// 后端预览（用于最终确认）
const refreshPreview = async () => {
  isLoadingPreview.value = true
  try {
    const blob = await overlayTemplateApi.previewWithConfig(templateConfig.value)
    if (previewImageUrl.value) {
      URL.revokeObjectURL(previewImageUrl.value)
    }
    previewImageUrl.value = URL.createObjectURL(blob)
  } catch (error: any) {
    console.error('预览失败:', error)
  } finally {
    isLoadingPreview.value = false
  }
}

// 设置画布尺寸
const setCanvasSize = (width: number, height: number, vertical = false) => {
  if (vertical) {
    // 竖屏交换宽高
    templateConfig.value.canvas.width = height
    templateConfig.value.canvas.height = width
  } else {
    templateConfig.value.canvas.width = width
    templateConfig.value.canvas.height = height
  }
  // 重置缩放到适配
  zoomLevel.value = calculateFitZoom()
}

// 选择元素
const selectElement = (elementId: string) => {
  selectedElementId.value = elementId
}

// 添加文本元素
const addTextElement = () => {
  const id = `text_${Date.now()}`
  templateConfig.value.elements.push({
    id,
    type: 'text',
    name: '新文本',
    visible: true,
    position: {
      container_anchor: 'bottom-left',
      element_anchor: 'bottom-left',
      x: 0.02,
      y: -0.02,
      use_safe_area: true
    },
    size: {
      width: 0.2,
      height: 0.05
    },
    content: {
      source: 'province',
      prefix: '',
      suffix: '',
      format: '{}'
    },
    layout: {
      horizontal_align: 'left',
      vertical_align: 'bottom',
      width: null,  // 初始为 null，表示使用自然宽度；用户可以设置固定宽度
      wrap: false,
      line_height: 1.2
    },
    style: {
      font_family: 'system_msyh',
      font_size: 0.025,
      color: '#FFFFFF'
    }
  })
  selectedElementId.value = id
}

// 删除元素
const deleteElement = (elementId: string) => {
  const index = templateConfig.value.elements.findIndex(el => el.id === elementId)
  if (index > -1) {
    templateConfig.value.elements.splice(index, 1)
    if (selectedElementId.value === elementId) {
      selectedElementId.value = null
    }
  }
}

// 获取元素边框样式（与 Canvas 渲染逻辑一致，使用百分比）
// 注意：此函数访问 elementStyleVersion 以确保拖动时重新计算
const getElementOutlineStyle = (element: OverlayElement) => {
  // 访问版本号以建立响应式依赖
  const _version = elementStyleVersion.value
  const config = templateConfig.value

  // Canvas 原始尺寸
  const canvasWidth = config.canvas.width
  const canvasHeight = config.canvas.height

  // 计算安全区（使用 Canvas 坐标系）
  const safeArea = config.safe_area
  const safeAreaLeft = canvasWidth * safeArea.left
  const safeAreaTop = canvasHeight * safeArea.top
  const safeAreaRight = canvasWidth * safeArea.right
  const safeAreaBottom = canvasHeight * safeArea.bottom
  const safeAreaWidth = canvasWidth - safeAreaLeft - safeAreaRight
  const safeAreaHeight = canvasHeight - safeAreaTop - safeAreaBottom

  // 容器锚点始终相对于画布计算（不受 use_safe_area 影响）
  // position.x/y 是相对于画布的偏移
  const contentArea = { x: 0, y: 0, width: canvasWidth, height: canvasHeight }

  // 锚点位置
  const anchorPositions: Record<string, { x: number; y: number }> = {
    'top-left': { x: 0, y: 0 },
    'top': { x: 0.5, y: 0 },
    'top-right': { x: 1, y: 0 },
    'left': { x: 0, y: 0.5 },
    'center': { x: 0.5, y: 0.5 },
    'right': { x: 1, y: 0.5 },
    'bottom-left': { x: 0, y: 1 },
    'bottom': { x: 0.5, y: 1 },
    'bottom-right': { x: 1, y: 1 }
  }

  const containerAnchor = anchorPositions[element.position.container_anchor] || anchorPositions['top-left']
  const elementAnchor = anchorPositions[element.position.element_anchor] || anchorPositions['top-left']

  // 容器锚点位置（Canvas 坐标系）
  const anchorX = contentArea.x + contentArea.width * containerAnchor.x
  const anchorY = contentArea.y + contentArea.height * containerAnchor.y

  // 元素偏移（相对于整个画布）
  // position.x/y 的单位是比例（0-1），范围 -0.5 到 0.5
  const offsetX = element.position.x * canvasWidth
  const offsetY = element.position.y * canvasHeight

  // 字体大小（Canvas 坐标系）
  const fontSize = (element.style?.font_size || 0.025) * canvasHeight

  // 获取布局配置
  const layout = element.layout
  const wrapEnabled = layout?.wrap === true
  const fixedWidth = layout?.width  // 设置的固定宽度（百分比）

  // 获取文本内容来测量
  const content = element.content
  let text = ''
  if (content) {
    // 如果是数值型数据源，应用小数位数格式化
    let rawText = getSampleText(content.source, content.sample_text) || ''
    if (numericSources.has(content.source)) {
      rawText = formatNumericValue(rawText, content.decimal_places)
    }
    text = rawText
    // 使用 format 字段应用前缀后缀
    const formatStr = content.format || '{}'
    try {
      text = formatStr.replace('{}', text)
    } catch {
      // 保持原文本
    }
  }

  // 创建临时 Canvas 测量文本（使用 Canvas 原始尺寸）
  const tempCanvas = document.createElement('canvas')
  const tempCtx = tempCanvas.getContext('2d')
  let naturalTextWidth = fontSize * 3  // 默认宽度
  let ascent = fontSize * 0.8
  let descent = fontSize * 0.2

  if (tempCtx && text) {
    const fontFamily = getFontFamilyName(element.style?.font_family || 'system_msyh')
    // 与 getHandlePosition 保持一致：将双引号替换为单引号并包裹
    const fontCss = fontFamily.replace(/"/g, "'")
    tempCtx.font = `${fontSize}px '${fontCss}'`
    const metrics = tempCtx.measureText(text)
    naturalTextWidth = metrics.width
    // 获取文字的实际垂直边界
    ascent = metrics.actualBoundingBoxAscent || fontSize * 0.8
    descent = metrics.actualBoundingBoxDescent || fontSize * 0.2
  }

  // 计算文本宽度：如果设置了固定宽度，使用固定宽度；否则使用自然宽度
  let textWidth = naturalTextWidth
  if (fixedWidth !== undefined && fixedWidth !== null) {
    textWidth = fixedWidth * canvasWidth
  }

  const textHeight = ascent + descent

  // 计算元素高度：如果有 layout.height 且启用折行，使用 layout.height
  let elementHeight = textHeight
  if (wrapEnabled && layout?.height !== undefined && layout?.height !== null) {
    elementHeight = layout.height * canvasHeight
  }

  // 计算文本左上角位置（与 renderOverlayCanvas 中的逻辑完全一致）
  // 后端 PIL: final_x = container_x + offset_x - elem_anchor_x
  //          final_y = container_y + offset_y - elem_anchor_y
  // Canvas 渲染时: fillText 的 y 是基线位置，需要加上 ascent
  // 定界框: 直接使用左上角坐标

  // 元素锚点偏移（相对于元素左上角）
  const elemAnchorOffsetX = textWidth * elementAnchor.x
  const elemAnchorOffsetY = elementHeight * elementAnchor.y

  // 文字左上角位置（元素左上角）
  const textX = anchorX + offsetX - elemAnchorOffsetX
  const textY = anchorY + offsetY - elemAnchorOffsetY

  // 转换为百分比（相对于 .preview-content 的原始尺寸）
  const previewBaseWidth = BASE_PREVIEW_SIZE
  const previewBaseHeight = BASE_PREVIEW_SIZE / (canvasWidth / canvasHeight)
  const scaleToPreviewX = previewBaseWidth / canvasWidth
  const scaleToPreviewY = previewBaseHeight / canvasHeight
  const leftPct = (textX * scaleToPreviewX) / previewBaseWidth * 100
  const topPct = (textY * scaleToPreviewY) / previewBaseHeight * 100
  const widthPct = (textWidth * scaleToPreviewX) / previewBaseWidth * 100
  const heightPct = (elementHeight * scaleToPreviewY) / previewBaseHeight * 100

  // 调试：输出 outline 位置
  // console.log(`[getElementOutlineStyle] left=${leftPct.toFixed(2)}% top=${topPct.toFixed(2)}% width=${widthPct.toFixed(2)}% height=${heightPct.toFixed(2)}%`)

  return {
    left: `${leftPct.toFixed(3)}%`,
    top: `${topPct.toFixed(3)}%`,
    width: `${widthPct.toFixed(3)}%`,
    height: `${heightPct.toFixed(3)}%`
  }
}

// 是否显示行高控制点（需要 wrap=true）
const hasLineHeight = computed(() => {
  if (!selectedElement.value) return false
  const layout = selectedElement.value.layout
  return layout?.wrap === true
})

// 判断特定控制点是否应该显示
// 控制点显示逻辑：
// - 四角：始终显示（用于调整字号）
// - n/s（上下）：折行时显示，或作为锚点时显示
// - e/w（左右）：始终显示（允许用户设置固定宽度），除非作为锚点时已由其他方式处理
// - 居中锚点标记：单独显示（当锚点是 center 时）
const shouldShowHandle = (handle: string): boolean => {
  if (!selectedElement.value) return false
  const anchor = selectedElement.value.position.element_anchor || 'top-left'

  // n/s 控制点：折行时显示，或作为锚点时显示
  if (handle === 'n') {
    return hasLineHeight.value || anchor === 'top'
  }
  if (handle === 's') {
    return hasLineHeight.value || anchor === 'bottom'
  }

  // e/w 控制点：始终显示，除非锚点正好是该位置（避免与四角重叠）
  // 始终显示是为了让用户可以拖动设置固定宽度
  if (handle === 'e') {
    return anchor !== 'right'
  }
  if (handle === 'w') {
    return anchor !== 'left'
  }

  // 四角始终显示
  return true
}

// 获取控制点位置（相对于 .preview-content 的百分比）
const getHandlePosition = (handle: string) => {
  if (!selectedElement.value) return {}

  const config = templateConfig.value
  if (!config || !config.canvas) return {}

  const canvasWidth = config.canvas.width
  const canvasHeight = config.canvas.height

  // 计算安全区
  const safeArea = config.safe_area
  const safeAreaLeft = canvasWidth * safeArea.left
  const safeAreaTop = canvasHeight * safeArea.top
  const safeAreaRight = canvasWidth * safeArea.right
  const safeAreaBottom = canvasHeight * safeArea.bottom
  const safeAreaWidth = canvasWidth - safeAreaLeft - safeAreaRight
  const safeAreaHeight = canvasHeight - safeAreaTop - safeAreaBottom

  // 容器锚点始终相对于画布计算（不受 use_safe_area 影响）
  const contentArea = { x: 0, y: 0, width: canvasWidth, height: canvasHeight }

  const anchorPositions: Record<string, { x: number; y: number }> = {
    'top-left': { x: 0, y: 0 },
    'top': { x: 0.5, y: 0 },
    'top-right': { x: 1, y: 0 },
    'left': { x: 0, y: 0.5 },
    'center': { x: 0.5, y: 0.5 },
    'right': { x: 1, y: 0.5 },
    'bottom-left': { x: 0, y: 1 },
    'bottom': { x: 0.5, y: 1 },
    'bottom-right': { x: 1, y: 1 }
  }

  const containerAnchor = anchorPositions[selectedElement.value.position.container_anchor] || anchorPositions['top-left']
  const elementAnchor = anchorPositions[selectedElement.value.position.element_anchor] || anchorPositions['top-left']

  const anchorX = contentArea.x + contentArea.width * containerAnchor.x
  const anchorY = contentArea.y + contentArea.height * containerAnchor.y

  // position.x/y 的单位是比例（0-1），范围 -0.5 到 0.5
  const offsetX = selectedElement.value.position.x * canvasWidth
  const offsetY = selectedElement.value.position.y * canvasHeight

  const fontSize = (selectedElement.value.style?.font_size || 0.025) * canvasHeight

  const content = selectedElement.value.content
  let text = ''
  if (content) {
    text = getSampleText(content.source, content.sample_text) || ''
    // 使用 format 字段应用前缀后缀
    const formatStr = content.format || '{}'
    try {
      text = formatStr.replace('{}', text)
    } catch {
      // 保持原文本
    }
  }

  const tempCanvas = document.createElement('canvas')
  const tempCtx = tempCanvas.getContext('2d')
  let textWidth = fontSize * 3
  let ascent = fontSize * 0.8
  let descent = fontSize * 0.2

  if (tempCtx && text) {
    const fontId = selectedElement.value.style?.font_family || ''
    const fontFamily = getFontFamilyName(fontId).replace(/"/g, "'")
    // 使用单引号包裹 fontFamily
    tempCtx.font = `${fontSize}px '${fontFamily}'`
    const metrics = tempCtx.measureText(text)
    textWidth = metrics.width
    ascent = metrics.actualBoundingBoxAscent || fontSize * 0.8
    descent = metrics.actualBoundingBoxDescent || fontSize * 0.2
  }

  const textHeight = ascent + descent

  // 获取布局配置，检查是否启用折行和固定宽度
  const layout = selectedElement.value.layout
  const wrapEnabled = layout?.wrap === true
  const fixedWidth = layout?.width

  // 如果设置了固定宽度，使用固定宽度（不依赖折行模式）
  if (fixedWidth !== undefined && fixedWidth !== null) {
    textWidth = fixedWidth * canvasWidth
  }

  // 计算元素高度：如果有 layout.height 且启用折行，使用 layout.height
  let elementHeight = textHeight
  if (wrapEnabled && layout?.height !== undefined && layout?.height !== null) {
    elementHeight = layout.height * canvasHeight
  }

  const elemAnchorOffsetX = textWidth * elementAnchor.x
  const elemAnchorOffsetY = elementHeight * elementAnchor.y

  // 文本左上角位置（Canvas 坐标系）
  const textX = anchorX + offsetX - elemAnchorOffsetX
  const textY = anchorY + offsetY - elemAnchorOffsetY

  // 转换为百分比
  // 关键修复：百分比应该基于 .preview-content 的实际尺寸
  const previewBaseWidth = BASE_PREVIEW_SIZE
  const previewBaseHeight = BASE_PREVIEW_SIZE / (canvasWidth / canvasHeight)
  const scaleToPreviewX = previewBaseWidth / canvasWidth
  const scaleToPreviewY = previewBaseHeight / canvasHeight
  const toPctX = (x: number) => (x * scaleToPreviewX) / previewBaseWidth * 100
  const toPctY = (y: number) => (y * scaleToPreviewY) / previewBaseHeight * 100

  // 控制点尺寸转换为百分比
  // 关键：百分比应该基于缩放后的容器尺寸，
  // 因为控制点和 outline 都在同一个被 transform: scale() 的容器内
  const HANDLE_SIZE = 10  // 控制点是 10x10 像素
  const zoomFactor = zoomLevel.value / 100
  const scaledWidth = previewBaseWidth * zoomFactor
  const scaledHeight = previewBaseHeight * zoomFactor
  // 控制点尺寸占缩放后容器的百分比
  const handleSizePctX = HANDLE_SIZE / scaledWidth * 100
  const handleSizePctY = HANDLE_SIZE / scaledHeight * 100

  // 计算各控制点位置
  let left = textX
  let top = textY
  let right = textX + textWidth
  let bottom = textY + elementHeight

  // 计算边框的百分比位置
  const leftPct = toPctX(left)
  const topPct = toPctY(top)
  const rightPct = toPctX(right)
  const bottomPct = toPctY(bottom)

  // 获取当前元素的锚点
  const currentAnchor = selectedElement.value.position.element_anchor || 'top-left'

  // 计算控制点样式类
  const getHandleClass = (handleType: string): string => {
    const classes = ['resize-handle']
    const anchor = currentAnchor

    // 判断控制点是否是当前锚点对应的控制点
    let isCorrespondingHandle = false

    switch (anchor) {
      case 'top-left':
        // 只显示 NW 红色
        isCorrespondingHandle = handleType === 'nw'
        break
      case 'top-right':
        // 只显示 NE 红色
        isCorrespondingHandle = handleType === 'ne'
        break
      case 'bottom-left':
        // 只显示 SW 红色
        isCorrespondingHandle = handleType === 'sw'
        break
      case 'bottom-right':
        // 只显示 SE 红色
        isCorrespondingHandle = handleType === 'se'
        break
      case 'top':
        // 只显示 N 红色（无论是否折行）
        isCorrespondingHandle = handleType === 'n'
        break
      case 'bottom':
        // 只显示 S 红色（无论是否折行）
        isCorrespondingHandle = handleType === 's'
        break
      case 'left':
        // 只显示 W 红色
        isCorrespondingHandle = handleType === 'w'
        break
      case 'right':
        // 只显示 E 红色
        isCorrespondingHandle = handleType === 'e'
        break
      case 'center':
        // center 锚点：不修改现有控制点，不添加 handle-center 类
        // 居中标记会在 HTML 中单独添加
        break
    }

    // 只有对应的控制点才添加红色类
    if (isCorrespondingHandle) {
      classes.push('handle-anchor-red')
    }

    return classes.join(' ')
  }

  switch (handle) {
    case 'nw':
      return {
        left: `${leftPct - handleSizePctX / 2}%`,
        top: `${topPct - handleSizePctY / 2}%`,
        class: getHandleClass('nw')
      }
    case 'ne':
      return {
        left: `${rightPct - handleSizePctX / 2}%`,
        top: `${topPct - handleSizePctY / 2}%`,
        class: getHandleClass('ne')
      }
    case 'sw':
      return {
        left: `${leftPct - handleSizePctX / 2}%`,
        top: `${bottomPct - handleSizePctY / 2}%`,
        class: getHandleClass('sw')
      }
    case 'se':
      return {
        left: `${rightPct - handleSizePctX / 2}%`,
        top: `${bottomPct - handleSizePctY / 2}%`,
        class: getHandleClass('se')
      }
    case 'n':
      return {
        left: `${(leftPct + rightPct) / 2 - handleSizePctX / 2}%`,
        top: `${topPct - handleSizePctY / 2}%`,
        class: getHandleClass('n')
      }
    case 's':
      return {
        left: `${(leftPct + rightPct) / 2 - handleSizePctX / 2}%`,
        top: `${bottomPct - handleSizePctY / 2}%`,
        class: getHandleClass('s')
      }
    case 'e':
      return {
        left: `${rightPct - handleSizePctX / 2}%`,
        top: `${(topPct + bottomPct) / 2 - handleSizePctY / 2}%`,
        class: getHandleClass('e')
      }
    case 'w':
      return {
        left: `${leftPct - handleSizePctX / 2}%`,
        top: `${(topPct + bottomPct) / 2 - handleSizePctY / 2}%`,
        class: getHandleClass('w')
      }
    // 新增：返回居中锚点标记的样式
    // 居中标记应该显示在定界框的中心位置
    case 'center-marker':
      return {
        left: `${(leftPct + rightPct) / 2 - handleSizePctX / 2}%`,
        top: `${(topPct + bottomPct) / 2 - handleSizePctY / 2}%`,
        class: 'resize-handle anchor-center-marker'
      }
    default:
      return {
        left: '0%',
        top: '0%',
        class: 'resize-handle'
      }
  }
}

// 处理元素鼠标按下（开始拖动）
const handleElementMouseDown = (event: MouseEvent, element: OverlayElement) => {
  if (event.button !== 0) return // 只响应左键

  // 阻止事件传播和默认行为
  event.preventDefault()
  event.stopPropagation()

  selectElement(element.id)
  isDragging.value = true
  dragStartPos.value = { x: event.clientX, y: event.clientY }
  // 只更新拖动需要的位置字段，保留其他字段
  elementStartPos.value.x = element.position.x
  elementStartPos.value.y = element.position.y
}

// 处理画布区域鼠标按下（用于空格键拖动）
const handleCanvasMouseDown = (event: MouseEvent) => {

  // 只处理左键
  if (event.button !== 0) return

  // 始终阻止浏览器的默认滚动行为（autoscroll）
  event.preventDefault()

  // 记录鼠标按下状态和位置
  isMouseDownOnCanvas.value = true
  lastMousePos.value = { x: event.clientX, y: event.clientY }

  // 空格键拖动画布
  if (isSpacePressed.value && previewContainerRef.value) {
    event.stopPropagation()
    event.stopImmediatePropagation()  // 阻止其他监听器
    isPanning.value = true
    panStartPos.value = { x: event.clientX, y: event.clientY }
    panStartScroll.value = {
      x: previewContainerRef.value.scrollLeft,
      y: previewContainerRef.value.scrollTop
    }
    previewContainerRef.value.classList.add('is-panning')
  
  }
}

// 触摸开始（移动端直接拖动画布）
const handleCanvasTouchStart = (event: TouchEvent) => {
  // 只响应单指触摸（拖动），双指（缩放）由 handleTouchMove 处理
  if (event.touches.length === 1 && previewContainerRef.value) {
    const touch = event.touches[0]
    isPanning.value = true
    panStartPos.value = { x: touch.clientX, y: touch.clientY }
    panStartScroll.value = {
      x: previewContainerRef.value.scrollLeft,
      y: previewContainerRef.value.scrollTop
    }
    previewContainerRef.value.classList.add('is-panning')
  
  }
}

// 触摸移动
const handleCanvasTouchMove = (event: TouchEvent) => {
  if (isPanning.value && previewContainerRef.value) {
    event.preventDefault()  // 防止页面滚动

    const touch = event.touches[0]
    if (!touch) return

    const deltaX = touch.clientX - panStartPos.value.x
    const deltaY = touch.clientY - panStartPos.value.y

    const container = previewContainerRef.value
    const newScrollLeft = panStartScroll.value.x - deltaX
    const newScrollTop = panStartScroll.value.y - deltaY

    // 计算滚动范围
    const maxScrollLeft = container.scrollWidth - container.clientWidth
    const maxScrollTop = container.scrollHeight - container.clientHeight

    // 限制在有效范围内
    const clampedScrollLeft = Math.max(0, Math.min(maxScrollLeft, newScrollLeft))
    const clampedScrollTop = Math.max(0, Math.min(maxScrollTop, newScrollTop))

    // 直接设置滚动位置
    container.scrollLeft = clampedScrollLeft
    container.scrollTop = clampedScrollTop
  }
}

// 触摸结束
const handleCanvasTouchEnd = () => {
  if (isPanning.value) {
    isPanning.value = false
    if (previewContainerRef.value) {
      previewContainerRef.value.classList.remove('is-panning')
    }
  }
}

// 处理缩放开始
const handleResizeStart = (event: MouseEvent, element: OverlayElement, handle: string) => {


  // 居中锚点标记不触发任何操作
  if (handle === 'center-marker') {
  
    return
  }

  if (event.button !== 0) {
  
    return
  }

  // 先设置状态，确保即使后续代码出错，状态也已设置
  selectElement(element.id)
  isResizing.value = true
  resizeHandle.value = handle
  dragStartPos.value = { x: event.clientX, y: event.clientY }



  // 阻止事件传播和默认行为
  event.stopPropagation()
  event.preventDefault()

  // 计算元素的实际边界（画布百分比）
  // 与 getElementOutlineStyle 中的计算逻辑一致
  const config = templateConfig.value
  const canvasWidth = config.canvas.width
  const canvasHeight = config.canvas.height

  // 锚点位置映射
  const anchorPositions: Record<string, { x: number; y: number }> = {
    'top-left': { x: 0, y: 0 },
    'top': { x: 0.5, y: 0 },
    'top-right': { x: 1, y: 0 },
    'left': { x: 0, y: 0.5 },
    'center': { x: 0.5, y: 0.5 },
    'right': { x: 1, y: 0.5 },
    'bottom-left': { x: 0, y: 1 },
    'bottom': { x: 0.5, y: 1 },
    'bottom-right': { x: 1, y: 1 }
  }

  // 获取锚点配置
  const containerAnchor = element.position.container_anchor || 'top-left'
  const elementAnchor = element.position.element_anchor || 'top-left'
  const posX = element.position.x || 0
  const posY = element.position.y || 0

  // 计算容器锚点位置（始终相对于画布，不受 use_safe_area 影响）
  const containerAnchorPos = anchorPositions[containerAnchor] || anchorPositions['top-left']
  const elementAnchorPos = anchorPositions[elementAnchor] || anchorPositions['top-left']

  // 容器锚点始终相对于画布
  const contentArea = { x: 0, y: 0, width: canvasWidth, height: canvasHeight }

  const anchorX = contentArea.x + contentArea.width * containerAnchorPos.x
  const anchorY = contentArea.y + contentArea.height * containerAnchorPos.y

  // 计算偏移（像素）
  // position.x/y 的单位是比例（0-1），范围 -0.5 到 0.5
  const offsetX = posX * canvasWidth
  const offsetY = posY * canvasHeight

  // 获取文本尺寸
  const style = element.style || {}
  const layout = element.layout || {}
  const fontSize = style.font_size || 0.025
  const actualFontSize = fontSize * canvasHeight
  const fontFamily = getFontFamilyName(style.font_family || 'system_msyh')
  const wrapEnabled = layout.wrap === true
  const fixedWidth = layout.width

  // 使用临时 canvas 测量文本
  let textWidth = 0
  let ascent = 0
  let descent = 0

  const tempCtx = overlayCanvasRef.value?.getContext('2d')




  // 获取文本内容
  let textSource = ''
  let customSampleText = ''

  if (element.type === 'text' && element.content) {
    textSource = element.content.source || ''
    customSampleText = element.content.sample_text || ''
  }






  if (tempCtx) {
    let text = getSampleText(textSource, customSampleText)
    // 应用 format 字段（与 getHandlePosition 保持一致）
    const formatStr = element.content?.format || '{}'
    try {
      text = formatStr.replace('{}', text)
    } catch {
      // 保持原文本
    }
  
    // 与 getHandlePosition 一致：将双引号替换为单引号
    const fontCss = fontFamily.replace(/"/g, "'")
    tempCtx.font = `${actualFontSize}px '${fontCss}'`
    const metrics = tempCtx.measureText(text)
    textWidth = metrics.width
    ascent = metrics.actualBoundingBoxAscent || actualFontSize * 0.8
    descent = metrics.actualBoundingBoxDescent || actualFontSize * 0.2
  
  }

  // 如果设置了固定宽度，使用设置的宽度（不依赖折行模式）
  if (fixedWidth !== undefined && fixedWidth !== null) {
    textWidth = fixedWidth * canvasWidth
  }

  const textHeight = ascent + descent

  // 计算元素高度
  let elementHeight = textHeight
  if (wrapEnabled && layout.height !== undefined && layout.height !== null) {
    elementHeight = layout.height * canvasHeight
  }

  // 元素锚点偏移
  const elemAnchorOffsetX = textWidth * elementAnchorPos.x
  const elemAnchorOffsetY = elementHeight * elementAnchorPos.y

  // 元素左上角位置（画布像素）
  const elemLeft = anchorX + offsetX - elemAnchorOffsetX
  const elemTop = anchorY + offsetY - elemAnchorOffsetY
  const elemRight = elemLeft + textWidth
  const elemBottom = elemTop + elementHeight

  // 计算预览内容百分比（与 mousePctX/Y 使用相同的坐标系）
  const previewBaseWidth = BASE_PREVIEW_SIZE
  const previewBaseHeight = BASE_PREVIEW_SIZE / (canvasWidth / canvasHeight)
  const scaleToPreviewX = previewBaseWidth / canvasWidth
  const scaleToPreviewY = previewBaseHeight / canvasHeight

  // 元素边界转换为预览内容百分比（0-100）
  const elemLeftPct = (elemLeft * scaleToPreviewX) / previewBaseWidth * 100
  const elemTopPct = (elemTop * scaleToPreviewY) / previewBaseHeight * 100
  const elemRightPct = (elemRight * scaleToPreviewX) / previewBaseWidth * 100
  const elemBottomPct = (elemBottom * scaleToPreviewY) / previewBaseHeight * 100

  // 当前宽度/高度（预览内容百分比）
  const currentWidthPct = elemRightPct - elemLeftPct
  const currentHeightPct = elemBottomPct - elemTopPct

  // 调试日志






  // 获取 getHandlePosition 计算的控制点位置（用于对比）
  const handlePos = getHandlePosition('e')


  // 对于四角控制点，计算拖动开始时鼠标到元素中心的距离（预览内容百分比）
  let centerDistance: number | undefined
  if (['nw', 'ne', 'sw', 'se'].includes(handle)) {
    // 计算鼠标在预览内容中的位置百分比（与 handleMouseMove 中的计算逻辑一致）
    const zoomFactor = zoomLevel.value / 100
    const aspectRatio = canvasWidth / canvasHeight
    const previewBaseWidth = BASE_PREVIEW_SIZE
    const previewBaseHeight = BASE_PREVIEW_SIZE / aspectRatio

    const containerRect = previewContainerRef.value?.getBoundingClientRect()
    if (containerRect) {
      const mouseX = event.clientX - containerRect.left
      const mouseY = event.clientY - containerRect.top
      const scrollLeft = previewContainerRef.value.scrollLeft
      const scrollTop = previewContainerRef.value.scrollTop

      const scrollWrapper = previewContainerRef.value.querySelector('.preview-scroll-wrapper') as HTMLElement
      if (scrollWrapper) {
        const scrollWrapperWidth = scrollWrapper.offsetWidth
        const scrollWrapperHeight = scrollWrapper.offsetHeight
        const contentLeft = (scrollWrapperWidth - previewBaseWidth * zoomFactor) / 2
        const contentTop = (scrollWrapperHeight - previewBaseHeight * zoomFactor) / 2

        const mouseInScrollX = mouseX + scrollLeft
        const mouseInScrollY = mouseY + scrollTop
        const mouseInContentX = mouseInScrollX - contentLeft
        const mouseInContentY = mouseInScrollY - contentTop

        const mouseUnscaledX = mouseInContentX / zoomFactor
        const mouseUnscaledY = mouseInContentY / zoomFactor
        const mousePctX = (mouseUnscaledX / previewBaseWidth) * 100
        const mousePctY = (mouseUnscaledY / previewBaseHeight) * 100

        // 计算元素中心点（预览内容百分比）
        const elemCenterX = (elemLeftPct + elemRightPct) / 2
        const elemCenterY = (elemTopPct + elemBottomPct) / 2

        // 计算鼠标到元素中心的距离
        const deltaX = mousePctX - elemCenterX
        const deltaY = mousePctY - elemCenterY
        centerDistance = Math.sqrt(deltaX * deltaX + deltaY * deltaY)

      
      }
    }
  }

  elementStartPos.value = {
    x: posX,
    y: posY,
    left: elemLeftPct,
    top: elemTopPct,
    right: elemRightPct,
    bottom: elemBottomPct,
    width: currentWidthPct,
    height: currentHeightPct,
    fontSize: fontSize,
    centerDistance
  }
}

// 全局鼠标移动处理
const handleMouseMove = (event: MouseEvent) => {
  // 始终更新鼠标位置（用于空格键拖动检测）
  lastMousePos.value = { x: event.clientX, y: event.clientY }

  // 调试日志
  if (isDragging.value) {
  
  }

  // 空格键拖动画布
  if (isPanning.value && previewContainerRef.value) {
    event.preventDefault()
    event.stopPropagation()

    const container = previewContainerRef.value

    const deltaX = event.clientX - panStartPos.value.x
    const deltaY = event.clientY - panStartPos.value.y

    const newScrollLeft = panStartScroll.value.x - deltaX
    const newScrollTop = panStartScroll.value.y - deltaY

    // 计算滚动范围
    const maxScrollLeft = container.scrollWidth - container.clientWidth
    const maxScrollTop = container.scrollHeight - container.clientHeight

    // 限制在有效范围内
    const clampedScrollLeft = Math.max(0, Math.min(maxScrollLeft, newScrollLeft))
    const clampedScrollTop = Math.max(0, Math.min(maxScrollTop, newScrollTop))

    // 调试日志 - 显示实际设置后的值
  

    // 使用 requestAnimationFrame 设置滚动，避免事件循环冲突
    requestAnimationFrame(() => {
      if (previewContainerRef.value) {
        previewContainerRef.value.scrollLeft = clampedScrollLeft
        previewContainerRef.value.scrollTop = clampedScrollTop
      }
    })
    return
  }

  if (!selectedElement.value) return

  const element = selectedElement.value

  if (isDragging.value) {
    // 拖动元素
    if (!previewCanvasRef.value) return
    const zoomFactor = zoomLevel.value / 100

    const deltaX = event.clientX - dragStartPos.value.x
    const deltaY = event.clientY - dragStartPos.value.y

    console.log('[Drag] 鼠标移动: deltaX=', deltaX.toFixed(1), 'px, deltaY=', deltaY.toFixed(1), 'px, zoom=', zoomFactor.toFixed(2))

    // 将像素偏移转换为画布百分比（-50 到 50）
    // deltaX 是视口中的像素，需要除以 zoomFactor 转换为未缩放像素
    // 然后除以预览内容宽度，得到相对于预览内容的百分比
    // 最后除以 100 得到画布百分比（因为 position.x 的单位是画布宽度的比例）
    const canvasWidth = templateConfig.value.canvas.width
    const canvasHeight = templateConfig.value.canvas.height
    const aspectRatio = canvasWidth / canvasHeight
    const previewBaseWidth = BASE_PREVIEW_SIZE
    const previewBaseHeight = BASE_PREVIEW_SIZE / aspectRatio

    console.log('[Drag] 预览内容尺寸: width=', previewBaseWidth, ', height=', previewBaseHeight.toFixed(0))

    // 将视口像素转换为预览内容像素
    const deltaPreviewX = deltaX / zoomFactor
    const deltaPreviewY = deltaY / zoomFactor

    console.log('[Drag] 预览内容像素: deltaPreviewX=', deltaPreviewX.toFixed(1), ', deltaPreviewY=', deltaPreviewY.toFixed(1))

    // 转换为预览内容百分比
    const deltaPreviewPctX = (deltaPreviewX / previewBaseWidth) * 100
    const deltaPreviewPctY = (deltaPreviewY / previewBaseHeight) * 100

    console.log('[Drag] 预览内容百分比: deltaPreviewPctX=', deltaPreviewPctX.toFixed(2), '%, deltaPreviewPctY=', deltaPreviewPctY.toFixed(2), '%')

    // 转换为画布百分比（position.x/y 的单位）
    const deltaCanvasPctX = deltaPreviewPctX / 100
    const deltaCanvasPctY = deltaPreviewPctY / 100

    console.log('[Drag] 画布百分比(position单位): deltaCanvasPctX=', deltaCanvasPctX.toFixed(4), ', deltaCanvasPctY=', deltaCanvasPctY.toFixed(4))

    const oldX = element.position.x
    const oldY = element.position.y

    const newX = elementStartPos.value.x + deltaCanvasPctX
    const newY = elementStartPos.value.y + deltaCanvasPctY

    console.log('[Drag] 位置: oldX=', oldX.toFixed(4), '-> newX=', newX.toFixed(4), ', 实际变化=', (newX - oldX).toFixed(4))

    element.position.x = newX
    element.position.y = newY

    // 强制触发轮廓样式更新
    elementStyleVersion.value++
  }

  if (isResizing.value && resizeHandle.value) {
    // 缩放元素
    if (!previewCanvasRef.value || !selectedElement.value) {
    
      isResizing.value = false
      resizeHandle.value = null
      return
    }

    const zoomFactor = zoomLevel.value / 100
    const canvasWidth = templateConfig.value.canvas.width
    const canvasHeight = templateConfig.value.canvas.height
    const aspectRatio = canvasWidth / canvasHeight
    const previewBaseWidth = BASE_PREVIEW_SIZE
    const previewBaseHeight = BASE_PREVIEW_SIZE / aspectRatio

    // 获取预览容器的矩形（视口）
    const containerRect = previewContainerRef.value.getBoundingClientRect()

    // 鼠标在视口内的相对位置
    const mouseX = event.clientX - containerRect.left
    const mouseY = event.clientY - containerRect.top

    // 获取滚动偏移
    const scrollLeft = previewContainerRef.value.scrollLeft
    const scrollTop = previewContainerRef.value.scrollTop

    // 鼠标在 scroll wrapper 内的绝对位置（考虑滚动）
    const mouseInScrollX = mouseX + scrollLeft
    const mouseInScrollY = mouseY + scrollTop

    // 获取 scroll wrapper 的实际尺寸
    const scrollWrapper = previewContainerRef.value.querySelector('.preview-scroll-wrapper') as HTMLElement
    if (!scrollWrapper) return

    const scrollWrapperWidth = scrollWrapper.offsetWidth
    const scrollWrapperHeight = scrollWrapper.offsetHeight

    // 计算预览内容在 scroll wrapper 中的位置（居中）
    const contentLeft = (scrollWrapperWidth - previewBaseWidth * zoomFactor) / 2
    const contentTop = (scrollWrapperHeight - previewBaseHeight * zoomFactor) / 2

    // 鼠标相对于预览内容左上角的位置（像素，已缩放）
    const mouseInContentX = mouseInScrollX - contentLeft
    const mouseInContentY = mouseInScrollY - contentTop

    // 转换为未缩放的像素坐标
    const mouseUnscaledX = mouseInContentX / zoomFactor
    const mouseUnscaledY = mouseInContentY / zoomFactor

    // 转换为预览内容的百分比坐标（这是最终用于 layout.width/height 的值）
    const mousePctX = (mouseUnscaledX / previewBaseWidth) * 100
    const mousePctY = (mouseUnscaledY / previewBaseHeight) * 100

    // 获取元素起始边界
    const elemLeft = elementStartPos.value.left || 0
    const elemTop = elementStartPos.value.top || 0
    const elemRight = elementStartPos.value.right || 0
    const elemBottom = elementStartPos.value.bottom || 0

    const layout = element.layout
    const wrapEnabled = layout?.wrap === true
    const hasFixedWidth = layout?.width !== undefined && layout?.width !== null
    const initialFontSize = elementStartPos.value.fontSize || 0.025

    switch (resizeHandle.value) {
      case 'n': {
        // 上边缘 - 调整行高
        if (layout && wrapEnabled) {
          const newHeight = elemBottom - mousePctY
          layout.height = newHeight / 100
        }
        break
      }
      case 's': {
        // 下边缘 - 调整行高
        if (layout && wrapEnabled) {
          const newHeight = mousePctY - elemTop
          layout.height = newHeight / 100
        }
        break
      }
      case 'e': {
        // 右边缘 - 调整宽度
        // 折行模式或有固定宽度时都可以调整
        if (layout && (wrapEnabled || hasFixedWidth)) {
          const newWidthPreviewPct = mousePctX - elemLeft
          const newWidthCanvasPct = newWidthPreviewPct / 100
          layout.width = newWidthCanvasPct
        }
        break
      }
      case 'w': {
        // 左边缘 - 调整宽度
        // 折行模式或有固定宽度时都可以调整
        if (layout && (wrapEnabled || hasFixedWidth)) {
          const newWidthPreviewPct = elemRight - mousePctX
          const newWidthCanvasPct = newWidthPreviewPct / 100
          layout.width = newWidthCanvasPct
        }
        break
      }
      case 'nw':
      case 'ne':
      case 'sw':
      case 'se': {
        // 四角控制点：调整字号，跟随鼠标位置
        const elemCenterX = (elemLeft + elemRight) / 2
        const elemCenterY = (elemTop + elemBottom) / 2

        const deltaX_pct = mousePctX - elemCenterX
        const deltaY_pct = mousePctY - elemCenterY
        const currentDistance_pct = Math.sqrt(deltaX_pct * deltaX_pct + deltaY_pct * deltaY_pct)

        const initialDistance_pct = elementStartPos.value.centerDistance
        const referenceDistance = initialDistance_pct || elementStartPos.value.width || 10
        const scaleRatio = referenceDistance > 0 ? currentDistance_pct / referenceDistance : 1

        // 调整字号
        if (element.style) {
          element.style.font_size = initialFontSize * scaleRatio
        }

        // 如果启用了折行，同时缩放宽度和高度
        if (layout && wrapEnabled) {
          const initialWidth = elementStartPos.value.width
          const initialHeight = elementStartPos.value.height
          const newWidthPreviewPct = initialWidth * scaleRatio
          const newHeightPreviewPct = initialHeight * scaleRatio

          layout.width = newWidthPreviewPct / 100
          layout.height = newHeightPreviewPct / 100
        } else if (layout && hasFixedWidth) {
          // 非折行模式但有固定宽度时，同时缩放宽度
          const initialWidth = elementStartPos.value.width
          const newWidthPreviewPct = initialWidth * scaleRatio
          layout.width = newWidthPreviewPct / 100
        }
        break
      }
    }
  }
}

// 停止拖动/缩放
const handleMouseUp = (event?: MouseEvent) => {

  isDragging.value = false
  isResizing.value = false
  resizeHandle.value = null
  isPanning.value = false
  isMouseDownOnCanvas.value = false

  // 移除 is-panning class
  if (previewContainerRef.value) {
    previewContainerRef.value.classList.remove('is-panning')
  }
}

// 点击内容区域 - 清除所有拖动/缩放状态
const handleContentClick = (event: MouseEvent) => {
  // 如果点击的是控制点或元素轮廓，不处理
  if ((event.target as HTMLElement).closest('.resize-handle')) return
  if ((event.target as HTMLElement).closest('.element-outline')) return

  // 只有在非拖动/缩放状态时才清除状态
  // 注意：click 事件在 mouseup 之后触发，此时拖动/缩放应该已经结束
  // 如果仍在拖动/缩放状态，说明是在拖动过程中点击的，不应该清除状态
  // 这里只是为了安全起见，清理可能残留的状态
  if (!isDragging.value && !isResizing.value && !isPanning.value) {
    // 非拖动状态，点击空白区域取消选择
    // selectedElementId.value = null  // 可选：点击空白取消选择
  }
}

// 触发文件输入

// 触发文件输入
const triggerFileInput = () => {
  fileInputRef.value?.click()
}

// 处理文件选择
const handleFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) {
    // 仅保存在本地（使用 URL.createObjectURL）
    if (referenceImage.value) {
      URL.revokeObjectURL(referenceImage.value)
    }
    referenceImage.value = URL.createObjectURL(file)
  }
  target.value = ''
}

// 清除参考图
const clearReferenceImage = () => {
  if (referenceImage.value) {
    URL.revokeObjectURL(referenceImage.value)
  }
  referenceImage.value = null
}

// 导航
const handleBack = () => {
  router.back()
}

const goHome = () => {
  router.push('/')
}

const handleCommand = (command: string) => {
  switch (command) {
    case 'settings':
      router.push('/settings')
      break
    case 'admin':
      router.push('/admin')
      break
    case 'logout':
      authStore.logout()
      router.push('/login')
      break
  }
}

// 快捷键
const handleKeydown = (e: KeyboardEvent) => {
  // 空格键按下 - 只在鼠标位于画布容器中时才进入拖动模式
  if (e.code === 'Space' && !e.repeat) {
    // 检查鼠标是否在画布容器中
    if (previewContainerRef.value) {
      const rect = previewContainerRef.value.getBoundingClientRect()
      const isInCanvas = (
        lastMousePos.value.x >= rect.left &&
        lastMousePos.value.x <= rect.right &&
        lastMousePos.value.y >= rect.top &&
        lastMousePos.value.y <= rect.bottom
      )

      // 只有鼠标在画布中时才启用拖动模式
      if (isInCanvas) {
        // 阻止默认行为（防止滚动页面等）
        e.preventDefault()
        e.stopPropagation()

        // 将焦点移到画布容器上
        if (document.activeElement !== previewContainerRef.value) {
          previewContainerRef.value.focus()
        }

        // 锁定滚动
        shouldLockScroll.value = true
        isSpacePressed.value = true

        // 如果鼠标已经在画布上按下，立即启动拖动
        if (isMouseDownOnCanvas.value && previewContainerRef.value) {
          isPanning.value = true
          panStartPos.value = { ...lastMousePos.value }
          panStartScroll.value = {
            x: previewContainerRef.value.scrollLeft,
            y: previewContainerRef.value.scrollTop
          }
        }
        return
      }
    }
    // 如果鼠标不在画布中，让空格键正常工作（例如在输入框中输入空格）
  }

  // Ctrl+S / Cmd+S 保存
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
    e.preventDefault()
    saveTemplate()
  }
}

// 空格键释放
const handleKeyup = (e: KeyboardEvent) => {
  if (e.code === 'Space') {
    isSpacePressed.value = false
    isPanning.value = false

    // 延迟解锁滚动（给浏览器一点时间完成任何待处理的滚动）
    setTimeout(() => {
      shouldLockScroll.value = false
    }, 100)
  }
}

// 初始化
onMounted(async () => {
  // 等待 DOM 渲染完成后计算缩放
  await nextTick()
  zoomLevel.value = calculateFitZoom()
  isUserZoomed.value = false  // 重置为自动适配模式

  // 初始居中画布
  await nextTick()
  fitToContainer()

  // 监听容器大小变化
  if (previewContainerRef.value) {
    resizeObserver = new ResizeObserver(() => {
      // 只有在用户没有手动调整缩放时才自动适配
      if (!isUserZoomed.value) {
        zoomLevel.value = calculateFitZoom()
      }
      // 重新渲染 Canvas
      renderOverlayCanvas()
    })
    resizeObserver.observe(previewContainerRef.value)
  }

  // 检查是否为新建模式
  if (route.params.id !== 'new') {
    await loadTemplate()
  }
  // 初始渲染 Canvas
  renderOverlayCanvas()
  // 在捕获阶段监听空格键，优先于其他元素处理
  document.addEventListener('keydown', handleKeydown, { capture: true })
  document.addEventListener('keyup', handleKeyup)
  // 全局鼠标移动事件（用于拖动画布和元素）
  document.addEventListener('mousemove', handleMouseMove)
  // 全局鼠标释放事件（防止鼠标移出容器后松开无法结束拖动）
  document.addEventListener('mouseup', handleMouseUp)
  // 同时监听 window 的 mouseup 作为备用
  window.addEventListener('mouseup', handleMouseUp)

  // 监听滚动事件：在滚动锁定时阻止滚动并恢复位置
  if (previewContainerRef.value) {
    let lastValidScrollLeft = 0
    let lastValidScrollTop = 0

    previewContainerRef.value.addEventListener('scroll', (e) => {
      const target = e.target as HTMLElement

    

      // 拖动时允许滚动，并更新记录的位置
      if (isPanning.value) {
        lastValidScrollLeft = target.scrollLeft
        lastValidScrollTop = target.scrollTop
      
        return
      }

      // 滚动锁定时阻止滚动
      if (shouldLockScroll.value) {
      
        target.scrollLeft = lastValidScrollLeft
        target.scrollTop = lastValidScrollTop
        return
      }

      // 记录正常滚动位置
      lastValidScrollLeft = target.scrollLeft
      lastValidScrollTop = target.scrollTop
    })
  }

  // 初始居中画布（与点击"适配"效果一致）
  nextTick(() => {
    fitToContainer()
  })
})

onBeforeUnmount(() => {
  if (previewImageUrl.value) {
    URL.revokeObjectURL(previewImageUrl.value)
  }
  if (referenceImage.value) {
    URL.revokeObjectURL(referenceImage.value)
  }
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  document.removeEventListener('keydown', handleKeydown, { capture: true })
  document.removeEventListener('keyup', handleKeyup)
  document.removeEventListener('mousemove', handleMouseMove)
  document.removeEventListener('mouseup', handleMouseUp)
  window.removeEventListener('mouseup', handleMouseUp)
})
</script>

<style scoped>
.overlay-template-editor {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.overlay-template-editor > .el-header {
  position: sticky;
  top: 0;
  z-index: 1000;
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
  gap: 16px;
}

.overlay-template-editor > .el-main {
  flex: 1;
  overflow: hidden;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.nav-btn {
  padding: 8px;
}

.home-nav-btn {
  margin-left: 0;
  margin-right: 12px;
}

.header-left h1 {
  font-size: 20px;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  padding: 5px 10px;
  border-radius: 4px;
  transition: background-color 0.3s;
}

.user-info:hover {
  background-color: #f5f7fa;
}

.user-info .username {
  display: inline;
}

.editor-main {
  flex: 1;
  padding: 0;
  overflow: hidden;
  background: #f5f7fa;
}

.editor-layout {
  display: flex;
  height: 100%;
}

/* 左侧预览区 */
.preview-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16px;
  overflow: hidden;
}

.preview-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.zoom-level-button {
  min-width: 60px;
  font-family: monospace;
}

.opacity-control {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: 12px;
}

.opacity-label,
.opacity-value {
  font-size: 12px;
  color: #909399;
}

.preview-container {
  position: relative;
  flex: 1;
  background: #1a1a1a;
  border-radius: 8px;
  overflow: auto;
}

.preview-container.pan-mode {
  overscroll-behavior: none;
}

/* 按住空格键时显示抓手光标 */
.preview-container.space-pressed {
  cursor: grab;
}

/* 拖动中显示抓取中光标 */
.preview-container.is-panning {
  user-select: none;
  overscroll-behavior: none;
  overflow: hidden !important;  /* 拖动时禁用滚动条 */
  cursor: grabbing;
}

.preview-container.is-panning::-webkit-scrollbar {
  display: none;  /* 隐藏滚动条 */
}

/* 使容器可以接收键盘事件，即使没有焦点 */
.preview-container {
  outline: none;
}

.preview-container:focus {
  outline: none;
}

.preview-container::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.preview-container::-webkit-scrollbar-track {
  background: #2a2a2a;
}

.preview-container::-webkit-scrollbar-thumb {
  background: #555;
  border-radius: 4px;
}

.preview-container::-webkit-scrollbar-thumb:hover {
  background: #777;
}

/* 滚动包装器 - 提供正确的滚动区域 */
.preview-scroll-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

/* 预览内容包装器 - 用于定位覆盖层 */
.preview-content {
  /* 使用 flex 居中，不需要 absolute 定位 */
  flex-shrink: 0;
  transition: transform 0.1s ease-out;
}

/* 参考图 */
.reference-image {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 1;
  object-fit: contain;
  pointer-events: none;
}

/* 屏幕框 - 完整的屏幕边界（最底层指示） */
.screen-frame {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border: 2px solid rgba(255, 255, 0, 0.8);
  box-sizing: border-box;
  z-index: 2;
  pointer-events: none;
}

/* 安全区边距 - 遮挡区域（阴影显示） */
.safe-margin {
  position: absolute;
  background: rgba(255, 0, 0, 0.15);
  z-index: 2;
  pointer-events: none;
  box-sizing: border-box;
}

.safe-margin.top {
  top: 0;
  left: 0;
  right: 0;
}

.safe-margin.bottom {
  bottom: 0;
  left: 0;
  right: 0;
}

.safe-margin.left {
  top: 0;
  bottom: 0;
  left: 0;
}

.safe-margin.right {
  top: 0;
  bottom: 0;
  right: 0;
}

/* 覆盖层预览 */
.overlay-preview {
  position: relative;
  z-index: 3;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  pointer-events: none;
}

/* 实时 Canvas 预览 */
.overlay-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 2;
  pointer-events: none;
}

/* 安全区内容 - 可用内容区域（虚线框） */
.safe-area-content {
  position: absolute;
  border: 2px dashed rgba(0, 255, 0, 0.7);
  z-index: 4;
  pointer-events: none;
  box-sizing: border-box;
  background: rgba(0, 255, 0, 0.05);
}

.element-outline {
  position: absolute;
  border: 1px dashed transparent;
  z-index: 5;
  cursor: move;
  pointer-events: auto;
}

.element-outline:hover {
  border-color: rgba(64, 158, 255, 0.5);
}

.element-outline.selected {
  border-color: #409eff;
  border-style: solid;
}

.element-outline.dragging {
  cursor: grabbing;
}

/* 控制点覆盖层 - 在 .preview-content 内部，与 element-outline 同级 */
.resize-handles-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 10;
}

/* 控制手柄基础样式 - 使用反向缩放保持固定大小 */
.resize-handle,
.anchor-indicator {
  position: absolute;
  width: 10px;
  height: 10px;
  background: #fff;
  border: 2px solid #409eff;
  border-radius: 2px;
  pointer-events: auto;
  transform-origin: top left;
  transform: scale(calc(1 / var(--preview-scale, 1)));
  transition: transform 0.1s;
}

/* 四角控制点 - 调整字号 */
.resize-handle.corner.nw {
  cursor: nw-resize;
  width: 16px;
  height: 16px;
}

.resize-handle.corner.ne {
  cursor: ne-resize;
  width: 16px;
  height: 16px;
}

.resize-handle.corner.sw {
  cursor: sw-resize;
  width: 16px;
  height: 16px;
}

.resize-handle.corner.se {
  cursor: se-resize;
  width: 16px;
  height: 16px;
}

/* 四边中点控制点 - 需要保持居中变换 */
.resize-handle.edge.n {
  cursor: n-resize;
}

.resize-handle.edge.e {
  cursor: e-resize;
}

.resize-handle.edge.s {
  cursor: s-resize;
}

.resize-handle.edge.w {
  cursor: w-resize;
}

/* 悬停效果 - 需要同时应用反向缩放和悬停放大 */
.resize-handle:hover {
  transform: scale(calc(1.2 / var(--preview-scale, 1))) !important;
}

/* 锚点对应的控制点 - 红色边框 */
.resize-handle.handle-anchor-red {
  background: #fff;
  border-color: #f56c6c;
}

/* 居中锚点标记 - 红色、半透明 */
.resize-handle.anchor-center-marker {
  background: #fff;
  border-color: #f56c6c;
  opacity: 0.5;
}

/* 右侧配置面板 */
.config-panel {
  width: 360px;
  background: #fff;
  border-left: 1px solid #e4e7ed;
  overflow-y: auto;
  padding: 16px;
}

.config-section {
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #ebeef5;
}

.config-section:last-child {
  border-bottom: none;
}

.config-section h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 500;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-header h3 {
  margin: 0;
}

/* 预设按钮 */
.preset-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

/* 元素列表 */
.element-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.element-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
}

.element-item:hover {
  background: #e6f7ff;
}

.element-item.active {
  background: #bae7ff;
}

.drag-handle {
  cursor: grab;
}

.element-name-input {
  flex: 1;
  font-size: 14px;
}

.element-name-input :deep(.el-input__wrapper) {
  padding: 0 8px;
  background: transparent;
  box-shadow: none;
}

.element-name-input :deep(.el-input__inner) {
  font-size: 14px;
}

.form-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.4;
}

/* 移动端适配 */
@media (max-width: 1024px) {
  .editor-layout {
    flex-direction: column;
  }

  .config-panel {
    width: 100%;
    border-left: none;
    border-top: 1px solid #e4e7ed;
    max-height: 50vh;
  }
}
</style>
