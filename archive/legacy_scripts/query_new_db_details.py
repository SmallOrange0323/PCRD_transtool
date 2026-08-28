# -*- coding: utf-8 -*-
import sys

print(
    "[LEGACY ARCHIVE ONLY] This historical investigation script is disabled. "
    "Use current diagnostics/fetch tooling instead."
)
sys.exit(1)

import sqlite3

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在最新 00500026 版資料庫中檢索 栞(冬日) 與下月新活動 10215 ===")

conn = sqlite3.connect('dashboard/redive_tw.db')
cur = conn.cursor()

# 1. 再次檢索 栞(冬日)
cur.execute("SELECT unit_name, rarity FROM unit_data WHERE unit_id = 138801")
row = cur.fetchone()
if row:
    print(f"✅ 栞（冬日）基本數據已收錄！初始星等: {row[1]}")
    
    cur.execute("SELECT union_burst, main_skill_1, main_skill_2 FROM unit_skill_data WHERE unit_id = 138801")
    sk = cur.fetchone()
    if sk:
        print(f"  - 技能關聯已就緒: UB={sk[0]}, 技能1={sk[1]}, 技能2={sk[2]}")
        cur.execute("SELECT name, description FROM skill_data WHERE skill_id = ?", (sk[0],))
        ub = cur.fetchone()
        if ub:
            print(f"    ✨ UB名稱: {ub[0]}")
    else:
        print("  - ❌ 技能關聯依然缺失！")
else:
    print("❌ 栞（冬日）依然不在 unit_data 中！")

# 2. 檢索有無下個月新活動 (ID 10215)
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='event_story_detail'")
has_table = cur.fetchone()
if has_table:
    cur.execute("SELECT DISTINCT story_group_id, title FROM event_story_detail WHERE story_group_id = 10215")
    act = cur.fetchone()
    if act:
        print(f"✅ 成功找到 8 月份新形式活動 10215 資料！標題: {act[1]}")
    else:
        print("❌ 尚未在 event_story_detail 中找到 10215 活動。")
else:
    print("❌ 找不到 event_story_detail 表。")

conn.close()
