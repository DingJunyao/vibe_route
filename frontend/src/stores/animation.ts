// frontend/src/stores/animation.ts

import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type {
  AnimationPreferences,
  PlaybackState,
  CameraMode,
  OrientationMode,
  MarkerStyle,
  PlaybackSpeed,
} from '@/types/animation'
import {
  DEFAULT_PREFERENCES,
  ANIMATION_STORAGE_KEY,
  PLAYBACK_SPEEDS,
} from '@/types/animation'

export const useAnimationStore = defineStore('animation', () => {
  // 是否显示播放控件
  const showControls = ref(false)

  // 显示播放控件
  function setShowControls(value: boolean) {
    showControls.value = value
  }
  // 从 localStorage 加载偏好设置
  const loadPreferences = (): AnimationPreferences => {
    try {
      const saved = localStorage.getItem(ANIMATION_STORAGE_KEY)
      if (saved) {
        return { ...DEFAULT_PREFERENCES, ...JSON.parse(saved) }
      }
    } catch (e) {
      console.warn('Failed to load animation preferences:', e)
    }
    return { ...DEFAULT_PREFERENCES }
  }

  // 保存偏好设置到 localStorage
  const savePreferences = (prefs: AnimationPreferences) => {
    try {
      localStorage.setItem(ANIMATION_STORAGE_KEY, JSON.stringify(prefs))
    } catch (e) {
      console.warn('Failed to save animation preferences:', e)
    }
  }

  // 偏好设置
  const preferences = ref<AnimationPreferences>(loadPreferences())

  // 监听偏好设置变化并保存
  watch(preferences, (newPrefs) => {
    savePreferences(newPrefs)
  }, { deep: true })

  // 当前播放状态
  const playbackState = ref<PlaybackState>({
    isPlaying: false,
    currentTime: 0,
    playbackSpeed: preferences.value.defaultSpeed,
    cameraMode: preferences.value.defaultCameraMode,
    orientationMode: preferences.value.defaultOrientationMode,
    showInfoPanel: preferences.value.showInfoPanel,
    markerStyle: preferences.value.markerStyle,
  })

  // 重置播放状态
  function resetPlaybackState() {
    playbackState.value = {
      isPlaying: false,
      currentTime: 0,
      playbackSpeed: preferences.value.defaultSpeed,
      cameraMode: preferences.value.defaultCameraMode,
      orientationMode: preferences.value.defaultOrientationMode,
      showInfoPanel: preferences.value.showInfoPanel,
      markerStyle: preferences.value.markerStyle,
    }
  }

  // 设置播放状态
  function setPlaybackState<K extends keyof PlaybackState>(
    key: K,
    value: PlaybackState[K]
  ) {
    playbackState.value[key] = value
  }

  // 切换播放/暂停
  function togglePlayPause() {
    playbackState.value.isPlaying = !playbackState.value.isPlaying
  }

  // 切换倍速
  function cycleSpeed() {
    const currentIndex = PLAYBACK_SPEEDS.indexOf(
      playbackState.value.playbackSpeed as PlaybackSpeed
    )
    const nextIndex = (currentIndex + 1) % PLAYBACK_SPEEDS.length
    playbackState.value.playbackSpeed = PLAYBACK_SPEEDS[nextIndex]
  }

  // 设置倍速
  function setSpeed(speed: number) {
    if (PLAYBACK_SPEEDS.includes(speed as PlaybackSpeed)) {
      playbackState.value.playbackSpeed = speed
    }
  }

  // 切换相机模式（同时切换朝向模式）
  function toggleCameraMode() {
    const cameraModes: CameraMode[] = ['full', 'fixed-center']
    const orientationModes: OrientationMode[] = ['north-up', 'track-up']

    const currentCameraIndex = cameraModes.indexOf(playbackState.value.cameraMode)
    const currentOrientationIndex = orientationModes.indexOf(playbackState.value.orientationMode)

    // 切换相机模式
    playbackState.value.cameraMode = cameraModes[(currentCameraIndex + 1) % cameraModes.length]

    // 当切换到固定中心时，同时切换朝向模式
    if (playbackState.value.cameraMode === 'fixed-center') {
      playbackState.value.orientationMode = orientationModes[(currentOrientationIndex + 1) % orientationModes.length]
    } else {
      // 全轨迹视图时，重置为正北朝上
      playbackState.value.orientationMode = 'north-up'
    }
  }

  // 设置相机模式
  function setCameraMode(mode: CameraMode) {
    playbackState.value.cameraMode = mode
  }

  // 切换朝向模式
  function toggleOrientationMode() {
    const modes: OrientationMode[] = ['north-up', 'track-up']
    const currentIndex = modes.indexOf(playbackState.value.orientationMode)
    playbackState.value.orientationMode = modes[(currentIndex + 1) % modes.length]
  }

  // 设置朝向模式
  function setOrientationMode(mode: OrientationMode) {
    playbackState.value.orientationMode = mode
  }

  // 切换信息浮层
  function toggleInfoPanel() {
    playbackState.value.showInfoPanel = !playbackState.value.showInfoPanel
  }

  // 切换标记样式
  function cycleMarkerStyle() {
    const styles: MarkerStyle[] = ['arrow', 'car', 'person']
    const currentIndex = styles.indexOf(playbackState.value.markerStyle)
    playbackState.value.markerStyle = styles[(currentIndex + 1) % styles.length]
  }

  // 设置标记样式
  function setMarkerStyle(style: MarkerStyle) {
    playbackState.value.markerStyle = style
  }

  // 重置偏好设置
  function resetPreferences() {
    preferences.value = { ...DEFAULT_PREFERENCES }
  }

  // 更新偏好设置
  function updatePreferences<K extends keyof AnimationPreferences>(
    key: K,
    value: AnimationPreferences[K]
  ) {
    preferences.value[key] = value
  }

  // 监听 storage 事件（跨标签页同步）
  if (typeof window !== 'undefined') {
    window.addEventListener('storage', (e) => {
      if (e.key === ANIMATION_STORAGE_KEY && e.newValue) {
        try {
          preferences.value = {
            ...DEFAULT_PREFERENCES,
            ...JSON.parse(e.newValue),
          }
        } catch (err) {
          console.warn('Failed to sync animation preferences:', err)
        }
      }
    })
  }

  return {
    // 状态
    preferences,
    playbackState,
    showControls: computed(() => showControls.value),

    // 计算属性
    isPlaying: computed(() => playbackState.value.isPlaying),
    currentTime: computed(() => playbackState.value.currentTime),
    playbackSpeed: computed(() => playbackState.value.playbackSpeed),
    cameraMode: computed(() => playbackState.value.cameraMode),
    orientationMode: computed(() => playbackState.value.orientationMode),
    showInfoPanel: computed(() => playbackState.value.showInfoPanel),
    markerStyle: computed(() => playbackState.value.markerStyle),

    // 方法
    resetPlaybackState,
    setPlaybackState,
    togglePlayPause,
    cycleSpeed,
    setSpeed,
    toggleCameraMode,
    setCameraMode,
    toggleOrientationMode,
    setOrientationMode,
    toggleInfoPanel,
    cycleMarkerStyle,
    setMarkerStyle,
    setShowControls,
    resetPreferences,
    updatePreferences,
    loadPreferences,
    savePreferences,
  }
})
