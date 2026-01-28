/**
 * 远程日志工具
 * 将前端日志发送到后端，通过 WebSocket 在电脑端查看
 */

import { getWebSocketOrigin } from './origin'

// 是否启用远程日志（开发环境或通过 URL 参数启用）
const ENABLED = import.meta.env.DEV || new URLSearchParams(window.location.search).has('remote-log')

// 调试开关：通过 VITE_DEBUG_WS 环境变量控制，默认开启
const DEBUG = import.meta.env.VITE_DEBUG_WS !== 'false'

// 后端 API 地址
const API_BASE = '/api'

// WebSocket 关闭代码说明
const CLOSE_CODE_DESCRIPTIONS: Record<number, string> = {
  1000: '正常关闭',
  1001: '端点离开',
  1002: '协议错误',
  1003: '不支持的数据类型',
  1006: '异常关闭（连接丢失）',
  1008: '违反政策',
  1011: '内部错误',
}

// 格式化时间戳
function timestamp(): string {
  return new Date().toISOString().split('T')[1].slice(0, -1)
}

// 格式化 readyState
function readyStateName(ws: WebSocket | null): string {
  if (!ws) return 'null'
  const states = ['CONNECTING', 'OPEN', 'CLOSING', 'CLOSED']
  return states[ws.readyState] || `UNKNOWN(${ws.readyState})`
}

// 调试日志
function debugLog(category: string, ...args: unknown[]) {
  if (DEBUG) {
    const tag = `[RemoteLogWS:${category}]`
    const time = timestamp()
    console.log(`${tag} [${time}]`, ...args)
  }
}

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

/**
 * 连接远程日志 WebSocket
 * @returns WebSocket 实例和清理函数
 */
export function connectRemoteLogWebSocket(): { ws: WebSocket | null; cleanup: () => void } {
  if (!ENABLED) {
    debugLog('Init', '远程日志未启用')
    return { ws: null, cleanup: () => {} }
  }

  const wsUrl = getWebSocketUrl()
  debugLog('Init', `连接远程日志 WebSocket: ${wsUrl}`)
  debugLog('Init', `getWebSocketOrigin() 返回: ${getWebSocketOrigin()}`)

  let ws: WebSocket | null = null
  let reconnectTimer: number | null = null

  const connect = () => {
    try {
      ws = new WebSocket(wsUrl)
      debugLog('Connect', `WebSocket 对象已创建, readyState=${readyStateName(ws)}`)

      ws.onopen = (event) => {
        debugLog('onopen', `连接成功!`, {
          url: wsUrl,
          readyState: readyStateName(ws),
          event: {
            type: event.type,
            bubbles: event.bubbles,
            cancelable: event.cancelable,
          }
        })

        // 清除重连定时器
        if (reconnectTimer) {
          clearTimeout(reconnectTimer)
          reconnectTimer = null
        }
      }

      ws.onmessage = (event) => {
        debugLog('onmessage', `收到数据:`, {
          data: event.data,
          dataType: typeof event.data,
          dataLength: event.data?.length,
          origin: event.origin,
        })
      }

      ws.onclose = (event) => {
        const closeDesc = CLOSE_CODE_DESCRIPTIONS[event.code] || '未知代码'

        debugLog('onclose', `连接关闭:`, {
          code: event.code,
          description: closeDesc,
          reason: event.reason || '(无)',
          wasClean: event.wasClean,
          readyState: readyStateName(ws),
        })

        // 3秒后尝试重连
        reconnectTimer = window.setTimeout(() => {
          debugLog('Reconnect', `尝试重新连接...`)
          connect()
        }, 3000)
      }

      ws.onerror = (error) => {
        debugLog('onerror', `连接错误:`, {
          error,
          errorType: error?.type,
          target: error?.target,
          readyState: readyStateName(ws),
          url: wsUrl,
        })
      }
    } catch (error) {
      debugLog('Connect', `创建 WebSocket 失败:`, error)
    }
  }

  // 开始连接
  connect()

  // 返回清理函数
  const cleanup = () => {
    debugLog('Cleanup', `清理远程日志 WebSocket`)

    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }

    if (ws) {
      ws.close(1000, 'Remote log cleanup')
      ws = null
    }
  }

  return { ws, cleanup }
}

// 获取 WebSocket URL（使用统一的 origin 工具）
export function getWebSocketUrl(): string {
  const origin = getWebSocketOrigin()
  debugLog('URL', `getWebSocketOrigin() 返回: ${origin}`)
  const url = `${origin}/api/ws/logs`
  debugLog('URL', `最终 WebSocket URL: ${url}`)
  return url
}
