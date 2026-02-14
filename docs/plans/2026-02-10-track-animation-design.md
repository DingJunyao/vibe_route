# 轨迹动画功能设计文档

**日期**: 2026-02-10
**状态**: 设计完成，待实施

---

## 1. 功能概述

轨迹动画功能允许用户在轨迹详情页和分享页面上以动画形式回放轨迹，支持 1:1 真实时间回放、多种倍速、画面模式切换，并可导出为视频文件。

### 核心特性

- **1:1 真实回放**: 基于轨迹实际录制时长回放，支持多种倍速档位
- **画面模式**: 全轨迹画面 / 固定中心（正北朝上 / 轨迹朝上）
- **双色轨迹**: 已经过和未经过的轨迹用不同颜色显示
- **移动标记**: 方向箭头标记，支持多种图标样式
- **视频导出**: 支持前端和后端两种导出方式，可选分辨率和帧率
- **本地持久化**: 用户偏好设置保存到 localStorage

---

## 2. 架构设计

### 2.1 组件结构

```
TrackDetail.vue / SharedTrack.vue
    │
    ├── TrackAnimationPlayer.vue (核心播放器)
    │   ├── AnimationHUD.vue (浮动控制面板)
    │   └── MovingMarker.vue (移动标记)
    │
    └── UniversalMap.vue
        ├── AMap.vue + AnimationMapMixin
        ├── BMap.vue + AnimationMapMixin
        ├── TencentMap.vue + AnimationMapMixin
        └── LeafletMap.vue + AnimationMapMixin
```

### 2.2 新增文件清单

**前端组件**:
- `frontend/src/components/animation/TrackAnimationPlayer.vue`
- `frontend/src/components/animation/AnimationHUD.vue`
- `frontend/src/components/animation/MovingMarker.vue`
- `frontend/src/components/animation/AnimationExporter.ts`
- `frontend/src/composables/animation/useAnimationState.ts`

**前端混入**:
- `frontend/src/components/map/AnimationMapMixin.ts`

**后端**:
- `backend/app/api/animation.py`
- `backend/app/schemas/animation.py`
- `backend/app/services/animation_service.py`

---

## 3. UI/UX 设计

### 3.1 入口按钮

在地图右上角控制栏添加"播放动画"按钮，位置在全屏按钮左侧。

### 3.2 HUD 控制面板

```
┌─────────────────────────────────────────────────────┐
│  地图内容区域                                        │
│                                                     │
│              ┌─────────────────────┐                │
│              │   ⏸  2.0x          │  ← 播放/暂停 + 倍速  │
│              │   ▰▰▰▱▰▰▰▰▰▰▰    │  ← 进度条        │
│              │   00:15:32 / 01:23:45 │             │
│              │                     │                │
│              │  [🎯] [📍] [⚙️] [📹] │  ← 功能按钮   │
│              └─────────────────────┘                │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**控制元素说明**:

| 元素 | 功能 |
|------|------|
| 播放/暂停按钮 | 切换播放状态 |
| 倍速显示 | 点击切换档位：0.25x, 0.5x, 1x, 2x, 4x, 8x, 16x |
| 进度条 | 可拖动滑块，支持快进快退 |
| 时间显示 | 当前时间 / 总时长 |
| 🎯 画面模式 | 切换：全轨迹画面 / 固定中心 |
| 📍 浮层显示 | 切换信息浮层开关 |
| ⚙️ 标记样式 | 选择箭头/车/人等图标 |
| 📹 导出视频 | 打开导出对话框 |

### 3.3 信息浮层

可选显示的浮动信息卡片，跟随移动标记：

```
┌─────────────────┐
│ 12:35:42        │
│ 35.2 km/h       │
│ 1,234m ▲        │
└─────────────────┘
```

---

## 4. 数据类型定义

### 4.1 前端类型

```typescript
// animation.ts
export interface AnimationConfig {
  trackId: number
  trackPoints: TrackPoint[]
  startTime: string      // ISO 8601
  endTime: string        // ISO 8601
  duration: number       // 毫秒
}

export interface PlaybackState {
  isPlaying: boolean
  currentTime: number    // 毫秒
  playbackSpeed: number  // 0.25, 0.5, 1, 2, 4, 8, 16
  cameraMode: 'full' | 'fixed-center'
  orientationMode: 'north-up' | 'track-up'
  showInfoPanel: boolean
  markerStyle: 'arrow' | 'car' | 'person'
}

export interface ExportConfig {
  resolution: '720p' | '1080p' | '4k'
  fps: 30 | 60
  showHUD: boolean
  format: 'webm' | 'mp4'
}

export interface MarkerPosition {
  lat: number
  lng: number
  bearing: number
  speed: number | null
  elevation: number | null
  time: string | null
}

export interface AnimationPreferences {
  defaultSpeed: number
  showInfoPanel: boolean
  markerStyle: 'arrow' | 'car' | 'person'
  defaultCameraMode: 'full' | 'fixed-center'
  defaultOrientationMode: 'north-up' | 'track-up'
  exportResolution: '720p' | '1080p' | '4k'
  exportFPS: 30 | 60
  exportShowHUD: boolean
}
```

### 4.2 后端 Schema

```python
class AnimationExportRequest(BaseModel):
    resolution: Literal['720p', '1080p', '4k'] = '1080p'
    fps: Literal[30, 60] = 30
    show_hud: bool = True
    format: Literal['webm', 'mp4'] = 'mp4'
    speed: float = 1.0
```

---

## 5. 核心功能实现

### 5.1 时间与进度计算

```typescript
// 基于轨迹的实际录制时长
const totalDuration = new Date(track.end_time).getTime() - new Date(track.start_time).getTime()

// 当前播放时间
const currentTime = ref(0)

// 二分查找 + 时间插值计算当前点索引
const getCurrentPointIndex = (time: number): { index: number; progress: number } => {
  // 返回点索引和该点内的插值进度 (0-1)
}
```

### 5.2 双色轨迹绘制

各地图组件实现 `drawAnimationTrack` 方法：
- `passedSegment`: { start: 0, end: currentIndex, color: '#409eff' }
- `remainingSegment`: { start: currentIndex, end: points.length, color: '#c0c4cc' }

### 5.3 移动标记平滑过渡

```typescript
// 在两个轨迹点之间进行插值
const interpolatePosition = (
  point1: TrackPoint,
  point2: TrackPoint,
  progress: number
): MarkerPosition => {
  const lat = point1.latitude_wgs84 + (point2.latitude_wgs84 - point1.latitude_wgs84) * progress
  const lng = point1.longitude_wgs84 + (point2.longitude_wgs84 - point1.longitude_wgs84) * progress
  const bearing = point1.bearing + (point2.bearing - point1.bearing) * progress
  return { lat, lng, bearing, speed, elevation, time }
}
```

### 5.4 画面中心跟随 + 地图旋转

```typescript
// 固定中心模式
if (cameraMode.value === 'fixed-center') {
  map.setCenter(currentLngLat)

  if (orientationMode.value === 'track-bearing') {
    // 计算最短旋转路径（处理 350° → 10° 的情况）
    const currentBearing = map.getBearing()
    let delta = targetBearing - currentBearing
    if (delta > 180) delta -= 360
    if (delta < -180) delta += 360

    // 平滑旋转
    map.setBearing(currentBearing + delta * 0.1)
  }
}
```

### 5.5 动态采样优化

```typescript
// 根据倍速和点密度决定采样率
const getSampleStep = (speed: number, zoom: number): number => {
  if (speed >= 8) return 4
  if (speed >= 4) return 2
  return 1
}

// 根据点数量动态调整渲染策略
const getRenderStrategy = (pointCount: number): 'full' | 'sampled' | 'simplified' => {
  if (pointCount < 500) return 'full'
  if (pointCount < 2000) return 'sampled'
  return 'simplified'
}
```

---

## 6. 视频导出功能

### 6.1 前端导出

```typescript
class AnimationExporter {
  async export(config: ExportConfig): Promise<Blob> {
    // 1. 创建离屏 Canvas
    const canvas = document.createElement('canvas')
    canvas.width = config.width
    canvas.height = config.height

    // 2. 使用 MediaRecorder 录制
    const stream = canvas.captureStream(config.fps)
    const recorder = new MediaRecorder(stream, {
      mimeType: 'video/webm;codecs=vp9',
      videoBitsPerSecond: config.bitrate
    })

    // 3. 逐帧渲染
    for (let time = 0; time <= duration; time += frameDuration) {
      await this.drawMapFrame(ctx, time)
      if (config.showHUD) this.drawHUD(ctx, time, duration)
      recorder.requestData()
      await this.waitFrame(config.fps)
    }

    return new Blob(chunks, { type: 'video/webm' })
  }
}
```

### 6.2 后端导出

```python
class AnimationService:
    async def export_video(self, track_id: int, config: ExportConfig):
        # 1. 启动 Playwright 浏览器
        page = await browser.new_page()
        await page.goto(f"/tracks/{track_id}/animation-only")

        # 2. 设置导出模式并录制
        await page.evaluate(f"window.startAnimationExport({config})")
        video_path = await page.video.path()

        # 3. 可选：使用 FFmpeg 转码为 MP4
        if config.format == 'mp4':
            await self.convert_to_mp4(video_path, config)

        return video_path
```

### 6.3 导出方式选择策略

| 场景 | 推荐方式 |
|------|---------|
| 短轨迹（< 5 分钟） | 前端导出 |
| 长轨迹（≥ 5 分钟） | 后端导出 |
| 移动端 | 后端导出 |

---

## 7. 各地图引擎适配

### 7.1 统一接口

```typescript
interface AnimationMapAdapter {
  drawAnimationTrack(
    passedPoints: TrackPoint[],
    remainingPoints: TrackPoint[],
    passedColor: string,
    remainingColor: string
  ): void

  moveMarker(position: LatLng, bearing: number): void
  setCenter(position: LatLng): void
  setBearing(bearing: number): Promise<void>
  getBearing(): number
  captureMap(): string | Promise<string> | null
}
```

### 7.2 兼容性

| 引擎 | 旋转支持 | 备注 |
|------|---------|------|
| 高德 | ⚠️ 有限 | 需切换 3D 模式 |
| 百度 GL | ✅ 支持 | `setMapStyle({ heading })` |
| 百度 Legacy | ❌ 不支持 | 固定正北朝上 |
| 腾讯 | ✅ 支持 | `setRotation()` |
| Leaflet | ✅ 支持 | 需 rotate 插件 |

不支持旋转的地图引擎将禁用"轨迹朝上"选项。

---

## 8. API 端点

### 8.1 新增后端 API

```python
# 创建动画导出任务
POST /api/tracks/{track_id}/animation/export
Request: AnimationExportRequest
Response: { "task_id": str }

# 查询导出任务状态
GET /api/tracks/{track_id}/animation/export/status/{task_id}
Response: TaskStatus

# 下载已完成的视频
GET /api/tracks/{track_id}/animation/export/download/{task_id}
Response: video/webm or video/mp4
```

---

## 9. 本地存储

### 9.1 存储键

```typescript
const STORAGE_KEY = 'vibe-route-animation-prefs'
```

### 9.2 存储内容

```typescript
interface AnimationPreferences {
  defaultSpeed: number
  showInfoPanel: boolean
  markerStyle: 'arrow' | 'car' | 'person'
  defaultCameraMode: 'full' | 'fixed-center'
  defaultOrientationMode: 'north-up' | 'track-up'
  exportResolution: '720p' | '1080p' | '4k'
  exportFPS: 30 | 60
  exportShowHUD: boolean
}
```

### 9.3 跨标签页同步

监听 `storage` 事件实现多标签页同步。

---

## 10. 错误处理

### 10.1 边界情况

| 情况 | 处理方式 |
|------|---------|
| 轨迹点数为 0 | 禁用播放，提示"无轨迹数据" |
| 只有 1 个点 | 禁用播放，提示"轨迹点不足" |
| 时间数据缺失 | 使用点索引，平均分配时长 |
| bearing 缺失 | 箭头默认朝北或根据前后点计算 |
| 画面间隙过大 | 正常处理，快速跳过 |
| 播放到终点 | 自动暂停，显示"播放完成" |

### 10.2 导出失败处理

| 场景 | 处理方式 |
|------|---------|
| 前端内存不足 | 提示使用后端导出 |
| FFmpeg 不可用 | 返回 WebM 格式 |
| 导出超时 | 保存已录制部分 |
| 用户取消 | 清理临时文件 |

---

## 11. 实施优先级

### Phase 1 - 核心播放功能
- [ ] TrackAnimationPlayer 核心逻辑
- [ ] AnimationHUD 控制面板
- [ ] 双色轨迹绘制
- [ ] 移动标记实现

### Phase 2 - 画面模式
- [ ] 固定中心模式
- [ ] 地图旋转（各引擎适配）
- [ ] 平滑过渡动画

### Phase 3 - 视频导出
- [ ] 前端 MediaRecorder 导出
- [ ] 导出对话框 UI
- [ ] 后端 Playwright 导出

### Phase 4 - 优化与完善
- [ ] 动态采样优化
- [ ] 本地存储持久化
- [ ] 错误处理完善

---

## 12. 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 高德地图旋转限制 | 功能不完整 | 提供降级方案（正北朝上） |
| 前端导出内存限制 | 长轨迹无法导出 | 引导使用后端导出 |
| 百度 Legacy 不支持旋转 | 体验受限 | 明确告知用户限制 |
| FFmpeg 安装问题 | 后端导出失败 | 提供 WebM 备选方案 |

---

## 附录：参考资料

- MediaRecorder API: https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder
- Playwright Video: https://playwright.dev/python/docs/video
- Leaflet Rotate: https://github.com/jieter/Leaflet.ROT
