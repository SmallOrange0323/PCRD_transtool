# -*- coding: utf-8 -*-
import sqlite3
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

db_path = 'dashboard/redive_tw.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 探測表一：v1_1cce670d294c2e33b6e52da88a1f53a6b03213208454ff8cd39d1994e79e5577 (可能為 chara_story_story_group)
t1 = "v1_1cce670d294c2e33b6e52da88a1f53a6b03213208454ff8cd39d1994e79e5577"
print(f"=== 探測表 {t1} ===")
try:
    cur.execute(f"SELECT * FROM \"{t1}\" WHERE \"3372fa8ffc94594f6c11ab7d1fad16166e608b84aa10a59f12a34f3dc35c8279\" = 138301")
    rows = cur.fetchall()
    for r in rows:
        print(r)
except Exception as e:
    print("Error:", e)

# 探測表二：v1_ee40c0099888c2f48a09d48a47942ab1dbfd4f92b945836cfa1418d067d64ed7
t2 = "v1_ee40c0099888c2f48a09d48a47942ab1dbfd4f92b945836cfa1418d067d64ed7"
print(f"\n=== 探測表 {t2} ===")
try:
    cur.execute(f"SELECT * FROM \"{t2}\" WHERE \"36c4216a2bf3e366578ae5d1379b7ad5d008a8264163036629b0f6255b4c24d2\" = 138301")
    rows = cur.fetchall()
    for r in rows:
        print(r)
except Exception as e:
    print("Error:", e)

# 探測表三：v1_66502a58d3c3751f010e01269ca3ad6089d6a410b26c356ac0676cf662da2d22
t3 = "v1_66502a58d3c3751f010e01269ca3ad6089d6a410b26c356ac0676cf662da2d22"
print(f"\n=== 探測表 {t3} ===")
try:
    # 含有 138301 的欄位
    cur.execute(f"PRAGMA table_info(\"{t3}\")")
    cols = [c[1] for c in cur.fetchall()]
    # 尋找含有 138301 的行
    for c in cols:
        cur.execute(f"SELECT * FROM \"{t3}\" WHERE \"{c}\" = 138301")
        rows = cur.fetchall()
        if rows:
            print(f"欄位 {c}:")
            for r in rows:
                print(r)
except Exception as e:
    print("Error:", e)

conn.close()
