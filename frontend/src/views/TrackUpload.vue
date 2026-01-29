<template>
  <el-container class="upload-container">
    <el-header>
      <div class="header-content">
        <el-button @click="$router.back()" :icon="ArrowLeft" />
        <el-button @click="$router.push('/home')" :icon="HomeFilled" />
        <h1>上传轨迹</h1>
        <div></div>
      </div>
    </el-header>

    <el-main class="main">
      <el-card class="upload-card">
        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-width="120px"
          @submit.prevent="handleSubmit"
        >
          <!-- 文件上传 -->
          <el-form-item label="轨迹文件" prop="file" required>
            <el-upload
              ref="uploadRef"
              :auto-upload="false"
              :limit="1"
              :on-change="handleFileChange"
              :on-remove="handleFileRemove"
              accept=".gpx,.csv,.xlsx,.kml,.kmz"
              drag
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                将 GPX、CSV、XLSX、KML 或 KMZ 文件拖到此处，或<em>点击上传</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  支持 GPX、GPS Logger CSV、本项目导出 CSV/XLSX、两步路 KML/KMZ 格式的轨迹文件
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
            <el-button @click="$router.back()">取消</el-button>
          </el-form-item>
        </el-form>
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
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules, type UploadInstance, type UploadFile } from 'element-plus'
import { ArrowLeft, HomeFilled, UploadFilled } from '@element-plus/icons-vue'
import { trackApi } from '@/api/track'

const router = useRouter()
const formRef = ref<FormInstance>()
const uploadRef = ref<UploadInstance>()

const uploading = ref(false)
const progress = ref(0)
const progressStatus = ref<'success' | 'exception' | 'warning' | ''>('')

const form = reactive({
  file: null as File | null,
  name: '',
  description: '',
  original_crs: 'wgs84',
  fill_geocoding: false,
})

const rules: FormRules = {
  file: [{ required: true, message: '请选择轨迹文件（GPX、CSV、XLSX、KML 或 KMZ）', trigger: 'change' }],
  name: [
    { required: true, message: '请输入轨迹名称', trigger: 'blur' },
    { min: 1, max: 200, message: '轨迹名称长度应为1-200个字符', trigger: 'blur' },
  ],
}

function handleFileChange(file: UploadFile) {
  if (file.raw) {
    form.file = file.raw
    // 如果名称为空，使用文件名作为默认名称
    if (!form.name && file.name) {
      form.name = file.name.replace(/\.(gpx|csv|xlsx|kml|kmz)$/i, '')
    }
  }
}

function handleFileRemove() {
  form.file = null
}

async function handleSubmit() {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    if (!form.file) {
      ElMessage.warning('请选择要上传的轨迹文件')
      return
    }

    uploading.value = true
    progress.value = 30
    progressStatus.value = ''

    try {
      await trackApi.upload({
        file: form.file,
        name: form.name,
        description: form.description || undefined,
        original_crs: form.original_crs,
        fill_geocoding: form.fill_geocoding,
      })

      progress.value = 100
      progressStatus.value = 'success'

      ElMessage.success('轨迹上传成功！')

      // 延迟跳转到轨迹列表
      setTimeout(() => {
        router.push('/tracks')
      }, 1000)
    } catch (error) {
      progress.value = 100
      progressStatus.value = 'exception'
      // 错误已在拦截器中处理
    } finally {
      uploading.value = false
    }
  })
}
</script>

<style scoped>
.upload-container {
  height: 100%;
  background: #f5f7fa;
}

.el-header {
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: center;
  padding: 0 20px;
}

.header-content {
  display: flex;
  align-items: center;
  width: 100%;
  gap: 20px;
}

.header-content h1 {
  font-size: 20px;
  margin: 0;
  flex: 1;
}

.main {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.upload-card {
  margin-bottom: 20px;
}

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
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
