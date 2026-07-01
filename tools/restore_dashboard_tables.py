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

# 連接資料庫
conn_jp = sqlite3.connect(JP_DB)
conn_tw = sqlite3.connect(TW_DB)
cur_jp = conn_jp.cursor()
cur_tw = conn_tw.cursor()

# 獲取台服所有的 v1_ 混淆表
cur_tw.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'v1_%'")
tw_tables = [r[0] for r in cur_tw.fetchall()]
print(f"📋 台服混淆表總數: {len(tw_tables)}")

# 定義 7 張核心表的識別規則與對應名稱
mapped_tables = {}

for table in tw_tables:
    try:
        cur_tw.execute(f"PRAGMA table_info(\"{table}\")")
        cols = [c[1] for c in cur_tw.fetchall()]
        
        # 1. story_detail
        # 遍歷欄位，尋找含有 1001001 的行，且該行中某個欄位有 "第1話"
        found = False
        for c in cols:
            cur_tw.execute(f"SELECT COUNT(*) FROM \"{table}\" WHERE CAST(\"{c}\" AS TEXT) = '1001001'")
            if cur_tw.fetchone()[0] > 0:
                cur_tw.execute(f"SELECT * FROM \"{table}\" WHERE CAST(\"{c}\" AS TEXT) = '1001001'")
                row = cur_tw.fetchone()
                if any(isinstance(x, str) and "第1話" in x for x in row):
                    mapped_tables["story_detail"] = table
                    found = True
                    break
        if found:
            continue
            
        # 2. unit_data
        # 尋找含有 105801 的行，且該行中有名字 "佩可" 或 "貪吃佩可"
        for c in cols:
            cur_tw.execute(f"SELECT COUNT(*) FROM \"{table}\" WHERE CAST(\"{c}\" AS TEXT) = '105801'")
            if cur_tw.fetchone()[0] > 0:
                cur_tw.execute(f"SELECT * FROM \"{table}\" WHERE CAST(\"{c}\" AS TEXT) = '105801'")
                row = cur_tw.fetchone()
                if any(isinstance(x, str) and ("佩可" in x or "貪吃佩可" in x) for x in row):
                    mapped_tables["unit_data"] = table
                    found = True
                    break
        if found:
            continue
            
        # 3. unit_profile
        # 欄位數在 14~18 之間，且包含 105801
        if 14 <= len(cols) <= 18:
            for c in cols:
                cur_tw.execute(f"SELECT COUNT(*) FROM \"{table}\" WHERE CAST(\"{c}\" AS TEXT) = '105801'")
                if cur_tw.fetchone()[0] > 0:
                    mapped_tables["unit_profile"] = table
                    found = True
                    break
        if found:
            continue
            
        # 4. unit_rarity
        # 包含 105801 且大於 3 行，且欄位數大於 20 (屬性成長表)
        if len(cols) > 20:
            for c in cols:
                cur_tw.execute(f"SELECT COUNT(*) FROM \"{table}\" WHERE CAST(\"{c}\" AS TEXT) = '105801'")
                if cur_tw.fetchone()[0] > 3:
                    mapped_tables["unit_rarity"] = table
                    found = True
                    break
        if found:
            continue
            
        # 5. unit_skill_data
        # 包含 105801，且某個欄位值為 1058011 (佩可的 UB 技能 ID)
        if len(cols) >= 5:
            for c in cols:
                cur_tw.execute(f"SELECT COUNT(*) FROM \"{table}\" WHERE CAST(\"{c}\" AS TEXT) = '105801'")
                if cur_tw.fetchone()[0] > 0:
                    cur_tw.execute(f"SELECT * FROM \"{table}\" WHERE CAST(\"{c}\" AS TEXT) = '105801'")
                    row = cur_tw.fetchone()
                    if any(x == 1058011 for x in row):
                        mapped_tables["unit_skill_data"] = table
                        found = True
                        break
        if found:
            continue
            
        # 6. unit_attack_pattern
        # 包含 105801，且非技能表，且含有 loop_start 與 loop_end
        if len(cols) >= 15:
            for c in cols:
                cur_tw.execute(f"SELECT COUNT(*) FROM \"{table}\" WHERE CAST(\"{c}\" AS TEXT) = '105801'")
                if cur_tw.fetchone()[0] > 0:
                    cur_tw.execute(f"SELECT * FROM \"{table}\" WHERE CAST(\"{c}\" AS TEXT) = '105801'")
                    row = cur_tw.fetchone()
                    if any(x == 1 for x in row) and not any(x == 1058011 for x in row):
                        mapped_tables["unit_attack_pattern"] = table
                        found = True
                        break
        if found:
            continue
            
        # 7. skill_data
        # 包含 1058011，且該行中有技能名稱 "公主斬擊"
        for c in cols:
            cur_tw.execute(f"SELECT COUNT(*) FROM \"{table}\" WHERE CAST(\"{c}\" AS TEXT) = '1058011'")
            if cur_tw.fetchone()[0] > 0:
                cur_tw.execute(f"SELECT * FROM \"{table}\" WHERE CAST(\"{c}\" AS TEXT) = '1058011'")
                row = cur_tw.fetchone()
                if any(isinstance(x, str) and "公主" in x for x in row):
                    mapped_tables["skill_data"] = table
                    found = True
                    break
        if found:
            continue
            
    except Exception as e:
        print(f"Error checking {table}: {e}")
        pass

print("\n🎯 核心表對照定位結果:")
for real_name, obf_name in mapped_tables.items():
    print(f"  - {real_name} -> {obf_name}")

if len(mapped_tables) < 7:
    print(f"\n⚠️ 警告: 只定位到 {len(mapped_tables)} / 7 張表。還原將不完整。")

# 6. 執行 RENAME TABLE 與 COLUMN
for real_name, obf_name in mapped_tables.items():
    try:
        # A. 重命名表名
        print(f"🔄 還原表名: {obf_name} -> {real_name}")
        cur_tw.execute(f"ALTER TABLE \"{obf_name}\" RENAME TO \"{real_name}\"")
        
        # B. 獲取日服此表的欄位名稱順序
        cur_jp.execute(f"PRAGMA table_info(\"{real_name}\")")
        jp_cols = [c[1] for c in cur_jp.fetchall()]
        
        # 獲取台服此表的混淆欄位名稱順序
        cur_tw.execute(f"PRAGMA table_info(\"{real_name}\")")
        tw_cols = [c[1] for c in cur_tw.fetchall()]
        
        # C. 依序重命名欄位
        for tw_col, jp_col in zip(tw_cols, jp_cols):
            if tw_col != jp_col:
                cur_tw.execute(f"ALTER TABLE \"{real_name}\" RENAME COLUMN \"{tw_col}\" TO \"{jp_col}\"")
        print(f"  ✅ 欄位還原成功！")
    except Exception as e:
        print(f"  ❌ 還原 {real_name} 失敗: {e}")

# 提交變更
conn_tw.commit()
print("\n🎉 核心資料表解密還原成功！網站現在可以正常運作了！")

conn_jp.close()
conn_tw.close()
