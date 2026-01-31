<script setup lang="ts">
import { ref, watch, computed, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { DocumentCopy, VideoPause } from '@element-plus/icons-vue'
import QRCode from 'qrcode'
import { liveRecordingApi } from '@/api/liveRecording'
import { formatTimeWithRelative, formatTimeShort } from '@/utils/relativeTime'

// Props
interface Props {
  visible: boolean
  recordingId: number
  token: string
  name: string
  status: 'active' | 'ended'
  fillGeocoding: boolean
  lastUploadAt: string | null
  lastPointTime: string | null
  lastPointCreatedAt: string | null
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  fillGeocoding: false,
  lastUploadAt: null,
  lastPointTime: null,
  lastPointCreatedAt: null,
})

// Emits
const emit = defineEmits<{
  'update:visible': [value: boolean]
  'ended': []
  'fillGeocodingChanged': [value: boolean]
}>()

// 对话框数据
const dialogVisible = ref(props.visible)
const gpsLoggerUrl = ref('')
const qrCode = ref('')
const copyButtonText = ref('复制')

// 对话框内时间刷新
const DIALOG_REFRESH_INTERVAL = 1000 // 1 秒
const dialogTimeRefreshKey = ref(0)
let dialogRefreshTimer: number | null = null

// 计算属性：是否是移动端
const isMobile = computed(() => window.innerWidth <= 1366)

// 初始化数据
async function initData() {
  if (!props.token) return

  try {
    // 获取实时记录详情
    const detail = await liveRecordingApi.getDetail(props.recordingId)

    // 生成 GPS Logger URL
    gpsLoggerUrl.value = liveRecordingApi.getGpsLoggerUrl(props.token)

    // 生成二维码
    qrCode.value = await QRCode.toString(gpsLoggerUrl.value, {
      width: 200,
      margin: 2,
      type: 'svg',
    })
  } catch (error) {
    console.error('获取实时记录详情失败:', error)
  }
}

// 监听 visible 变化
watch(() => props.visible, async (newVal) => {
  dialogVisible.value = newVal
  if (newVal) {
    await initData()
    startDialogTimeRefresh()
  } else {
    stopDialogTimeRefresh()
  }
})

// 监听 dialogVisible 变化，同步到父组件
watch(dialogVisible, (newVal) => {
  if (newVal !== props.visible) {
    emit('update:visible', newVal)
  }
})

// 刷新对话框内的时间数据
async function refreshDialogTimes() {
  try {
    const status = await liveRecordingApi.getStatus(props.recordingId)
    // 更新时间通过 event 传递给父组件，或者在这里直接更新
    // 由于我们不存储完整的状态，这里只更新刷新 key
  } catch (error) {
    // 静默处理错误
  }
  // 更新刷新 key，触发模板重新计算
  dialogTimeRefreshKey.value++
}

// 启动对话框时间刷新
function startDialogTimeRefresh() {
  if (dialogRefreshTimer) return
  refreshDialogTimes()
  dialogRefreshTimer = window.setInterval(() => {
    refreshDialogTimes()
  }, DIALOG_REFRESH_INTERVAL)
}

// 停止对话框时间刷新
function stopDialogTimeRefresh() {
  if (dialogRefreshTimer) {
    clearInterval(dialogRefreshTimer)
    dialogRefreshTimer = null
  }
}

// 格式化对话框内时间（依赖 dialogTimeRefreshKey 以触发刷新）
function formatTimeWithRelativeDialog(timeStr: string | null | undefined): string {
  // 依赖 dialogTimeRefreshKey，确保定时触发重新计算
  void dialogTimeRefreshKey.value
  return formatTimeWithRelative(timeStr)
}

// 复制 URL
function copyUrl() {
  const url = gpsLoggerUrl.value

  // 检查剪贴板 API 是否可用
  if (!navigator.clipboard) {
    const textarea = document.createElement('textarea')
    textarea.value = url
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()

    try {
      const successful = document.execCommand('copy')
      document.body.removeChild(textarea)
      if (successful) {
        copyButtonText.value = '已复制'
        ElMessage.success('URL 已复制到剪贴板')
        setTimeout(() => {
          copyButtonText.value = '复制'
        }, 2000)
      } else {
        ElMessage.error('复制失败，请手动选择复制')
      }
    } catch (err) {
      document.body.removeChild(textarea)
      ElMessage.error('复制失败，请手动选择复制')
      console.error('复制失败:', err)
    }
    return
  }

  navigator.clipboard.writeText(url).then(() => {
    copyButtonText.value = '已复制'
    ElMessage.success('URL 已复制到剪�贴板')
    setTimeout(() => {
      copyButtonText.value = '复制'
    }, 2000)
  }).catch((err) => {
    const isSecureContext = window.isSecureContext
    if (!isSecureContext) {
      ElMessage.warning('剪贴板 API 需要 HTTPS 环境，请手动选择复制')
    } else {
      ElMessage.error('复制失败，请手动复制')
    }
    console.error('复制失败:', err)
  })
}

// 更新填充地理信息设置
async function updateFillGeocoding(value: boolean) {
  const originalValue = props.fillGeocoding

  try {
    await liveRecordingApi.updateFillGeocoding(props.recordingId, value)
    ElMessage.success(value ? '已开启自动填充地理信息' : '已关闭自动填充地理信息')
    emit('fillGeocodingChanged', value)
  } catch (error) {
    // 失败时父组件不需要恢复，因为我们使用 props
    console.error('更新填充地理信息设置失败:', error)
  }
}

// 结束实时记录（带二次确认）
async function confirmEndRecording() {
  try {
    // 构建确认消息，包含最近上传信息
    let confirmMessage = `确定要结束实时记录"${props.name}"吗？`
    if (props.lastPointCreatedAt || props.lastUploadAt || props.lastPointTime) {
      confirmMessage += '<p style="margin-top: 12px;">最近上传信息：</p>'
      if (props.lastPointCreatedAt || props.lastUploadAt) {
        confirmMessage += `<p style="margin: 4px 0;">最近更新：${formatTimeWithRelative(props.lastPointCreatedAt || props.lastUploadAt)}</p>`
      }
      if (props.lastPointTime) {
        confirmMessage += `<p style="margin: 4px 0;">轨迹点时间：${formatTimeWithRelative(props.lastPointTime)}</p>`
      }
      confirmMessage += '<p style="margin-top: 8px; color: #E6A23C;">出于应用程序、网络等多方面的原因，在手机的 App 上停止记录轨迹后，不一定上传了全部的轨迹，会继续传输。</p>'
      confirmMessage += '<p style="margin-top: 8px; color: #E6A23C;">请务必确认你已经上传了全部轨迹点。如果觉得轨迹点时间对不上，请先检查你的 GPS 记录程序（如 GPS Logger）是否正常上传。</p>'
    }
    confirmMessage += '<p style="margin-top: 12px;">结束后将无法继续上传轨迹点。</p>'

    await ElMessageBox.confirm(
      confirmMessage,
      '确认结束记录',
      {
        confirmButtonText: '确定结束',
        cancelButtonText: '取消',
        type: 'warning',
        dangerouslyUseHTMLString: true,
      }
    )

    await liveRecordingApi.end(props.recordingId)
    ElMessage.success('记录已结束')
    dialogVisible.value = false
    emit('ended')
  } catch (error) {
    // 用户取消或错误已在拦截器中处理
  }
}

// 清理定时器
onUnmounted(() => {
  stopDialogTimeRefresh()
})
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    :title="`实时记录配置 - ${name}`"
    :width="isMobile ? '95%' : '500px'"
    class="responsive-dialog live-recording-dialog"
  >
    <div class="recording-detail-content">
      <!-- 最近上传信息 -->
      <div class="upload-info-section">
        <div class="info-item">
          <span class="info-label">最近更新：</span>
          <span class="info-value">{{ formatTimeWithRelativeDialog(lastPointCreatedAt || lastUploadAt) }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">轨迹点时间：</span>
          <span class="info-value">{{ formatTimeWithRelativeDialog(lastPointTime) }}</span>
        </div>
      </div>

      <!-- 填充地理信息开关 -->
      <div class="setting-section">
        <div class="setting-item">
          <span class="setting-label">上传时自动填充地理信息</span>
          <el-switch
            :model-value="fillGeocoding"
            @change="updateFillGeocoding"
            :disabled="status !== 'active'"
          />
        </div>
        <div class="setting-tip">
          开启后，上传轨迹点时会自动获取省市区、道路名称等地理信息
        </div>
      </div>

      <!-- GPS Logger URL -->
      <div class="url-section">
        <div class="url-label">GPS Logger URL：</div>
        <el-input :model-value="gpsLoggerUrl" readonly type="textarea" :rows="4" class="url-textarea" />
        <el-button @click="copyUrl" :icon="DocumentCopy" type="primary" class="copy-button">
          {{ copyButtonText }}
        </el-button>
      </div>

      <!-- 二维码 -->
      <div class="qrcode-container" v-if="qrCode">
        <div class="qrcode" v-html="qrCode"></div>
        <p class="qrcode-tip">扫描二维码查看配置说明</p>
      </div>
    </div>

    <template #footer>
      <el-button @click="dialogVisible = false">关闭</el-button>
      <el-button
        v-if="status === 'active'"
        type="danger"
        @click="confirmEndRecording"
      >
        <el-icon><VideoPause /></el-icon>
        结束记录
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
/* 实时记录详情对话框 */
.recording-detail-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 最近上传信息区域 */
.upload-info-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  margin: 12px 0;
}

.upload-info-section .info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.upload-info-section .info-label {
  font-size: 14px;
  color: var(--el-text-color-regular);
}

.upload-info-section .info-value {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

/* 设置区域 */
.setting-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.setting-label {
  font-size: 14px;
  color: var(--el-text-color-regular);
}

.setting-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-left: 0;
}

/* URL 区域 */
.url-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.url-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-regular);
}

.url-textarea {
  font-family: monospace;
}

.copy-button {
  align-self: flex-start;
}

/* 二维码容器 */
.qrcode-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 20px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.qrcode {
  width: 200px;
  height: 200px;
}

.qrcode :deep(svg) {
  width: 100%;
  height: 100%;
}

.qrcode-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin: 0;
}
</style>
