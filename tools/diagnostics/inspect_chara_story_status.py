#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查詢 dashboard/redive_tw.db 台版資料庫中 chara_story_status 表的範例資料與特定角色 (如怜) 故事紀錄。
"""

import sys
import sqlite3
from pathlib import Path

# 統一從檔案位置推導專案根目錄，徹底解除 cwd 依賴
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
DB_PATH = DASHBOARD_DIR / "redive_tw.db"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    if not DB_PATH.exists():
        print(f"[ERROR] 找不到台版資料庫檔案: {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chara_story_status'")
    if not cur.fetchone():
        print(f"[WARN] 資料庫 {DB_PATH.name} 中不存在 chara_story_status 資料表。")
        conn.close()
        return

    # 1. 查詢前 20 筆資料，看看 chara_id_1 是什麼
    cur.execute("SELECT story_id, chara_id_1, chara_id_2, chara_id_3, unlock_story_name FROM chara_story_status LIMIT 20")
    for r in cur.fetchall():
        print(r)
        
    print("\n=== 模糊搜尋包含 100501 或 180501 或者是含有 怜(公主) 故事名稱的行 ===")
    cur.execute("SELECT story_id, chara_id_1, unlock_story_name FROM chara_story_status WHERE unlock_story_name LIKE '%怜%' LIMIT 20")
    for r in cur.fetchall():
        print(r)

    conn.close()

if __name__ == "__main__":
    main()
