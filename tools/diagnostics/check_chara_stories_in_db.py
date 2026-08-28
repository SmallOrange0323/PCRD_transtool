#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
檢測特定角色故事組 (如 1506, 1805) 在資料庫與本機 story/ 目錄中的就緒度。
"""

import sys
import sqlite3
from pathlib import Path

# 統一從檔案位置推導專案根目錄，徹底解除 cwd 依賴
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
DB_PATH = DASHBOARD_DIR / "redive_tw.db"
STORY_DIR = DASHBOARD_DIR / "story"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    print("=== 正在檢測 禊&美美&鏡華(1506) 與 怜(公主)(1805) 的故事數據就緒度 ===")

    if not DB_PATH.exists():
        print(f"[ERROR] 找不到資料庫檔案: {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    for gid in [1506, 1805]:
        print(f"\n🔍 檢查故事組 ID: {gid}")
        cur.execute("SELECT story_id, title, sub_title FROM story_detail WHERE story_group_id = ?", (gid,))
        rows = cur.fetchall()
        print(f"  - 資料庫中收錄的章節數量: {len(rows)}")
        for r in rows:
            print(f"    - [{r[0]}] {r[1]} | {r[2]}")
            
        # 檢查本地對白檔案
        for i in range(1, 5):
            json_file = STORY_DIR / f"{gid}00{i}.json"
            exist = json_file.exists()
            print(f"    - 檔案 story/{gid}00{i}.json 是否存在: {exist}")
            
    conn.close()

if __name__ == "__main__":
    main()
