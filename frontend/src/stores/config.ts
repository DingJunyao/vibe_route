import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, type PublicConfig } from '@/api/auth'
import { adminApi, type SystemConfig, type MapLayerConfig } from '@/api/admin'
import { useAuthStore } from './auth'
import { useUserConfigStore } from './userConfig'

export const useConfigStore = defineStore('config', () => {
  // State
  const publicConfig = ref<PublicConfig | null>(null)
  const adminConfig = ref<SystemConfig | null>(null)
  const loading = ref(false)
  let fetchPromise: Promise<PublicConfig | SystemConfig | null> | null = null

  // Actions
  async function fetchConfig(forceRefresh = false): Promise<PublicConfig | SystemConfig | null> {
    // 如果正在加载，返回现有的 Promise
    if (loading.value && fetchPromise) {
      return fetchPromise
    }

    // 如果已经加载过且不是强制刷新，直接返回
    if (!forceRefresh && publicConfig.value) {
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
            invite_code_required: data.invite_code_required,
            registration_enabled: data.registration_enabled,
            font_config: data.font_config,
            show_road_sign_in_region_tree: data.show_road_sign_in_region_tree,
            spatial_backend: data.spatial_backend,
            allow_server_poster: data.allow_server_poster,
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

  // 强制刷新配置（用于配置更新后）
  async function refreshConfig(): Promise<void> {
    await fetchConfig(true)
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

  // 检查是否需要邀请码
  function isInviteCodeRequired(): boolean {
    return publicConfig.value?.invite_code_required ?? false
  }

  // 检查注册是否启用
  function isRegistrationEnabled(): boolean {
    return publicConfig.value?.registration_enabled ?? true
  }

  // 检查字体是否已完整配置
  function areFontsConfigured(): boolean {
    const fc = publicConfig.value?.font_config
    return !!(fc?.font_a && fc?.font_b && fc?.font_c)
  }

  // 管理员方法：更新配置
  async function updateConfig(data: {
    registration_enabled?: boolean
    invite_code_required?: boolean
    default_map_provider?: string
    geocoding_provider?: string
    geocoding_config?: Record<string, unknown>
    map_layers?: Record<string, unknown>
    font_config?: { font_a?: string; font_b?: string; font_c?: string }
    show_road_sign_in_region_tree?: boolean
    spatial_backend?: string
    allow_server_poster?: boolean
  }): Promise<SystemConfig> {
    const result = await adminApi.updateConfig(data)
    adminConfig.value = result
    publicConfig.value = {
      default_map_provider: result.default_map_provider,
      map_layers: result.map_layers,
      invite_code_required: result.invite_code_required,
      registration_enabled: result.registration_enabled,
      font_config: result.font_config,
      show_road_sign_in_region_tree: result.show_road_sign_in_region_tree,
      spatial_backend: result.spatial_backend,
      allow_server_poster: result.allow_server_poster,
    }
    return result
  }

  // 统一的配置 getter（优先使用 adminConfig，回退到 publicConfig）
  const config = computed(() => adminConfig.value || publicConfig.value)

  // 系统配置的默认地图提供商
  const defaultMapProvider = computed(() => publicConfig.value?.default_map_provider || 'osm')

  // 系统配置的地图层
  const mapLayers = computed(() => publicConfig.value?.map_layers || {})

  // 获取有效的地图提供商（考虑用户配置）
  function getEffectiveProvider(): string {
    const userConfigStore = useUserConfigStore()
    return userConfigStore.getEffectiveProvider.value || defaultMapProvider.value
  }

  // 获取有效的地图层（考虑用户配置）
  function getEffectiveLayers(): Record<string, MapLayerConfig> {
    const userConfigStore = useUserConfigStore()
    return userConfigStore.getEffectiveLayers.value || mapLayers.value
  }

  // 根据地图层 ID 获取地图层配置（优先用户配置）
  function getMapLayerById(id: string): MapLayerConfig | undefined {
    const userConfigStore = useUserConfigStore()
    const userLayer = userConfigStore.getMapLayerById(id)
    if (userLayer) return userLayer
    return publicConfig.value?.map_layers?.[id]
  }

  // 初始化时获取配置（不等待，让组件自己等待）
  fetchConfig()

  return {
    publicConfig,
    adminConfig,
    config,
    loading,
    defaultMapProvider,
    mapLayers,
    fetchConfig,
    refreshConfig,
    getMapProvider,
    getMapLayers,
    getMapLayerById,
    getEffectiveProvider,
    getEffectiveLayers,
    isMapLayerEnabled,
    isInviteCodeRequired,
    isRegistrationEnabled,
    areFontsConfigured,
    updateConfig,
  }
})
