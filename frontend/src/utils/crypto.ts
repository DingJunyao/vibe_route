/**
 * 密码加密工具
 * 使用 SHA256 对密码进行哈希加密后再传输给后端
 */

// 导入 js-sha256
import { sha256 as sha256Sync } from 'js-sha256'

/**
 * 将字符串转换为 SHA256 哈希值（同步版本）
 * @param text 要加密的文本
 * @returns SHA256 哈希值的十六进制字符串
 */
function sha256(text: string): string {
  return sha256Sync(text)
}

/**
 * 对密码进行加密（用于登录、注册等场景）
 * 始终使用 SHA256 加密，无论环境如何
 * @param password 明文密码
 * @returns 加密后的密码
 */
export async function hashPassword(password: string): Promise<string> {
  // 始终使用 SHA256 加密
  return sha256(password)
}
