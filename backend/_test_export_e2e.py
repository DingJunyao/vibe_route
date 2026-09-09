# 临时端到端测试脚本（验证后删除）
import asyncio
import sys

import httpx
from sqlalchemy import select

from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.models.user import User


async def main() -> int:
    async with async_session_maker() as db:
        result = await db.execute(
            select(User.id).where(User.is_valid == True).order_by(User.id).limit(1)
        )
        user_id = result.scalar_one_or_none()
    if user_id is None:
        print("RESULT: no valid user found")
        return 1

    token = create_access_token({"sub": str(user_id)})

    async with httpx.AsyncClient(timeout=60) as client:
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post(
            "http://localhost:8000/api/animation/export",
            params={"track_id": 85},
            json={
                "resolution": "720p",
                "show_hud": True,
                "speed": 100.0,  # 测试倍速（轨迹 85 时长 4h14m）
                "start_time": 0,
                "camera_mode": "full",
                "orientation_mode": "north-up",
                "marker_style": "arrow",
                "show_info_panel": True,
            },
            headers=headers,
        )
        print(f"start: HTTP {resp.status_code}")
        if resp.status_code != 200:
            print("start body:", resp.text[:300])
            return 1
        task_id = resp.json()["task_id"]
        print(f"task_id: {task_id}")

        final = None
        for i in range(240):
            await asyncio.sleep(2)
            r = await client.get(
                f"http://localhost:8000/api/animation/export/{task_id}",
                headers=headers,
            )
            data = r.json()
            if i % 10 == 0 or data["status"] in ("completed", "failed", "cancelled"):
                print(f"  [{i * 2}s] {data['status']} progress={data['progress']}")
            if data["status"] in ("completed", "failed", "cancelled"):
                final = data
                break

        if final is None:
            print("RESULT: TIMEOUT")
            return 1

        print(f"RESULT: status={final['status']} error={final.get('error')}")
        print(f"RESULT: download_url={final.get('download_url')}")

        if final["status"] != "completed":
            return 1

        url = final["download_url"]
        r = await client.get(f"http://localhost:8000{url}")
        print(f"download check: HTTP {r.status_code} size={len(r.content)} bytes")
        return 0 if (r.status_code == 200 and len(r.content) > 1000) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
