# -*- coding: utf-8 -*-
"""tests 共享 fixture / helper

收编前的现状：`workdir`/`_db_env`/`_track_points`/`_gpx` 在
`test_region_propagation.py` 与 `test_import_multilanguage.py` 里各有一份逐字相同的拷贝，
`test_indonesia_shield.py` 还另有 `workdir`。`_db_env` 一旦要改（加模型、换
`expire_on_commit`），就得同步改多处，漏改是静默的（该文件的用例会用上缺模型的 schema）。
故收编到此处，各测试文件改为 `from conftest import _db_env, _track_points, _gpx`
（`workdir` 是 fixture，pytest 自动注入，无需 import）。

`tests/` 下无 `__init__.py`，pytest 走 prepend 导入模式并把本目录放进 `sys.path`，
故 `from conftest import ...` 可用（`from app.models import ...` 同样依赖 `backend/` 在 path 上）。
"""
import contextlib
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, TrackPoint, User


@pytest.fixture
def workdir():
    """临时目录（不用 pytest tmp_path：本机 %TEMP%/pytest-of-* 残留不可访问）"""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@contextlib.asynccontextmanager
async def _db_env(workdir):
    """独立 SQLite + 一个用户；退出时 dispose（Windows 下否则临时目录无法清理）"""
    engine = create_async_engine(f"sqlite+aiosqlite:///{workdir / 'test.db'}")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            user = User(username='u', email='u@example.com', hashed_password='x')
            db.add(user)
            await db.commit()
            await db.refresh(user)
            yield db, user
    finally:
        await engine.dispose()


async def _track_points(db, track_id):
    result = await db.execute(
        select(TrackPoint).where(TrackPoint.track_id == track_id).order_by(TrackPoint.point_index)
    )
    return list(result.scalars().all())


def _gpx(hour=8):
    pts = ''.join(
        f'<trkpt lat="{-7.280 - i * 0.001}" lon="{112.735 + i * 0.001}">'
        f'<ele>{10 + i}</ele><time>2026-09-01T{hour:02d}:00:{i * 10:02d}Z</time></trkpt>'
        for i in range(2)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<gpx version="1.1" creator="t" xmlns="http://www.topografix.com/GPX/1/1">'
        f'<trk><name>t</name><trkseg>{pts}</trkseg></trk></gpx>'
    )
