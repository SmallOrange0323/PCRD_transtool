# -*- coding: utf-8 -*-
import sqlite3
import urllib.request
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('dashboard/redive_jp.db')
cur = conn.cursor()

print("=== 正在查詢 138301 佩可莉姆（阿斯特萊亞）完整技能與個人劇情數據 ===")

# 1. 技能 ID
cur.execute("SELECT unit_id, UB1, UB2, skill_1, skill_2 FROM unit_skill_data WHERE unit_id = 138301 OR unit_id = 138331")
skills = cur.fetchall()
print("\n[技能結構 ID (UB & 一般技能)]:", skills)

if skills:
    ub_id, s1_id, s2_id = skills[0][1], skills[0][3], skills[0][4]
    cur.execute("SELECT skill_id, name, description FROM skill_data WHERE skill_id IN (?, ?, ?)", (ub_id, s1_id, s2_id))
    skill_details = cur.fetchall()
    print("\n[技能名稱與詳細說明]:")
    for sk in skill_details:
        print(f"  - 技能 ID {sk[0]}: 【{sk[1]}】")
        print(f"    說明: {sk[2]}")

# 2. 個人劇情
# 查詢角色對應的 chara_index_id 或是 story_group_id
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%chara%'")
chara_tables = [r[0] for r in cur.fetchall()]
print("\n[個人劇情相關資料表]:", chara_tables)

cur.execute("SELECT story_id, title, sub_title FROM story_detail WHERE story_id >= 1000000 AND story_id < 2000000 AND (title LIKE '%ペコ%' OR sub_title LIKE '%ペコ%') ORDER BY story_id DESC LIMIT 10")
stories = cur.fetchall()
print("\n[最新個人劇情選集]:", stories)
