# CLAUDE.md

Vibe Route - 全栈 Web 轨迹管理系统

## 开发情况

本项目为 monorepo 项目，包含前端和后端。

### 前端

技术栈：TypeScrpt + Vue + Vite + Element UI

目录：`frontend`，所有前端相关操作均在此目录下进行。

开发 URL：`http://localhost:5173`

通常会打开浏览器调试。如有需要，可以使用 Chrome 开发者工具 MCP 查看页面情况，操作页面。由于一般情况下已经打开了页面，所以不要使用 Playwright。

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

数据库操作优先使用相应的 MCP。

开发过程中不要自行修改数据库，除非开发者明确允许此操作。

表结构需要变动时，除了维护 alembic 外，还需要提供对应的 SQL 脚本，包括一下数据库引擎的版本：

- SQLite
- MySQL
- PostgreSQL（未启用 PostGIS 支持）
- PostgreSQL（启用 PostGIS 支持）（如与 PostGIS 无关，则不需要此项）

### 测试

所有操作均需确保无语法层面上的报错，构建、编译通过。

### 记录要点

当某项开发工作完成、告一段落或有关键性进展时，需要自动记录要点。用户要求记录要点时，也要记录。

要点按照以下的索引记录。

注意：为了节约 token，即便用户要求记录到 CLAUDE.md，也要按照下面的索引记录。

## 项目索引

本项目文档已模块化拆分，按需加载以提高性能。详细信息请查看 `./cc` 目录下的对应文件。

### 文档模块

| 文件 | 描述 | 加载场景 |
|------|------|----------|
| [`cc/overview.md`](./cc/overview.md) | 项目概述、开发环境 | 项目初始化、环境配置 |
| [`cc/workflow.md`](./cc/workflow.md) | 工作流规范、测试、审查 | 问题诊断、代码审查 |
| [`cc/quick-commands.md`](./cc/quick-commands.md) | 快速命令（ARM/x86） | 环境搭建、服务启动 |
| [`cc/architecture.md`](./cc/architecture.md) | 架构核心、认证、多坐标系 | 架构设计、功能开发 |
| [`cc/map-components.md`](./cc/map-components.md) | 地图组件、缩放 | 地图相关开发 |
| [`cc/features.md`](./cc/features.md) | 各功能模块详解 | 功能开发、问题修复 |
| [`cc/development.md`](./cc/development.md) | 开发规范、UI规范 | 新功能开发、UI 调整 |
| [`cc/changelog.md`](./cc/changelog.md) | 变更历史 | 版本升级、问题排查 |

## 快速导航

### 环境搭建
- ARM 平台安装 → [`cc/quick-commands.md`](./cc/quick-commands.md)
- x86 平台安装 → [`cc/quick-commands.md`](./cc/quick-commands.md)

### 问题诊断
- 诊断流程 → [`cc/workflow.md`](./cc/workflow.md)
- MCP 使用 → [`cc/workflow.md`](./cc/workflow.md)

### 开发任务
- 添加 API 端点 → [`cc/development.md`](./cc/development.md)
- 添加前端页面 → [`cc/development.md`](./cc/development.md)
- 数据库模型 → [`cc/architecture.md`](./cc/architecture.md)

### 地图相关
- Tooltip 定位 → [`cc/map-components.md`](./cc/map-components.md)
- 坐标系转换 → [`cc/architecture.md`](./cc/architecture.md)
- 地图缩放 → [`cc/map-components.md`](./cc/map-components.md)

### 功能模块
- 实时记录 → [`cc/features.md`](./cc/features.md)
- 地理编码 → [`cc/features.md`](./cc/features.md)
- 轨迹插值 → [`cc/features.md`](./cc/features.md)
- 覆盖层模板 → [`cc/features.md`](./cc/features.md)
- 海报生成 → [`cc/features.md`](./cc/features.md)
