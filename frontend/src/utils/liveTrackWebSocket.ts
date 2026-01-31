/**
 * 实时轨迹 WebSocket 客户端
 * 用于接收实时记录或轨迹的更新推送
 */

import { getWebSocketOrigin } from './origin'

// 调试开关：通过 VITE_DEBUG_WS 环境变量控制，默认开启
const DEBUG = import.meta.env.VITE_DEBUG_WS !== 'false'

// WebSocket 关闭代码说明
const CLOSE_CODE_DESCRIPTIONS: Record<number, string> = {
  1000: '正常关闭',
  1001: '端点离开',
  1002: '协议错误',
  1003: '不支持的数据类型',
  1004: '保留',
  1005: '无状态码',
  1006: '异常关闭（连接丢失）',
  1007: '数据类型不一致',
  1008: '违反政策',
  1009: '消息过大',
  1010: '缺少扩展',
  1011: '内部错误',
  1012: '服务重启',
  1013: '尝试重连',
  1014: '无效数据',
  1015: 'TLS 握手失败',
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
    const tag = `[LiveTrackWebSocket:${category}]`
    const time = timestamp()
    console.log(`${tag} [${time}]`, ...args)
  }
}

// WebSocket 消息类型
export type WebSocketMessageType =
  | 'connected'      // 连接成功
  | 'pong'           // 心跳响应
  | 'point_added'    // 新点添加
  | 'stats_updated'  // 统计更新
  | 'disconnected'   // 连接断开
  | 'should_reconnect' // 询问是否应该重连

// 新点数据
export interface PointAddedData {
  track_id: number
  point: {
    id: number
    point_index: number
    latitude: number
    longitude: number
    elevation: number | null
    speed: number | null
    time: string | null
    created_at: string | null  // 服务器创建时间
  }
  stats: {
    distance: number
    duration: number
    elevation_gain: number
    elevation_loss: number
  }
}

// WebSocket 消息
export interface WebSocketMessage {
  type: WebSocketMessageType
  data: any
}

// 消息处理器类型
export type MessageHandler = (message: WebSocketMessage) => void

// 连接状态
export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

/**
 * 实时轨迹 WebSocket 客户端类
 */
export class LiveTrackWebSocket {
  private ws: WebSocket | null = null
  private url: string
  private token: string
  private recordingId: number | null = null
  private trackId: number | null = null
  private handlers: Map<WebSocketMessageType, Set<MessageHandler>> = new Map()
  private status: ConnectionStatus = 'disconnected'
  private reconnectTimer: number | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 2000  // 2秒
  private heartbeatTimer: number | null = null
  private shouldReconnectCallback: (() => boolean) | null = null

  /**
   * 构造函数
   * @param token 认证 token
   * @param recordingId 实时记录 ID（与 trackId 二选一）
   * @param trackId 轨迹 ID（与 recordingId 二选一）
   */
  constructor(token: string, recordingId?: number, trackId?: number) {
    this.token = token
    this.recordingId = recordingId || null
    this.trackId = trackId || null

    // 构建 WebSocket URL
    this.url = this.buildWebSocketUrl(recordingId, trackId)

    debugLog('Constructor', `创建实例, url=${this.url}, recordingId=${recordingId}, trackId=${trackId}`)
  }

  /**
   * 构建 WebSocket URL
   * 使用统一的 getWebSocketOrigin 工具函数
   */
  private buildWebSocketUrl(recordingId?: number | null, trackId?: number | null): string {
    const wsOrigin = getWebSocketOrigin()
    debugLog('URL', `getWebSocketOrigin() 返回: ${wsOrigin}`)

    const path = recordingId
      ? `/api/ws/live-recording/${recordingId}`
      : trackId
        ? `/api/ws/track/${trackId}`
        : ''

    if (!path) {
      throw new Error('必须提供 recordingId 或 trackId')
    }

    const wsUrl = `${wsOrigin}${path}?token=${this.token}`
    debugLog('URL', `最终 WebSocket URL: ${wsUrl}`)
    return wsUrl
  }

  /**
   * 连接 WebSocket
   */
  connect(): void {
    if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) {
      debugLog('Connect', `已连接或正在连接, readyState=${readyStateName(this.ws)}`)
      return
    }

    this.status = 'connecting'
    debugLog('Connect', `开始连接, url=${this.url}`)

    try {
      this.ws = new WebSocket(this.url)
      debugLog('Connect', `WebSocket 对象已创建, readyState=${readyStateName(this.ws)}`)

      this.ws.onopen = (event) => {
        this.status = 'connected'
        this.reconnectAttempts = 0

        debugLog('onopen', `连接成功!`, {
          url: this.url,
          readyState: readyStateName(this.ws),
          event: {
            type: event.type,
            bubbles: event.bubbles,
            cancelable: event.cancelable,
          }
        })

        // 启动心跳
        this.startHeartbeat()
      }

      this.ws.onmessage = (event) => {
        debugLog('onmessage', `收到原始数据:`, {
          data: event.data,
          dataType: typeof event.data,
          dataLength: event.data?.length,
          origin: event.origin,
          lastEventId: event.lastEventId,
        })

        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          debugLog('onmessage', `解析后的消息:`, message)

          // 触发对应类型的处理器
          const handlers = this.handlers.get(message.type)
          if (handlers) {
            debugLog('onmessage', `触发 ${handlers.size} 个 "${message.type}" 处理器`)
            handlers.forEach(handler => {
              try {
                handler(message)
              } catch (error) {
                debugLog('onmessage', `处理器执行错误:`, error)
              }
            })
          } else {
            debugLog('onmessage', `没有 "${message.type}" 类型的处理器`)
          }
        } catch (error) {
          debugLog('onmessage', `JSON 解析失败:`, error, `原始数据: ${event.data}`)
        }
      }

      this.ws.onclose = (event) => {
        this.status = 'disconnected'
        this.stopHeartbeat()

        const closeDesc = CLOSE_CODE_DESCRIPTIONS[event.code] || '未知代码'

        debugLog('onclose', `连接关闭:`, {
          code: event.code,
          description: closeDesc,
          reason: event.reason || '(无)',
          wasClean: event.wasClean,
          readyState: readyStateName(this.ws),
          reconnectAttempts: this.reconnectAttempts,
          maxReconnectAttempts: this.maxReconnectAttempts,
        })

        // 触发 disconnected 事件
        const handlers = this.handlers.get('disconnected')
        if (handlers) {
          handlers.forEach(handler => {
            try {
              handler({ type: 'disconnected', data: { code: event.code, reason: event.reason } })
            } catch (error) {
              debugLog('onclose', `disconnected 处理器执行错误:`, error)
            }
          })
        }

        // 检查是否应该重连
        const shouldRetry = this.shouldReconnectCallback ? this.shouldReconnectCallback() : true

        // 如果是非正常关闭，尝试重连
        if (event.code !== 1000 && shouldRetry && this.reconnectAttempts < this.maxReconnectAttempts) {
          debugLog('onclose', `将尝试重连...`)
          this.scheduleReconnect()
        } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
          debugLog('onclose', `已达到最大重连次数，停止重连`)
        } else if (!shouldRetry) {
          debugLog('onclose', `回调返回 false，停止重连`)
        }
      }

      this.ws.onerror = (error) => {
        this.status = 'error'

        debugLog('onerror', `连接错误:`, {
          error,
          errorType: error?.type,
          target: error?.target,
          readyState: readyStateName(this.ws),
          url: this.url,
        })
      }
    } catch (error) {
      this.status = 'error'
      debugLog('Connect', `创建 WebSocket 失败:`, error)
      this.scheduleReconnect()
    }
  }

  /**
   * 断开连接
   */
  disconnect(): void {
    debugLog('Disconnect', `主动断开连接`)

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }

    this.stopHeartbeat()
    this.reconnectAttempts = this.maxReconnectAttempts  // 防止自动重连

    if (this.ws) {
      debugLog('Disconnect', `关闭 WebSocket, 当前 readyState=${readyStateName(this.ws)}`)
      this.ws.close(1000, 'User disconnected')
      this.ws = null
    }

    this.status = 'disconnected'
  }

  /**
   * 安排重连
   */
  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      debugLog('Reconnect', `达到最大重连次数 (${this.maxReconnectAttempts})，停止重连`)
      return
    }

    this.reconnectAttempts++
    const delay = this.reconnectDelay * this.reconnectAttempts

    debugLog('Reconnect', `${delay}ms 后尝试第 ${this.reconnectAttempts}/${this.maxReconnectAttempts} 次重连`)

    this.reconnectTimer = window.setTimeout(() => {
      debugLog('Reconnect', `开始第 ${this.reconnectAttempts} 次重连`)
      this.connect()
    }, delay)
  }

  /**
   * 启动心跳
   */
  private startHeartbeat(): void {
    this.stopHeartbeat()

    debugLog('Heartbeat', `启动心跳 (30秒间隔)`)

    this.heartbeatTimer = window.setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        debugLog('Heartbeat', `发送 ping`)
        this.ws.send('ping')
      } else {
        debugLog('Heartbeat', `跳过 ping, readyState=${readyStateName(this.ws)}`)
      }
    }, 30000) // 30秒发送一次心跳
  }

  /**
   * 停止心跳
   */
  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
      debugLog('Heartbeat', `停止心跳`)
    }
  }

  /**
   * 注册消息处理器
   * @param type 消息类型
   * @param handler 处理函数
   */
  on(type: WebSocketMessageType, handler: MessageHandler): () => void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set())
    }
    this.handlers.get(type)!.add(handler)

    debugLog('Handler', `注册 "${type}" 处理器, 当前共有 ${this.handlers.get(type)!.size} 个`)

    // 返回取消订阅函数
    return () => {
      this.off(type, handler)
    }
  }

  /**
   * 取消消息处理器
   * @param type 消息类型
   * @param handler 处理函数
   */
  off(type: WebSocketMessageType, handler: MessageHandler): void {
    const handlers = this.handlers.get(type)
    if (handlers) {
      handlers.delete(handler)
      debugLog('Handler', `移除 "${type}" 处理器, 剩余 ${handlers.size} 个`)
      if (handlers.size === 0) {
        this.handlers.delete(type)
        debugLog('Handler', `"${type}" 类型已无处理器，删除该类型`)
      }
    }
  }

  /**
   * 获取连接状态
   */
  getStatus(): ConnectionStatus {
    return this.status
  }

  /**
   * 是否已连接
   */
  isConnected(): boolean {
    const connected = this.status === 'connected' && this.ws?.readyState === WebSocket.OPEN
    debugLog('Status', `isConnected=${connected}, status=${this.status}, readyState=${readyStateName(this.ws)}`)
    return connected
  }

  /**
   * 设置重连判断回调
   * @param callback 返回 true 表示应该重连，false 表示停止重连
   */
  setShouldReconnectCallback(callback: () => boolean): void {
    this.shouldReconnectCallback = callback
    debugLog('Callback', `设置重连判断回调`)
  }
}

/**
 * 获取当前用户的 token（用于 WebSocket 认证）
 */
export function getCurrentToken(): string | null {
  const token = localStorage.getItem('token')
  debugLog('Auth', `getCurrentToken: ${token ? '有 token' : '无 token'}`)
  return token
}
