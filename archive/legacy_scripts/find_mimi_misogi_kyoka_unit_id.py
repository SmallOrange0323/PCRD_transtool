#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[Archive / Legacy] 歷史一次性查詢 禊＆美美＆鏡華 角色在 unit_data 表中的真實 unit_id。
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
    print("=== 正在查詢 禊＆美美＆鏡華 角色在 unit_data 表中的真實 unit_id ===")

    if not DB_PATH.exists():
        print(f"[ERROR] 找不到台版資料庫: {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='unit_data'")
    if not cur.fetchone():
        print(f"[WARN] 資料庫 {DB_PATH.name} 中不存在 unit_data 資料表。")
        conn.close()
        return

    cur.execute("SELECT unit_id, unit_name, rarity FROM unit_data WHERE unit_name LIKE '%禊%' AND unit_name LIKE '%美美%'")
    for r in cur.fetchall():
        print(r)

    conn.close()

if __name__ == "__main__":
    main()
