#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查詢資料庫中 event_story_detail 與 story_detail 的最新活動與故事組 ID。
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

    # 1. 查詢 event_story_detail 中的所有 story_group_id
    cur.execute("SELECT story_group_id, title FROM event_story_detail ORDER BY story_group_id DESC LIMIT 15")
    rows = cur.fetchall()
    print("=== event_story_detail 最新活動 ID 與標題 ===")
    for r in rows:
        print(f"  活動 ID: {r[0]} | 標題: {r[1]}")

    # 2. 查詢 story_detail 裡最大的一些 ID
    cur.execute("SELECT story_group_id, title FROM story_detail ORDER BY story_group_id DESC LIMIT 15")
    rows2 = cur.fetchall()
    print("\n=== story_detail 最新故事組 ID 與標題 ===")
    for r in rows2:
        print(f"  故事組 ID: {r[0]} | 標題: {r[1]}")

    conn.close()

if __name__ == "__main__":
    main()
