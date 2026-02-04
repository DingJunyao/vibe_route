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

// // 初始化远程日志
// initRemoteLog()

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
