# 轨迹海报与截图功能设计

## 概述

为轨迹详情页添加海报生成功能，支持将轨迹数据导出为高清图片，用于社交分享和个人存档。

## 总体架构

### 组件架构

1. **ExportDialog 对话框**
   - 位置：轨迹详情页顶部工具栏
   - 配置选项：
     - 模板选择：简洁模板 / 丰富模板
     - 信息级别：基础信息 / 运动数据 / 经过区域
     - 尺寸预设：竖版 1080x1920 / 竖版 2160x3840（4K） / 横版 1920x1080 / 横版 3840x2160（4K） / 自定义
     - 水印开关
   - 实时预览（使用较小尺寸预览）
   - 导出按钮

2. **PosterGenerator 工具类**
   - `captureMap(mapRef, scale)`: 使用 html2canvas 截取地图
   - `drawPoster(canvas, track, config)`: Canvas 绘制海报内容
   - `downloadPoster(canvas, filename)`: 转换为 PNG 并下载

3. **模板系统**
   - `SimpleTemplate`: 简洁模板（基础信息 + 地图）
   - `RichTemplate`: 丰富模板（基础 + 运动数据 + 地图）
   - `GeoTemplate`: 地理模板（基础 + 经过区域 + 地图）

## 模板设计

### 简洁模板（SimpleTemplate）

- **布局**：上半部分地图（60%），下半部分信息卡片（40%）
- **信息内容**：
  - 轨迹名称（大标题）
  - 日期时间
  - 里程、时长（网格布局 2x1）
- **视觉风格**：卡片式设计，白色背景带阴影

### 丰富模板（RichTemplate）

- **布局**：左侧地图（50%），右侧信息面板（50%）
- **信息内容**（从上到下）：
  - 轨迹名称、日期
  - 运动数据网格（2x3）：里程、时长、平均速度、最高速度、爬升、下降
  - 运动类型图标（骑行/跑步/其他）
- **视觉风格**：现代运动风，渐变背景

### 地理模板（GeoTemplate）

- **布局**：简洁模板的变体，信息卡片中增加经过区域
- **信息内容**：
  - 轨迹名称、日期
  - 运动数据（1x2）：里程、时长
  - 经过区域（最多显示前 5 个区域，超过显示"..."）

## 数据流

### 生成流程

1. **用户配置阶段**
   - 打开导出对话框 → 选择模板、信息级别、尺寸
   - 点击"预览"按钮 → 生成预览图（使用 scale=1）
   - 点击"导出"按钮 → 开始正式生成

2. **地图捕获阶段**
   - 调用 `mapRef.value.fitBounds()` 将地图居中到完整轨迹
   - 调用 `html2capture(mapElement, { scale: targetScale })` 获取高清地图截图
   - 显示进度提示："正在捕获地图（scale=4）"

3. **海报绘制阶段**
   - 创建指定尺寸的 Canvas
   - 绘制背景（纯色/渐变/图片）
   - 绘制地图图片（根据模板布局定位）
   - 绘制文字和数据（使用轨迹 API 返回的数据）
   - 绘制水印（如果启用）

4. **导出阶段**
   - `canvas.toDataURL('image/png')` 转换为图片
   - 创建 `<a>` 标签触发下载
   - 文件名格式：`{轨迹名称}.png`

## 地图截图高清方案

### html2canvas scale 参数

- **1080P 海报**：`scale = 2`（生成相当于 2x 分辨率的截图）
- **4K 海报**：`scale = 4`（生成相当于 4x 分辨率的截图）

### 技术要点

- html2canvas 会按 scale 倍数放大 DOM 元素再截图
- 即使屏幕是 1080P，也能生成 4K 清晰度的地图
- scale=4 时内存消耗较大，需要显示加载提示

## 错误处理

### 地图捕获失败

- **场景**：html2canvas 截图失败（地图加载中、跨域问题等）
- **处理**：
  - 重试机制：最多重试 3 次，每次间隔 1 秒
  - 友好提示："地图捕获失败，请重试"
  - 降级方案：失败时使用低分辨率（scale=1）

### Canvas 绘制错误

- **场景**：Canvas 尺寸过大（4K）导致内存溢出
- **处理**：
  - 检测：捕获 `RangeError` 或内存相关异常
  - 提示："海报尺寸过大，建议降低分辨率"
  - 自动降级：切换到 scale=2 并重新生成

### 数据缺失

- **场景**：轨迹数据不完整（如缺少经过区域）
- **处理**：
  - 检测：启动前验证必需字段是否存在
  - 优雅降级：缺失字段显示"--"或跳过该部分
  - 提示："部分数据缺失，已自动调整"

### 网络问题

- **场景**：用户在弱网环境下操作
- **处理**：
  - 显示实时进度条
  - 超时提示（120 秒）
  - 可取消操作

## 测试策略

### 单元测试

- `PosterGenerator` 工具类测试
  - `drawPoster` 参数验证（尺寸、配置）
  - 不同模板的正确渲染
  - 水印开关功能

### 集成测试

- 完整生成流程测试
  - 不同尺寸（1080P、4K）生成
  - 不同地图提供商（高德、百度、腾讯、Leaflet）
  - 跨浏览器兼容性（Chrome、Edge、Firefox）

### 性能测试

- 生成时间测试
  - scale=1 / scale=2 / scale=4 的生成时间
  - 大量轨迹点（>10000 点）的表现
- 内存占用测试
  - 4K 海报生成时的内存峰值

### 视觉测试

- 预览图与最终图一致性
- 文字清晰度（特别是 scale=4 时）
- 布局正确性（地图、信息区域位置）

### 用户验收测试

- 社交分享：上传到微信、微博验证显示效果
- 个人存档：在不同设备查看

---

## 实施记录

**实施日期：** 2025-02-06
**实施状态：** 已完成

### 实施内容

1. 安装 html2canvas 依赖
2. 创建海报类型定义 (`frontend/src/types/poster.ts`)
3. 创建海报生成器工具类 (`frontend/src/utils/posterGenerator.ts`)
4. 创建海报导出对话框组件 (`frontend/src/components/PosterExportDialog.vue`)
5. 在轨迹详情页集成海报导出功能
6. 添加地图 DOM 元素获取接口
7. 实现错误处理和降级方案

### 文件清单

- 新增: `frontend/src/types/poster.ts`
- 新增: `frontend/src/utils/posterGenerator.ts`
- 新增: `frontend/src/components/PosterExportDialog.vue`
- 修改: `frontend/src/views/TrackDetail.vue`
- 修改: `frontend/src/components/map/UniversalMap.vue`
- 修改: `frontend/src/components/map/AMap.vue`
- 修改: `frontend/src/components/map/BMap.vue`
- 修改: `frontend/src/components/map/TencentMap.vue`
- 修改: `frontend/src/components/map/LeafletMap.vue`
- 修改: `frontend/package.json`

### 测试验证

- [x] 简洁模板生成
- [x] 丰富模板生成
- [x] 地理模板生成
- [x] 不同尺寸导出（1080P / 4K）
- [x] 水印开关功能
- [x] 错误处理和降级方案
- [x] 前端开发服务器编译成功
