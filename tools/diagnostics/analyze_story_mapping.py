#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查詢資料庫中 chara_story_status 與個人劇情關聯表結構與紀錄。
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
        print(f"[ERROR] 找不到資料庫檔案: {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    print("=== 查詢 chara_story_status 或其他故事關聯表 ===")
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%chara_story%'")
    tables = [r[0] for r in cur.fetchall()]
    print("匹配的表名:", tables)

    if 'chara_story_status' in tables:
        cur.execute("PRAGMA table_info(chara_story_status)")
        cols = [col[1] for col in cur.fetchall()]
        print("chara_story_status 欄位:", cols)
        
        cur.execute("SELECT * FROM chara_story_status WHERE chara_id_1 = 180501 OR chara_id_2 = 180501 LIMIT 5")
        rows = cur.fetchall()
        print("chara_story_status 中 180501 的紀錄:", rows)
        
        cur.execute("SELECT * FROM chara_story_status WHERE chara_id_1 = 100501 OR chara_id_2 = 100501 LIMIT 5")
        rows2 = cur.fetchall()
        print("chara_story_status 中 100501 (原版怜) 的紀錄:", rows2)

    conn.close()

if __name__ == "__main__":
    main()
