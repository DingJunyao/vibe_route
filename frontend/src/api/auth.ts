import { http } from './request'

// 类型定义
export interface User {
  id: number
  username: string
  email: string
  is_admin: boolean
  is_active: boolean
  created_at: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
  invite_code?: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

// API 方法
export const authApi = {
  // 登录
  login(data: LoginRequest): Promise<AuthResponse> {
    return http.post('/auth/login', data)
  },

  // 注册
  register(data: RegisterRequest): Promise<AuthResponse> {
    return http.post('/auth/register', data)
  },

  // 获取当前用户信息
  getCurrentUser(): Promise<User> {
    return http.get('/auth/me')
  },

  // 登出
  logout(): Promise<{ message: string }> {
    return http.post('/auth/logout')
  },
}
