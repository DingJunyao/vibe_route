/**
 * 相对时间格式化工具函数
 */

/**
 * 将时间字符串转换为相对时间描述
 * @param timeStr ISO 格式的时间字符串（如 "2024-01-29T12:00:00+00:00"）
 * @returns 相对时间描述，如 "刚刚"、"5秒前"、"3分钟前"等
 */
export function formatRelativeTime(timeStr: string | null | undefined): string {
  if (!timeStr) return '无'

  const now = Date.now()
  const time = new Date(timeStr).getTime()
  const diff = now - time

  if (diff < 0) {
    // 未来时间，可能是时区问题
    return '刚刚'
  }

  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  if (seconds < 10) {
    return '刚刚'
  } else if (seconds < 60) {
    return `${seconds}秒前`
  } else if (minutes < 60) {
    return `${minutes}分钟前`
  } else if (hours < 24) {
    return `${hours}小时前`
  } else if (days < 7) {
    return `${days}天前`
  } else {
    // 超过一周显示具体日期
    const date = new Date(timeStr)
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hour = String(date.getHours()).padStart(2, '0')
    const minute = String(date.getMinutes()).padStart(2, '0')
    return `${year}-${month}-${day} ${hour}:${minute}`
  }
}

/**
 * 将时间字符串格式化为具体时间 + 相对时间
 * @param timeStr ISO 格式的时间字符串
 * @returns 格式化的时间，如 "2025-01-01 11:12:13（12 分钟前）"
 */
export function formatTimeWithRelative(timeStr: string | null | undefined): string {
  if (!timeStr) return '无'

  const date = new Date(timeStr)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  const second = String(date.getSeconds()).padStart(2, '0')

  const absoluteTime = `${year}-${month}-${day} ${hour}:${minute}:${second}`

  // 计算相对时间
  const now = Date.now()
  const time = date.getTime()
  const diff = now - time

  if (diff < 0) {
    return absoluteTime
  }

  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  let relativeTime = ''
  if (seconds < 10) {
    relativeTime = '刚刚'
  } else if (seconds < 60) {
    relativeTime = `${seconds}秒前`
  } else if (minutes < 60) {
    relativeTime = `${minutes}分钟前`
  } else if (hours < 24) {
    relativeTime = `${hours}小时前`
  } else if (days < 7) {
    relativeTime = `${days}天前`
  } else {
    // 超过一周不显示相对时间
    return absoluteTime
  }

  return `${absoluteTime}（${relativeTime}）`
}

/**
 * 格式化为简短的相对时间（用于标签显示）
 * @param timeStr ISO 格式的时间字符串
 * @returns 如 "刚刚"、"10秒前"、"5分钟前"等
 */
export function formatTimeShort(timeStr: string | null | undefined): string {
  if (!timeStr) return ''

  const now = Date.now()
  const time = new Date(timeStr).getTime()
  const diff = now - time

  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)

  if (seconds < 10) return '刚刚'
  if (seconds < 60) return `${seconds}秒前更新`
  if (minutes < 60) return `${minutes}分钟前更新`
  return `${hours}小时前更新`
}

/**
 * 将时间字符串格式化为易读的日期时间
 * @param timeStr ISO 格式的时间字符串
 * @returns 格式化的日期时间，如 "2024-01-29 12:00"
 */
export function formatDateTime(timeStr: string | null | undefined): string {
  if (!timeStr) return '无'

  const date = new Date(timeStr)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  const second = String(date.getSeconds()).padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`
}
