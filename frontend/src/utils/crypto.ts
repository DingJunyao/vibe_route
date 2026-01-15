/**
 * 密码加密工具
 * 使用 SHA256 对密码进行哈希加密后再传输给后端
 */

/**
 * 将字符串转换为 SHA256 哈希值
 * @param text 要加密的文本
 * @returns SHA256 哈希值的十六进制字符串
 */
export async function sha256(text: string): Promise<string> {
  const encoder = new TextEncoder()
  const data = encoder.encode(text)
  const hashBuffer = await crypto.subtle.digest('SHA-256', data)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  const hashHex = hashArray.map((b) => b.toString(16).padStart(2, '0')).join('')
  return hashHex
}

/**
 * 对密码进行加密（用于登录、注册等场景）
 * @param password 明文密码
 * @returns 加密后的密码
 */
export async function hashPassword(password: string): Promise<string> {
  return sha256(password)
}
