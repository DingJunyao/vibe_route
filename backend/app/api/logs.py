"""
日志转发 API
用于接收前端日志并通过 WebSocket 推送到查看器
"""
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List
import json

from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(tags=["logs"])


class LogEntry(BaseModel):
    """日志条目"""
    level: str  # log, info, warn, error
    tag: str  # 日志标签（如 [AMap]）
    message: str  # 日志消息
    data: dict | None = None  # 附加数据
    timestamp: float  # 时间戳


# WebSocket 连接管理器
class LogViewerManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, subprotocol: str | None = None):
        await websocket.accept(subprotocol=subprotocol)
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """广播日志到所有连接的查看器"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # 清理断开的连接
        for conn in disconnected:
            self.disconnect(conn)


manager = LogViewerManager()


@router.post("/logs")
async def receive_log(
    entry: LogEntry,
    current_user: User = Depends(get_current_user),
):
    """
    接收前端日志并广播到所有 WebSocket 查看器

    前端调用示例：
    fetch('/api/logs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            level: 'log',
            tag: '[AMap]',
            message: '地图被点击',
            data: { lnglat: {...} },
            timestamp: Date.now()
        })
    })
    """
    # 广播到所有 WebSocket 连接的查看器
    await manager.broadcast({
        "type": "log",
        "data": entry.model_dump()
    })

    return JSONResponse(content={"status": "ok"})


@router.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """
    WebSocket 端点，用于实时查看日志

    在电脑浏览器中连接：
    const ws = new WebSocket('ws://192.168.x.x:8000/api/ws/logs');
    ws.onmessage = (event) => {
        const log = JSON.parse(event.data);
        console.log(log.data);
    };
    """
    from app.core.database import async_session_maker
    from app.core.security import decode_token
    from app.services.user_service import user_service

    protocol_header = websocket.headers.get("sec-websocket-protocol", "")
    protocols = [part.strip() for part in protocol_header.split(",") if part.strip()]
    token = protocols[1] if len(protocols) >= 2 and protocols[0] == "bearer" else None

    try:
        payload = decode_token(token) if token else None
        user_id = payload.get("sub") if payload else None
        if not user_id:
            await websocket.close(code=1008, reason="Invalid token")
            return

        async with async_session_maker() as db:
            user = await user_service.get_by_id(db, int(user_id))
            if not user or not user.is_active:
                await websocket.close(code=1008, reason="User not found")
                return
    except Exception:
        await websocket.close(code=1008, reason="Authentication failed")
        return

    await manager.connect(websocket, subprotocol="bearer")

    # 发送连接成功消息
    await websocket.send_json({
        "type": "connected",
        "message": "日志查看器已连接"
    })

    try:
        while True:
            # 保持连接，接收客户端的心跳或控制消息
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
