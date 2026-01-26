import sqlite3

conn = sqlite3.connect('D:/code/vibe_route/backend/data/vibe_route.db')
cursor = conn.cursor()

# 检查列是否存在
cursor.execute('PRAGMA table_info(invite_codes)')
columns = cursor.fetchall()
column_names = [col[1] for col in columns]

if 'is_valid' not in column_names:
    cursor.execute('ALTER TABLE invite_codes ADD COLUMN is_valid BOOLEAN DEFAULT 1 NOT NULL')
    conn.commit()
    print('Added is_valid column to invite_codes table')
else:
    print('is_valid column already exists')

conn.close()
