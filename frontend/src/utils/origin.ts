/**
 * 获取当前应用的 origin（协议 + 域名 + 端口）
 *
 * 优先级：
 * 1. VITE_ORIGIN 环境变量（开发环境内网穿透时配置）
 * 2. 当前页面的 origin
 *
 * @returns origin 字符串
 */
export function getAppOrigin(): string {
  // 开发环境：检查是否配置了 VITE_ORIGIN（内网穿透场景）
  if (import.meta.env.VITE_ORIGIN) {
    return import.meta.env.VITE_ORIGIN
  }

  // 默认使用当前页面的 origin
  return window.location.origin
}

/**
 * 获取 WebSocket 的 origin（ws:// 或 wss:// + 域名 + 端口）
 *
 * 优先级：
 * 1. VITE_ORIGIN 环境变量（内网穿透场景）
 * 2. 根据当前访问地址自动判断：
 *   - localhost/127.0.0.1 → ws://localhost:8000（本地开发）
 *   - 局域网 IP（如 192.168.x.x、10.x.x.x）→ ws://IP:8000（局域网访问）
 *   - 生产域名 → wss://domain 或 ws://domain（与主站共享端口，不添加 8000）
 *
 * @returns WebSocket origin 字符串（如 ws://localhost:8000 或 wss://example.com）
 */
export function getWebSocketOrigin(): string {
  // 检查是否配置了 VITE_ORIGIN（内网穿透场景）
  if (import.meta.env.VITE_ORIGIN) {
    const url = new URL(import.meta.env.VITE_ORIGIN)
    const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = url.hostname
    // 内网穿透时所有流量通过同一个端口，不需要额外的端口
    return `${protocol}//${host}`
  }

  const currentHost = window.location.hostname

  // 判断是否为本地地址（localhost、127.0.0.1 或局域网 IP）
  const isLocalAddress =
    currentHost === 'localhost' ||
    currentHost === '127.0.0.1' ||
    /^10\./.test(currentHost) ||
    /^172\.(1[6-9]|2[0-9]|3[01])\./.test(currentHost) ||
    /^192\.168\./.test(currentHost)

  if (isLocalAddress) {
    // 本地开发或局域网访问：使用 ws:// + host:8000
    return `ws://${currentHost}:8000`
  }

  // 生产域名：使用当前页面的协议和主机，不添加端口（与主站共享端口）
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${currentHost}`
}
