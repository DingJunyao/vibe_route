<template>
  <el-container class="settings-container">
    <el-header>
      <div class="header-left">
        <el-button @click="$router.push('/')" :icon="ArrowLeft" class="nav-btn" />
        <el-button @click="$router.push('/home')" :icon="HomeFilled" class="nav-btn home-nav-btn" />
        <h1>设置</h1>
      </div>
      <div class="header-right">
        <el-dropdown @command="handleCommand">
          <span class="user-info">
            <el-icon><User /></el-icon>
            <span class="username">{{ authStore.user?.username }}</span>
            <el-icon class="el-icon--right"><arrow-down /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="recordings">
                <el-icon><Film /></el-icon>
                录屏任务
              </el-dropdown-item>
              <el-dropdown-item command="admin" v-if="authStore.user?.is_admin">
                <el-icon><Setting /></el-icon>
                后台管理
              </el-dropdown-item>
              <el-dropdown-item class="dropdown-divider" :disabled="true" />
              <el-dropdown-item command="logout">
                <el-icon><SwitchButton /></el-icon>
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>

    <el-main class="main">
      <el-tabs v-model="activeTab" type="border-card" class="settings-tabs">
        <!-- 用户信息选项卡 -->
        <el-tab-pane label="用户信息" name="profile">
          <el-card class="profile-card" shadow="never">
            <template #header>
              <span>账户信息</span>
            </template>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="用户名">
                <div class="profile-value">
                  <span>{{ authStore.user?.username }}</span>
                  <el-button
                    type="primary"
                    size="small"
                    text
                    :icon="Edit"
                    @click="openEditUsernameDialog"
                  >
                    修改用户名
                  </el-button>
                </div>
              </el-descriptions-item>
              <el-descriptions-item label="邮箱">
                {{ authStore.user?.email }}
              </el-descriptions-item>
              <el-descriptions-item label="角色">
                <el-tag v-if="authStore.user?.is_admin" type="danger">管理员</el-tag>
                <el-tag v-else type="info">普通用户</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="创建时间">
                {{ formatDate(authStore.user?.created_at) }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>

          <el-card class="password-card" shadow="never">
            <template #header>
              <span>修改密码</span>
            </template>
            <el-form label-width="90px" class="password-form" @submit.prevent>
              <el-form-item label="当前密码">
                <el-input v-model="oldPassword" type="password" show-password autocomplete="current-password" />
              </el-form-item>
              <el-form-item label="新密码">
                <el-input v-model="newPassword" type="password" show-password autocomplete="new-password" />
              </el-form-item>
              <el-form-item label="确认密码">
                <el-input v-model="confirmPassword" type="password" show-password autocomplete="new-password" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="changingPassword" @click="submitPasswordChange">
                  修改密码
                </el-button>
              </el-form-item>
            </el-form>
          </el-card>
        </el-tab-pane>

        <!-- 通知设置选项卡 -->
        <el-tab-pane label="通知设置" name="notify">
          <el-card class="notify-card" shadow="never">
            <template #header>
              <span>录屏任务邮件通知</span>
            </template>
            <p class="settings-hint">
              录屏任务完成或失败时，向您的账户邮箱（{{ authStore.user?.email || '未设置' }}）发送通知邮件。
              需管理员开启邮件通知后方可送达。
            </p>
            <el-skeleton :rows="2" animated v-if="notifyLoading" />
            <template v-else>
              <div class="notify-row">
                <div class="notify-info">
                  <div class="notify-label">录制完成通知</div>
                  <div class="notify-desc">录屏任务完成后发送邮件</div>
                </div>
                <el-switch
                  v-model="notifyCompleted"
                  :loading="notifySaving"
                  @change="saveNotifySettings"
                />
              </div>
              <div class="notify-row">
                <div class="notify-info">
                  <div class="notify-label">录制失败通知</div>
                  <div class="notify-desc">录屏任务失败或中断时发送邮件</div>
                </div>
                <el-switch
                  v-model="notifyFailed"
                  :loading="notifySaving"
                  @change="saveNotifySettings"
                />
              </div>
            </template>
          </el-card>
        </el-tab-pane>

        <!-- 地图设置选项卡 -->
        <el-tab-pane label="地图设置" name="map">
          <el-card class="map-settings-card" shadow="never">
            <template #header>
              <div class="card-header">
                <span>地图配置</span>
                <span class="card-header-subtitle">自定义您的地图 API Key</span>
              </div>
            </template>

            <div class="map-settings-content">
              <p class="settings-hint">
                在这里配置您自己的地图 API Key，配置将覆盖系统默认设置。
                这些配置仅用于您自己的轨迹和分享页面。
              </p>

              <!-- 地图层列表 -->
              <div class="map-layers-section">
                <div class="section-title">地图层配置</div>
                <p class="section-hint">
                  选择单选按钮设为默认地图，使用开关启用/禁用地图，
                  <span class="desktop-only">拖拽</span>
                  <span class="mobile-only">点击左边的向上</span>按钮调整顺序。
                </p>

                <div class="map-layers-list">
                  <div
                    v-for="layer in sortedLayers"
                    :key="layer.id"
                    class="map-layer-item"
                    :class="{ 'is-default': isDefaultLayer(layer.id) }"
                  >
                    <!-- 第一行：拖拽手柄、名称、开关、状态 -->
                    <div class="map-layer-main">
                      <!-- 移动端排序按钮 -->
                      <div class="mobile-sort-buttons">
                        <el-button
                          :icon="ArrowUp"
                          :disabled="layer.order === 0"
                          @click="moveLayer(layer, -1)"
                          circle
                          size="small"
                        />
                      </div>

                      <!-- 拖拽手柄（桌面端） -->
                      <div class="drag-handle desktop-only">
                        <el-icon :icon="Rank" />
                      </div>

                      <!-- 地图名称 -->
                      <div class="layer-name">
                        {{ layer.name }}
                      </div>

                      <!-- 默认地图单选 -->
                      <el-radio
                        :model-value="userConfig.map_provider"
                        :value="layer.id"
                        @change="setDefaultLayer(layer.id)"
                        :disabled="!layer.enabled"
                      />

                      <!-- 启用/禁用开关 -->
                      <el-switch
                        v-model="layer.enabled"
                        @change="updateLayerEnabled(layer)"
                        :disabled="isDefaultLayer(layer.id) && layer.enabled"
                      />

                      <!-- 状态标签 -->
                      <el-tag v-if="isDefaultLayer(layer.id)" type="success" size="small">默认</el-tag>
                    </div>

                    <!-- 第二行：API Key 配置 -->
                    <div class="map-layer-config">
                      <!-- 天地图 tk -->
                      <div v-if="layer.id === 'tianditu'" class="config-row">
                        <span class="config-label">Token (tk):</span>
                        <el-input
                          v-model="layer.tk"
                          placeholder="请输入天地图 Token"
                          clearable
                          class="config-input"
                          @input="onConfigChange"
                        />
                      </div>

                      <!-- 高德地图 -->
                      <div v-if="layer.id === 'amap'" class="config-row">
                        <span class="config-label">API Key:</span>
                        <el-input
                          v-model="layer.api_key"
                          placeholder="请输入高德地图 API Key"
                          clearable
                          class="config-input"
                          @input="onConfigChange"
                        />
                      </div>
                      <div v-if="layer.id === 'amap'" class="config-row">
                        <span class="config-label">安全密钥:</span>
                        <el-input
                          v-model="layer.security_js_code"
                          placeholder="请输入安全密钥"
                          clearable
                          class="config-input"
                          @input="onConfigChange"
                        />
                      </div>

                      <!-- 腾讯地图 -->
                      <div v-if="layer.id === 'tencent'" class="config-row">
                        <span class="config-label">API Key:</span>
                        <el-input
                          v-model="layer.api_key"
                          placeholder="请输入腾讯地图 API Key"
                          clearable
                          class="config-input"
                          @input="onConfigChange"
                        />
                      </div>

                      <!-- 百度地图 -->
                      <div v-if="layer.id === 'baidu'" class="config-row">
                        <span class="config-label">API Key (AK):</span>
                        <el-input
                          v-model="layer.ak"
                          placeholder="请输入百度地图 AK"
                          clearable
                          class="config-input"
                          @input="onConfigChange"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 操作按钮 -->
            <div class="settings-actions">
              <el-button type="primary" :loading="saving" @click="saveConfig">
                保存配置
              </el-button>
              <el-button @click="resetConfig" :disabled="!hasCustomConfig">
                重置为系统默认
              </el-button>
            </div>
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </el-main>

    <!-- 修改用户名对话框 -->
    <el-dialog
      v-model="editUsernameDialogVisible"
      title="修改用户名"
      :width="isMobile ? '95%' : '420px'"
      :close-on-click-modal="false"
    >
      <el-form label-width="80px" @submit.prevent>
        <el-form-item label="用户名">
          <el-input
            v-model="editUsername"
            maxlength="50"
            show-word-limit
            placeholder="3-50 个字符"
            @keyup.enter="submitUsernameChange"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editUsernameDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingUsername" @click="submitUsernameChange">
          保存
        </el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, isRef } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowUp,
  ArrowLeft,
  ArrowDown,
  HomeFilled,
  User,
  Setting,
  SwitchButton,
  Film,
  Edit,
  Rank,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useUserConfigStore } from '@/stores/userConfig'
import { useConfigStore } from '@/stores/config'
import type { MapLayerConfig } from '@/api/admin'
import type { UserConfigUpdate } from '@/api/userConfig'

const router = useRouter()
const authStore = useAuthStore()
const userConfigStore = useUserConfigStore()
const configStore = useConfigStore()

// 当前选项卡
const activeTab = ref('profile')

// 移动端判定（项目断点：1366px）
const screenWidth = ref(window.innerWidth)
const isMobile = computed(() => screenWidth.value <= 1366)
function handleResize() {
  screenWidth.value = window.innerWidth
}

// 修改用户名
const editUsernameDialogVisible = ref(false)
const editUsername = ref('')
const savingUsername = ref(false)

// 修改密码
const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const changingPassword = ref(false)

// 邮件通知开关
const notifyCompleted = ref(false)
const notifyFailed = ref(false)
const notifyLoading = ref(false)
const notifySaving = ref(false)

// 用户配置
const userConfig = ref<{
  map_provider: string | null
  map_layers: Record<string, MapLayerConfig> | null
}>({
  map_provider: null,
  map_layers: null,
})

// 是否正在保存
const saving = ref(false)

// 是否有自定义配置
const hasCustomConfig = computed(() => {
  return !!userConfig.value.map_provider || !!userConfig.value.map_layers
})

// 排序后的地图层列表
const sortedLayers = computed(() => {
  if (!userConfig.value.map_layers) return []
  return Object.values(userConfig.value.map_layers)
    .filter(layer => layer.id !== 'osm')  // 不显示 OSM
    .sort((a, b) => a.order - b.order)
})

// 检查是否为默认地图
function isDefaultLayer(id: string): boolean {
  return userConfig.value.map_provider === id
}

// 设置默认地图
function setDefaultLayer(id: string) {
  userConfig.value.map_provider = id
  onConfigChange()
}

// 更新地图层启用状态
function updateLayerEnabled(layer: MapLayerConfig) {
  onConfigChange()
}

// 移动地图层顺序（移动端）
function moveLayer(layer: MapLayerConfig, direction: number) {
  if (!userConfig.value.map_layers) return

  const layers = sortedLayers.value
  const currentIndex = layers.findIndex(l => l.id === layer.id)
  const newIndex = currentIndex + direction

  if (newIndex < 0 || newIndex >= layers.length) return

  // 交换 order
  const currentOrder = layer.order
  const targetOrder = layers[newIndex].order

  layer.order = targetOrder
  layers[newIndex].order = currentOrder

  onConfigChange()
}

// 配置变更标记
let configChanged = false

function onConfigChange() {
  configChanged = true
}

// 保存配置
async function saveConfig() {
  saving.value = true
  try {
    const updateData: UserConfigUpdate = {
      map_provider: userConfig.value.map_provider,
      map_layers: userConfig.value.map_layers || undefined,
    }

    await userConfigStore.updateConfig(updateData)
    await configStore.refreshConfig()

    configChanged = false
    ElMessage.success('配置已保存')
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    saving.value = false
  }
}

// 重置配置
async function resetConfig() {
  try {
    await ElMessageBox.confirm(
      '确定要重置为系统默认配置吗？您的自定义配置将被清除。',
      '确认重置',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch {
    return // 用户取消
  }

  await userConfigStore.resetConfig()
  await loadUserConfig()
  await configStore.refreshConfig()

  configChanged = false
  ElMessage.success('配置已重置')
}

// 加载用户配置
async function loadUserConfig() {
  await userConfigStore.fetchConfig()

  // 同步邮件通知开关
  notifyCompleted.value = userConfigStore.config?.notify_recording_completed ?? false
  notifyFailed.value = userConfigStore.config?.notify_recording_failed ?? false

  // 合并系统配置和用户配置
  const systemLayers = configStore.mapLayers || {}
  const userLayers = userConfigStore.config?.map_layers || {}

  // 创建合并后的地图层配置
  const mergedLayers: Record<string, MapLayerConfig> = {}

  // 先添加所有系统地图层
  for (const [id, layer] of Object.entries(systemLayers)) {
    mergedLayers[id] = { ...layer }
  }

  // 用户配置覆盖系统配置
  if (userConfigStore.config?.map_layers) {
    for (const [id, layer] of Object.entries(userLayers)) {
      if (layer && mergedLayers[id]) {
        mergedLayers[id] = { ...mergedLayers[id]!, ...layer }
      }
    }
  }

  userConfig.value = {
    map_provider: userConfigStore.config?.map_provider || null,
    map_layers: mergedLayers,
  }

  configChanged = false
}

// 保存邮件通知开关
async function saveNotifySettings() {
  notifySaving.value = true
  try {
    await userConfigStore.updateConfig({
      notify_recording_completed: notifyCompleted.value,
      notify_recording_failed: notifyFailed.value,
    })
    ElMessage.success('通知设置已保存')
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    notifySaving.value = false
  }
}

// 修改用户名
function openEditUsernameDialog() {
  editUsername.value = authStore.user?.username || ''
  editUsernameDialogVisible.value = true
}

async function submitUsernameChange() {
  const username = editUsername.value.trim()
  if (username.length < 3 || username.length > 50) {
    ElMessage.warning('用户名长度需在 3-50 个字符之间')
    return
  }
  if (username === authStore.user?.username) {
    editUsernameDialogVisible.value = false
    return
  }

  savingUsername.value = true
  try {
    await authStore.updateProfile({ username })
    editUsernameDialogVisible.value = false
    ElMessage.success('用户名修改成功')
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    savingUsername.value = false
  }
}

async function submitPasswordChange() {
  if (!oldPassword.value || !newPassword.value || !confirmPassword.value) {
    ElMessage.warning('请填写完整的密码信息')
    return
  }
  if (newPassword.value.length < 6) {
    ElMessage.warning('新密码至少需要 6 位')
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }

  changingPassword.value = true
  try {
    await authStore.changePassword(oldPassword.value, newPassword.value)
    oldPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
    ElMessage.success('密码修改成功')
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    changingPassword.value = false
  }
}

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 头部下拉菜单
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
  } else if (command === 'recordings') {
    router.push('/recordings')
  }
}

// 组件挂载时加载数据
onMounted(async () => {
  window.addEventListener('resize', handleResize)

  // 先确保系统配置已加载
  await configStore.fetchConfig()
  // 然后加载用户配置
  notifyLoading.value = true
  try {
    await loadUserConfig()
  } finally {
    notifyLoading.value = false
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

// 路由离开前检查未保存的更改
defineExpose({
  hasUnsavedChanges: () => configChanged,
})
</script>

<style scoped>
.settings-container {
  height: 100vh;
  background: #f5f7fa;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.settings-container > .el-header {
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
  font-weight: 500;
  white-space: nowrap;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 下拉菜单分割线 */
.dropdown-divider {
  margin: 4px 0;
  height: 1px;
  padding: 0;
  overflow: hidden;
  line-height: 0;
  background-color: var(--el-border-color-lighter);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  color: var(--el-text-color-primary);
  outline: none;
}

.user-info .username {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.main {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 0;
}

.settings-tabs {
  flex: 1;
  min-height: 0;
}

.settings-tabs :deep(.el-tabs__content) {
  height: calc(100% - 55px);
  overflow-y: auto;
}

.settings-tabs :deep(.el-tab-pane) {
  padding: 16px;
}

/* 用户信息卡片 */
.profile-card {
  max-width: 600px;
  margin-bottom: 16px;
}

.password-card {
  max-width: 600px;
}

.password-form {
  max-width: 420px;
}

.profile-value {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 通知设置卡片 */
.notify-card {
  max-width: 600px;
}

.notify-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 0;
}

.notify-row + .notify-row {
  border-top: 1px solid var(--el-border-color-lighter);
}

.notify-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.notify-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
}

/* 地图设置卡片 */
.map-settings-card {
  max-width: 800px;
}

.card-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card-header-subtitle {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-weight: normal;
}

.map-settings-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.settings-hint {
  padding: 12px;
  background-color: var(--el-color-info-light-9);
  border: 1px solid var(--el-color-info-light-5);
  border-radius: 4px;
  color: var(--el-text-color-primary);
  font-size: 14px;
  margin: 0 0 16px 0;
}

.map-layers-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.section-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.map-layers-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.map-layer-item {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 12px;
  transition: background-color 0.2s;
}

.map-layer-item:active {
  background-color: var(--el-fill-color-light);
}

.map-layer-item:hover {
  background-color: var(--el-fill-color-extra-light);
}

.map-layer-item.is-default {
  border-color: var(--el-color-success);
  background-color: var(--el-color-success-light-9);
}

.map-layer-main {
  display: flex;
  align-items: center;
  gap: 12px;
}

.drag-handle {
  cursor: grab;
  color: var(--el-text-color-secondary);
}

.drag-handle:active {
  cursor: grabbing;
}

.layer-name {
  flex: 1;
  font-weight: 500;
}

.map-layer-config {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.config-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.config-label {
  min-width: 120px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.config-input {
  flex: 1;
}

.settings-actions {
  display: flex;
  gap: 12px;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.mobile-only {
  display: none;
}

/* 移动端优化（项目断点：1366px） */
@media (max-width: 1366px) {
  .header-left h1 {
    font-size: 16px;
  }

  .desktop-only {
    display: none !important;
  }

  .mobile-only {
    display: inline !important;
  }

  .map-layer-main {
    flex-wrap: nowrap;
  }

  .layer-name {
    flex: 1;
    min-width: 80px;
    font-size: 13px;
  }

  .map-layer-main :deep(.el-radio) {
    margin-right: 8px;
  }

  .map-layer-main :deep(.el-switch) {
    margin-right: 0;
  }

  .config-row {
    flex-wrap: wrap;
  }

  .config-label {
    min-width: 80px;
    font-size: 12px;
  }

  /* 移动端隐藏拖拽手柄 */
  .drag-handle {
    display: none;
  }

  /* 移动端显示排序按钮 */
  .mobile-sort-buttons {
    display: flex;
    gap: 4px;
  }
}
</style>
