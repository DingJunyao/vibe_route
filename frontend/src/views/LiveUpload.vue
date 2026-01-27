<template>
  <el-container class="upload-container">
    <el-header>
      <div class="header-content">
        <h1>实时轨迹上传</h1>
      </div>
    </el-header>

    <el-main class="main">
      <!-- 加载中 -->
      <el-card v-if="loading" class="loading-card">
        <el-skeleton :rows="3" animated />
      </el-card>

      <!-- token 无效 -->
      <el-card v-else-if="!recording" class="error-card">
        <el-result icon="error" title="无效的链接" sub-title="此上传链接已失效或不存在">
          <template #extra>
            <el-button type="primary" @click="$router.push('/login')">返回登录</el-button>
          </template>
        </el-result>
      </el-card>

      <template v-else>
        <!-- GPS Logger URL 显示卡片 -->
        <el-card class="url-display-card">
          <template #header>
            <div class="card-header">
              <el-icon><Link /></el-icon>
              <span>GPS Logger 上传地址</span>
            </div>
          </template>

          <div class="url-content">
            <p class="url-intro">使用以下 URL 配置 GPS Logger 应用进行实时轨迹记录：</p>

            <!-- GPS Logger URL -->
            <div class="url-section">
              <div class="url-label">GPS Logger URL：</div>
              <el-input :model-value="gpsLoggerUrl" readonly type="textarea" :rows="3" class="url-textarea">
                <template #append>
                  <el-button @click="copyGpsLoggerUrl" :icon="DocumentCopy">
                    {{ copyButtonText }}
                  </el-button>
                </template>
              </el-input>
            </div>

            <!-- 使用说明 -->
            <el-divider content-position="left">使用说明</el-divider>

            <div class="instructions">
              <ol class="instruction-list">
                <li>点击上方"复制"按钮复制 URL</li>
                <li>打开 GPS Logger 应用</li>
                <li>进入设置 → 日志记录 → 日志记录 URL</li>
                <li>粘贴复制的 URL 并保存</li>
                <li>开始记录轨迹，应用会自动上传到本系统</li>
              </ol>
            </div>

            <!-- 分隔线 -->
            <el-divider />

            <!-- 切换到文件上传模式 -->
            <div class="upload-mode-switch">
              <el-button type="primary" @click="showFileUpload = true" text>
                <el-icon><Upload /></el-icon>
                或直接上传 GPX 文件
              </el-button>
            </div>
          </div>
        </el-card>

        <!-- 文件上传表单（折叠） -->
        <el-collapse-transition>
          <el-card v-show="showFileUpload" class="upload-card">
            <template #header>
              <div class="card-header">
                <span>上传 GPX 文件</span>
                <el-button type="info" size="small" text @click="showFileUpload = false">
                  <el-icon><Close /></el-icon>
                </el-button>
              </div>
            </template>

            <el-form
              ref="formRef"
              :model="form"
              :rules="rules"
              label-width="120px"
              @submit.prevent="handleSubmit"
            >
              <!-- 文件上传 -->
              <el-form-item label="GPX 文件" prop="file" required>
                <el-upload
                  ref="uploadRef"
                  :auto-upload="false"
                  :limit="1"
                  :on-change="handleFileChange"
                  :on-remove="handleFileRemove"
                  accept=".gpx"
                  drag
                >
                  <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                  <div class="el-upload__text">
                    将 GPX 文件拖到此处，或<em>点击上传</em>
                  </div>
                  <template #tip>
                    <div class="el-upload__tip">
                      只支持 GPX 格式的轨迹文件
                    </div>
                  </template>
                </el-upload>
              </el-form-item>

              <!-- 轨迹名称 -->
              <el-form-item label="轨迹名称" prop="name" required>
                <el-input
                  v-model="form.name"
                  placeholder="请输入轨迹名称"
                  maxlength="200"
                  show-word-limit
                />
              </el-form-item>

              <!-- 轨迹描述 -->
              <el-form-item label="轨迹描述">
                <el-input
                  v-model="form.description"
                  type="textarea"
                  :rows="3"
                  placeholder="请输入轨迹描述（可选）"
                  maxlength="1000"
                  show-word-limit
                />
              </el-form-item>

              <!-- 原始坐标系 -->
              <el-form-item label="原始坐标系" prop="original_crs">
                <el-radio-group v-model="form.original_crs">
                  <el-radio value="wgs84">WGS84 (GPS 原始坐标)</el-radio>
                  <el-radio value="gcj02">GCJ02 (国测局坐标)</el-radio>
                  <el-radio value="bd09">BD09 (百度坐标)</el-radio>
                </el-radio-group>
                <div class="form-tip">
                  如果不确定，请选择 WGS84（大多数 GPS 设备的默认坐标系）
                </div>
              </el-form-item>

              <!-- 处理选项 -->
              <el-divider content-position="left">处理选项</el-divider>

              <el-form-item label="填充地理信息">
                <el-switch v-model="form.fill_geocoding" />
                <span class="switch-label">
                  自动填充轨迹点所在行政区划（省、市、区）和道路信息（道路名称和编号）
                </span>
              </el-form-item>

              <!-- 提交按钮 -->
              <el-form-item>
                <el-button
                  type="primary"
                  :loading="uploading"
                  :disabled="!form.file"
                  @click="handleSubmit"
                >
                  {{ uploading ? '上传中...' : '开始上传' }}
                </el-button>
                <el-button @click="resetForm">重置</el-button>
              </el-form-item>
            </el-form>
          </el-card>
        </el-collapse-transition>

        <!-- 上传成功 -->
        <el-card v-if="uploadSuccess" class="success-card">
          <el-result icon="success" title="上传成功" sub-title="轨迹已成功上传到系统中">
            <template #extra>
              <el-button type="primary" @click="resetForm">继续上传</el-button>
            </template>
          </el-result>
        </el-card>

        <!-- 上传进度 -->
        <el-card v-if="uploading" class="progress-card">
          <template #header>
            <div class="progress-header">
              <span>上传进度</span>
              <el-tag type="info">{{ progressStatus }}</el-tag>
            </div>
          </template>
          <el-progress :percentage="progress" :status="progressStatus" />
        </el-card>
      </template>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules, type UploadInstance, type UploadFile } from 'element-plus'
import { Link, DocumentCopy, Upload, UploadFilled, Close } from '@element-plus/icons-vue'
import { liveRecordingApi } from '@/api/liveRecording'

const route = useRoute()
const formRef = ref<FormInstance>()
const uploadRef = ref<UploadInstance>()

const loading = ref(true)
const recording = ref<{ name: string; description: string | null } | null>(null)
const uploading = ref(false)
const uploadSuccess = ref(false)
const showFileUpload = ref(false)
const progress = ref(0)
const progressStatus = ref<'success' | 'exception' | 'warning' | ''>('')
const copyButtonText = ref('复制')

const token = ref('')
const gpsLoggerUrl = computed(() => {
  if (!token.value) return ''
  const origin = window.location.origin
  return `${origin}/api/live-recordings/log/${token.value}?lat=%LAT&lon=%LON&time=%TIME&alt=%ALT&spd=%SPD`
})

const form = reactive({
  file: null as File | null,
  name: '',
  description: '',
  original_crs: 'wgs84',
  fill_geocoding: false,
})

const rules: FormRules = {
  file: [{ required: true, message: '请选择 GPX 文件', trigger: 'change' }],
  name: [
    { required: true, message: '请输入轨迹名称', trigger: 'blur' },
    { min: 1, max: 200, message: '轨迹名称长度应为1-200个字符', trigger: 'blur' },
  ],
}

// 从 URL 获取 token 并验证
onMounted(async () => {
  const queryToken = route.query.token as string
  if (!queryToken) {
    loading.value = false
    return
  }

  token.value = queryToken

  try {
    // 通过无认证 API 获取记录信息
    const info = await liveRecordingApi.getInfoByToken(queryToken)
    recording.value = {
      name: info.name,
      description: info.description,
    }
    loading.value = false
  } catch (error: any) {
    ElMessage.error(error.message || '无效的上传链接')
    loading.value = false
  }
})

// 复制 GPS Logger URL
function copyGpsLoggerUrl() {
  navigator.clipboard.writeText(gpsLoggerUrl.value).then(() => {
    copyButtonText.value = '已复制'
    ElMessage.success('URL 已复制到剪贴板')
    setTimeout(() => {
      copyButtonText.value = '复制'
    }, 2000)
  }).catch(() => {
    ElMessage.error('复制失败，请手动复制')
  })
}

function handleFileChange(file: UploadFile) {
  if (file.raw) {
    form.file = file.raw
    // 如果名称为空，使用文件名作为默认名称
    if (!form.name && file.name) {
      form.name = file.name.replace(/\.gpx$/i, '')
    }
  }
}

function handleFileRemove() {
  form.file = null
}

function resetForm() {
  form.file = null
  form.name = ''
  form.description = ''
  form.original_crs = 'wgs84'
  form.fill_geocoding = false
  uploadSuccess.value = false
  showFileUpload.value = false
  progress.value = 0
  progressStatus.value = ''
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
  if (formRef.value) {
    formRef.value.clearValidate()
  }
}

async function handleSubmit() {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    if (!form.file) {
      ElMessage.warning('请选择要上传的 GPX 文件')
      return
    }

    if (!token.value) {
      ElMessage.error('缺少上传凭证')
      return
    }

    uploading.value = true
    uploadSuccess.value = false
    progress.value = 30
    progressStatus.value = ''

    try {
      const response = await liveRecordingApi.uploadWithToken(token.value, {
        file: form.file,
        name: form.name,
        description: form.description || undefined,
        original_crs: form.original_crs,
        fill_geocoding: form.fill_geocoding,
      })

      progress.value = 100
      progressStatus.value = 'success'
      uploadSuccess.value = true

      ElMessage.success(`轨迹上传成功！已添加到"${response.recording_name}"`)

      // 清空文件，方便继续上传
      if (uploadRef.value) {
        uploadRef.value.clearFiles()
      }
      form.file = null
      form.name = ''
      form.description = ''
    } catch (error: any) {
      progress.value = 100
      progressStatus.value = 'exception'
      ElMessage.error(error.message || '上传失败，请检查链接是否有效')
    } finally {
      uploading.value = false
    }
  })
}
</script>

<style scoped>
.upload-container {
  min-height: 100vh;
  background: #f5f7fa;
}

.el-header {
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 20px;
}

.header-content h1 {
  font-size: 20px;
  margin: 0;
}

.main {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.loading-card,
.error-card,
.url-display-card,
.upload-card,
.success-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* URL 显示卡片 */
.url-display-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.url-display-card :deep(.el-card__header) {
  background: transparent;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
}

.url-display-card :deep(.el-card__body) {
  padding: 24px;
}

.url-content {
  color: white;
}

.url-intro {
  font-size: 16px;
  margin: 0 0 20px 0;
  opacity: 0.95;
}

.url-section {
  margin-bottom: 20px;
}

.url-label {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 8px;
  opacity: 0.9;
}

.url-textarea {
  font-family: 'Courier New', monospace;
  font-size: 13px;
}

.url-textarea :deep(.el-textarea__inner) {
  background: rgba(255, 255, 255, 0.95);
  color: #333;
}

.url-textarea :deep(.el-input-group__append) {
  background: rgba(255, 255, 255, 0.9);
}

.el-divider {
  border-color: rgba(255, 255, 255, 0.2);
}

.el-divider :deep(.el-divider__text) {
  color: rgba(255, 255, 255, 0.9);
}

.instructions {
  background: rgba(255, 255, 255, 0.1);
  padding: 16px;
  border-radius: 8px;
}

.instruction-list {
  margin: 0;
  padding-left: 20px;
  line-height: 1.8;
}

.instruction-list li {
  margin-bottom: 8px;
}

.upload-mode-switch {
  text-align: center;
}

.upload-mode-switch :deep(.el-button) {
  color: white;
}

/* 文件上传 */
:deep(.el-upload-dragger) {
  padding: 40px;
}

:deep(.el-icon--upload) {
  font-size: 67px;
  color: #409eff;
  margin-bottom: 16px;
}

.el-upload__text {
  font-size: 14px;
  color: #606266;
}

.el-upload__text em {
  color: #409eff;
  font-style: normal;
}

.el-upload__tip {
  font-size: 12px;
  color: #909399;
  margin-top: 7px;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}

.switch-label {
  margin-left: 10px;
  font-size: 14px;
  color: #606266;
}

.progress-card {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 400px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 1000;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 移动端响应式 */
@media (max-width: 1366px) {
  .main {
    padding: 10px;
  }

  .url-display-card :deep(.el-card__body) {
    padding: 16px;
  }

  .progress-card {
    width: 90%;
    right: 5%;
    bottom: 10px;
  }

  :deep(.el-form-item__label) {
    width: 100px !important;
  }
}
</style>
