<template>
  <el-container class="log-url-container">
    <el-header>
      <div class="header-content">
        <h1>实时轨迹记录</h1>
      </div>
    </el-header>

    <el-main class="main">
      <!-- 加载中 -->
      <el-card v-if="loading" class="loading-card">
        <el-skeleton :rows="3" animated />
      </el-card>

      <!-- token 无效 -->
      <el-card v-else-if="!recording" class="error-card">
        <el-result icon="error" title="无效的链接" sub-title="此记录链接已失效或不存在">
          <template #extra>
            <el-button type="primary" @click="$router.push('/login')">返回首页</el-button>
          </template>
        </el-result>
      </el-card>

      <!-- 引导页面 -->
      <el-card v-else class="guide-card">
        <template #header>
          <div class="card-header">
            <el-icon><Link /></el-icon>
            <span>GPS Logger 记录地址</span>
          </div>
        </template>

        <div class="guide-content">
          <!-- 记录信息 -->
          <div class="recording-info">
            <div class="info-item">
              <span class="info-label">记录名称：</span>
              <span class="info-value">{{ recording.name }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">状态：</span>
              <el-tag v-if="recording.status === 'active'" type="success" size="small">正在记录</el-tag>
              <el-tag v-else type="info" size="small">已结束</el-tag>
            </div>
            <div class="info-item-url">
              <div class="url-label">URL：</div>
              <el-input :model-value="fullUrl" readonly type="textarea" :rows="4" class="url-textarea" />
              <el-button @click="copyUrl" :icon="DocumentCopy" type="primary" class="copy-button">
                {{ copyButtonText }}
              </el-button>
            </div>
            <div v-if="recording.description" class="info-item">
              <span class="info-label">描述：</span>
              <span class="info-value">{{ recording.description }}</span>
            </div>
          </div>

          <!-- 使用说明 -->
          <el-divider content-position="left">配置步骤</el-divider>

          <div class="instructions">
            <ol class="step-list">
              <li><strong>复制此 URL：</strong>点击上方“复制”按钮</li>
              <li>用 <strong>Android</strong> 系统的手机打开 <el-link type="primary" href="https://gpslogger.app/" target="_blank">GPS Logger（GPS 记录器）</el-link> App</li>
              <li>在菜单中找到<strong>“自定义 URL”</strong>选项</li>
              <li>打开<strong>“记录到自定义 URL”</strong></li>
              <li><strong>“URL”</strong>粘贴刚刚复制的 URL</li>
              <li><strong>现在配置完成，可以开始记录了！</strong></li>
            </ol>

            <el-alert type="info" :closable="false" show-icon class="tip-alert">
              <template #title>
                <div class="instruction-title">提示</div>
              </template>
              <ul class="tip-list">
                <li>确保手机有网络连接</li>
                <li>应用在后台运行时也能记录</li>
                <li>记录会消耗一定的流量和电量</li>
              </ul>
            </el-alert>
          </div>
        </div>
      </el-card>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Link, DocumentCopy } from '@element-plus/icons-vue'
import { liveRecordingApi } from '@/api/liveRecording'

const route = useRoute()

const loading = ref(true)
const recording = ref<{ name: string; description: string | null; status: string } | null>(null)
const copyButtonText = ref('复制')

// 从 URL 获取 token
const token = computed(() => route.params.token as string)

// 完整的 GPS Logger URL（包含占位符）
const fullUrl = computed(() => {
  if (!token.value) return ''
  const origin = window.location.origin
  // 注意：这里保留占位符 %LAT, %LON 等，GPS Logger 会替换它们
  return `${origin}/api/live-recordings/log/${token.value}?lat=%LAT&lon=%LON&time=%TIME&alt=%ALT&spd=%SPD`
})

onMounted(async () => {
  if (!token.value) {
    loading.value = false
    return
  }

  try {
    // 验证 token 并获取记录信息
    const info = await liveRecordingApi.getInfoByToken(token.value)
    recording.value = {
      name: info.name,
      description: info.description,
      status: info.status,
    }
    loading.value = false
  } catch (error: any) {
    ElMessage.error(error.message || '无效的记录链接')
    loading.value = false
  }
})

function copyUrl() {
  // 检查剪贴板 API 是否可用
  if (!navigator.clipboard) {
    // 尝试使用传统的 execCommand 方法作为回退
    const textarea = document.createElement('textarea')
    textarea.value = fullUrl.value
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

  // 使用现代剪贴板 API
  navigator.clipboard.writeText(fullUrl.value).then(() => {
    copyButtonText.value = '已复制'
    ElMessage.success('URL 已复制到剪贴板')
    setTimeout(() => {
      copyButtonText.value = '复制'
    }, 2000)
  }).catch((err) => {
    // 检查是否是因为非安全上下文（http vs https）
    const isSecureContext = window.isSecureContext
    if (!isSecureContext) {
      ElMessage.warning('剪贴板 API 需要 HTTPS 环境，请手动选择复制')
    } else {
      ElMessage.error('复制失败，请手动复制')
    }
    console.error('复制失败:', err)
  })
}
</script>

<style scoped>
.log-url-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.el-header {
  background: rgba(255, 255, 255, 0.95);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 20px;
}

.header-content h1 {
  font-size: 20px;
  margin: 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.main {
  max-width: 700px;
  margin: 0 auto;
  padding: 20px;
}

.loading-card,
.error-card,
.guide-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 500;
}

.guide-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 记录信息 */
.recording-info {
  padding: 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.info-item:last-child {
  margin-bottom: 0;
}

.info-label {
  font-weight: 500;
  color: var(--el-text-color-regular);
  min-width: 80px;
}

.info-value {
  color: var(--el-text-color-primary);
}

/* URL 显示项（特殊布局） */
.info-item-url {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-item-url .url-label {
  font-weight: 500;
  color: var(--el-text-color-regular);
}

.copy-button {
  align-self: flex-start;
}

/* URL 显示 */
.url-display {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.url-label {
  font-size: 16px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.url-textarea {
  font-family: 'Courier New', monospace;
  font-size: 13px;
}

.url-textarea :deep(.el-textarea__inner) {
  background: var(--el-fill-color-light);
  color: #333;
  border: 2px solid var(--el-color-primary);
}

/* 使用说明 */
.instructions {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.step-list {
  margin: 0;
  padding-left: 20px;
  line-height: 1.8;
}

.step-list li {
  margin-bottom: 8px;
}

.tip-alert {
  background: #ecf5ff;
  border-color: #b3d8ff;
}

.tip-list {
  margin: 8px 0 0 0;
  padding-left: 20px;
}

.tip-list li {
  margin-bottom: 4px;
}

/* 移动端响应式 */
@media (max-width: 768px) {
  .main {
    padding: 10px;
  }

  .card-header {
    font-size: 16px;
  }

  .url-textarea :deep(.el-textarea__inner) {
    font-size: 11px;
  }

  .step-list {
    padding-left: 16px;
  }
}
</style>
