import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('dashboard/redive_tw.db')
conn.text_factory = lambda x: x.decode('utf-8', errors='replace')
cursor = conn.cursor()

keywords = ['幻變少女', '少女', 'マホ', 'メモリアル', '主線', 'メイン']

for kw in keywords:
    cursor.execute(f"SELECT story_id, title FROM story_detail WHERE title LIKE '%{kw}%'")
    results = cursor.fetchall()
    print(f"\n包含「{kw}」的資料 ({len(results)} 筆)：")
    for story_id, title in results[:10]:
        print(f"  story_id: {story_id}, title: {title}")
    if len(results) > 10:
        print(f"  ... 還有 {len(results) - 10} 筆")

conn.close()