import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi, type PublicConfig } from '@/api/auth'
import { adminApi, type SystemConfig, type MapLayerConfig } from '@/api/admin'
import { useAuthStore } from './auth'

export const useConfigStore = defineStore('config', () => {
  // State
  const publicConfig = ref<PublicConfig | null>(null)
  const adminConfig = ref<SystemConfig | null>(null)
  const loading = ref(false)
  let fetchPromise: Promise<PublicConfig | SystemConfig | null> | null = null

  // Actions
  async function fetchConfig(): Promise<PublicConfig | SystemConfig | null> {
    // 如果正在加载，返回现有的 Promise
    if (loading.value && fetchPromise) {
      return fetchPromise
    }

    // 如果已经加载过，直接返回
    if (publicConfig.value) {
      return publicConfig.value
    }

    loading.value = true

    // 判断是否为管理员
    const authStore = useAuthStore()
    const isAdmin = authStore.user?.is_admin ?? false

    if (isAdmin) {
      // 管理员获取完整配置
      fetchPromise = adminApi.getConfig()
        .then((data) => {
          adminConfig.value = data
          publicConfig.value = {
            default_map_provider: data.default_map_provider,
            map_layers: data.map_layers,
          }
          return data
        })
        .catch((error) => {
          // 错误已在拦截器中处理
          return null
        })
        .finally(() => {
          loading.value = false
          fetchPromise = null
        })
    } else {
      // 普通用户只获取公开配置
      fetchPromise = authApi.getPublicConfig()
        .then((data) => {
          publicConfig.value = data
          return data
        })
        .catch((error) => {
          // 错误已在拦截器中处理
          return null
        })
        .finally(() => {
          loading.value = false
          fetchPromise = null
        })
    }

    return fetchPromise
  }

  function getMapProvider(): string {
    return publicConfig.value?.default_map_provider || 'osm'
  }

  // 获取所有已启用的地图层配置
  function getMapLayers(): MapLayerConfig[] {
    if (!publicConfig.value?.map_layers) return []
    return Object.values(publicConfig.value.map_layers)
      .filter(layer => layer.enabled)
      .sort((a, b) => a.order - b.order)
  }

  // 根据 ID 获取地图层配置（包括未启用的）
  function getMapLayerById(id: string): MapLayerConfig | undefined {
    return publicConfig.value?.map_layers?.[id]
  }

  // 检查地图层是否启用
  function isMapLayerEnabled(id: string): boolean {
    return publicConfig.value?.map_layers?.[id]?.enabled ?? false
  }

  // 管理员方法：更新配置
  async function updateConfig(data: {
    registration_enabled?: boolean
    invite_code_required?: boolean
    default_map_provider?: string
    geocoding_provider?: string
    geocoding_config?: Record<string, unknown>
    map_layers?: Record<string, unknown>
  }): Promise<SystemConfig> {
    const result = await adminApi.updateConfig(data)
    adminConfig.value = result
    publicConfig.value = {
      default_map_provider: result.default_map_provider,
      map_layers: result.map_layers,
    }
    return result
  }

  // 初始化时获取配置（不等待，让组件自己等待）
  fetchConfig()

  return {
    publicConfig,
    adminConfig,
    loading,
    fetchConfig,
    getMapProvider,
    getMapLayers,
    getMapLayerById,
    isMapLayerEnabled,
    updateConfig,
  }
})
