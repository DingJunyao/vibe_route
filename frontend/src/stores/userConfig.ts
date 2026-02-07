import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { userConfigApi } from '@/api/userConfig'
import type { UserConfig, UserConfigUpdate } from '@/api/userConfig'
import { useConfigStore } from './config'

export const useUserConfigStore = defineStore('userConfig', () => {
  // State
  const config = ref<UserConfig | null>(null)
  const loading = ref(false)

  // Getters
  const hasCustomConfig = computed(() => !!config.value && (
    !!config.value.map_provider ||
    !!config.value.map_layers
  ))

  // 获取有效的地图提供商（用户配置优先于系统配置）
  const getEffectiveProvider = computed(() => {
    const configStore = useConfigStore()
    return config.value?.map_provider || configStore.defaultMapProvider
  })

  // 获取有效的地图层列表（用户配置覆盖系统配置）
  const getEffectiveLayers = computed(() => {
    const configStore = useConfigStore()
    const systemLayers = configStore.mapLayers || {}

    // 如果用户有自定义地图层配置，合并到系统配置中
    if (config.value?.map_layers) {
      const userLayers = config.value.map_layers
      const merged = { ...systemLayers }

      // 用户配置覆盖系统配置
      for (const [id, layer] of Object.entries(userLayers)) {
        if (layer) {
          merged[id] = layer
        }
      }

      return merged
    }

    return systemLayers
  })

  // 根据地图层 ID 获取地图层配置（优先用户配置）
  function getMapLayerById(id: string) {
    const effectiveLayers = getEffectiveLayers.value
    return effectiveLayers[id] || null
  }

  // Actions
  async function fetchConfig() {
    loading.value = true
    try {
      config.value = await userConfigApi.getConfig()
    } catch (error) {
      // 如果用户还没有配置，API 会返回空配置，这是正常的
      console.log('No user config found')
    } finally {
      loading.value = false
    }
  }

  async function updateConfig(data: UserConfigUpdate) {
    loading.value = true
    try {
      config.value = await userConfigApi.updateConfig(data)
    } finally {
      loading.value = false
    }
  }

  async function resetConfig() {
    loading.value = true
    try {
      await userConfigApi.resetConfig()
      config.value = null
    } finally {
      loading.value = false
    }
  }

  async function fetchSharedConfig(token: string) {
    // 用于分享页面，获取分享者的配置
    loading.value = true
    try {
      const sharedConfig = await userConfigApi.getConfig()
      // 分享页面使用分享者的配置
      return sharedConfig
    } catch (error) {
      return null
    } finally {
      loading.value = false
    }
  }

  return {
    config,
    loading,
    hasCustomConfig,
    getEffectiveProvider,
    getEffectiveLayers,
    getMapLayerById,
    fetchConfig,
    updateConfig,
    resetConfig,
    fetchSharedConfig,
  }
})
