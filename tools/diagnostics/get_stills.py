#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查詢 dashboard/redive_jp.db 日版資料庫中劇照關聯表 (如 story_still) 與話數關聯。
"""

import sys
import sqlite3
from pathlib import Path

# 統一從檔案位置推導專案根目錄，徹底解除 cwd 依賴
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
JP_DB_PATH = DASHBOARD_DIR / "redive_jp.db"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    if not JP_DB_PATH.exists():
        print(f"[WARN] 找不到日版資料庫檔案: {JP_DB_PATH}")
        return

    conn = sqlite3.connect(str(JP_DB_PATH))
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]

    still_tables = [t for t in tables if 'still' in t or 'detail' in t]
    print("關聯的資料表:", still_tables)

    if 'story_still' in tables:
        cur.execute("SELECT story_id, still_id FROM story_still WHERE story_id >= 1383000 AND story_id < 1383999")
        stills = cur.fetchall()
        print("在 story_still 查到的結果:", stills)
    else:
        print("沒有 story_still 表")

    conn.close()

if __name__ == "__main__":
    main()
