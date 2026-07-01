# -*- coding: utf-8 -*-
import sqlite3
import urllib.request
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在深度查詢『佩可莉姆（阿斯特萊亞）』(ID: 138301) 的技能、個人劇情與 CDN 數據 ===")

db_path = 'dashboard/redive_jp.db'
if not os.path.exists(db_path):
    print("找不到日版資料庫")
    sys.exit(0)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 1. 查詢角色基本資訊與數值/技能
cur.execute("SELECT unit_id, unit_name, comment, motion_type FROM unit_data WHERE unit_id = 138301 OR unit_id = 138331")
unit_info = cur.fetchall()
print("\n[角色基本資料]:", unit_info)

# 2. 查詢個人劇情 (Chara Story)
cur.execute("SELECT story_id, title, sub_title FROM chara_story_detail WHERE story_id LIKE '1383%' OR title LIKE '%ペコリーヌ%' AND title LIKE '%アストレア%' OR story_id LIKE '%1383%'")
stories = cur.fetchall()

if not stories:
    # 從 chara_story_story_group 或是 story_detail / chara_story_detail 搜尋
    cur.execute("SELECT story_id, title, sub_title FROM chara_story_detail WHERE story_id >= 1138300 AND story_id < 1138400")
    stories = cur.fetchall()

print(f"\n[個人劇情列表 (找到 {len(stories)} 話)]:")
for s in stories:
    print(f"  - 話數 ID: {s[0]} | 標題: {s[1]} - {s[2]}")

# 3. 測試 CDN 音檔 (第一個語音檔 vo_adv_storyid_000.m4a)
if stories:
    sample_story_id = stories[0][0]
    sample_vo = f"vo_adv_{sample_story_id}_000.m4a"
    url = f"https://redive.estertion.win/sound/story_vo/{sample_vo}"
    vo_ok = False
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=3)
        if res.status == 200: vo_ok = True
    except: pass
    print(f"\n[CDN 語音檔測試]: {sample_vo} -> {'✅ 已上架可下載' if vo_ok else '❌ 尚無音檔 (404)'}")
else:
    print("\n[個人劇情]: 未在 chara_story_detail 中查到故事組記錄")
