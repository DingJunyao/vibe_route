import { ref } from 'vue'

/**
 * 顶部进度条状态管理
 * 类似 GitHub 的页面加载进度条
 */
class NProgressStore {
  private _isLoading = ref(false)
  private _progress = ref<number | null>(null)
  private _requestCount = 0

  get isLoading() {
    return this._isLoading.value
  }

  get progress() {
    return this._progress.value
  }

  /**
   * 开始加载
   */
  start() {
    this._requestCount++
    this._isLoading.value = true
    this._progress.value = null // 使用自动模拟进度
  }

  /**
   * 完成加载
   */
  done() {
    this._requestCount = Math.max(0, this._requestCount - 1)
    if (this._requestCount === 0) {
      this._isLoading.value = false
    }
  }

  /**
   * 设置进度（0-100）
   */
  set(value: number) {
    this._progress.value = Math.max(0, Math.min(100, value))
  }

  /**
   * 增加进度
   */
  increment(amount = 10) {
    if (this._progress.value === null) {
      this._progress.value = 0
    }
    this._progress.value = Math.min(100, this._progress.value + amount)
  }

  /**
   * 强制停止
   */
  forceDone() {
    this._requestCount = 0
    this._isLoading.value = false
    this._progress.value = null
  }
}

export const nProgressStore = new NProgressStore()
