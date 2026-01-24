import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

# 连接数据库
db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'vibe_route.db')
engine = create_engine(f'sqlite:///{db_path}')

with engine.connect() as conn:
    # 检查 memo 列
    result = conn.execute(text("PRAGMA table_info(track_points)"))
    columns = result.fetchall()
    has_memo = any(col[1] == 'memo' for col in columns)

    print(f"Has memo column: {has_memo}")

    if not has_memo:
        print("Adding memo column...")
        conn.execute(text("ALTER TABLE track_points ADD COLUMN memo TEXT"))
        conn.commit()
        print("Memo column added successfully!")
    else:
        print("Memo column already exists")
