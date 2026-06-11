import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('dashboard/redive_tw.db')
conn.text_factory = lambda x: x.decode('utf-8', errors='replace')
cursor = conn.cursor()

keywords = ['幻變', '真步', '第3部', '第三部', '幻変', 'マホ', '真步']

query = """
SELECT story_id, title 
FROM story_detail 
WHERE """ + " OR ".join([f"title LIKE '%{kw}%'" for kw in keywords])

cursor.execute(query)
results = cursor.fetchall()

print(f"找到 {len(results)} 筆相關資料：")
for story_id, title in results:
    print(f"  story_id: {story_id}, title: {title}")

conn.close()