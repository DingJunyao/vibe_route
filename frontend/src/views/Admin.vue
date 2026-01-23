<template>
  <div class="admin-container">
    <el-container>
      <el-header>
        <div class="header-content">
          <el-button @click="$router.back()" :icon="ArrowLeft">返回</el-button>
          <h1>后台管理</h1>
        </div>
      </el-header>

      <el-main class="main">
        <el-tabs v-model="activeTab" type="border-card">
          <!-- 系统配置 -->
          <el-tab-pane label="系统配置" name="config">
            <el-card v-loading="loadingConfig" shadow="never">
              <el-form :model="config" label-width="150px">
                <!-- 注册设置 -->
                <div class="form-section">
                  <div class="section-title">注册设置</div>
                  <el-form-item label="允许注册">
                    <el-switch v-model="config.registration_enabled" />
                    <span class="form-tip">是否开放用户注册</span>
                  </el-form-item>
                  <el-form-item label="需要邀请码">
                    <el-switch v-model="config.invite_code_required" />
                    <span class="form-tip">注册时是否需要邀请码</span>
                  </el-form-item>
                </div>

                <!-- 地图设置 -->
                <div class="form-section">
                  <div class="section-title">
                    地图设置
                    <span class="section-tip">选择单选按钮设为默认地图，使用开关启用/禁用地图，拖拽调整显示顺序</span>
                  </div>
                  <draggable
                    v-model="allMapLayers"
                    item-key="id"
                    handle=".drag-handle"
                    @end="onDragEnd"
                  >
                    <template #item="{ element: layer }">
                      <div
                        class="map-layer-item"
                        :class="{ 'is-default': layer.id === config.default_map_provider }"
                      >
                        <el-icon class="drag-handle">
                          <Rank />
                        </el-icon>
                        <el-radio
                          :model-value="config.default_map_provider"
                          :value="layer.id"
                          @change="config.default_map_provider = layer.id"
                          :disabled="!layer.enabled"
                        >
                          <span class="layer-name">{{ layer.name }}</span>
                          <span class="layer-id">({{ layer.id }})</span>
                        </el-radio>
                        <!-- 天地图 tk 输入框 -->
                        <el-input
                          v-if="layer.id === 'tianditu'"
                          v-model="layer.tk"
                          placeholder="请输入天地图 tk"
                          size="small"
                          style="width: 200px"
                          clearable
                          show-password
                        />
                        <!-- 高德地图 JS API Key 和安全密钥输入框 -->
                        <div v-if="layer.id === 'amap'" class="amap-inputs">
                          <el-input
                            v-model="layer.api_key"
                            placeholder="API Key（必填）"
                            size="small"
                            style="width: 180px"
                            clearable
                            show-password
                          />
                          <el-input
                            v-model="layer.security_js_code"
                            placeholder="安全密钥（可选）"
                            size="small"
                            style="width: 160px"
                            clearable
                            show-password
                          />
                        </div>
                        <el-switch
                          v-model="layer.enabled"
                          @change="onMapLayerToggle(layer)"
                          :disabled="layer.id === config.default_map_provider && layer.enabled"
                        />
                        <span class="layer-status">
                          <template v-if="layer.id === config.default_map_provider">
                            <el-tag size="small" type="success">默认</el-tag>
                          </template>
                          <template v-else-if="layer.enabled">
                            <el-tag size="small" type="info">已启用</el-tag>
                          </template>
                          <template v-else>
                            <el-tag size="small" type="warning">已禁用</el-tag>
                          </template>
                        </span>
                      </div>
                    </template>
                  </draggable>
                </div>

                <!-- 地理编码设置 -->
                <div class="form-section">
                  <div class="section-title">地理编码设置</div>
                  <el-form-item label="编码提供商">
                    <el-radio-group v-model="config.geocoding_provider" @change="onGeocodingProviderChange">
                      <el-radio value="nominatim">Nominatim</el-radio>
                      <el-radio value="gdf">GDF</el-radio>
                      <el-radio value="amap">高德地图</el-radio>
                      <el-radio value="baidu">百度地图</el-radio>
                    </el-radio-group>
                  </el-form-item>

                  <!-- Nominatim 配置 -->
                  <template v-if="config.geocoding_provider === 'nominatim'">
                    <el-form-item label="Nominatim URL">
                      <el-input v-model="config.geocoding_config.nominatim.url" placeholder="http://localhost:8080" />
                      <span class="form-hint">自建 Nominatim 服务的地址</span>
                    </el-form-item>
                  </template>

                  <!-- GDF 配置 -->
                  <template v-if="config.geocoding_provider === 'gdf'">
                    <el-form-item label="数据路径">
                      <el-input v-model="config.geocoding_config.gdf.data_path" placeholder="data/area_data" />
                    </el-form-item>
                  </template>

                  <!-- 高德地图配置 -->
                  <template v-if="config.geocoding_provider === 'amap'">
                    <el-form-item label="API Key">
                      <el-input v-model="config.geocoding_config.amap.api_key" placeholder="请输入高德地图 API Key" show-password />
                    </el-form-item>
                    <el-form-item label="并发频率">
                      <el-input-number v-model="config.geocoding_config.amap.freq" :min="1" :max="50" controls-position="right" />
                      <span class="form-hint">每秒请求数，建议值为 3</span>
                    </el-form-item>
                  </template>

                  <!-- 百度地图配置 -->
                  <template v-if="config.geocoding_provider === 'baidu'">
                    <el-form-item label="API Key">
                      <el-input v-model="config.geocoding_config.baidu.api_key" placeholder="请输入百度地图 API Key" show-password />
                    </el-form-item>
                    <el-form-item label="并发频率">
                      <el-input-number v-model="config.geocoding_config.baidu.freq" :min="1" :max="50" controls-position="right" />
                      <span class="form-hint">每秒请求数，建议值为 3</span>
                    </el-form-item>
                    <el-form-item label="获取英文信息">
                      <el-switch v-model="config.geocoding_config.baidu.get_en_result" />
                      <span class="form-hint">开启后会额外请求英文版本的地理信息</span>
                    </el-form-item>
                  </template>
                </div>

                <el-form-item>
                  <el-button type="primary" @click="saveConfig" :loading="saving">保存配置</el-button>
                  <el-button @click="loadConfig">重置</el-button>
                </el-form-item>
              </el-form>
            </el-card>
          </el-tab-pane>

          <!-- 用户管理 -->
          <el-tab-pane label="用户管理" name="users">
            <el-card v-loading="loadingUsers" shadow="never">
              <el-table :data="users" style="width: 100%">
                <el-table-column prop="id" label="ID" width="80" />
                <el-table-column prop="username" label="用户名" min-width="150" />
                <el-table-column prop="email" label="邮箱" min-width="200">
                  <template #default="{ row }">
                    {{ row.email || '-' }}
                  </template>
                </el-table-column>
                <el-table-column label="角色" width="120">
                  <template #default="{ row }">
                    <el-tag :type="row.is_admin ? 'danger' : 'primary'" size="small">
                      {{ row.is_admin ? '管理员' : '普通用户' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="状态" width="100">
                  <template #default="{ row }">
                    <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                      {{ row.is_active ? '正常' : '已禁用' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="created_at" label="创建时间" width="180">
                  <template #default="{ row }">
                    {{ formatDateTime(row.created_at) }}
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="200" fixed="right">
                  <template #default="{ row }">
                    <el-button
                      v-if="!row.is_admin"
                      type="primary"
                      size="small"
                      text
                      @click="toggleUserAdmin(row)"
                    >
                      设为管理员
                    </el-button>
                    <el-button
                      v-else
                      type="info"
                      size="small"
                      text
                      disabled
                    >
                      已是管理员
                    </el-button>
                    <el-button
                      v-if="row.is_active"
                      type="warning"
                      size="small"
                      text
                      @click="toggleUserActive(row)"
                    >
                      禁用
                    </el-button>
                    <el-button
                      v-else
                      type="success"
                      size="small"
                      text
                      @click="toggleUserActive(row)"
                    >
                      启用
                    </el-button>
                    <el-button
                      type="danger"
                      size="small"
                      text
                      @click="deleteUser(row)"
                    >
                      删除
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </el-tab-pane>

          <!-- 邀请码管理 -->
          <el-tab-pane label="邀请码" name="invite-codes">
            <el-card v-loading="loadingInviteCodes" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>邀请码列表</span>
                  <el-button type="primary" :icon="Plus" @click="showCreateInviteCodeDialog">
                    创建邀请码
                  </el-button>
                </div>
              </template>

              <el-table :data="inviteCodes" style="width: 100%">
                <el-table-column prop="id" label="ID" width="80" />
                <el-table-column prop="code" label="邀请码" min-width="150">
                  <template #default="{ row }">
                    <el-tag>{{ row.code }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="使用情况" width="150">
                  <template #default="{ row }">
                    {{ row.used_count }} / {{ row.max_uses }}
                  </template>
                </el-table-column>
                <el-table-column label="状态" width="100">
                  <template #default="{ row }">
                    <el-tag :type="getInviteCodeStatus(row).type" size="small">
                      {{ getInviteCodeStatus(row).text }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="expires_at" label="过期时间" width="180">
                  <template #default="{ row }">
                    {{ row.expires_at ? formatDateTime(row.expires_at) : '永久有效' }}
                  </template>
                </el-table-column>
                <el-table-column prop="created_at" label="创建时间" width="180">
                  <template #default="{ row }">
                    {{ formatDateTime(row.created_at) }}
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="100" fixed="right">
                  <template #default="{ row }">
                    <el-button
                      v-if="row.is_valid"
                      type="danger"
                      size="small"
                      text
                      @click="deleteInviteCode(row)"
                    >
                      删除
                    </el-button>
                    <el-button v-else type="info" size="small" text disabled>
                      已删除
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </el-tab-pane>
        </el-tabs>
      </el-main>
    </el-container>

    <!-- 创建邀请码对话框 -->
    <el-dialog v-model="createInviteCodeDialogVisible" title="创建邀请码" width="500px">
      <el-form :model="inviteCodeForm" label-width="120px">
        <el-form-item label="邀请码">
          <el-input v-model="inviteCodeForm.code" placeholder="留空自动生成" />
          <span class="form-tip">留空则自动生成随机邀请码</span>
        </el-form-item>
        <el-form-item label="最大使用次数">
          <el-input-number v-model="inviteCodeForm.max_uses" :min="1" :max="1000" />
        </el-form-item>
        <el-form-item label="有效期（天）">
          <el-input-number v-model="inviteCodeForm.expires_in_days" :min="1" :max="365" />
          <span class="form-tip">留空则永久有效</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createInviteCodeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creatingInviteCode" @click="createInviteCode">
          创建
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Plus, Rank } from '@element-plus/icons-vue'
import draggable from 'vuedraggable'
import { adminApi, type SystemConfig, type User, type InviteCode, type MapLayerConfig, type CRSType } from '@/api/admin'
import { useAuthStore } from '@/stores/auth'
import { useConfigStore } from '@/stores/config'

const router = useRouter()
const authStore = useAuthStore()
const configStore = useConfigStore()

// 检查管理员权限
if (!authStore.user?.is_admin) {
  ElMessage.error('需要管理员权限')
  router.push('/')
}

const activeTab = ref('config')
const loadingConfig = ref(false)
const loadingUsers = ref(false)
const loadingInviteCodes = ref(false)
const saving = ref(false)
const creatingInviteCode = ref(false)

// 系统配置
const config = reactive<SystemConfig>({
  registration_enabled: true,
  invite_code_required: false,
  default_map_provider: 'osm',
  geocoding_provider: 'nominatim',
  geocoding_config: {
    nominatim: { url: '', email: '' },
    gdf: { data_path: '' },
    amap: { api_key: '' },
    baidu: { api_key: '' },
  },
  map_layers: {},
})

// 所有地图层列表（按固定顺序）
const allMapLayers = ref<MapLayerConfig[]>([])

// 用户列表
const users = ref<User[]>([])

// 邀请码列表
const inviteCodes = ref<InviteCode[]>([])
const createInviteCodeDialogVisible = ref(false)
const inviteCodeForm = reactive({
  code: '',
  max_uses: 1,
  expires_in_days: undefined as number | undefined,
})

// 初始化 geocoding_config
function initGeocodingConfig() {
  if (!config.geocoding_config) {
    config.geocoding_config = {}
  }
  if (!config.geocoding_config.nominatim) {
    config.geocoding_config.nominatim = { url: 'http://localhost:8080' }
  }
  if (!config.geocoding_config.gdf) {
    config.geocoding_config.gdf = { data_path: '' }
  }
  if (!config.geocoding_config.amap) {
    config.geocoding_config.amap = { api_key: '', freq: 3 }
  }
  if (!config.geocoding_config.baidu) {
    config.geocoding_config.baidu = { api_key: '', freq: 3, get_en_result: false }
  }
}

// 加载系统配置
async function loadConfig() {
  loadingConfig.value = true
  try {
    const data = await adminApi.getConfig()
    Object.assign(config, data)
    initGeocodingConfig()
    // 初始化地图层列表（按固定顺序）
    initMapLayers()
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    loadingConfig.value = false
  }
}

// 初始化地图层列表
function initMapLayers() {
  if (!config.map_layers) {
    config.map_layers = {}
  }
  // 按 order 字段排序
  allMapLayers.value = Object.values(config.map_layers).sort((a: unknown, b: unknown) => (a as MapLayerConfig).order - (b as MapLayerConfig).order)
}

// 拖拽结束后的处理
function onDragEnd() {
  // 更新所有地图层的 order 值
  allMapLayers.value.forEach((layer: MapLayerConfig, index: number) => {
    layer.order = index
  })
}

// 地图层切换事件
function onMapLayerToggle(layer: MapLayerConfig) {
  if (!layer.enabled) {
    // 如果禁用的是当前默认地图，需要切换默认地图
    if (layer.id === config.default_map_provider) {
      // 找到第一个启用的地图作为默认
      const firstEnabled = allMapLayers.value.find((l: MapLayerConfig) => l.enabled && l.id !== layer.id)
      if (firstEnabled) {
        config.default_map_provider = firstEnabled.id
      } else {
        // 如果没有其他启用的地图，不允许禁用
        layer.enabled = true
        ElMessage.warning('至少需要保留一个启用的地图')
      }
    }
  }
}

// 保存系统配置
async function saveConfig() {
  saving.value = true
  try {
    // 确保 map_layers 被正确保存
    const updateData: Partial<SystemConfig> = {
      ...config,
      map_layers: config.map_layers,
    }
    const updatedConfig = await adminApi.updateConfig(updateData)
    // 更新 config store 中的配置
    configStore.adminConfig = updatedConfig
    ElMessage.success('配置保存成功')
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    saving.value = false
  }
}

// 地理编码提供商切换时初始化配置
function onGeocodingProviderChange() {
  initGeocodingConfig()
}

// 加载用户列表
async function loadUsers() {
  loadingUsers.value = true
  try {
    users.value = await adminApi.getUsers({ limit: 100 })
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    loadingUsers.value = false
  }
}

// 切换用户管理员状态
async function toggleUserAdmin(user: User) {
  try {
    await adminApi.updateUser(user.id, { is_admin: !user.is_admin })
    ElMessage.success('操作成功')
    await loadUsers()
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

// 切换用户启用状态
async function toggleUserActive(user: User) {
  const action = user.is_active ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(`确定要${action}用户 "${user.username}" 吗？`, '确认操作', {
      type: 'warning',
    })
    await adminApi.updateUser(user.id, { is_active: !user.is_active })
    ElMessage.success('操作成功')
    await loadUsers()
  } catch (error) {
    // 用户取消或错误已在拦截器中处理
  }
}

// 删除用户
async function deleteUser(user: User) {
  try {
    await ElMessageBox.confirm(`确定要删除用户 "${user.username}" 吗？此操作不可撤销。`, '确认删除', {
      type: 'warning',
    })
    await adminApi.deleteUser(user.id)
    ElMessage.success('删除成功')
    await loadUsers()
  } catch (error) {
    // 用户取消或错误已在拦截器中处理
  }
}

// 加载邀请码列表
async function loadInviteCodes() {
  loadingInviteCodes.value = true
  try {
    inviteCodes.value = await adminApi.getInviteCodes({ limit: 100 })
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    loadingInviteCodes.value = false
  }
}

// 显示创建邀请码对话框
function showCreateInviteCodeDialog() {
  inviteCodeForm.code = ''
  inviteCodeForm.max_uses = 1
  inviteCodeForm.expires_in_days = undefined
  createInviteCodeDialogVisible.value = true
}

// 创建邀请码
async function createInviteCode() {
  creatingInviteCode.value = true
  try {
    await adminApi.createInviteCode({
      code: inviteCodeForm.code || undefined,
      max_uses: inviteCodeForm.max_uses,
      expires_in_days: inviteCodeForm.expires_in_days,
    })
    ElMessage.success('邀请码创建成功')
    createInviteCodeDialogVisible.value = false
    await loadInviteCodes()
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    creatingInviteCode.value = false
  }
}

// 删除邀请码
async function deleteInviteCode(inviteCode: InviteCode) {
  try {
    await ElMessageBox.confirm(`确定要删除邀请码 "${inviteCode.code}" 吗？`, '确认删除', {
      type: 'warning',
    })
    await adminApi.deleteInviteCode(inviteCode.id)
    ElMessage.success('删除成功')
    await loadInviteCodes()
  } catch (error) {
    // 用户取消或错误已在拦截器中处理
  }
}

// 获取邀请码状态
function getInviteCodeStatus(inviteCode: InviteCode) {
  if (!inviteCode.is_valid) {
    return { type: 'info', text: '已删除' }
  }
  if (inviteCode.expires_at && new Date(inviteCode.expires_at) < new Date()) {
    return { type: 'danger', text: '已过期' }
  }
  if (inviteCode.used_count >= inviteCode.max_uses) {
    return { type: 'warning', text: '已用完' }
  }
  return { type: 'success', text: '可用' }
}

// 格式化日期时间
function formatDateTime(dateStr: string): string {
  const date = new Date(dateStr)
  const year = date.getFullYear()
  const month = (date.getMonth() + 1).toString().padStart(2, '0')
  const day = date.getDate().toString().padStart(2, '0')
  const hours = date.getHours().toString().padStart(2, '0')
  const minutes = date.getMinutes().toString().padStart(2, '0')
  const seconds = date.getSeconds().toString().padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

onMounted(async () => {
  await loadConfig()
  await loadUsers()
  await loadInviteCodes()
})
</script>

<style scoped>
.admin-container {
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
  gap: 20px;
  width: 100%;
}

.header-content h1 {
  font-size: 20px;
  margin: 0;
  flex: 1;
}

.main {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}

.form-section {
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 1px solid #ebeef5;
}

.form-section:last-child {
  border-bottom: none;
}

.section-title {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 20px;
  padding-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.section-tip {
  font-size: 12px;
  color: #909399;
  font-weight: normal;
}

.form-tip {
  margin-left: 10px;
  font-size: 12px;
  color: #909399;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.map-layers-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.map-layer-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 4px;
  transition: background-color 0.2s;
  cursor: grab;
}

.map-layer-item:active {
  cursor: grabbing;
}

.map-layer-item:hover {
  background: #ecf5ff;
}

.map-layer-item.is-default {
  background: #f0f9ff;
  border: 1px solid #b3d8ff;
}

.map-layer-item.drag-over {
  border: 2px dashed #409eff;
  background: #ecf5ff;
}

.drag-handle {
  cursor: grab;
  color: #909399;
  font-size: 18px;
  flex-shrink: 0;
}

.drag-handle:active {
  cursor: grabbing;
}

/* vuedraggable 拖拽时的样式 */
.map-layers-list :deep(.sortable-ghost) {
  opacity: 0.5;
  background: #ecf5ff;
}

.map-layers-list :deep(.sortable-drag) {
  opacity: 0.8;
}

.map-layer-item :deep(.el-radio) {
  margin: 0;
  flex: 1;
}

.map-layer-item :deep(.el-radio__label) {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.layer-name {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.layer-id {
  font-size: 12px;
  color: #909399;
}

.layer-status {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}

.map-layer-item :deep(.el-input) {
  margin-left: 8px;
}

.map-layer-item :deep(.el-input__wrapper) {
  width: 200px;
}

/* 高德地图输入框组 */
.amap-inputs {
  display: flex;
  gap: 6px;
  margin-left: 8px;
}

/* 移动端响应式 */
@media (max-width: 768px) {
  .main {
    padding: 10px;
  }

  .header-content h1 {
    font-size: 16px;
  }

  :deep(.el-form-item__label) {
    width: 120px !important;
  }
}
</style>
