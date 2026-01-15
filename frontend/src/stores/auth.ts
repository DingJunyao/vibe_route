import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import type { User, LoginRequest, RegisterRequest } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  // State
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<User | null>(null)

  // Getters
  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.is_admin ?? false)

  // Actions
  async function login(credentials: LoginRequest) {
    const response = await authApi.login(credentials)
    token.value = response.access_token
    user.value = response.user
    localStorage.setItem('token', response.access_token)
  }

  async function register(data: RegisterRequest) {
    const response = await authApi.register(data)
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
})
