#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[Archive / Legacy] 歷史一次性檢查阿斯特萊亞佩可劇情的 CG/插畫 (still_id) 與背景 (bg_id)。
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
    print("=== 正在檢查阿斯特萊亞佩可劇情的 CG/插畫 (still_id) 與背景 (bg_id) ===")

    if not JP_DB_PATH.exists():
        print(f"[WARN] 找不到日版資料庫: {JP_DB_PATH}")
        return

    conn = sqlite3.connect(str(JP_DB_PATH))
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='story_detail'")
    if not cur.fetchone():
        print(f"[WARN] 資料庫 {JP_DB_PATH.name} 中不存在 story_detail 資料表。")
        conn.close()
        return

    # 查詢 1383001 ~ 1383004 劇情的詳細資訊與劇照 ID
    cur.execute("SELECT story_id, title, sub_title, story_group_id FROM story_detail WHERE story_id >= 1000000 AND story_id < 2000000 AND (story_id LIKE '11383%' OR story_id LIKE '1383%')")
    rows = cur.fetchall()

    if not rows:
        cur.execute("SELECT story_id, title, sub_title FROM story_detail WHERE story_id >= 1383000 AND story_id < 1383999")
        rows = cur.fetchall()

    print(f"找到 {len(rows)} 筆劇情詳細記錄：")
    for r in rows:
        print(r)

    conn.close()

if __name__ == "__main__":
    main()
