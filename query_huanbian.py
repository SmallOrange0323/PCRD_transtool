import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('dashboard/redive_tw.db')
conn.text_factory = lambda x: x.decode('utf-8', errors='replace')
cursor = conn.cursor()

cursor.execute("SELECT story_id, title FROM story_detail WHERE title LIKE '%幻變%'")
results = cursor.fetchall()

print(f"找到 {len(results)} 筆包含「幻變」的資料：")
for story_id, title in results:
    print(f"  story_id: {story_id}, title: {title}")

conn.close()