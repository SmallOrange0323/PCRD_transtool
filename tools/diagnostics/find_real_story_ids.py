#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查詢資料庫中特定角色 (如可可蘿公主、怜公主) 的真實故事 ID 映射與章節標題。
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
    print("=== 正在查詢 可可蘿(公主) 與 怜(公主) 的真實故事 ID 映射 ===")

    if not DB_PATH.exists():
        print(f"[ERROR] 找不到資料庫檔案: {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # 查詢 chara_story_status
    cur.execute("SELECT story_id, chara_id_1, unlock_story_name FROM chara_story_status WHERE unlock_story_name LIKE '%可可蘿（公主）%' OR unlock_story_name LIKE '%怜（公主）%'")
    for r in cur.fetchall():
        print("chara_story_status:", r)

    # 也去 story_detail 中查詢
    cur.execute("SELECT story_id, title, sub_title, story_group_id FROM story_detail WHERE title LIKE '%可可蘿（公主）%' OR title LIKE '%怜（公主）%'")
    for r in cur.fetchall():
        print("story_detail:", r)

    conn.close()

if __name__ == "__main__":
    main()
