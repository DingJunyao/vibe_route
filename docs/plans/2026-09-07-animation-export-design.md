# 动画导出服务端录制设计

日期：2026-09-07

## 背景

动画导出功能原为占位实现：`capture_animation_video` 不录制任何内容，sleep 后返回不存在的文件 URL。此前还修复了两个被掩盖的 bug（前端 `/api/v1` 前缀错误、后端 `TrackPoint.index` 字段名错误）。

## 目标

用 Playwright 服务端录制真实动画视频，导出画面与用户点击导出按钮时的视图完全一致。

## 架构

```
前端用户点导出
  → POST /api/animation/export（http 客户端带 token + 视图状态）
  → 后端查询 points（校验 + 计算时长）
  → 创建任务(pending) + background_tasks 启动录制
  → capture_animation_video:
     1. chromium.launch(headless) → new_context(viewport=分辨率, record_video_dir)
     2. add_init_script: 注入用户 token 到 localStorage
     3. goto FRONTEND_URL/tracks/{id}?export=true&speed=X&startTime=X&camera=X&...
     4. 等待完成信号（body[data-export-state]）
     5. close context → 视频落盘 → 移动到 exports/animation/
  → 任务 completed + download_url（前端已有轮询）
  → 前端 downloadFile 下载
```

### 关键机制

- **认证注入**：API 层从请求头取 `Authorization`，经 `page.add_init_script` 写入 localStorage——复用导出用户自己的会话，无新安全面
- **完成信号**：前端导出模式播放完成/失败时设置 `document.body.dataset.exportState`；服务端 `page.wait_for_selector('body[data-export-state]')` 等待
- **实时进度**：前端播放循环中（已节流）把百分比写入 `body.dataset.exportProgress`，服务端轮询 `page.evaluate` 读取 → 映射 10%-100%
- **超时兜底**：`(时长/速度)*2 + 60s`

## 视图状态传递

### 状态收集（点击导出时）

| 状态 | 来源 |
|------|------|
| 起点 `startTime` | `animationStore.currentTime`（用户当前播放位置 ms） |
| 轨迹模式 `cameraMode` | `animationStore.cameraMode`（full / fixed-center） |
| 朝向/标记/信息面板 | `animationStore.orientationMode / markerStyle / showInfoPanel` |
| 地图图层 `layerId` | `mapRef.getCurrentLayerId()`（已暴露） |
| 缩放与中心 | `mapRef.getCurrentViewState()`（需新增到 defineExpose） |

地图引擎本身来自后端用户配置，注入 token 后页面自动加载一致。

### 传递路径

```
ExportConfig 扩展 → POST 请求体 → AnimationExportRequest schema
→ background_tasks.add_task(capture_animation_video, ..., view_state)
→ URL 查询参数
```

不存任务表（YAGNI：无重试/恢复需求），省去跨 3 引擎 DB 迁移。

### 导出模式页面（TrackDetail）

解析 URL 参数 → 应用相机/朝向/标记/HUD → `setMapViewState(center, zoom)` → `seek(startTime)` → 自动播放 → 写进度/完成信号。

## 范围裁剪

- 格式：仅 webm（Playwright 输出格式），对话框不显示格式选项
- 帧率：Playwright 录制帧率不可精确控制，对话框不显示帧率选项
- 分辨率保留（= 录制视口），HUD、倍速保留

## 错误处理

| 场景 | 处理 |
|------|------|
| 页面加载超时 | `wait_for_selector('.map-content', 30s)` 超时 → 任务 failed |
| 播放失败 | 前端 `data-export-state="failed"` → 服务端抛异常 |
| 整体超时 | `(duration/speed)*2 + 60s` 上限 |
| Chromium 未安装 | Playwright 抛错 → 任务 failed |

错误全部汇入既有任务状态机（`animation_export.py` 的 try/except → failed）。

## 配置

- `settings.FRONTEND_URL`（默认 `http://localhost:5173`）：录制页地址，替换硬编码

## 验证

- 后端 `py_compile` + 前端 `vite build`
- 端到端：真实浏览器触发一次导出，确认视频生成、内容正确（Edge DevTools MCP 观察）
