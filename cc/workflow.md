# 工作流规范

## 工作流原则

### 问题诊断流程

```
Chrome DevTools MCP 分析
    ↓
添加调试日志
    ↓
用户提供日志/截图
    ↓
分析解决
```

**优先使用 MCP 工具**：
- `chrome-devtools` MCP 获取控制台错误、网络请求、性能分析
- 直接检查数据库状态
- 截图验证前端显示

### 代码修改验证

每次代码修改后必须：
1. **编译通过**: 前端在 `frontend` 目录下执行 `npm run build`，后端 Python 语法检查
2. **功能测试**: 运行相关测试
3. **lint 检查**: 项目有 lint 时运行

**不通过不结束任务**。

### 任务完成标准

- 编译通过，测试通过
- 用户验证（如需要）
- 大任务完成后整理要点到本文件
- 保持文件大小 < 40KB（压缩历史版本到独立文件）

## 开发环境状态

- **前端服务**: 通常已运行 `npm run dev`（热重载）
- **后端服务**: 通常已运行 `uvicorn app.main:app --reload`（热重载）
- **操作原则**: 任务中**不再启动/关闭**已有服务
- **Python 环境**: Anaconda 环境 `vibe_route`，所有 Python 操作需切换到此环境

## 调试工具使用

### Chrome DevTools MCP

当需要调试前端问题时：

1. 确保浏览器以远程调试模式运行。如果没有运行，提示用户执行（以下语句不要自己执行！）：
   ```powershell
   # Windows (Edge)
   Stop-Process -Name msedge -Force;
   Start-Sleep -Milliseconds 500;
   Start-Process "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" -ArgumentList "--remote-debugging-port=9222"
   ```

2. 使用 MCP 工具：
   - `list_console_messages` - 查看控制台日志
   - `list_network_requests` - 查看网络请求
   - `take_screenshot` - 截取页面
   - `get_console_message` - 获取特定消息

3. 日志分析：
   - 搜索 `[标签]` 格式的日志（如 `[AMap]`, `[TrackDetail]`）
   - 优先分析 ERROR 级别
   - 检查网络请求状态码

### 数据库检查

需要时使用 MCP 或直接 SQL 查询验证数据状态。

**重要约束**：
- ✅ 可以：使用 MCP 查询/验证数据状态
- ❌ 禁止：直接修改数据库数据
- ⚠️ 数据显示问题：优先检查前端/后端逻辑，非必要不直接改数据库

## 文档更新规范

### CLAUDE.md 维护

- **大小限制**: < 40KB
- **压缩策略**: 详细内容移至 `ref/CLAUDE_ARCHIVE.md` 或 `./cc` 目录
- **更新时机**: 大功能完成后
- **格式**: 简洁表格 + 关键代码片段

### 代码注释

- 与现有代码保持一致的语言风格
- 复杂逻辑添加解释注释
- 不注释显而易见的代码

## Tips

当遇到 Edit 失败报错时，使用 serena 来编辑代码。

### 开发检查清单

For map coordinate conversions, always use the MapService.covert_coords method with provider-specific transformations. AMap/Tencent use GCJ-02, Baidu uses BD-09, Leaflet uses WGS-84.

For text alignment and wrapping features: always test justify overflow, control point positioning when toggling wrap mode, and width adjustment in non-wrap mode before considering implementation complete.

When handling Chinese characters in font uploads or text display, always use UTF-8 encoding and check for full-width vs single-width quote/comparison operator issues.

For undo/redo implementation: always debounce state recording during drag operations, avoid naming conflicts with browser 'history' object, and test multi-step undo jumps.

For control handles on bounding boxes: use shouldShowHandle function instead of hasLineHeight in v-if conditions, align handles to bounding box edges, and display N/S handles when acting as anchors even without line wrapping.

Before fixing any UI bug, first use chrome-devtools to take a snapshot and inspect the computed CSS styles, Vue component state, and actual rendered DOM. Then identify the root cause before editing code.

After implementing any text alignment or control point feature, test: (1) justify mode overflow, (2) wrap mode toggle detaching controls, (3) width adjustment when wrap disabled, (4) coordinate switching across AMap/Baidu/Tencent/Leaflet, (5) control point display after provider switch. Only consider complete when all pass.

For any coordinate or marker-related fix: (1) Test coordinate conversion works for all four providers (AMap=GCJ-02, Baidu=BD-09, Tencent=GCJ-02, Leaflet=WGS-84), (2) Verify green latest-point markers display correctly on each, (3) Switch between providers and confirm control points still render, (4) Use MapService.convert_coords consistently, never manually transform coordinates.

## Testing

用户会在开发过程中对项目多次测试。当用户对项目中存在的问题询问时，除一般的逻辑外，还应当考虑到：

- 数据库里面的数据
- 前端的显示效果

这些都可以使用插件或 MCP 解决。优先考虑 MCP。

## Reviewing

在合适的情况下，或者是用户提出审查项目时，使用 code-review-excellence skill 来审查这个项目。排除 ./ref_gpxutil。

审查结果存入 ./ref/CODE_REVIEW_REPORT.md，如果已存在，则覆盖它。

## 应急流程

### 编译失败
1. 检查语法错误
2. 检查导入依赖
3. 检查类型定义
4. 逐个修复直到通过

### 测试失败
1. 分析失败原因
2. 添加调试日志
3. 修复代码
4. 重新测试

### 无法定位问题
1. 使用 Chrome DevTools 深入分析
2. 添加详细日志重现
3. 最小化复现步骤
4. 向用户提供复现路径

## Summarize

每次大的更改，当用户提出整理要点，都要把要点记录在本文件中。
