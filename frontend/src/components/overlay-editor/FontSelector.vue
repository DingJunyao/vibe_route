<template>
  <div class="font-selector">
    <el-select :modelValue="modelValue" @update:modelValue="handleChange" size="small" :loading="isLoading" :disabled="isUploading" style="width: 100%">
      <el-option-group v-if="systemFonts.length > 0" label="系统字体">
        <el-option
          v-for="font in systemFonts"
          :key="font.id"
          :label="font.name"
          :value="font.id"
          :style="{ fontFamily: getPreviewFont(font.id) }"
        />
      </el-option-group>
      <el-option-group v-if="adminFonts.length > 0" label="管理员字体">
        <el-option
          v-for="font in adminFonts"
          :key="font.id"
          :label="font.name"
          :value="font.id"
          :style="{ fontFamily: getPreviewFont(font.id) }"
        />
      </el-option-group>
      <el-option-group v-if="userFonts.length > 0" label="我的字体">
        <el-option
          v-for="font in userFonts"
          :key="font.id"
          :label="font.name"
          :value="font.id"
          :style="{ fontFamily: getPreviewFont(font.id) }"
        />
      </el-option-group>
      <template #dropdown>
        <el-button
          size="small"
          :icon="Upload"
          :loading="isUploading"
          @click="handleUpload"
          title="上传字体"
        >
          上传
        </el-button>
      </template>
    </el-select>
    <el-dialog v-model="uploadDialogVisible" title="上传字体" width="400px">
      <el-upload
        drag
        :auto-upload="false"
        :show-file-list="false"
        :on-change="handleFileChange"
        :before-upload="beforeUpload"
        accept=".ttf,.otf,.ttc,.woff2"
        :limit="1"
      >
        <el-button size="small">选择字体文件</el-button>
      </el-upload>
      <div v-if="uploadProgress > 0" class="upload-progress">
        <el-progress :percentage="uploadProgress" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { Upload } from '@element-plus/icons-vue'
import { overlayTemplateApi, type Font } from '@/api/overlayTemplate'
import { ElMessage } from 'element-plus'

interface Props {
  modelValue: string
}

interface Emits {
  (e: 'update:modelValue', value: string): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const fonts = ref<Font[]>([])
const isLoading = ref(false)
const loadedFonts = ref<Set<string>>(new Set())

const uploadDialogVisible = ref(false)
const isUploading = ref(false)
const uploadProgress = ref(0)

const systemFonts = computed(() => fonts.value.filter(f => f.type === 'system'))
const adminFonts = computed(() => fonts.value.filter(f => f.type === 'admin'))
const userFonts = computed(() => fonts.value.filter(f => f.type === 'user'))

// 动态加载字体到浏览器
const loadFont = async (font: Font): Promise<void> => {
  if (loadedFonts.value.has(font.id) || font.type === 'system') {
    return
  }

  try {
    const fontUrl = overlayTemplateApi.getFontFileUrl(font.id)
    const fontName = `user_font_${font.id}`

    // 创建 @font-face 规则
    // 不指定 format，让浏览器自动检测
    // 后端会自动转换 TTF 为 WOFF2，但如果转换失败会返回原始格式
    const style = document.createElement('style')
    style.textContent = `
      @font-face {
        font-family: '${fontName}';
        src: url('${fontUrl}');
        font-display: swap;
      }
    `
    document.head.appendChild(style)

    // 标记为已加载（即使字体可能加载失败，也要避免重复尝试）
    loadedFonts.value.add(font.id)

    console.log('Font loading:', font.name, 'from', fontUrl)
  } catch (error) {
    console.error('Failed to load font', font.name, error)
  }
}

// 获取预览字体族名称
const getPreviewFont = (fontId: string): string => {
  const font = fonts.value.find(f => f.id === fontId)
  if (!font) return 'sans-serif'

  if (font.type === 'system') {
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

  return `user_font_${fontId}`
}

const loadFonts = async () => {
  isLoading.value = true
  try {
    const response = await overlayTemplateApi.listFonts()
    fonts.value = response.items

    // 预加载前3个非系统字体
    const userFontsToLoad = response.items.filter(f => f.type !== 'system')
    for (const font of userFontsToLoad.slice(0, 3)) {
      await loadFont(font)
    }
  } catch (error) {
    console.error('Failed to load fonts:', error)
  } finally {
    isLoading.value = false
  }
}

const handleChange = (value: string) => {
  emit('update:modelValue', value)
}

// 上传相关
const handleUpload = () => {
  uploadDialogVisible.value = true
}

const beforeUpload = () => {
  return true
}

const handleFileChange = async (file: any) => {
  if (!file) return

  isUploading.value = true
  uploadProgress.value = 0

  try {
    const response = await overlayTemplateApi.uploadFont(file.raw, (progress) => {
      uploadProgress.value = progress
    })

    ElMessage.success('字体上传成功')
    uploadDialogVisible.value = false

    // 重新加载字体列表
    await loadFonts()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '上传失败')
  } finally {
    isUploading.value = false
    uploadProgress.value = 0
  }
}

// 监听选中字体变化，按需加载
watch(() => props.modelValue, async (newValue) => {
  if (newValue) {
    const font = fonts.value.find(f => f.id === newValue)
    if (font && font.type !== 'system' && !loadedFonts.value.has(newValue)) {
      await loadFont(font)
    }
  }
}, { immediate: true })

onMounted(() => {
  loadFonts()
})
</script>

<style scoped>
.font-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.font-selector :deep(.el-select) {
  width: 100%;
  min-width: 200px;
  flex: 1;
}

.upload-progress {
  margin-top: 16px;
}
</style>
