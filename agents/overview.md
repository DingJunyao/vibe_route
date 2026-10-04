# 项目概述

## Vibe Route - 全栈 Web 轨迹管理系统

基于 [gpxutil](https://github.com/DingJunyao/gpxutil) 构建。用户上传 GPX 文件，系统解析轨迹、坐标转换（WGS84/GCJ02/BD09）、地理编码填充、地图可视化。

## 开发环境

- **Python**: Anaconda 环境 `vibe_route`，所有 Python 操作需切换到此环境。如果没有 Anaconda，请寻找项目是否有 venv。
- **后端**：后端根目录在 `backend` 目录下。所有与后端相关的操作均在 `backend` 目录下，使用前述 Python 环境运行。
- **前端**：前端根目录在 `frontend` 目录下。所有与前端相关的操作均在 `frontend` 目录下运行。
- **数据库**: 查看 `backend/.env` 确定。一般来说是 SQLite。如果要使用 worktree，需要复制一份数据库文件。
- **浏览器**:
  - Windows: Edge 远程调试
    ```powershell
    Stop-Process -Name msedge -Force; Start-Sleep -Milliseconds 500; Start-Process "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" -ArgumentList "--remote-debugging-port=9222"
    ```
  - Linux: Chromium
- **开发服务**: 前后端热重载已开启，任务中不再启动/关闭服务。

## 前端地址

前端运行在 `http://localhost:5173`
