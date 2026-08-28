#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
探勘資料庫中 unit_data 欄位數值與 chara_id 映射關係。
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

    # 1. 檢索所有表，看看有沒有與 chara_id 相關的表
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]

    # 2. 查詢 unit_data 欄位
    cur.execute("PRAGMA table_info(unit_data)")
    cols = [col[1] for col in cur.fetchall()]
    print("unit_data 欄位:", cols)

    # 查詢 unit_data 中 180301 的所有數值
    cur.execute("SELECT * FROM unit_data WHERE unit_id = 180301")
    print("180301 欄位數值:", cur.fetchone())

    # 查詢 unit_data 中 180501 的所有數值
    cur.execute("SELECT * FROM unit_data WHERE unit_id = 180501")
    print("180501 欄位數值:", cur.fetchone())

    # 查詢 chara_identity (若存在)
    if 'chara_identity' in tables:
        cur.execute("SELECT * FROM chara_identity LIMIT 5")
        print("chara_identity 範例:", cur.fetchall())

    conn.close()

if __name__ == "__main__":
    main()
