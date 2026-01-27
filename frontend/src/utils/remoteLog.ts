/**
 * 远程日志工具
 * 将前端日志发送到后端，通过 WebSocket 在电脑端查看
 */

// 是否启用远程日志（开发环境或通过 URL 参数启用）
const ENABLED = import.meta.env.DEV || new URLSearchParams(window.location.search).has('remote-log')

// 后端 API 地址
const API_BASE = '/api'

// 日志级别
type LogLevel = 'log' | 'info' | 'warn' | 'error'

// 解析日志标签（如 "[AMap] 地图被点击" -> tag="[AMap]", message="地图被点击"）
function parseLogMessage(args: unknown[]): { tag: string; message: string } {
  if (args.length === 0) return { tag: '', message: '' }

  const first = args[0]
  if (typeof first === 'string') {
    // 匹配 [XXX] 格式的标签
    const match = first.match(/^(\[[^\]]+\])\s*(.*)$/s)
    if (match) {
      const remainingArgs = args.slice(1).map(arg => formatArg(arg)).join(' ')
      return {
        tag: match[1],
        message: match[2] + (remainingArgs ? ' ' + remainingArgs : '')
      }
    }
  }

  // 没有标签，全部作为消息
  return {
    tag: '',
    message: args.map(arg => formatArg(arg)).join(' ')
  }
}

// 格式化参数（处理对象、数组等）
function formatArg(arg: unknown): string {
  if (arg === null) return 'null'
  if (arg === undefined) return 'undefined'
  if (typeof arg === 'string') return arg
  if (typeof arg === 'number' || typeof arg === 'boolean') return String(arg)
  try {
    return JSON.stringify(arg)
  } catch {
    return String(arg)
  }
}

// 发送日志到后端
async function sendLog(level: LogLevel, args: unknown[]) {
  if (!ENABLED) return

  const { tag, message } = parseLogMessage(args)

  // 使用 sendBeacon 避免阻塞，fallback 到 fetch
  const payload = JSON.stringify({
    level,
    tag,
    message,
    timestamp: Date.now()
  })

  // 优先使用 sendBeacon（不会阻塞页面卸载）
  if (navigator.sendBeacon) {
    const blob = new Blob([payload], { type: 'application/json' })
    navigator.sendBeacon(`${API_BASE}/logs`, blob)
  } else {
    // fallback 到 fetch（使用 keepalive）
    fetch(`${API_BASE}/logs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: payload,
      keepalive: true
    }).catch(() => {
      // 忽略错误，避免影响主流程
    })
  }
}

// 保存原始 console 方法
const originalConsole = {
  log: console.log,
  info: console.info,
  warn: console.warn,
  error: console.error
}

// 重写 console 方法
export function initRemoteLog() {
  if (!ENABLED) return

  console.log = (...args: unknown[]) => {
    originalConsole.log(...args)
    sendLog('log', args)
  }

  console.info = (...args: unknown[]) => {
    originalConsole.info(...args)
    sendLog('info', args)
  }

  console.warn = (...args: unknown[]) => {
    originalConsole.warn(...args)
    sendLog('warn', args)
  }

  console.error = (...args: unknown[]) => {
    originalConsole.error(...args)
    sendLog('error', args)
  }

  console.log('[RemoteLog] 远程日志已启用')
}

// 获取 WebSocket URL（自动检测当前协议和主机）
export function getWebSocketUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.hostname
  const port = 8000
  return `${protocol}//${host}:${port}/api/ws/logs`
}
