#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查詢 dist_story_map/redive_tw.db 發布資料庫中特定角色 ID 的真實名稱與星等。
"""

import sys
import sqlite3
from pathlib import Path

# 統一從檔案位置推導專案根目錄，徹底解除 cwd 依賴
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = PROJECT_ROOT / "dist_story_map"
DIST_DB_PATH = DIST_DIR / "redive_tw.db"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    print("=== 正在查詢 dist_story_map/redive_tw.db 中三個角色 ID 的真實名稱 ===")

    if not DIST_DB_PATH.exists():
        print(f"[ERROR] 找不到發布資料庫檔案: {DIST_DB_PATH}")
        return

    conn = sqlite3.connect(str(DIST_DB_PATH))
    cur = conn.cursor()

    for uid in [180301, 180501, 180801, 150601]:
        cur.execute("SELECT unit_name, rarity FROM unit_data WHERE unit_id = ?", (uid,))
        row = cur.fetchone()
        if row:
            print(f"  - ID {uid} 的名稱為: {row[0]} | 星等: {row[1]}")
        else:
            print(f"  - ❌ ID {uid} 在發佈資料庫中不存在")

    conn.close()

if __name__ == "__main__":
    main()
