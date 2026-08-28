#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查詢 dashboard/redive_jp.db 日版資料庫中指定話數 (如 1383004) 的解鎖獎勵 (CG/插畫)。
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
    print("=== 正在查詢 1383004 (阿斯特萊亞佩可 第 4 話) 的解鎖獎勵 (CG/插畫) ===")

    if not JP_DB_PATH.exists():
        print(f"[WARN] 找不到日版資料庫檔案: {JP_DB_PATH}")
        return

    conn = sqlite3.connect(str(JP_DB_PATH))
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='story_detail'")
    if not cur.fetchone():
        print(f"[WARN] 資料庫 {JP_DB_PATH.name} 中不存在 story_detail 資料表。")
        conn.close()
        return

    cur.execute("""
        SELECT reward_type_1, reward_id_1, reward_type_2, reward_id_2, reward_type_3, reward_id_3 
        FROM story_detail 
        WHERE story_id = 1383004
    """)
    row = cur.fetchone()

    if row:
        print("解鎖獎勵欄位:")
        for idx in range(3):
            rtype = row[idx * 2]
            rid = row[idx * 2 + 1]
            print(f"  - 獎勵 {idx+1}: 類型={rtype} | ID={rid}")
            if rtype == 8:  # 8 通常代表 CG/Still 劇照解鎖！
                print(f"    ✨ 發現解鎖的 CG 插畫 ID (still_id): {rid}！")
    else:
        print("找不到第 4 話紀錄")

    conn.close()

if __name__ == "__main__":
    main()
