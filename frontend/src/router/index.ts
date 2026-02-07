import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// 扩展 meta 类型
declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    requiresAdmin?: boolean
    guest?: boolean
    public?: boolean  // 所有人都可以访问（包括已登录用户）
    devOnly?: boolean
  }
}

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
    path: '/tracks/:id/map-only',
    name: 'TrackMapOnly',
    component: () => import('@/views/TrackMapOnly.vue'),
    meta: { public: true },  // 公开访问，用于 Playwright 截图
  },
  {
    path: '/tracks/:id/geo-editor',
    name: 'GeoEditor',
    component: () => import('@/views/GeoEditor.vue'),
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
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Settings.vue'),
    meta: { requiresAuth: true },
  },
  // 分享页面（公开访问，无需登录）
  {
    path: '/s/:token',
    name: 'SharedTrack',
    component: () => import('@/views/SharedTrack.vue'),
    meta: { public: true },
  },
  // 日志查看器（仅开发环境）
  {
    path: '/log-viewer',
    name: 'LogViewer',
    component: () => import('@/views/LogViewer.vue'),
    meta: { requiresAuth: true, devOnly: true },
  },
  // 实时轨迹上传页面（无需认证，通过 token 验证）
  {
    path: '/live-upload',
    name: 'LiveUpload',
    component: () => import('@/views/LiveUpload.vue'),
    meta: { guest: true },
  },
  // GPS Logger URL 引导页面（无需认证，通过 token 验证，所有人都可以访问）
  {
    path: '/live-recordings/log/:token',
    name: 'LogUrlGuide',
    component: () => import('@/views/LogUrlGuide.vue'),
    meta: { public: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()
  const isDev = import.meta.env.DEV

  // 开发环境专用路由
  if (to.meta.devOnly && !isDev) {
    next({ name: 'Home' })
    return
  }

  // public 页面：所有人都可以访问
  if (to.meta.public) {
    next()
    return
  }

  if (to.meta.requiresAuth && !authStore.isLoggedIn) {
    // 需要登录但未登录，跳转到登录页
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } else if (to.meta.requiresAdmin) {
    // 需要管理员权限 - 如果没有用户信息，先尝试获取
    if (!authStore.user && authStore.isLoggedIn) {
      await authStore.fetchCurrentUser()
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
