// frontend/src/types/axios.d.ts
// 扩展 axios 请求配置类型：skipProgress / skipAuth 均由 src/api/request.ts 的拦截器消费
import 'axios'

declare module 'axios' {
  export interface AxiosRequestConfig {
    /** 跳过顶部加载进度条（用于轮询等后台请求） */
    skipProgress?: boolean
    /** 跳过 401 时的登录页跳转（用于无需认证的公开接口） */
    skipAuth?: boolean
  }
}
