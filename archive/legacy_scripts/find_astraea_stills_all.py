#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[Archive / Legacy] 歷史一次性搜尋與阿斯特萊亞佩可 (138301) 相關的所有 still_id (從日版資料庫 redive_jp.db)。
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
    print("=== 正在搜尋與阿斯特萊亞佩可 (138301) 相關的所有 still_id ===")

    if not JP_DB_PATH.exists():
        print(f"[WARN] 找不到日版資料庫檔案: {JP_DB_PATH}")
        return

    conn = sqlite3.connect(str(JP_DB_PATH))
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]

    # 搜尋 story_still 表或卡片關聯表
    if 'chara_story_still' in tables:
        cur.execute("SELECT * FROM chara_story_still WHERE story_id >= 1383000 AND story_id < 1383999")
        print("chara_story_still 結果:", cur.fetchall())

    # 或者是查詢與 still_unit_mapping 相關的
    mapping_table = [t for t in tables if 'still' in t]
    print("包含 still 的表名:", mapping_table)

    for t in mapping_table:
        try:
            cur.execute(f"SELECT * FROM {t} LIMIT 5")
            print(f"表 {t} 的樣本數據:", cur.fetchall())
        except Exception as e:
            print(f"查詢表 {t} 出錯:", e)

    conn.close()

if __name__ == "__main__":
    main()
