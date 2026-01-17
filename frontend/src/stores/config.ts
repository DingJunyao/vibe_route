import { defineStore } from 'pinia'
import { ref } from 'vue'
import { adminApi, type SystemConfig, type MapLayerConfig } from '@/api/admin'

export const useConfigStore = defineStore('config', () => {
  // State
  const config = ref<SystemConfig | null>(null)
  const loading = ref(false)
  let fetchPromise: Promise<SystemConfig | null> | null = null

  // Actions
  async function fetchConfig(): Promise<SystemConfig | null> {
    // 如果正在加载，返回现有的 Promise
    if (loading.value && fetchPromise) {
      return fetchPromise
    }

    // 如果已经加载过，直接返回
    if (config.value) {
      return config.value
    }

    loading.value = true
    fetchPromise = adminApi.getConfig()
      .then((data) => {
        config.value = data
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

    return fetchPromise
  }

  function getMapProvider(): string {
    return config.value?.default_map_provider || 'osm'
  }

  // 获取所有已启用的地图层配置
  function getMapLayers(): MapLayerConfig[] {
    if (!config.value?.map_layers) return []
    return Object.values(config.value.map_layers)
      .filter(layer => layer.enabled)
      .sort((a, b) => a.order - b.order)
  }

  // 根据 ID 获取地图层配置（包括未启用的）
  function getMapLayerById(id: string): MapLayerConfig | undefined {
    return config.value?.map_layers?.[id]
  }

  // 检查地图层是否启用
  function isMapLayerEnabled(id: string): boolean {
    return config.value?.map_layers?.[id]?.enabled ?? false
  }

  // 初始化时获取配置（不等待，让组件自己等待）
  fetchConfig()

  return {
    config,
    loading,
    fetchConfig,
    getMapProvider,
    getMapLayers,
    getMapLayerById,
    isMapLayerEnabled,
  }
})
