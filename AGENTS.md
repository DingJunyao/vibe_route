# AGENTS.md

Vibe Route - 全栈 Web 轨迹管理系统

本文件是面向各类 AI 编程智能体（Claude Code、Codex CLI、Cursor、ZCode 等）的统一项目说明入口，原 `CLAUDE.md` 已重命名并通用化至此。

## 开发情况

本项目为 monorepo 项目，包含前端和后端。

### 前端

技术栈：TypeScript + Vue + Vite + Element UI

目录：`frontend`，所有前端相关操作均在此目录下进行。

开发 URL：`http://localhost:5173`

通常会打开浏览器调试。如有需要，优先使用当前智能体可用的浏览器工具（如 Chrome DevTools MCP 或等价的浏览器调试/自动化能力）查看页面情况、操作页面；开发者浏览器一般情况下已经打开了页面，因此不要自行启动 Playwright 等新的浏览器实例。开发者在 Windows 下使用 Edge 浏览器，在 Linux 下使用 Chromium 浏览器。

响应式设计，移动端和桌面端的断点为 1366 px。

开发时要兼顾不同地图引擎和桌面、移动端的体验。

目前需要考虑的地图引擎如下：

- 高德地图
- 百度地图（分为 GL 版本和 Legacy 版本，前者常用，后者只在一些特殊场景下使用）
- 腾讯地图
- Leaflet：目前支持高德地图、百度地图、腾讯地图、天地图、OpenStreetMap。

### 后端

技术栈：Python + FastAPI

目录：`backend`，所有后端相关操作均在此目录下进行，并且使用虚拟环境。

虚拟环境：先找 `conda` 下的 `vibe_route` 环境，没有则使用 `.venv` 下的环境。

### 数据库

数据库：`backend/.env` 文件中指定。一般情况下为 `backend/data/vibe_route.db`。

数据库操作优先使用数据库相关的 MCP。

开发过程中不要自行修改数据库，除非开发者明确允许此操作。

表结构需要变动时，除了维护 alembic 外，还需要提供对应的 SQL 脚本，包括以下数据库引擎的版本：

- SQLite
- MySQL
- PostgreSQL（未启用 PostGIS 支持）
- PostgreSQL（启用 PostGIS 支持）（如与 PostGIS 无关，则不需要此项）

### 测试

所有操作均需确保无语法层面上的报错，构建、编译通过。

### 记录要点

当某项开发工作完成、告一段落或有关键性进展时，需要自动记录要点。用户要求记录要点时，也要记录。

要点按照以下的索引记录。

注意：为了节约 token，即便用户要求记录到 AGENTS.md（或 CLAUDE.md 等其他指令文件），也要按照下面的索引记录。

## 项目索引

本项目文档已模块化拆分，按需加载以提高性能。详细信息请查看 `./agents` 目录下的对应文件。

### 文档模块

| 文件 | 描述 | 加载场景 |
|------|------|----------|
| [`agents/overview.md`](./agents/overview.md) | 项目概述、开发环境 | 项目初始化、环境配置 |
| [`agents/workflow.md`](./agents/workflow.md) | 工作流规范、测试、审查 | 问题诊断、代码审查 |
| [`agents/quick-commands.md`](./agents/quick-commands.md) | 快速命令（ARM/x86） | 环境搭建、服务启动 |
| [`agents/architecture.md`](./agents/architecture.md) | 架构核心、认证、多坐标系 | 架构设计、功能开发 |
| [`agents/map-components.md`](./agents/map-components.md) | 地图组件、缩放 | 地图相关开发 |
| [`agents/features.md`](./agents/features.md) | 各功能模块详解 | 功能开发、问题修复 |
| [`agents/development.md`](./agents/development.md) | 开发规范、UI规范 | 新功能开发、UI 调整 |
| [`agents/changelog.md`](./agents/changelog.md) | 变更历史 | 版本升级、问题排查 |

## 快速导航

### 环境搭建
- ARM 平台安装 → [`agents/quick-commands.md`](./agents/quick-commands.md)
- x86 平台安装 → [`agents/quick-commands.md`](./agents/quick-commands.md)

### 问题诊断
- 诊断流程 → [`agents/workflow.md`](./agents/workflow.md)
- MCP 使用 → [`agents/workflow.md`](./agents/workflow.md)

### 开发任务
- 添加 API 端点 → [`agents/development.md`](./agents/development.md)
- 添加前端页面 → [`agents/development.md`](./agents/development.md)
- 数据库模型 → [`agents/architecture.md`](./agents/architecture.md)

### 地图相关
- Tooltip 定位 → [`agents/map-components.md`](./agents/map-components.md)
- 坐标系转换 → [`agents/architecture.md`](./agents/architecture.md)
- 地图缩放 → [`agents/map-components.md`](./agents/map-components.md)

### 功能模块
- 实时记录 → [`agents/features.md`](./agents/features.md)
- 地理编码 → [`agents/features.md`](./agents/features.md)
- 轨迹插值 → [`agents/features.md`](./agents/features.md)
- 覆盖层模板 → [`agents/features.md`](./agents/features.md)
- 海报生成 → [`agents/features.md`](./agents/features.md)
