# -*- coding: utf-8 -*-
import sqlite3
import shutil
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JP_DB = os.path.join(BASE_DIR, "dashboard", "redive_jp.db")
TW_DB = os.path.join(BASE_DIR, "dashboard", "redive_tw.db")
BACKUP_DB = os.path.join(BASE_DIR, "dashboard", "redive_tw.db.bak")

print("====================================================")
print("🛠️ 開始執行 PCRD 台服資料庫自動解密還原流程...")
print("====================================================")

# 1. 備份 TW DB
if not os.path.exists(BACKUP_DB):
    print(f"📦 備份原始混淆資料庫: {TW_DB} -> {BACKUP_DB}")
    shutil.copy(TW_DB, BACKUP_DB)
else:
    print(f"📦 已存在備份檔 {BACKUP_DB}，將從備份還原並進行解密，確保乾淨的操作。")
    shutil.copy(BACKUP_DB, TW_DB)

# 2. 連接資料庫
conn_jp = sqlite3.connect(JP_DB)
conn_tw = sqlite3.connect(TW_DB)
cur_jp = conn_jp.cursor()
cur_tw = conn_tw.cursor()

# 3. 取得日服明文表結構
cur_jp.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
jp_tables = [r[0] for r in cur_jp.fetchall()]

# 構建日服表的欄位結構特徵
jp_table_schemas = {}
for table in jp_tables:
    cur_jp.execute(f"PRAGMA table_info(\"{table}\")")
    cols = cur_jp.fetchall()
    # 儲存結構: [(col_id, name, type, notnull, dflt_value, pk), ...]
    # 特徵使用 (欄位總數, [欄位類型], [是否為主鍵])
    col_types = [c[2] for c in cols]
    col_pks = [c[5] for c in cols]
    jp_table_schemas[table] = {
        "cols": [c[1] for c in cols],
        "feature": (len(cols), tuple(col_types), tuple(col_pks))
    }

# 4. 取得台服混淆表結構
cur_tw.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'v1_%'")
tw_obfuscated_tables = [r[0] for r in cur_tw.fetchall()]

tw_table_features = {}
for table in tw_obfuscated_tables:
    try:
        cur_tw.execute(f"PRAGMA table_info(\"{table}\")")
        cols = cur_tw.fetchall()
        col_names = [c[1] for c in cols]
        col_types = [c[2] for c in cols]
        col_pks = [c[5] for c in cols]
        tw_table_features[table] = {
            "cols": col_names,
            "feature": (len(cols), tuple(col_types), tuple(col_pks))
        }
    except Exception:
        pass

print(f"📋 日服明文表數量: {len(jp_tables)}")
print(f"📋 台服混淆表數量: {len(tw_obfuscated_tables)}")

# 5. 進行匹配與重命名
matched_count = 0
unmatched_tables = []

for jp_table, jp_info in jp_table_schemas.items():
    jp_feature = jp_info["feature"]
    
    # 尋找匹配特徵的台服混淆表
    candidates = []
    for tw_table, tw_info in tw_table_features.items():
        if tw_info["feature"] == jp_feature:
            candidates.append(tw_table)
            
    # 如果只有唯一候選者，則是完美匹配！
    if len(candidates) == 1:
        tw_table = candidates[0]
        try:
            # A. 重命名資料表
            cur_tw.execute(f"ALTER TABLE \"{tw_table}\" RENAME TO \"{jp_table}\"")
            
            # B. 重命名欄位 (SQLite 3.25.0+ 支援 ALTER TABLE RENAME COLUMN)
            tw_cols = tw_table_features[tw_table]["cols"]
            jp_cols = jp_info["cols"]
            for tw_col, jp_col in zip(tw_cols, jp_cols):
                if tw_col != jp_col:
                    cur_tw.execute(f"ALTER TABLE \"{jp_table}\" RENAME COLUMN \"{tw_col}\" TO \"{jp_col}\"")
                    
            matched_count += 1
        except Exception as e:
            print(f"❌ 還原表 {jp_table} 失敗: {e}")
    else:
        unmatched_tables.append((jp_table, len(candidates)))

# 提交變更
conn_tw.commit()

print("====================================================")
print(f"🎉 解密還原完成！ 成功匹配並解密表數: {matched_count} / {len(jp_tables)}")
print(f"⚠️ 未成功匹配的明文表數量: {len(unmatched_tables)}")
print("====================================================")

conn_jp.close()
conn_tw.close()
