<template>
  <el-container class="home-container">
    <!-- 顶部导航栏 -->
    <el-header class="header">
      <div class="header-left">
        <h1 class="logo">Vibe Route</h1>
        <el-button @click="$router.push('/tracks')" :icon="List" class="desktop-only">轨迹列表</el-button>
      </div>
      <div class="header-right">
        <el-button
          v-if="fontsConfigured"
          type="success"
          :icon="Flag"
          @click="showRoadSignDialog"
          class="desktop-only"
        >
          道路标志
        </el-button>
        <el-button type="warning" :icon="VideoPlay" @click="showLiveRecordingDialog" class="desktop-only">
          记录实时轨迹
        </el-button>
        <el-button type="primary" :icon="Upload" @click="$router.push('/upload')" class="desktop-only">
          上传轨迹
        </el-button>
        <el-dropdown @command="handleCommand">
          <span class="user-info">
            <el-icon><User /></el-icon>
            <span class="username">{{ authStore.user?.username }}</span>
            <el-icon class="el-icon--right"><arrow-down /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="tracks" v-if="isMobile">
                <el-icon><List /></el-icon>
                轨迹列表
              </el-dropdown-item>
              <el-dropdown-item command="upload" v-if="isMobile">
                <el-icon><Upload /></el-icon>
                上传轨迹
              </el-dropdown-item>
              <el-dropdown-item command="roadSign" v-if="isMobile && fontsConfigured">
                <el-icon><Flag /></el-icon>
                道路标志
              </el-dropdown-item>
              <el-dropdown-item command="liveRecording" v-if="isMobile">
                <el-icon><VideoPlay /></el-icon>
                记录实时轨迹
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
    <el-main class="main">
      <!-- 统计卡片 -->
      <el-row :gutter="20" class="stats-row">
        <el-col :xs="12" :sm="6">
          <el-card shadow="hover" class="stat-card" @click="$router.push('/tracks')">
            <div class="stat-card-content">
              <div class="stat-icon" style="background: #409eff">
                <el-icon :size="24"><Location /></el-icon>
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ stats.total_tracks }}</div>
                <div class="stat-label">轨迹总数</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :xs="12" :sm="6">
          <el-card shadow="hover">
            <div class="stat-card-content">
              <div class="stat-icon" style="background: #67c23a">
                <el-icon :size="24"><Odometer /></el-icon>
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ formatDistance(stats.total_distance) }}</div>
                <div class="stat-label">总里程</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :xs="12" :sm="6">
          <el-card shadow="hover">
            <div class="stat-card-content">
              <div class="stat-icon" style="background: #e6a23c">
                <el-icon :size="24"><Clock /></el-icon>
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ formatDuration(stats.total_duration) }}</div>
                <div class="stat-label">总时长</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :xs="12" :sm="6">
          <el-card shadow="hover">
            <div class="stat-card-content">
              <div class="stat-icon" style="background: #f56c6c">
                <el-icon :size="24"><Top /></el-icon>
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ formatElevation(stats.total_elevation_gain) }}</div>
                <div class="stat-label">总爬升</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 地图 -->
      <el-card class="map-card" shadow="never">
        <template #header>
          <div class="map-header">
            <span v-if="!loadingTracks">所有轨迹</span>
            <span v-else class="loading-title">
              <el-icon class="is-loading"><Loading /></el-icon>
              正在加载所有轨迹……（{{ loadedTrackCount }}/{{ tracks.length }}）
            </span>
          </div>
        </template>
        <!-- 有数据时显示地图 -->
        <div v-if="tracksWithPoints.length > 0 || loadingTracks" class="map-container">
          <UniversalMap :tracks="tracksWithPoints" mode="home" @track-click="handleTrackClick" />
        </div>
        <!-- 无数据时显示空状态 -->
        <el-empty v-else description="暂无轨迹，请先上传">
          <el-button type="primary" @click="$router.push('/upload')">
            上传第一条轨迹
          </el-button>
        </el-empty>
      </el-card>
    </el-main>

    <!-- 道路标志对话框 -->
    <el-dialog v-model="roadSignDialogVisible" title="生成道路标志" :width="isMobile ? '95%' : '600px'" class="road-sign-dialog responsive-dialog">
      <el-form :model="roadSignForm" label-width="100px" class="road-sign-form">
        <!-- 道路类型 -->
        <el-form-item label="道路类型">
          <el-radio-group v-model="roadSignForm.sign_type">
            <el-radio value="way">普通道路</el-radio>
            <el-radio value="expwy">高速公路</el-radio>
          </el-radio-group>
        </el-form-item>

        <!-- 高速公路选项 -->
        <template v-if="roadSignForm.sign_type === 'expwy'">
          <el-form-item label="高速类型">
            <el-radio-group v-model="roadSignForm.is_provincial">
              <el-radio :value="false">国家高速</el-radio>
              <el-radio :value="true">省级高速</el-radio>
            </el-radio-group>
          </el-form-item>

          <!-- 道路编号 -->
          <el-form-item label="道路编号">
            <!-- 国家高速 -->
            <template v-if="!roadSignForm.is_provincial">
              <el-input
                v-model="roadSignForm.expwyCode"
                placeholder="如 5, 45, 4511"
                @input="onExpwyCodeInput"
              >
                <template #prepend>G</template>
              </el-input>
            </template>
            <!-- 省级高速 -->
            <template v-else>
              <el-input
                v-model="roadSignForm.expwyCode"
                placeholder="如 1, 11, A, A1, A12"
                @input="onExpwyCodeInput"
              >
                <template #prepend>
                  <div class="prepend-content">
                    <el-select v-model="roadSignForm.province" placeholder="省份">
                      <el-option v-for="prov in provinces" :key="prov.value" :label="prov.value" :value="prov.value" />
                    </el-select>
                    <span class="prefix-separator">S</span>
                  </div>
                </template>
              </el-input>
            </template>
          </el-form-item>

          <el-form-item label="带名称">
            <el-switch v-model="roadSignForm.has_name" />
          </el-form-item>

          <el-form-item label="道路名称" v-if="roadSignForm.has_name">
            <el-input v-model="roadSignForm.name" placeholder="如 连霍高速" />
          </el-form-item>
        </template>

        <!-- 普通道路编号 -->
        <el-form-item label="道路编号" v-if="roadSignForm.sign_type === 'way'">
          <el-input
            v-model="roadSignForm.code"
            placeholder="如 G318, S221, X001"
            @input="onRoadNumberInput"
          />
        </el-form-item>

        <!-- SVG 预览 -->
        <el-form-item label="预览" v-if="generatedSvg">
          <div class="svg-preview" v-html="generatedSvg"></div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="roadSignDialogVisible = false">取消</el-button>
        <el-button @click="generateRoadSign" :loading="generating">生成</el-button>
        <el-button type="primary" @click="downloadSvg" v-if="generatedSvg">下载</el-button>
      </template>
    </el-dialog>

    <!-- 实时记录对话框 -->
    <el-dialog v-model="liveRecordingDialogVisible" title="记录实时轨迹" :width="isMobile ? '95%' : '500px'" class="responsive-dialog">
      <el-form :model="liveRecordingForm" label-width="120px">
        <el-form-item label="记录名称">
          <el-input v-model="liveRecordingForm.name" placeholder="如：2024年1月骑行，不填则自动生成" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="liveRecordingForm.description" type="textarea" placeholder="可选，记录这次活动的描述" maxlength="1000" show-word-limit :rows="3" />
        </el-form-item>
        <el-form-item label="自动填充地理信息">
          <el-switch v-model="liveRecordingForm.fill_geocoding" />
          <div class="radio-hint">
            开启后，上传轨迹点时会自动获取省市区、道路名称等地理信息
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="liveRecordingDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="createLiveRecording" :loading="creatingRecording">创建</el-button>
      </template>
    </el-dialog>

    <!-- 上传 URL 对话框 -->
    <el-dialog v-model="uploadUrlDialogVisible" title="上传 URL 已生成" :width="isMobile ? '95%' : '500px'" class="responsive-dialog">
      <div class="upload-url-content">
        <p class="url-intro">使用以下 URL 上传轨迹，无需登录：</p>

        <!-- GPS Logger URL -->
        <div class="url-section">
          <div class="url-label">GPS Logger URL（推荐）：</div>
          <div class="url-box">
            <el-input :model-value="gpsLoggerUrl" readonly type="textarea" :rows="4" class="url-textarea" />
            <el-button @click="copyGpsLoggerUrl" :icon="DocumentCopy" type="primary" class="copy-button">
              {{ copyButtonText }}
            </el-button>
          </div>
        </div>

        <!-- 二维码 -->
        <div class="qrcode-container" v-if="uploadQrCode">
          <div class="qrcode" v-html="uploadQrCode"></div>
          <p class="qrcode-tip">扫描二维码，用 GPS Logger 等应用记录轨迹</p>
        </div>

        <el-alert type="info" :closable="false" show-icon class="url-alert">
          <ul class="url-tips">
            <li>此 URL 可以多次使用，直到你结束记录</li>
            <li>在"轨迹列表"页面的"实时记录"标签中可以管理记录</li>
            <li>结束记录后，token 将失效</li>
          </ul>
        </el-alert>
      </div>

      <template #footer>
        <el-button type="primary" @click="uploadUrlDialogVisible = false">知道了</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, onBeforeUnmount, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  User,
  ArrowDown,
  Setting,
  SwitchButton,
  Location,
  Odometer,
  Clock,
  Top,
  Upload,
  List,
  Loading,
  Flag,
  VideoPlay,
  DocumentCopy,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useConfigStore } from '@/stores/config'
import { trackApi, type Track, type TrackPoint, type UnifiedTrack } from '@/api/track'
import { roadSignApi } from '@/api/roadSign'
import { liveRecordingApi } from '@/api/liveRecording'
import QRCode from 'qrcode'
import UniversalMap from '@/components/map/UniversalMap.vue'

const router = useRouter()
const authStore = useAuthStore()
const configStore = useConfigStore()

// 响应式：判断是否为移动端
const screenWidth = ref(window.innerWidth)
const screenHeight = ref(window.innerHeight)
const isMobile = computed(() => screenWidth.value <= 1366)

// 检查字体是否已配置
const fontsConfigured = computed(() => configStore.areFontsConfigured())

// 标记组件是否已挂载，用于避免卸载后更新状态
let isMounted = true

// 监听窗口大小变化
function handleResize() {
  screenWidth.value = window.innerWidth
  screenHeight.value = window.innerHeight
}

const stats = ref({
  total_tracks: 0,
  total_distance: 0,
  total_duration: 0,
  total_elevation_gain: 0,
})

const tracks = ref<UnifiedTrack[]>([])
const tracksPoints = ref<Map<number, TrackPoint[]>>(new Map())
const loadingTracks = ref(false)
const loadedTrackCount = ref(0)

// 组合轨迹和点数据供地图组件使用
const tracksWithPoints = computed(() => {
  return tracks.value.map(track => ({
    id: track.id,
    name: track.name,
    start_time: track.start_time,
    end_time: track.end_time,
    distance: track.distance,
    duration: track.duration,
    points: tracksPoints.value.get(track.id) || [],
  }))
})

// 道路标志对话框
const roadSignDialogVisible = ref(false)
const generating = ref(false)
const generatedSvg = ref('')

// 省份列表
const provinces = [
  { value: '京', label: '北京 (京)' },
  { value: '津', label: '天津 (津)' },
  { value: '冀', label: '河北 (冀)' },
  { value: '晋', label: '山西 (晋)' },
  { value: '蒙', label: '内蒙古 (蒙)' },
  { value: '辽', label: '辽宁 (辽)' },
  { value: '吉', label: '吉林 (吉)' },
  { value: '黑', label: '黑龙江 (黑)' },
  { value: '沪', label: '上海 (沪)' },
  { value: '苏', label: '江苏 (苏)' },
  { value: '浙', label: '浙江 (浙)' },
  { value: '皖', label: '安徽 (皖)' },
  { value: '闽', label: '福建 (闽)' },
  { value: '赣', label: '江西 (赣)' },
  { value: '鲁', label: '山东 (鲁)' },
  { value: '豫', label: '河南 (豫)' },
  { value: '鄂', label: '湖北 (鄂)' },
  { value: '湘', label: '湖南 (湘)' },
  { value: '粤', label: '广东 (粤)' },
  { value: '桂', label: '广西 (桂)' },
  { value: '琼', label: '海南 (琼)' },
  { value: '渝', label: '重庆 (渝)' },
  { value: '川', label: '四川 (川)' },
  { value: '贵', label: '贵州 (贵)' },
  { value: '云', label: '云南 (云)' },
  { value: '藏', label: '西藏 (藏)' },
  { value: '陕', label: '陕西 (陕)' },
  { value: '甘', label: '甘肃 (甘)' },
  { value: '青', label: '青海 (青)' },
  { value: '宁', label: '宁夏 (宁)' },
  { value: '新', label: '新疆 (新)' },
]

// 道路标志表单
const roadSignForm = reactive({
  sign_type: 'way',
  code: '',
  expwyCode: '',  // 高速公路编号部分（不含前缀）
  is_provincial: false,
  has_name: false,
  province: '',
  name: '',
})

// 实时记录对话框
const liveRecordingDialogVisible = ref(false)
const uploadUrlDialogVisible = ref(false)
const creatingRecording = ref(false)
const liveRecordingForm = reactive({
  name: '',
  description: '',
  fill_geocoding: false,
})
const fullUploadUrl = ref('')
const gpsLoggerUrl = ref('')
const uploadQrCode = ref('')
const copyButtonText = ref('复制')

// 监听道路类型或高速类型变化，清空编号和预览
watch(() => [roadSignForm.sign_type, roadSignForm.is_provincial], () => {
  roadSignForm.code = ''
  roadSignForm.expwyCode = ''
  generatedSvg.value = ''
})

// 监听省份变化，更新完整编号并清空预览
watch(() => roadSignForm.province, () => {
  updateFullCode()
  generatedSvg.value = ''
})

// 监听 expwyCode 变化，更新完整编号并清空预览
watch(() => roadSignForm.expwyCode, () => {
  updateFullCode()
  generatedSvg.value = ''
})

// 监听普通道路编号变化，清空预览
watch(() => roadSignForm.code, () => {
  generatedSvg.value = ''
})

// 监听道路名称相关字段变化，清空预览
watch(() => [roadSignForm.has_name, roadSignForm.name], () => {
  generatedSvg.value = ''
})

// 普通道路编号输入处理（转大写）
function onRoadNumberInput(value: string) {
  const upperValue = value.toUpperCase()
  if (upperValue !== value) {
    roadSignForm.code = upperValue
  }
}

// 高速公路编号输入处理（转大写）
function onExpwyCodeInput(value: string) {
  const upperValue = value.toUpperCase()
  if (upperValue !== value) {
    roadSignForm.expwyCode = upperValue
  }
  // 同时更新完整的 code（用于校验和提交）
  updateFullCode()
}

// 更新完整的 code 值
function updateFullCode() {
  if (roadSignForm.sign_type === 'expwy') {
    const prefix = roadSignForm.is_provincial ? 'S' : 'G'
    roadSignForm.code = prefix + (roadSignForm.expwyCode || '')
  }
}

function showRoadSignDialog() {
  // 检查字体是否已配置
  if (!configStore.areFontsConfigured()) {
    ElMessageBox.alert(
      '道路标志功能需要管理员先配置 A、B、C 三种字体。请在后台管理的"字体管理"页面中上传并选择相应的字体文件。',
      '字体未配置',
      { type: 'warning' }
    )
    return
  }
  roadSignDialogVisible.value = true
}

// 道路编号校验规则
function validateRoadCode(code: string, signType: string, province?: string): { valid: boolean; message?: string } {
  const trimmedCode = code.trim().toUpperCase()

  if (!trimmedCode) {
    return { valid: false, message: '请输入道路编号' }
  }

  if (signType === 'way') {
    // 普通道路：字母 + 三位数字
    if (!/^[A-Z]\d{3}$/.test(trimmedCode)) {
      return {
        valid: false,
        message: '普通道路编号格式错误：应为字母 + 三位数字，如 G221、S221、X221'
      }
    }
  } else if (signType === 'expwy') {
    // 高速公路：国家高速或省级高速
    if (trimmedCode.startsWith('G')) {
      // 国家高速：G + 1-4位数字
      if (!/^G\d{1,4}$/.test(trimmedCode)) {
        return {
          valid: false,
          message: '国家高速编号格式错误：应为 G + 1-4位数字，如 G5、G45、G4511'
        }
      }
    } else if (trimmedCode.startsWith('S')) {
      // 省级高速：S + 纯数字(1-4位) 或 S + 字母 + 可选数字
      // 字母格式仅限四川（川）
      const letterFormatMatch = /^S[A-Z]\d{0,3}$/.exec(trimmedCode)
      if (letterFormatMatch) {
        // 字母格式，检查是否是四川
        if (province !== '川') {
          return {
            valid: false,
            message: '字母格式的省级高速编号仅限四川省使用，请选择四川或使用纯数字编号（如 S1、S11）'
          }
        }
      } else if (!/^S\d{1,4}$/.test(trimmedCode)) {
        return {
          valid: false,
          message: '省级高速编号格式错误：应为 S + 1-4位数字（如 S1、S11、S1111），或仅限四川使用 S + 字母 + 可选数字（如 SA、SC、SA1）'
        }
      }
    } else {
      return {
        valid: false,
        message: '高速公路编号应以 G（国家高速）或 S（省级高速）开头'
      }
    }
  }

  return { valid: true }
}

async function generateRoadSign() {
  // 校验道路编号
  const codeValidation = validateRoadCode(roadSignForm.code, roadSignForm.sign_type, roadSignForm.province)
  if (!codeValidation.valid) {
    ElMessage.warning(codeValidation.message || '请输入道路编号')
    return
  }

  // 校验省份（省级高速必填）
  if (roadSignForm.sign_type === 'expwy' && roadSignForm.is_provincial && !roadSignForm.province) {
    ElMessage.warning('请选择省份')
    return
  }

  // 校验道路名称（启用名称选项时必填）
  if (roadSignForm.sign_type === 'expwy' && roadSignForm.has_name && !roadSignForm.name) {
    ElMessage.warning('请填写道路名称')
    return
  }

  generating.value = true
  try {
    const response = await roadSignApi.generate({
      sign_type: roadSignForm.sign_type,
      code: roadSignForm.code.trim(),
      province: roadSignForm.is_provincial ? roadSignForm.province : undefined,
      name: roadSignForm.has_name ? roadSignForm.name : undefined,
    })
    generatedSvg.value = response.svg
    ElMessage.success(response.cached ? '从缓存加载' : '生成成功')
  } finally {
    generating.value = false
  }
}

function downloadSvg() {
  if (!generatedSvg.value) return
  const blob = new Blob([generatedSvg.value], { type: 'image/svg+xml' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${roadSignForm.code || 'road-sign'}.svg`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  ElMessage.success('下载成功')
}

// 点击轨迹跳转到详情页
function handleTrackClick(trackId: number) {
  console.log('[Home] handleTrackClick 被调用, trackId:', trackId)
  router.push(`/tracks/${trackId}`)
}

function handleCommand(command: string) {
  if (command === 'logout') {
    ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }).then(() => {
      authStore.logout()
      ElMessage.success('已退出登录')
      router.push('/login')
    })
  } else if (command === 'admin') {
    router.push('/admin')
  } else if (command === 'tracks') {
    router.push('/tracks')
  } else if (command === 'upload') {
    router.push('/upload')
  } else if (command === 'roadSign') {
    showRoadSignDialog()
  } else if (command === 'liveRecording') {
    showLiveRecordingDialog()
  }
}

// 显示实时记录对话框
function showLiveRecordingDialog() {
  liveRecordingForm.name = ''
  liveRecordingForm.description = ''
  liveRecordingDialogVisible.value = true
}

// 创建实时记录
async function createLiveRecording() {
  // 生成记录名称（如果未填写则使用当前时间）
  let name = liveRecordingForm.name.trim()
  if (!name) {
    const now = new Date()
    name = `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日 ${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`
  }

  creatingRecording.value = true
  try {
    const recording = await liveRecordingApi.create({
      name,
      description: liveRecordingForm.description.trim() || undefined,
      fill_geocoding: liveRecordingForm.fill_geocoding,
    })

    // 生成完整的上传 URL
    fullUploadUrl.value = liveRecordingApi.getFullUploadUrl(recording.token)
    gpsLoggerUrl.value = liveRecordingApi.getGpsLoggerUrl(recording.token)

    // 生成二维码（使用 GPS Logger URL）
    uploadQrCode.value = await QRCode.toString(gpsLoggerUrl.value, {
      width: 200,
      margin: 2,
      type: 'svg',
    })

    // 切换到 URL 对话框
    liveRecordingDialogVisible.value = false
    uploadUrlDialogVisible.value = true

    ElMessage.success('记录创建成功')
  } finally {
    creatingRecording.value = false
  }
}

// 复制上传 URL
function copyUploadUrl() {
  navigator.clipboard.writeText(fullUploadUrl.value).then(() => {
    ElMessage.success('URL 已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败，请手动复制')
  })
}

function copyGpsLoggerUrl() {
  const url = gpsLoggerUrl.value

  // 检查剪贴板 API 是否可用
  if (!navigator.clipboard) {
    // 尝试使用传统的 execCommand 方法作为回退
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

  // 使用现代剪贴板 API
  navigator.clipboard.writeText(url).then(() => {
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

function formatDistance(meters: number): string {
  if (meters < 1000) {
    return `${meters.toFixed(1)} m`
  }
  return `${(meters / 1000).toFixed(2)} km`
}

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (hours > 0) {
    return `${hours}h ${minutes}m`
  }
  return `${minutes}m`
}

function formatElevation(meters: number): string {
  return `${meters.toFixed(0)} m`
}

// 采样轨迹点（减少数据量，提高渲染性能）
function samplePoints(points: TrackPoint[], maxPoints: number = 500): TrackPoint[] {
  if (points.length <= maxPoints) return points

  const sampled: TrackPoint[] = []
  const step = Math.ceil(points.length / maxPoints)

  for (let i = 0; i < points.length; i += step) {
    sampled.push(points[i])
  }

  // 确保最后一个点被包含
  if (sampled[sampled.length - 1] !== points[points.length - 1]) {
    sampled.push(points[points.length - 1])
  }

  return sampled
}

// 获取所有轨迹的点数据（限制并发数量，避免阻塞其他请求）
async function fetchAllTracksPoints() {
  if (tracks.value.length === 0) return

  loadingTracks.value = true
  loadedTrackCount.value = 0

  try {
    // 限制并发数量为 3，避免占满 HTTP 连接池
    const concurrency = 3
    let index = 0
    const total = tracks.value.length

    // 使用递归函数来处理并发，每个请求完成后立即更新地图
    async function fetchNext() {
      // 检查组件是否已卸载或所有轨迹都已处理
      if (!isMounted || index >= total) {
        return
      }

      // 获取当前批次
      const batchSize = Math.min(concurrency, total - index)
      const batch = tracks.value.slice(index, index + batchSize)
      index += batchSize

      // 并发请求当前批次的轨迹点
      const promises = batch.map(async (track) => {
        try {
          const response = await trackApi.getPoints(track.id, 'wgs84')
          const points = samplePoints(response.points)

          // 每个请求完成后立即更新地图
          if (isMounted) {
            tracksPoints.value.set(track.id, points)
            loadedTrackCount.value++
          }

          return { success: true }
        } catch (error) {
          console.error(`Failed to load points for track ${track.id}:`, error)
          if (isMounted) {
            loadedTrackCount.value++
          }
          return { success: false }
        }
      })

       // 等待当前批次完成
      await Promise.all(promises)

      // 继续处理下一批
      await fetchNext()
    }

    // 开始获取
    await fetchNext()
  } finally {
    // 只有在组件仍然挂载时才更新 loading 状态
    if (isMounted) {
      loadingTracks.value = false
    }
  }
}

onMounted(() => {
  // 异步获取统计数据，不阻塞页面渲染（已包含实时轨迹）
  trackApi.getStats()
    .then((data: typeof stats.value) => {
      if (isMounted) stats.value = data
    })
    .catch(() => {
      // 错误已在拦截器中处理
    })

  // 异步获取统一轨迹列表（包含普通轨迹和实时记录），不阻塞页面渲染
  trackApi.getUnifiedList({ page: 1, page_size: 100 })
    .then((response: { items: typeof tracks.value }) => {
      if (isMounted) {
        // 按开始时间排序（从旧到新）
        tracks.value = response.items.sort((a, b) => {
          const timeA = a.start_time ? new Date(a.start_time).getTime() : 0
          const timeB = b.start_time ? new Date(b.start_time).getTime() : 0
          return timeA - timeB
        })
        // 异步获取轨迹点数据
        fetchAllTracksPoints()
      }
    })
    .catch(() => {
      // 错误已在拦截器中处理
    })

  // 添加窗口大小监听
  window.addEventListener('resize', handleResize)
})

// 组件卸载时设置标志，避免更新已卸载组件的状态
onUnmounted(() => {
  isMounted = false
  // 移除窗口大小监听器
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.home-container {
  height: 100%;
  background: #f5f7fa;
  display: flex;
  flex-direction: column;
}

.header {
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  flex-shrink: 0;
  gap: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-left .logo {
  margin: 0;
  font-size: 24px;
  color: #409eff;
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

.mobile-only {
  display: none;
}

:deep(.mobile-only) {
  display: none !important;
}

/* 移动端响应式 */
@media (max-width: 1366px) {
  .header {
    flex-wrap: wrap;
    padding: 10px;
  }

  .header-left {
    flex: 1;
    min-width: 0;
  }

  .header-left .logo {
    font-size: 18px;
  }

  .desktop-only {
    display: none !important;
  }

  .user-info .username {
    display: inline;
  }

  .mobile-only {
    display: block !important;
  }
}

.main {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  height: calc(100vh - 60px); /* 减去导航栏高度 */
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.stats-row {
  margin-bottom: 20px;
  flex-shrink: 0; /* 防止统计卡片被压缩 */
}

.stat-card {
  cursor: pointer;
  transition: box-shadow 0.3s;
}

.stat-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.stat-card-content {
  display: flex;
  align-items: center;
  gap: 15px;
}

.stat-icon {
  width: 50px;
  height: 50px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #333;
}

.stat-label {
  font-size: 14px;
  color: #999;
  margin-top: 5px;
}

.map-card {
  flex: 1; /* 自动填充剩余空间 */
  min-height: 0; /* 允许 flex 子元素缩小 */
  display: flex;
  flex-direction: column;
}

.map-card :deep(.el-card__body) {
  flex: 1;
  padding: 0;
  overflow: hidden;
}

.map-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.map-container {
  width: 100%;
  height: 100%;
  position: relative;
}

.map-empty {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  color: #909399;
}

.loading-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #909399;
}

/* 移动端响应式 */
@media (max-width: 1366px) {
  .header {
    flex-wrap: wrap;
    padding: 10px;
  }

  .header-left {
    flex: 1;
    min-width: 0;
  }

  .header-left .logo {
    font-size: 18px;
  }

  .desktop-only {
    display: none;
  }

  .user-info .username {
    display: inline;
  }

  .main {
    padding: 10px;
    height: calc(100vh - 60px); /* 减去导航栏高度 */
  }

  .stats-row {
    margin-bottom: 10px;
  }

  .stats-row :deep(.el-col) {
    margin-bottom: 10px;
  }

  .stats-row :deep(.el-card) {
    height: 100%;
  }

  .stats-row :deep(.el-card__body) {
    min-height: 70px;
    max-height: 80px;
    display: flex;
    align-items: center;
    padding: 10px;
  }

  .stat-icon {
    width: 36px;
    height: 36px;
    flex-shrink: 0;
  }

  .stat-icon :deep(.el-icon) {
    font-size: 18px;
  }

  .stat-value {
    font-size: 16px;
    white-space: nowrap;
  }

  .stat-label {
    font-size: 11px;
    white-space: nowrap;
  }

  .map-card {
    flex: 1;
    min-height: 200px;
  }

  .map-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 5px;
  }

  .map-header span {
    font-size: 14px;
  }

  /* 对话框移动端样式 */
  .responsive-dialog {
    width: 95% !important;
  }

  .road-sign-dialog {
    width: 95% !important;
  }

  .road-sign-dialog .el-dialog__body {
    max-height: 60vh;
    overflow-y: auto;
  }

  .road-sign-form :deep(.el-form-item__label) {
    width: 80px !important;
    font-size: 14px;
  }

  .road-sign-form :deep(.el-radio),
  .road-sign-form :deep(.el-radio__label) {
    font-size: 14px;
  }
}

/* 道路标志 SVG 预览 */
.svg-preview {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 4px;
  min-height: 200px;
  max-height: 400px;
  overflow: auto;
}

.svg-preview :deep(svg) {
  width: auto !important;
  height: auto !important;
  max-width: 100% !important;
  max-height: 360px !important;
  object-fit: contain;
}

/* 复合输入框 prepend 内容样式 */
.prepend-content {
  display: inline-flex;
  align-items: center;
  vertical-align: middle;
  height: 100%;
}

.prepend-content .el-select {
  width: 80px;
}

.prepend-content .el-select .el-input__wrapper {
  padding-right: 0;
  background-color: transparent;
  box-shadow: none;
  height: 32px;
}

.prepend-content .el-select .el-input__wrapper .el-input__suffix {
  display: none;
}

.prefix-separator {
  padding: 0 0 0 32px;
}

/* 统一 prepend 的背景色和文字颜色 */
.el-input__prepend {
  background-color: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
  font-weight: 500;
}

/* 上传 URL 对话框样式 */
.upload-url-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.url-intro {
  margin: 0 0 15px 0;
  color: var(--el-text-color-primary);
  font-size: 14px;
}

.url-section {
  margin-bottom: 15px;
}

.url-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-regular);
  margin-bottom: 8px;
}

.url-box {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.copy-button {
  align-self: flex-start;
}

.url-textarea :deep(textarea) {
  font-family: 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.4;
}

.qrcode-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
}

.qrcode {
  display: flex;
}

.qrcode :deep(svg) {
  width: 200px;
  height: 200px;
}

.qrcode-tip {
  margin: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.url-alert {
  margin: 0;
}

.url-tips {
  margin: 0;
  padding-left: 20px;
}

.url-tips li {
  margin-bottom: 5px;
  font-size: 13px;
}
</style>