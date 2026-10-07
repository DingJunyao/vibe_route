/**
 * 地图本地偏好设置
 *
 * 在 localStorage 中保存用户选择的地图，以便下次打开页面时使用
 */

const STORAGE_KEY = 'map_preference'
const ENGINE_STORAGE_KEY = 'map_engine_preference'

export interface MapPreference {
  layerId: string
  timestamp: number
}

/**
 * 地图引擎偏好：同一底图层可在 SDK 引擎与 Leaflet 瓦片引擎间切换
 * （key 为底图层 ID 家族前缀，如 amap / baidu / tencent / google）
 */
export type MapEngineType = 'sdk' | 'leaflet'

/**
 * 获取本地保存的地图偏好
 * @returns 地图偏好设置，如果不存在或过期则返回 null
 */
export function getLocalMapPreference(): MapPreference | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (!stored) return null

    const preference: MapPreference = JSON.parse(stored)

    // 检查是否过期（30天）
    const EXPIRY_DAYS = 30
    const expiryTime = EXPIRY_DAYS * 24 * 60 * 60 * 1000
    if (Date.now() - preference.timestamp > expiryTime) {
      localStorage.removeItem(STORAGE_KEY)
      return null
    }

    return preference
  } catch (error) {
    console.error('[mapLocalPreference] Failed to get local preference:', error)
    return null
  }
}

/**
 * 保存地图偏好到本地
 * @param layerId 地图层 ID
 */
export function saveLocalMapPreference(layerId: string): void {
  try {
    const preference: MapPreference = {
      layerId,
      timestamp: Date.now(),
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(preference))
  } catch (error) {
    console.error('[mapLocalPreference] Failed to save local preference:', error)
  }
}

/**
 * 清除本地保存的地图偏好
 */
export function clearLocalMapPreference(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch (error) {
    console.error('[mapLocalPreference] Failed to clear local preference:', error)
  }
}

/**
 * 读取引擎偏好表（layerId 家族 → 'sdk' | 'leaflet'）
 */
function getEnginePreferenceMap(): Record<string, MapEngineType> {
  try {
    const stored = localStorage.getItem(ENGINE_STORAGE_KEY)
    if (!stored) return {}
    const parsed = JSON.parse(stored)
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch (error) {
    console.error('[mapLocalPreference] Failed to get engine preference:', error)
    return {}
  }
}

/**
 * 获取指定底图层家族的引擎偏好（默认 'sdk'，保持既有行为）
 * @param layerFamily 底图层 ID 家族（如 amap / baidu / tencent / google）
 */
export function getLocalEnginePreference(layerFamily: string): MapEngineType {
  if (!layerFamily) return 'sdk'
  return getEnginePreferenceMap()[layerFamily] === 'leaflet' ? 'leaflet' : 'sdk'
}

/**
 * 保存指定底图层家族的引擎偏好
 */
export function saveLocalEnginePreference(layerFamily: string, engine: MapEngineType): void {
  try {
    const map = getEnginePreferenceMap()
    map[layerFamily] = engine
    localStorage.setItem(ENGINE_STORAGE_KEY, JSON.stringify(map))
  } catch (error) {
    console.error('[mapLocalPreference] Failed to save engine preference:', error)
  }
}

/**
 * 获取有效的地图层 ID
 * 优先级：本地偏好 > 默认值 > 系统默认
 * 如果本地偏好的地图层不存在，则返回 fallback
 *
 * @param availableLayers 可用的地图层 ID 列表
 * @param fallback 默认回退值
 * @returns 有效的地图层 ID
 */
export function getEffectiveMapLayer(
  availableLayers: string[],
  fallback: string
): string {
  const localPreference = getLocalMapPreference()

  if (localPreference) {
    const { layerId } = localPreference

    // 检查本地偏好的地图层是否仍然可用
    if (availableLayers.includes(layerId)) {
      return layerId
    }

    // 本地偏好的地图层不可用，清除本地偏好
    clearLocalMapPreference()
  }

  // 回退到默认值
  return fallback
}
