"""
WebSocket API 路由
用于实时推送轨迹更新
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Dict, Set
from loguru import logger
import json


class LiveTrackManager:
    """实时轨迹 WebSocket 连接管理器"""

    def __init__(self):
        # recording_id -> Set[WebSocket]
        self.recording_connections: Dict[int, Set[WebSocket]] = {}
        # track_id -> Set[WebSocket]
        self.track_connections: Dict[int, Set[WebSocket]] = {}

    async def connect_to_recording(self, websocket: WebSocket, recording_id: int):
        """连接到实时记录"""
        await websocket.accept()
        if recording_id not in self.recording_connections:
            self.recording_connections[recording_id] = set()
        self.recording_connections[recording_id].add(websocket)
        logger.info(f"WebSocket connected to recording {recording_id}")

    async def connect_to_track(self, websocket: WebSocket, track_id: int):
        """连接到轨迹"""
        await websocket.accept()
        if track_id not in self.track_connections:
            self.track_connections[track_id] = set()
        self.track_connections[track_id].add(websocket)
        logger.info(f"WebSocket connected to track {track_id}")

    def disconnect_from_recording(self, websocket: WebSocket, recording_id: int):
        """断开与实时记录的连接"""
        if recording_id in self.recording_connections:
            self.recording_connections[recording_id].discard(websocket)
            if not self.recording_connections[recording_id]:
                del self.recording_connections[recording_id]
        logger.info(f"WebSocket disconnected from recording {recording_id}")

    def disconnect_from_track(self, websocket: WebSocket, track_id: int):
        """断开与轨迹的连接"""
        if track_id in self.track_connections:
            self.track_connections[track_id].discard(websocket)
            if not self.track_connections[track_id]:
                del self.track_connections[track_id]
        logger.info(f"WebSocket disconnected from track {track_id}")

    async def broadcast_to_recording(self, recording_id: int, message: dict):
        """向订阅该实时记录的所有客户端广播消息"""
        if recording_id not in self.recording_connections:
            return

        disconnected = []
        for ws in self.recording_connections[recording_id]:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send message to WebSocket: {e}")
                disconnected.append(ws)

        # 清理断开的连接
        for ws in disconnected:
            self.recording_connections[recording_id].discard(ws)

        if not self.recording_connections[recording_id]:
            del self.recording_connections[recording_id]

    async def broadcast_to_track(self, track_id: int, message: dict):
        """向订阅该轨迹的所有客户端广播消息"""
        if track_id not in self.track_connections:
            return

        disconnected = []
        for ws in self.track_connections[track_id]:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send message to WebSocket: {e}")
                disconnected.append(ws)

        # 清理断开的连接
        for ws in disconnected:
            self.track_connections[track_id].discard(ws)

        if not self.track_connections[track_id]:
            del self.track_connections[track_id]

    def get_recording_connection_count(self, recording_id: int) -> int:
        """获取实时记录的连接数"""
        return len(self.recording_connections.get(recording_id, set()))

    def get_track_connection_count(self, track_id: int) -> int:
        """获取轨迹的连接数"""
        return len(self.track_connections.get(track_id, set()))


# 全局管理器实例
live_track_manager = LiveTrackManager()

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/live-recording/{recording_id}")
async def websocket_live_recording(
    websocket: WebSocket,
    recording_id: int,
    token: str = Query(..., description="认证 token"),
):
    """
    WebSocket 端点 - 实时记录更新推送

    连接后可接收以下类型的消息：
    - point_added: 新轨迹点添加
    - stats_updated: 统计信息更新

    消息格式：
    {
        "type": "point_added",
        "data": {
            "point_id": 123,
            "point_index": 5,
            "latitude": 39.9,
            "longitude": 116.4,
            "elevation": 50.0,
            "speed": 5.5,
            "time": "2024-01-01T12:00:00Z"
        }
    }
    """
    # 验证 token
    from app.core.database import async_session_maker
    from app.services.live_recording_service import live_recording_service

    async with async_session_maker() as db:
        recording = await live_recording_service.get_by_token(db, token)
        if not recording:
            await websocket.close(code=1008, reason="Invalid token")
            return

        if recording.id != recording_id:
            await websocket.close(code=1008, reason="Recording ID mismatch")
            return

        if recording.status != "active":
            await websocket.close(code=1000, reason="Recording is not active")
            return

    # 连接到管理器
    await live_track_manager.connect_to_recording(websocket, recording_id)

    # 发送连接成功消息
    await websocket.send_json({
        "type": "connected",
        "data": {
            "recording_id": recording_id,
            "message": "已连接到实时记录更新"
        }
    })

    try:
        while True:
            # 保持连接，接收客户端消息（心跳等）
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        live_track_manager.disconnect_from_recording(websocket, recording_id)
    except Exception as e:
        logger.error(f"WebSocket error for recording {recording_id}: {e}")
        live_track_manager.disconnect_from_recording(websocket, recording_id)


@router.websocket("/ws/track/{track_id}")
async def websocket_track(
    websocket: WebSocket,
    track_id: int,
    token: str = Query(..., description="认证 token"),
):
    """
    WebSocket 端点 - 轨迹更新推送

    与实时记录端点类似，但使用 track_id 订阅。
    适用于订阅已存在的轨迹（可能不是实时记录）。
    """
    # 验证 token（需要用户认证）
    from app.core.database import async_session_maker
    from app.services.live_recording_service import live_recording_service
    from app.services.user_service import user_service
    from app.core.security import decode_token

    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=1008, reason="Invalid token")
            return

        async with async_session_maker() as db:
            user = await user_service.get_by_id(db, int(user_id))
            if not user:
                await websocket.close(code=1008, reason="User not found")
                return

            # 验证轨迹存在且属于该用户
            from app.services.track_service import track_service
            track = await track_service.get_by_id(db, track_id, int(user_id))
            if not track:
                await websocket.close(code=1008, reason="Track not found")
                return

    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        await websocket.close(code=1008, reason="Authentication failed")
        return

    # 连接到管理器
    await live_track_manager.connect_to_track(websocket, track_id)

    # 发送连接成功消息
    await websocket.send_json({
        "type": "connected",
        "data": {
            "track_id": track_id,
            "message": "已连接到轨迹更新"
        }
    })

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        live_track_manager.disconnect_from_track(websocket, track_id)
    except Exception as e:
        logger.error(f"WebSocket error for track {track_id}: {e}")
        live_track_manager.disconnect_from_track(websocket, track_id)


# 辅助函数：发送新点添加通知
async def notify_point_added(
    recording_id: int,
    track_id: int,
    point_data: dict,
    stats_data: dict
):
    """
    当新点添加时通知所有订阅的客户端

    Args:
        recording_id: 实时记录 ID
        track_id: 轨迹 ID
        point_data: 新点数据
        stats_data: 更新后的统计信息
    """
    # 通知订阅该实时记录的客户端
    await live_track_manager.broadcast_to_recording(recording_id, {
        "type": "point_added",
        "data": {
            "track_id": track_id,
            "point": point_data,
            "stats": stats_data
        }
    })

    # 通知订阅该轨迹的客户端
    await live_track_manager.broadcast_to_track(track_id, {
        "type": "point_added",
        "data": {
            "recording_id": recording_id,
            "point": point_data,
            "stats": stats_data
        }
    })
