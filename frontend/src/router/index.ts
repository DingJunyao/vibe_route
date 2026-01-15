import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/home',
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { guest: true },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Register.vue'),
    meta: { guest: true },
  },
  {
    path: '/home',
    name: 'Home',
    component: () => import('@/views/Home.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/tracks',
    name: 'TrackList',
    component: () => import('@/views/TrackList.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/tracks/:id',
    name: 'TrackDetail',
    component: () => import('@/views/TrackDetail.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/upload',
    name: 'TrackUpload',
    component: () => import('@/views/TrackUpload.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/road-sign',
    name: 'RoadSignGenerator',
    component: () => import('@/views/RoadSignGenerator.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/overlay',
    name: 'OverlayGenerator',
    component: () => import('@/views/OverlayGenerator.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/admin',
    name: 'Admin',
    component: () => import('@/views/Admin.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth && !authStore.isLoggedIn) {
    // 需要登录但未登录，跳转到登录页
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } else if (to.meta.requiresAdmin) {
    // 需要管理员权限 - 如果没有用户信息，先尝试获取
    if (!authStore.user && authStore.isLoggedIn) {
      // 异步获取用户信息，同时放行（会在组件内再次检查）
      authStore.fetchCurrentUser()
    }
    if (authStore.user && !authStore.user.is_admin) {
      next({ name: 'Home' })
    } else {
      next()
    }
  } else if (to.meta.guest && authStore.isLoggedIn) {
    // 已登录用户访问 guest 页面，跳转到首页
    next({ name: 'Home' })
  } else {
    next()
  }
})

export default router
