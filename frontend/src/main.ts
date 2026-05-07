import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'

import App from './App.vue'
import router from './router'
import { initRemoteLog } from './utils/remoteLog'

import 'leaflet/dist/leaflet.css'

// 地理信息编辑器公共样式变量
import './components/geo-editor/styles/common.css'

// 初始化远程日志
initRemoteLog()

// 修复 Edge 浏览器最小化问题：
// Vue Router 在 visibilitychange 事件中会调用 history.replaceState/pushState，
// 这会触发 Edge 的 bug 导致窗口最小化被取消。通过拦截这些调用来修复。
// 参考: https://blog.csdn.net/u012961419/article/details/157805074
const originalReplaceState = window.history.replaceState
const originalPushState = window.history.pushState

window.history.replaceState = function (...args) {
  if (document.visibilityState === 'hidden') {
    return // 页面隐藏时拦截调用
  }
  return originalReplaceState.apply(this, args)
}

window.history.pushState = function (...args) {
  if (document.visibilityState === 'hidden') {
    return // 页面隐藏时拦截调用
  }
  return originalPushState.apply(this, args)
}

// 移动端调试工具（开发环境）
if (import.meta.env.DEV) {
  import('eruda').then((eruda) => {
    eruda.default?.init()
    console.log('Eruda 调试工具已启用')
  })
}

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })

app.mount('#app')
