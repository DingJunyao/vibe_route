<template>
  <NProgress :is-loading="nProgressStore.isLoading" :progress="nProgressStore.progress" />
  <router-view />
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import NProgress from '@/components/NProgress.vue'
import { nProgressStore } from '@/stores/nprogress'
import router from '@/router'

// 路由切换时显示进度条
router.beforeEach((to, from, next) => {
  // 只在路由变化时显示进度条
  if (to.path !== from.path) {
    nProgressStore.start()
  }
  next()
})

router.afterEach(() => {
  // 延迟一点完成，让用户看到进度条完成动画
  setTimeout(() => {
    nProgressStore.done()
  }, 100)
})

// 组件卸载时确保进度条停止
onMounted(() => {
  // 页面初始加载完成
  nProgressStore.forceDone()
})
</script>

<style>
/* 全局样式 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html,
body,
#app {
  width: 100%;
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial,
    'Noto Sans', sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol',
    'Noto Color Emoji';
}
</style>
