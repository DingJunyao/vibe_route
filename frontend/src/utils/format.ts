/**
 * 统一的格式化工具函数
 */

/**
 * 格式化距离
 * @param meters 米
 * @returns 格式化后的字符串 (如 "123 m" 或 "1.23 km" 或 "1 km" 或 "-")
 */
export function formatDistance(meters: number | undefined): string {
  if (meters === undefined || meters === null || isNaN(meters)) {
    return '-'
  }
  if (meters < 1000) {
    return `${Math.round(meters)} m`
  }
  const km = (meters / 1000).toFixed(2)
  // 去掉末尾的 .00
  return km.endsWith('.00') ? `${km.slice(0, -3)} km` : `${km} km`
}

/**
 * 格式化时长
 * @param seconds 秒
 * @returns 格式化后的字符串 (如 "42h 33min" 或 "1h 23min" 或 "45min" 或 "30s" 或 "-")
 */
export function formatDuration(seconds: number | undefined): string {
  if (seconds === undefined || seconds === null || isNaN(seconds)) {
    return '-'
  }
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)

  const parts: string[] = []
  if (hours > 0) {
    parts.push(`${hours}h`)
    if (minutes > 0) {
      parts.push(`${minutes}min`)
    }
  } else if (minutes > 0) {
    parts.push(`${minutes}min`)
  } else {
    parts.push(`${secs}s`)
  }
  return parts.join(' ')
}

/**
 * 格式化海拔
 * @param meters 米
 * @returns 格式化后的字符串 (如 "123 m")
 */
export function formatElevation(meters: number): string {
  return `${meters.toFixed(0)} m`
}

/**
 * 格式化速度
 * @param speedMps 米/秒
 * @returns 格式化后的字符串 (如 "12.3 km/h")
 */
export function formatSpeed(speedMps: number): string {
  if (speedMps == null || isNaN(speedMps)) {
    return '-'
  }
  const kmh = speedMps * 3.6
  return `${kmh.toFixed(1)} km/h`
}

/**
 * 格式化日期时间（完整格式）
 * @param dateStr ISO 时间字符串或 null
 * @returns 格式化后的字符串 (如 "2024-12-15 16:17:18" 或 "-")
 */
export function formatDateTime(dateStr: string | null): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

/**
 * 格式化日期（仅年月日）
 * @param dateStr ISO 时间字符串或 null
 * @returns 格式化后的字符串 (如 "2024-12-15" 或 "-")
 */
export function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/**
 * 格式化时间（仅时分秒）
 * @param dateStr ISO 时间字符串或 null
 * @returns 格式化后的字符串 (如 "16:17:18" 或 "-")
 */
export function formatTimeOnly(dateStr: string | null): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  return `${hours}:${minutes}:${seconds}`
}

/**
 * 格式化时间范围
 * @param start 开始时间 (ISO 字符串或 null)
 * @param end 结束时间 (ISO 字符串或 null)
 * @returns 格式化后的字符串 (如 "2024-01-01 12:00 - 13:30")
 */
export function formatTimeRange(start: string | null, end: string | null): string {
  if (!start) return '-'

  const startDate = new Date(start)
  const endDate = end ? new Date(end) : null

  const dateStr = startDate.toLocaleDateString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
  })

  const startTimeStr = startDate.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })

  if (endDate) {
    const endTimeStr = endDate.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    })
    return `${dateStr} ${startTimeStr} - ${endTimeStr}`
  }

  return `${dateStr} ${startTimeStr}`
}

/**
 * 格式化方位角
 * @param bearing 方位角 (度, 0-360)
 * @returns 格式化后的字符串 (如 "北" 或 "东北")
 */
export function formatBearing(bearing: number | null): string {
  if (bearing == null || isNaN(bearing)) {
    return '-'
  }

  const directions = ['北', '东北', '东', '东南', '南', '西南', '西', '西北']
  const index = Math.round(bearing / 45) % 8
  return directions[index]
}
