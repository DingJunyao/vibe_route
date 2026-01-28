<template>
  <el-container class="road-sign-container">
    <el-header>
      <div class="header-content">
        <el-button @click="$router.push('/home')" :icon="HomeFilled" />
        <h1>道路标志生成器</h1>
      </div>
    </el-header>

    <el-main>
      <el-row :gutter="30">
        <!-- 左侧：表单 -->
        <el-col :span="10">
          <el-card shadow="never">
            <template #header>
              <span>参数设置</span>
            </template>

            <el-form :model="form" label-width="80px" @submit.prevent="generate">
              <!-- 标志类型 -->
              <el-form-item label="标志类型">
                <el-radio-group v-model="form.sign_type">
                  <el-radio-button value="way">普通道路</el-radio-button>
                  <el-radio-button value="expwy">高速</el-radio-button>
                </el-radio-group>
              </el-form-item>

              <!-- 道路编号 -->
              <el-form-item label="道路编号" required>
                <el-input
                  v-model="form.code"
                  placeholder="如: G221, S221, G5, G45"
                  style="text-transform: uppercase"
                  @input="form.code = form.code.toUpperCase()"
                >
                  <template #prepend>
                    <span v-if="!form.code.startsWith('G') && !form.code.startsWith('S')">
                      {{ form.sign_type === 'way' ? 'G' : 'G' }}
                    </span>
                  </template>
                </el-input>
                <div class="form-tip">
                  <template v-if="form.sign_type === 'way'">
                    G=国道(红), S=省道(黄), X=县道(白), Y=乡道
                  </template>
                  <template v-else>
                    G=国家高速, S=省级高速
                  </template>
                </div>
              </el-form-item>

              <!-- 省份（仅高速） -->
              <el-form-item v-if="form.sign_type === 'expwy'" label="省份">
                <el-select
                  v-model="form.province"
                  placeholder="选择省份（省级高速必选）"
                  clearable
                  filterable
                  style="width: 100%"
                >
                  <el-option
                    v-for="p in provinces"
                    :key="p.value"
                    :label="p.label"
                    :value="p.value"
                  />
                </el-select>
                <div class="form-tip">选择省份后自动添加 S 前缀</div>
              </el-form-item>

              <!-- 道路名称（可选） -->
              <el-form-item label="道路名称">
                <el-input
                  v-model="form.name"
                  placeholder="如: 京沪高速"
                  clearable
                />
              </el-form-item>

              <!-- 操作按钮 -->
              <el-form-item>
                <el-button
                  type="primary"
                  @click="generate"
                  :loading="loading"
                  :disabled="!form.code"
                  style="width: 100%"
                >
                  生成标志
                </el-button>
              </el-form-item>

              <!-- 下载按钮 -->
              <el-form-item v-if="generatedSvg">
                <el-button
                  @click="downloadSvg"
                  :icon="Download"
                  style="width: 100%"
                >
                  下载 SVG
                </el-button>
              </el-form-item>
            </el-form>

            <!-- 示例 -->
            <el-divider content-position="left">快速示例</el-divider>
            <div class="examples">
              <el-tag
                v-for="example in examples"
                :key="example.code"
                @click="applyExample(example)"
                style="margin: 4px; cursor: pointer"
              >
                {{ example.label }}
              </el-tag>
            </div>
          </el-card>

          <!-- 历史记录 -->
          <el-card shadow="never" style="margin-top: 20px">
            <template #header>
              <div style="display: flex; justify-content: space-between; align-items: center">
                <span>最近生成</span>
                <el-button
                  type="danger"
                  size="small"
                  text
                  @click="clearCache"
                >
                  清除缓存
                </el-button>
              </div>
            </template>
            <el-scrollbar max-height="200">
              <div v-if="history.length === 0" class="empty-text">
                暂无历史记录
              </div>
              <div v-else class="history-list">
                <div
                  v-for="item in history"
                  :key="item.id"
                  class="history-item"
                  @click="applyHistory(item)"
                >
                  <el-tag size="small" :type="item.sign_type === 'way' ? 'warning' : 'success'">
                    {{ item.sign_type === 'way' ? '道路' : '高速' }}
                  </el-tag>
                  <span class="history-code">{{ item.code }}</span>
                  <span v-if="item.province" class="history-province">{{ item.province }}</span>
                  <span v-if="item.name" class="history-name">{{ item.name }}</span>
                </div>
              </div>
            </el-scrollbar>
          </el-card>
        </el-col>

        <!-- 右侧：预览 -->
        <el-col :span="14">
          <el-card shadow="never">
            <template #header>
              <span>预览</span>
            </template>
            <!-- 加载中显示骨架屏 -->
            <div v-if="loading" class="preview-container">
              <el-skeleton :rows="8" animated />
            </div>
            <!-- 加载完成后显示内容 -->
            <div v-else class="preview-container">
              <div v-if="!generatedSvg" class="preview-placeholder">
                <el-icon :size="80" color="#ddd">
                  <Picture />
                </el-icon>
                <p>输入参数后点击"生成标志"</p>
              </div>
              <div
                v-else
                v-html="generatedSvg"
                class="svg-preview"
              ></div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { HomeFilled, Download, Picture } from '@element-plus/icons-vue'
import { roadSignApi, type RoadSignResponse, type RoadSignListItem } from '@/api/roadSign'

// 表单数据
const form = reactive({
  sign_type: 'way' as 'way' | 'expwy',
  code: '',
  province: '',
  name: '',
})

// 状态
const loading = ref(false)
const generatedSvg = ref('')
const history = ref<RoadSignListItem[]>([])

// 标记组件是否已挂载，用于避免卸载后更新状态
const isMounted = ref(true)

// 省份列表
const provinces = [
  { value: '京', label: '北京' },
  { value: '津', label: '天津' },
  { value: '冀', label: '河北' },
  { value: '晋', label: '山西' },
  { value: '蒙', label: '内蒙古' },
  { value: '辽', label: '辽宁' },
  { value: '吉', label: '吉林' },
  { value: '黑', label: '黑龙江' },
  { value: '沪', label: '上海' },
  { value: '苏', label: '江苏' },
  { value: '浙', label: '浙江' },
  { value: '皖', label: '安徽' },
  { value: '闽', label: '福建' },
  { value: '赣', label: '江西' },
  { value: '鲁', label: '山东' },
  { value: '豫', label: '河南' },
  { value: '鄂', label: '湖北' },
  { value: '湘', label: '湖南' },
  { value: '粤', label: '广东' },
  { value: '桂', label: '广西' },
  { value: '琼', label: '海南' },
  { value: '渝', label: '重庆' },
  { value: '川', label: '四川' },
  { value: '贵', label: '贵州' },
  { value: '云', label: '云南' },
  { value: '藏', label: '西藏' },
  { value: '陕', label: '陕西' },
  { value: '甘', label: '甘肃' },
  { value: '青', label: '青海' },
  { value: '宁', label: '宁夏' },
  { value: '新', label: '新疆' },
  { value: '港', label: '香港' },
  { value: '澳', label: '澳门' },
  { value: '台', label: '台湾' },
]

// 示例
const examples = [
  { label: 'G221 国道', sign_type: 'way', code: 'G221' },
  { label: 'S221 省道', sign_type: 'way', code: 'S221' },
  { label: 'X221 县道', sign_type: 'way', code: 'X221' },
  { label: 'G5 京昆高速', sign_type: 'expwy', code: 'G5', name: '京昆高速' },
  { label: 'G45 大广高速', sign_type: 'expwy', code: 'G45', name: '大广高速' },
  { label: 'S21 豫S21', sign_type: 'expwy', code: 'S21', province: '豫' },
]

// 生成标志
async function generate() {
  if (!form.code) {
    ElMessage.warning('请输入道路编号')
    return
  }

  loading.value = true
  try {
    const result: RoadSignResponse = await roadSignApi.generate({
      sign_type: form.sign_type,
      code: form.code,
      province: form.province || undefined,
      name: form.name || undefined,
    })

    generatedSvg.value = result.svg

    if (result.cached) {
      ElMessage.success('已加载缓存')
    } else {
      ElMessage.success('生成成功')
    }

    // 刷新历史
    loadHistory()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '生成失败')
  } finally {
    loading.value = false
  }
}

// 应用示例
function applyExample(example: any) {
  form.sign_type = example.sign_type
  form.code = example.code
  form.province = example.province || ''
  form.name = example.name || ''
  generate()
}

// 应用历史记录
function applyHistory(item: RoadSignListItem) {
  form.sign_type = item.sign_type as 'way' | 'expwy'
  form.code = item.code
  form.province = item.province || ''
  form.name = item.name || ''
  generate()
}

// 加载历史记录
async function loadHistory() {
  try {
    const result = await roadSignApi.getList({ limit: 20 })
    if (isMounted.value) {
      history.value = result
    }
  } catch (error) {
    console.error('Failed to load history:', error)
  }
}

// 清除缓存
async function clearCache() {
  try {
    await ElMessageBox.confirm('确定要清除所有缓存吗？', '确认', {
      type: 'warning',
    })
    await roadSignApi.clearCache()
    ElMessage.success('缓存已清除')
    history.value = []
  } catch (error) {
    // 用户取消
  }
}

// 下载 SVG
function downloadSvg() {
  if (!generatedSvg.value) return

  const blob = new Blob([generatedSvg.value], { type: 'image/svg+xml' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${form.code || 'road-sign'}.svg`
  link.click()
  URL.revokeObjectURL(url)
  ElMessage.success('下载已开始')
}

onMounted(() => {
  loadHistory()
})

// 组件即将卸载时设置标志，避免更新已卸载组件的状态
onBeforeUnmount(() => {
  isMounted.value = false
})
</script>

<style scoped>
.road-sign-container {
  min-height: 100vh;
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
  gap: 16px;
}

.el-header h1 {
  font-size: 20px;
  margin: 0;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.examples {
  display: flex;
  flex-wrap: wrap;
}

.preview-container {
  min-height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-placeholder {
  text-align: center;
  color: #909399;
}

.preview-placeholder p {
  margin-top: 16px;
}

.svg-preview {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
}

.svg-preview :deep(svg) {
  max-width: 100%;
  max-height: 600px;
  width: auto;
  height: auto;
}

.empty-text {
  text-align: center;
  color: #909399;
  padding: 20px;
}

.history-list {
  font-size: 13px;
}

.history-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid #f5f7fa;
  cursor: pointer;
  transition: background 0.2s;
}

.history-item:hover {
  background: #f5f7fa;
}

.history-item:last-child {
  border-bottom: none;
}

.history-code {
  margin-left: 8px;
  font-weight: 500;
  color: #333;
}

.history-province {
  margin-left: 8px;
  color: #409eff;
}

.history-name {
  margin-left: 8px;
  color: #67c23a;
}
</style>
