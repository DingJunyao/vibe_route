import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import type { User, LoginRequest, RegisterRequest } from '@/api/auth'
import { hashPassword } from '@/utils/crypto'

export const useAuthStore = defineStore('auth', () => {
  // State
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<User | null>(null)

  // Getters
  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.is_admin ?? false)

  // Actions
  async function login(credentials: LoginRequest) {
    // 加密密码后再传输
    const hashedPassword = await hashPassword(credentials.password)
    const response = await authApi.login({
      username: credentials.username,
      password: hashedPassword,
    })
    token.value = response.access_token
    user.value = response.user
    localStorage.setItem('token', response.access_token)
  }

  async function register(data: RegisterRequest) {
    // 加密密码后再传输
    const hashedPassword = await hashPassword(data.password)
    const response = await authApi.register({
      username: data.username,
      email: data.email,
      password: hashedPassword,
      invite_code: data.invite_code,
    })
    token.value = response.access_token
    user.value = response.user
    localStorage.setItem('token', response.access_token)
  }

  async function fetchCurrentUser() {
    if (!token.value) return
    try {
      user.value = await authApi.getCurrentUser()
    } catch (error) {
      logout()
    }
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
  }

  // 初始化时如果有 token，自动获取用户信息
  if (token.value && !user.value) {
    fetchCurrentUser()
  }

  return {
    token,
    user,
    isLoggedIn,
    isAdmin,
    login,
    register,
    fetchCurrentUser,
    logout,
  }
}
)
