"""
添加 memo 列到 track_points 表

运行方式：
    cd backend
    python scripts/add_memo_column.py
"""
import sqlite3
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def add_memo_column():
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'vibe_route.db')

    print(f"Database path: {db_path}")
    print(f"Database exists: {os.path.exists(db_path)}")

    if not os.path.exists(db_path):
        print("ERROR: Database file not found!")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 检查 memo 列是否已存在
    cursor.execute("PRAGMA table_info(track_points)")
    columns = cursor.fetchall()
    has_memo = any(col[1] == 'memo' for col in columns)

    if has_memo:
        print("memo column already exists!")
        conn.close()
        return True

    # 添加 memo 列
    try:
        cursor.execute("ALTER TABLE track_points ADD COLUMN memo TEXT")
        conn.commit()
        print("SUCCESS: memo column added to track_points table!")
        return True
    except Exception as e:
        print(f"ERROR: Failed to add column: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = add_memo_column()
    sys.exit(0 if success else 1)
