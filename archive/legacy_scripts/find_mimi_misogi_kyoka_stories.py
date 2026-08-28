#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[Archive / Legacy] 歷史一次性檢索 禊、美美、鏡華 相關的所有個人劇情記錄。
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
    print("=== 正在檢索 禊、美美、鏡華 相關的所有個人劇情 ===")

    if not DB_PATH.exists():
        print(f"[ERROR] 找不到台版資料庫: {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='story_detail'")
    if not cur.fetchone():
        print(f"[WARN] 資料庫 {DB_PATH.name} 中不存在 story_detail 資料表。")
        conn.close()
        return

    # 在 story_detail 查詢所有含有 "禊"、"美美" 或 "鏡華" 的個人故事 (story_id 在 1000000 到 2000000 之間)
    cur.execute("""
        SELECT story_id, title, sub_title, story_group_id 
        FROM story_detail 
        WHERE story_id >= 1000000 AND story_id < 2000000 
          AND (title LIKE '%禊%' OR title LIKE '%美美%' OR title LIKE '%鏡華%')
        ORDER BY story_id DESC
    """)
    rows = cur.fetchall()
    print(f"共找到 {len(rows)} 筆記錄：")
    for r in rows[:40]:
        print(f"  story_id: {r[0]} | 標題: {r[1]} | {r[2]} | story_group_id: {r[3]}")

    conn.close()

if __name__ == "__main__":
    main()
