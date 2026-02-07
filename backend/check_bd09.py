import sqlite3
conn = sqlite3.connect('data/vibe_route.db')
cursor = conn.cursor()
cursor.execute('SELECT latitude_bd09, longitude_bd09 FROM track_points WHERE is_valid = 1 LIMIT 3')
print('BD09 coordinates:')
for row in cursor.fetchall():
    print(row)
conn.close()
