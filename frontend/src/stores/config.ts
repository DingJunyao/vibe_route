import { defineStore } from 'pinia'
import { ref } from 'vue'
import { adminApi, type SystemConfig } from '@/api/admin'

export type MapProvider = 'osm' | 'amap' | 'baidu'

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

  function getMapProvider(): MapProvider {
    const provider = config.value?.default_map_provider || 'osm'
    if (provider === 'osm' || provider === 'amap' || provider === 'baidu') {
      return provider as MapProvider
    }
    return 'osm'
  }

  // 初始化时获取配置（不等待，让组件自己等待）
  fetchConfig()

  return {
    config,
    loading,
    fetchConfig,
    getMapProvider,
  }
})
