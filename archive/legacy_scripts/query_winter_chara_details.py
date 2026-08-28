#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[Archive / Legacy] 歷史一次性確認資料庫中 若菜(冬日)與栞(冬日) 的技能與數據就緒狀態 (從台版資料庫 redive_tw.db)。
"""

import sys
import sqlite3
from pathlib import Path

# 統一從檔案位置推導專案根目錄，徹底解除 cwd 依賴
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
TW_DB_PATH = DASHBOARD_DIR / "redive_tw.db"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    print("=== 正在確認資料庫中 若菜(冬日)與栞(冬日) 的技能與數據就緒狀態 ===")

    if not TW_DB_PATH.exists():
        print(f"[ERROR] 找不到台版資料庫: {TW_DB_PATH}")
        return

    conn = sqlite3.connect(str(TW_DB_PATH))
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='unit_data'")
    if not cur.fetchone():
        print(f"[WARN] 資料庫 {TW_DB_PATH.name} 中不存在 unit_data 資料表。")
        conn.close()
        return

    ids = [138701, 138801]

    for uid in ids:
        print(f"\n🔍 檢查角色 ID: {uid}")
        
        # 1. 查詢角色基本名稱
        cur.execute("SELECT unit_name, rarity FROM unit_data WHERE unit_id = ?", (uid,))
        row = cur.fetchone()
        if row:
            print(f"  - 角色名稱: {row[0]} | 初始星等: {row[1]}")
        else:
            print(f"  - ❌ 角色未在 unit_data 表中收錄！")
            continue
            
        # 2. 查詢角色技能關聯
        cur.execute("SELECT union_burst, main_skill_1, main_skill_2 FROM unit_skill_data WHERE unit_id = ?", (uid,))
        skill_row = cur.fetchone()
        if skill_row:
            print(f"  - 技能關聯已就緒: UB={skill_row[0]}, 技能1={skill_row[1]}, 技能2={skill_row[2]}")
            
            # 查詢 UB 名稱與說明
            cur.execute("SELECT name, description FROM skill_data WHERE skill_id = ?", (skill_row[0],))
            ub_row = cur.fetchone()
            if ub_row:
                print(f"    ✨ UB名稱: {ub_row[0]}")
        else:
            print(f"  - ❌ 技能關聯未就緒！")

        # 3. 查詢個人劇情對話解鎖狀態
        cur.execute("SELECT story_id, title FROM story_detail WHERE story_group_id = ?", (uid // 100,))
        stories = cur.fetchall()
        print(f"  - 個人劇情解鎖章節 ({len(stories)} 筆):")
        for s in stories[:4]:
            print(f"    - [{s[0]}] {s[1]}")

    conn.close()

if __name__ == "__main__":
    main()
