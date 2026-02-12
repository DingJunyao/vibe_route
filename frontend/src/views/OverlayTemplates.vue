<template>
  <div class="overlay-templates-container">
    <!-- Header -->
    <el-header>
      <div class="header-left">
        <el-button @click="handleBack" :icon="ArrowLeft" class="nav-btn" />
        <el-button @click="goHome" :icon="HomeFilled" class="nav-btn home-nav-btn" />
        <h1>覆盖层模板</h1>
      </div>
      <div class="header-right">
        <el-button @click="showImportDialog = true" :icon="Upload" class="desktop-only">导入</el-button>
        <el-button type="primary" @click="createNewTemplate" :icon="Plus" class="desktop-only">新建模板</el-button>
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
    <el-main class="templates-main">
      <!-- 过滤器 -->
      <div class="filter-bar">
        <el-radio-group v-model="filterType" @change="loadTemplates">
          <el-radio-button value="all">全部</el-radio-button>
          <el-radio-button value="system">系统模板</el-radio-button>
          <el-radio-button value="user">我的模板</el-radio-button>
        </el-radio-group>
      </div>

      <!-- 模板列表 -->
      <div v-loading="isLoading" class="templates-grid">
        <el-card
          v-for="template in templates"
          :key="template.id"
          class="template-card"
          :class="{ 'system-card': template.is_system }"
          shadow="hover"
        >
          <!-- 预览图 -->
          <div class="template-preview">
            <img v-if="template.previewUrl" :src="template.previewUrl" :alt="template.name" />
            <div v-else class="preview-placeholder">
              <el-icon><Document /></el-icon>
              <span>{{ template.name }}</span>
            </div>
            <div v-if="template.is_system" class="system-badge">系统</div>
            <div v-if="template.is_public && !template.is_system" class="public-badge">公开</div>
          </div>

          <!-- 模板信息 -->
          <div class="template-info">
            <h3 class="template-name">{{ template.name }}</h3>
            <p class="template-desc">{{ template.description || '暂无描述' }}</p>
          </div>

          <!-- 操作按钮 -->
          <div class="template-actions">
            <el-button-group>
              <el-button
                size="small"
                @click="editTemplate(template)"
                :disabled="template.is_system"
              >
                <el-icon><Edit /></el-icon>
                编辑
              </el-button>
              <el-button
                size="small"
                @click="duplicateTemplate(template)"
              >
                <el-icon><CopyDocument /></el-icon>
                复制
              </el-button>
              <el-dropdown @command="(cmd) => handleAction(cmd, template)">
                <el-button size="small">
                  <el-icon><MoreFilled /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="preview">预览</el-dropdown-item>
                    <el-dropdown-item command="export">导出 YAML</el-dropdown-item>
                    <el-dropdown-item command="delete" :disabled="template.is_system">
                      <span style="color: #f56c6c">删除</span>
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </el-button-group>
          </div>
        </el-card>

        <!-- 新建卡片 -->
        <el-card
          class="template-card create-card"
          shadow="hover"
          @click="createNewTemplate"
        >
          <div class="create-placeholder">
            <el-icon><Plus /></el-icon>
            <span>新建模板</span>
          </div>
        </el-card>
      </div>
    </el-main>

    <!-- 导入对话框 -->
    <el-dialog v-model="showImportDialog" title="导入模板" width="500px">
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :show-file-list="true"
        :limit="1"
        accept=".yaml,.yml"
        @change="handleFileChange"
      >
        <el-button type="primary">选择 YAML 文件</el-button>
        <template #tip>
          <div class="el-upload__tip">只支持 YAML 格式的模板文件</div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="showImportDialog = false">取消</el-button>
        <el-button type="primary" @click="importTemplate" :loading="isImporting">导入</el-button>
      </template>
    </el-dialog>

    <!-- 预览对话框 -->
    <el-dialog v-model="showPreviewDialog" title="模板预览" width="80vw">
      <div class="preview-dialog-content">
        <div v-loading="isLoadingPreview" class="preview-image-container">
          <img v-if="previewImageUrl" :src="previewImageUrl" alt="预览图" />
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft, HomeFilled, Plus, Upload, Edit, CopyDocument,
  Document, MoreFilled, User, Setting, SwitchButton, ArrowDown
} from '@element-plus/icons-vue'
import { overlayTemplateApi, type OverlayTemplate } from '@/api/overlayTemplate'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

// 移动端检测
const isMobile = computed(() => window.innerWidth <= 768)

// 状态
const isLoading = ref(false)
const templates = ref<OverlayTemplate[]>([])
const filterType = ref<'all' | 'system' | 'user'>('all')
const showImportDialog = ref(false)
const showPreviewDialog = ref(false)
const isImporting = ref(false)
const isLoadingPreview = ref(false)
const previewImageUrl = ref('')
const currentTemplate = ref<OverlayTemplate | null>(null)
const uploadRef = ref()
const importFile = ref<File | null>(null)

// 加载模板列表
const loadTemplates = async () => {
  isLoading.value = true
  try {
    const params: { include_system?: boolean; only_public?: boolean } = {
      include_system: true
    }
    if (filterType.value === 'system') {
      params.only_public = false
      // API 会自动处理
    } else if (filterType.value === 'user') {
      params.include_system = false
    }

    const response = await overlayTemplateApi.list(params)
    let items = response.items

    // 客户端过滤
    if (filterType.value === 'system') {
      items = items.filter(t => t.is_system)
    } else if (filterType.value === 'user') {
      items = items.filter(t => !t.is_system)
    }

    templates.value = items
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '加载模板列表失败')
  } finally {
    isLoading.value = false
  }
}

// 新建模板
const createNewTemplate = () => {
  router.push('/overlay-templates/new')
}

// 编辑模板
const editTemplate = (template: OverlayTemplate) => {
  if (template.is_system) {
    ElMessage.warning('系统模板不能直接编辑，请先复制')
    return
  }
  router.push(`/overlay-templates/${template.id}`)
}

// 复制模板
const duplicateTemplate = async (template: OverlayTemplate) => {
  try {
    await overlayTemplateApi.duplicate(template.id)
    ElMessage.success('模板复制成功')
    loadTemplates()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '复制失败')
  }
}

// 处理操作
const handleAction = async (command: string, template: OverlayTemplate) => {
  switch (command) {
    case 'preview':
      currentTemplate.value = template
      showPreviewDialog.value = true
      loadPreview()
      break
    case 'export':
      await exportTemplate(template)
      break
    case 'delete':
      await deleteTemplate(template)
      break
  }
}

// 加载预览
const loadPreview = async () => {
  if (!currentTemplate.value) return

  isLoadingPreview.value = true
  try {
    const blob = await overlayTemplateApi.preview(currentTemplate.value.id)
    previewImageUrl.value = URL.createObjectURL(blob)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '加载预览失败')
  } finally {
    isLoadingPreview.value = false
  }
}

// 导出模板
const exportTemplate = async (template: OverlayTemplate) => {
  try {
    const blob = await overlayTemplateApi.export(template.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${template.name}.yaml`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '导出失败')
  }
}

// 删除模板
const deleteTemplate = async (template: OverlayTemplate) => {
  try {
    await ElMessageBox.confirm(`确定要删除模板 "${template.name}" 吗？`, '确认删除', {
      type: 'warning'
    })
    await overlayTemplateApi.delete(template.id)
    ElMessage.success('删除成功')
    loadTemplates()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

// 处理文件选择
const handleFileChange = (file: any) => {
  importFile.value = file.raw
}

// 导入模板
const importTemplate = async () => {
  if (!importFile.value) {
    ElMessage.warning('请选择文件')
    return
  }

  isImporting.value = true
  try {
    await overlayTemplateApi.import(importFile.value)
    ElMessage.success('导入成功')
    showImportDialog.value = false
    importFile.value = null
    uploadRef.value?.clearFiles()
    loadTemplates()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '导入失败')
  } finally {
    isImporting.value = false
  }
}

// 导航
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

const handleBack = () => {
  router.back()
}

const goHome = () => {
  router.push('/')
}

// 初始化
onMounted(() => {
  loadTemplates()
})
</script>

<style scoped>
.overlay-templates-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.overlay-templates-container > .el-header {
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

.overlay-templates-container > .el-main {
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

.templates-main {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  background: #f5f7fa;
}

.filter-bar {
  margin-bottom: 20px;
}

.templates-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

.template-card {
  cursor: pointer;
  transition: transform 0.2s;
}

.template-card:hover {
  transform: translateY(-4px);
}

.template-card.system-card {
  border-color: #409eff;
}

.create-card {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 250px;
  border: 2px dashed #dcdfe6;
  background: transparent;
}

.create-card:hover {
  border-color: #409eff;
}

.create-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  color: #909399;
}

.create-placeholder .el-icon {
  font-size: 48px;
}

.template-preview {
  position: relative;
  width: 100%;
  height: 150px;
  background: #f5f7fa;
  border-radius: 4px;
  overflow: hidden;
}

.template-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.preview-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;
}

.preview-placeholder .el-icon {
  font-size: 36px;
  margin-bottom: 8px;
}

.system-badge,
.public-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  color: #fff;
}

.system-badge {
  background: #409eff;
}

.public-badge {
  background: #67c23a;
}

.template-info {
  padding: 12px 0;
}

.template-name {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 500;
}

.template-desc {
  margin: 0;
  font-size: 13px;
  color: #909399;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.template-actions {
  border-top: 1px solid #ebeef5;
  padding-top: 12px;
}

.preview-dialog-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.preview-controls {
  display: flex;
  justify-content: center;
}

.preview-image-container {
  display: flex;
  justify-content: center;
  background: #f5f7fa;
  border-radius: 8px;
  min-height: 300px;
}

.preview-image-container img {
  max-width: 100%;
  max-height: 70vh;
  border-radius: 4px;
}

/* 移动端响应式 */
@media (max-width: 768px) {
  .overlay-templates-container > .el-header {
    flex-wrap: wrap;
    padding: 8px 12px;
  }

  .header-left h1 {
    font-size: 16px;
  }

  .desktop-only {
    display: none !important;
  }

  .templates-grid {
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 12px;
  }

  .template-card {
    min-height: 200px;
  }

  .template-preview {
    height: 100px;
  }
}
</style>
