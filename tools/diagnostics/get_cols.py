#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查詢 dashboard/redive_jp.db 日版資料庫中 story_detail 表欄位與指定話數 (如 1383001) 的詳細數值。
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

    # 檢查表是否存在
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='story_detail'")
    if not cur.fetchone():
        print(f"[WARN] 日版資料庫 {JP_DB_PATH.name} 中不存在 story_detail 資料表。")
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%story%'")
        story_tables = [r[0] for r in cur.fetchall()]
        print(f"  現有與故事相關的資料表: {story_tables}")
        conn.close()
        return

    # 取得 story_detail 的欄位名稱
    cur.execute("PRAGMA table_info(story_detail)")
    columns = [r[1] for r in cur.fetchall()]
    print("story_detail 欄位:", columns)

    # 查詢 1383001 的詳細資料
    cur.execute("SELECT * FROM story_detail WHERE story_id = 1383001")
    row = cur.fetchone()
    if row:
        for col, val in zip(columns, row):
            print(f"  {col}: {val}")
    else:
        print("  未找到話數 1383001 的紀錄。")

    conn.close()

if __name__ == "__main__":
    main()
