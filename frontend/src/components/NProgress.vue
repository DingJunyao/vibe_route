<template>
  <div class="nprogress-container">
    <div
      class="nprogress-bar"
      :class="{ 'nprogress-bar-complete': isComplete }"
      :style="barStyle"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

const props = defineProps<{
  /** 是否正在加载 */
  isLoading: boolean
  /** 当前进度 (0-100)，null 表示自动模拟进度 */
  progress: number | null
}>()

const isComplete = ref(false)
const currentProgress = ref(0)
let animationFrame: number | null = null
let startTime: number | null = null

// 自动模拟进度
const startProgress = () => {
  isComplete.value = false
  currentProgress.value = 0
  startTime = Date.now()

  const animate = () => {
    if (!props.isLoading) {
      // 完成动画
      currentProgress.value = 100
      isComplete.value = true

      // 动画完成后重置
      setTimeout(() => {
        if (!props.isLoading) {
          currentProgress.value = 0
          isComplete.value = false
        }
      }, 400)

      return
    }

    // 使用对数函数模拟进度：开始快，后面慢
    const elapsed = Date.now() - (startTime || 0)
    const progress = Math.min(90, 100 * (1 - Math.exp(-elapsed / 300)))
    currentProgress.value = progress

    animationFrame = requestAnimationFrame(animate)
  }

  animate()
}

// 监听 loading 状态
watch(() => props.isLoading, (loading) => {
  if (animationFrame !== null) {
    cancelAnimationFrame(animationFrame)
    animationFrame = null
  }

  if (loading) {
    startProgress()
  } else {
    // 完成动画
    currentProgress.value = 100
    isComplete.value = true

    setTimeout(() => {
      currentProgress.value = 0
      isComplete.value = false
    }, 400)
  }
}, { immediate: true })

// 计算样式
const barStyle = computed(() => {
  // 如果提供了明确的进度值，使用它；否则使用模拟进度
  const progress = props.progress !== null ? props.progress : currentProgress.value
  return {
    width: `${progress}%`
  }
})
</script>

<style scoped>
.nprogress-container {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 9999;
  pointer-events: none;
  height: 3px;
}

.nprogress-bar {
  height: 100%;
  background: linear-gradient(
    90deg,
    #409eff 0%,
    #66b1ff 50%,
    #409eff 100%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite linear;
  box-shadow: 0 0 10px rgba(64, 158, 255, 0.5);
  transition: width 0.4s ease;
  will-change: width;
}

.nprogress-bar-complete {
  transition: width 0.2s ease-out, opacity 0.2s ease-out;
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
