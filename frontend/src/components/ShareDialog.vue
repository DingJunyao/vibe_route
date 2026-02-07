<template>
  <el-dialog
    v-model="dialogVisible"
    title="分享轨迹"
    :width="isMobile ? '95%' : '500px'"
    class="responsive-dialog share-dialog"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div class="share-dialog-content">
      <!-- 分享开关 -->
      <div class="share-switch-row">
        <span class="share-label">启用分享</span>
        <el-switch
          v-model="isEnabled"
          @change="handleToggleShare"
          :loading="toggling"
        />
      </div>

      <el-alert
        v-if="isEnabled"
        type="info"
        :closable="false"
        show-icon
        class="share-hint"
      >
        启用分享后，任何人都可以通过链接访问此轨迹。
      </el-alert>

      <!-- 分享链接（仅在启用时显示） -->
      <div v-if="isEnabled" class="share-section">
        <div class="section-title">分享链接</div>
        <div class="share-link-row">
          <el-input
            :model-value="shareUrl"
            readonly
            class="share-url-input"
          >
            <template #append>
              <el-button
                :icon="copyIcon"
                @click="copyShareUrl"
              >
                复制
              </el-button>
            </template>
          </el-input>
        </div>
        <!-- 二维码 -->
        <div v-if="shareUrl" class="qrcode-container">
          <canvas ref="qrcodeCanvas" class="qrcode-canvas"></canvas>
        </div>
      </div>

      <!-- 嵌入代码（仅在启用时显示） -->
      <div v-if="isEnabled" class="share-section">
        <div class="section-title">嵌入代码</div>
        <p class="section-hint">将此轨迹嵌入到您的网站中</p>
        <div class="embed-code-row">
          <el-input
            :model-value="embedCode"
            readonly
            type="textarea"
            :rows="3"
            class="embed-code-input"
          />
        </div>
        <el-button
          :icon="copyIcon"
          @click="copyEmbedCode"
          size="small"
        >
          复制嵌入代码
        </el-button>
      </div>

      <!-- API Key 提示 -->
      <el-alert
        v-if="isEnabled && hasUserConfigKeys"
        type="success"
        :closable="false"
        show-icon
        class="share-hint"
      >
        分享页面将使用您的自定义地图 API Key。
      </el-alert>

      <el-alert
        v-if="isEnabled && !hasUserConfigKeys"
        type="warning"
        :closable="false"
        show-icon
        class="share-hint"
      >
        分享页面使用系统默认地图配置。您可以在
        <el-link type="primary" @click="openSettings">设置</el-link>
        中配置自己的 API Key。
      </el-alert>
    </div>

    <template #footer>
      <el-button @click="handleClose">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { DocumentCopy as CopyIcon } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import QRCode from 'qrcode'
import { trackApi, type ShareStatus } from '@/api/track'
import { useUserConfigStore } from '@/stores/userConfig'

interface Props {
  visible: boolean
  trackId: number
  initialStatus?: ShareStatus
}

const props = defineProps<Props>()

// 响应式：判断是否为移动端
const screenWidth = ref(window.innerWidth)
const isMobile = computed(() => screenWidth.value <= 1366)

// 监听窗口大小变化
window.addEventListener('resize', () => {
  screenWidth.value = window.innerWidth
})
const emit = defineEmits<{
  'update:visible': [value: boolean]
  'update:status': [status: ShareStatus]
}>()

const router = useRouter()
const userConfigStore = useUserConfigStore()

const dialogVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value)
})

const isEnabled = ref(false)
const shareStatus = ref<ShareStatus | null>(null)
const toggling = ref(false)
const qrcodeCanvas = ref<HTMLCanvasElement | null>(null)

const shareToken = computed(() => shareStatus.value?.share_token || '')
const shareUrl = computed(() => {
  if (!shareToken.value) return ''
  const baseUrl = window.location.origin
  return `${baseUrl}/s/${shareToken.value}`
})

const embedCode = computed(() => {
  if (!shareToken.value) return ''
  return `<iframe src="${shareUrl.value}?embed=true" width="100%" height="520" frameborder="0" scrolling="no" allowfullscreen allow="fullscreen"></iframe>`
})

// 检查用户是否有自定义 API Key
const hasUserConfigKeys = computed(() => {
  const config = userConfigStore.config
  if (!config) return false

  // 检查是否有任何 API Key 配置
  if (config.map_layers) {
    for (const layer of Object.values(config.map_layers)) {
      if (layer) {
        if (layer.tk || layer.api_key || layer.ak || layer.security_js_code) {
          return true
        }
      }
    }
  }

  return false
})

// 生成二维码
async function generateQRCode() {
  if (!shareUrl.value || !qrcodeCanvas.value) return

  try {
    await QRCode.toCanvas(qrcodeCanvas.value, shareUrl.value, {
      width: 200,
      margin: 2,
      color: {
        dark: '#000000',
        light: '#FFFFFF'
      }
    })
  } catch (err) {
    console.error('Failed to generate QR code:', err)
  }
}

// 复制分享链接
async function copyShareUrl() {
  try {
    await navigator.clipboard.writeText(shareUrl.value)
    ElMessage.success('链接已复制')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

// 复制嵌入代码
async function copyEmbedCode() {
  try {
    await navigator.clipboard.writeText(embedCode.value)
    ElMessage.success('嵌入代码已复制')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

// 切换分享状态
async function handleToggleShare() {
  if (toggling.value) return

  toggling.value = true
  try {
    let result: ShareStatus
    if (isEnabled.value) {
      // 启用分享
      result = await trackApi.createShare(props.trackId)
    } else {
      // 停用分享
      result = await trackApi.deleteShare(props.trackId)
    }

    shareStatus.value = result
    emit('update:status', result)

    ElMessage.success(isEnabled.value ? '分享已启用' : '分享已停用')

    // 启用分享后生成二维码
    if (isEnabled.value) {
      await nextTick()
      await generateQRCode()
    }
  } catch {
    // 发生错误，恢复开关状态
    isEnabled.value = !isEnabled.value
  } finally {
    toggling.value = false
  }
}

// 打开设置页面
function openSettings() {
  dialogVisible.value = false
  router.push({ name: 'Settings' })
}

function handleClose() {
  dialogVisible.value = false
}

// 监听 visible 变化，加载分享状态
watch(() => props.visible, async (visible) => {
  if (visible && props.trackId) {
    // 使用传入的初始状态或从服务器获取
    if (props.initialStatus) {
      shareStatus.value = props.initialStatus
      isEnabled.value = props.initialStatus.is_shared
    } else {
      try {
        const status = await trackApi.getShareStatus(props.trackId)
        shareStatus.value = status
        isEnabled.value = status.is_shared
      } catch {
        // 忽略错误
      }
    }

    // 如果已启用分享，生成二维码
    if (isEnabled.value && shareUrl.value) {
      await nextTick()
      await generateQRCode()
    }
  }
})
</script>

<style scoped>
.share-dialog-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.share-switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.share-label {
  font-size: 16px;
  font-weight: 500;
}

.share-hint {
  font-size: 13px;
}

.share-hint :deep(.el-alert__content) {
  font-size: 13px;
}

.share-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.section-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin: 0;
}

.share-url-input,
.embed-code-input {
  font-family: monospace;
  font-size: 12px;
}

.share-link-row {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.qrcode-container {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 16px;
  background-color: var(--el-fill-color-light);
  border-radius: 8px;
}

.qrcode-canvas {
  max-width: 100%;
}

.embed-code-row {
  position: relative;
}

/* 移动端优化 */
@media (max-width: 768px) {
  .share-label {
    font-size: 14px;
  }

  .section-title {
    font-size: 13px;
  }
}
</style>
