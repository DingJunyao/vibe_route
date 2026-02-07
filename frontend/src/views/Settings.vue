<template>
  <div class="settings-page">
    <el-header class="page-header">
      <h1>设置</h1>
    </el-header>

    <el-main class="page-main">
      <el-tabs v-model="activeTab" class="settings-tabs">
        <!-- 用户信息选项卡 -->
        <el-tab-pane label="用户信息" name="profile">
          <el-card class="profile-card">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="用户名">
                {{ authStore.user?.username }}
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
        </el-tab-pane>

        <!-- 地图设置选项卡 -->
        <el-tab-pane label="地图设置" name="map">
          <el-card class="map-settings-card">
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, isRef } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowUp, Rank } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useUserConfigStore } from '@/stores/userConfig'
import { useConfigStore } from '@/stores/config'
import type { MapLayerConfig } from '@/api/admin'
import type { UserConfigUpdate } from '@/api/userConfig'

const authStore = useAuthStore()
const userConfigStore = useUserConfigStore()
const configStore = useConfigStore()

// 当前选项卡
const activeTab = ref('profile')

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

// 格式化日期
function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 组件挂载时加载数据
onMounted(async () => {
  // 先确保系统配置已加载
  await configStore.fetchConfig()
  // 然后加载用户配置
  await loadUserConfig()
})

// 路由离开前检查未保存的更改
defineExpose({
  hasUnsavedChanges: () => configChanged,
})
</script>

<style scoped>
.settings-page {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.page-header {
  background-color: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color);
  padding: 0 20px;
  display: flex;
  align-items: center;
}

.page-header h1 {
  font-size: 20px;
  font-weight: 500;
}

.page-main {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.settings-tabs {
  height: 100%;
}

.settings-tabs :deep(.el-tabs__content) {
  height: calc(100% - 55px);
  overflow-y: auto;
}

/* 用户信息卡片 */
.profile-card {
  max-width: 600px;
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

/* 移动端优化 */
@media (max-width: 768px) {
  .mobile-only {
    display: inline;
  }

  .desktop-only {
    display: none;
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

@media (min-width: 769px) {
  .mobile-only {
    display: none;
  }

  .desktop-only {
    display: inline;
  }

  /* 移动端排序按钮隐藏 */
  .mobile-sort-buttons {
    display: none;
  }
}
</style>
