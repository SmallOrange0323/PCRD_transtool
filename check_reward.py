# -*- coding: utf-8 -*-
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('dashboard/redive_jp.db')
cur = conn.cursor()

print("=== 正在查詢 1383004 (阿斯特萊亞佩可 第 4 話) 的解鎖獎勵 (CG/插畫) ===")

cur.execute("""
    SELECT reward_type_1, reward_id_1, reward_type_2, reward_id_2, reward_type_3, reward_id_3 
    FROM story_detail 
    WHERE story_id = 1383004
""")
row = cur.fetchone()

if row:
    print(f"解鎖獎勵欄位:")
    for idx in range(3):
        rtype = row[idx * 2]
        rid = row[idx * 2 + 1]
        print(f"  - 獎勵 {idx+1}: 類型={rtype} | ID={rid}")
        if rtype == 8: # 8 通常代表 CG/Still 劇照解鎖！
            print(f"    ✨ 發現解鎖的 CG 插畫 ID (still_id): {rid}！")
else:
    print("找不到第 4 話紀錄")
