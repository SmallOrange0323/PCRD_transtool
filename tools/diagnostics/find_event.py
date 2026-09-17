import sqlite3
import os
import json

db_path = 'dashboard/redive_tw.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

# 搜尋包含 "夏天" 或 "最糟" 或 "開幕" 的劇情或活動
query_terms = ["最糟", "夏天", "開幕", "秘書"]

for t in ['event_story_data', 'event_top_adv', 'story_detail', 'hatsune_special_boss_ticket']:
    try:
        c.execute(f"SELECT * FROM {t} LIMIT 1")
        cols = [d[0] for d in c.description]
        print(f"Checking table {t} with cols {cols}")
        for col in cols:
            for term in query_terms:
                c.execute(f"SELECT * FROM {t} WHERE CAST({col} AS TEXT) LIKE ? LIMIT 5", (f"%{term}%",))
                res = c.fetchall()
                if res:
                    print(f"  Match in {t}.{col} for '{term}': {len(res)} rows")
                    for row in res[:3]:
                        print("   ", row)
    except Exception as e:
        pass

# 也檢查 chapters.json
chap_path = 'dashboard/data/chapters.json'
if os.path.exists(chap_path):
    with open(chap_path, 'r', encoding='utf-8') as f:
        chaps = json.load(f)
    print("Checking chapters.json...")
    for item in chaps:
        title = item.get('title', '')
        for term in query_terms:
            if term in title:
                print("  Chapter match:", item)
