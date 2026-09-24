#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exhaustive Semantic Verification Diagnostic (Phase F2A.3 Closing)

目的：
對目前現行明文資料庫 (dashboard/redive_tw.db) 與新生成的 Normalized 00610008 資料庫
進行 8 張表全部 mapped columns 的全量 (Exhaustive) 語意比對。
"""

import json
from pathlib import Path
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CURRENT_DB_PATH = PROJECT_ROOT / "dashboard" / "redive_tw.db"
NORMALIZED_DB_PATH = PROJECT_ROOT / "scratch" / "normalized_00610008.db"
MAPPING_FILE = PROJECT_ROOT / "pipeline" / "manifests" / "sonet_db_schema_map_0061.json"


def run_exhaustive_verification():
    if not CURRENT_DB_PATH.is_file():
        print(f"❌ 找不到目前明文資料庫: {CURRENT_DB_PATH}")
        sys.exit(1)
    if not NORMALIZED_DB_PATH.is_file():
        print(f"❌ 找不到 Normalized 資料庫: {NORMALIZED_DB_PATH}")
        sys.exit(1)
    if not MAPPING_FILE.is_file():
        print(f"❌ 找不到 Mapping 檔案: {MAPPING_FILE}")
        sys.exit(1)

    with open(MAPPING_FILE, "r", encoding="utf-8") as f:
        mapping_data = json.load(f)

    conn_cur = sqlite3.connect(str(CURRENT_DB_PATH))
    cur_cur = conn_cur.cursor()

    conn_norm = sqlite3.connect(str(NORMALIZED_DB_PATH))
    cur_norm = conn_norm.cursor()

    tables = mapping_data["tables"]
    overall_mismatches = 0
    report_rows = []

    print("================================================================================")
    print("🔬 開始執行 8 Tables Exhaustive Semantic Verification (全量語意驗證)")
    print("================================================================================")

    for tbl_name, tbl_meta in tables.items():
        pk = tbl_meta.get("primary_key")
        cols = list(tbl_meta.get("columns", {}).keys())
        
        # 檢查現有 DB 是否有這張表 (例如 story_group_data 在現行明文庫中是獨立在母檔中)
        cur_cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl_name,))
        if not cur_cur.fetchone():
            print(f"⚠️  表 [{tbl_name}]: 現行 redive_tw.db 中無此表 (為官方原生母檔專屬表，跳過對比)")
            report_rows.append({
                "table": tbl_name,
                "status": "SKIP_NOT_IN_CURRENT_DB",
                "common_pks": 0,
                "newer_only": 0,
                "legacy_only": 0,
                "mismatches": 0
            })
            continue

        # 取得兩側所有 PK (統一轉成字串以消除型態微差)
        cur_cur.execute(f'SELECT DISTINCT "{pk}" FROM "{tbl_name}"')
        cur_pks = {str(r[0]): r[0] for r in cur_cur.fetchall()}

        cur_norm.execute(f'SELECT DISTINCT "{pk}" FROM "{tbl_name}"')
        norm_pks = {str(r[0]): r[0] for r in cur_norm.fetchall()}

        common_pks_keys = sorted(list(set(cur_pks.keys()) & set(norm_pks.keys())), key=lambda x: int(x) if x.isdigit() else x)
        newer_only = sorted(list(set(norm_pks.keys()) - set(cur_pks.keys())), key=lambda x: int(x) if x.isdigit() else x)
        legacy_only = sorted(list(set(cur_pks.keys()) - set(norm_pks.keys())), key=lambda x: int(x) if x.isdigit() else x)

        tbl_mismatches = 0
        mismatch_samples = []

        # 比對共同 PK 的每一個 mapped column
        col_select = ", ".join(f'"{c}"' for c in cols)
        for pk_key in common_pks_keys:
            orig_pk_cur = cur_pks[pk_key]
            orig_pk_norm = norm_pks[pk_key]

            cur_cur.execute(f'SELECT {col_select} FROM "{tbl_name}" WHERE "{pk}" = ? LIMIT 1', (orig_pk_cur,))
            row_cur = cur_cur.fetchone()

            cur_norm.execute(f'SELECT {col_select} FROM "{tbl_name}" WHERE "{pk}" = ? LIMIT 1', (orig_pk_norm,))
            row_norm = cur_norm.fetchone()

            if row_cur != row_norm:
                # 容許整數/字串的型態微差 (例如 "100" vs 100)
                is_diff = False
                for c_idx, (v_c, v_n) in enumerate(zip(row_cur, row_norm)):
                    # 空值處理
                    if v_c is None and v_n is None:
                        continue
                    if str(v_c) != str(v_n):
                        is_diff = True
                        break
                if is_diff:
                    tbl_mismatches += 1
                    if len(mismatch_samples) < 3:
                        mismatch_samples.append({
                            "pk": val_pk,
                            "cur": dict(zip(cols, row_cur)),
                            "norm": dict(zip(cols, row_norm))
                        })

        overall_mismatches += tbl_mismatches
        status = "PASS" if tbl_mismatches == 0 else "FAIL"
        print(
            f"[{status}] 表: {tbl_name:<20} | 共同 PK: {len(common_pks_keys):<5} | "
            f"新版增量: {len(newer_only):<4} | 舊版獨有: {len(legacy_only):<4} | 不一致: {tbl_mismatches}"
        )

        if mismatch_samples:
            for s in mismatch_samples:
                print(f"     ❌ PK={s['pk']}:")
                print(f"        Current : {s['cur']}")
                print(f"        Norm    : {s['norm']}")

        report_rows.append({
            "table": tbl_name,
            "status": status,
            "common_pks": len(common_pks_keys),
            "newer_only": len(newer_only),
            "legacy_only": len(legacy_only),
            "mismatches": tbl_mismatches
        })

    conn_cur.close()
    conn_norm.close()

    print("\n================================================================================")
    print(f"📊 驗證總結: 總表數={len(tables)}, 總語意不一致筆數={overall_mismatches}")
    if overall_mismatches == 0:
        print("✅ 8 Tables Exhaustive Semantic Verification 全部通過！")
    else:
        print(f"❌ 存在 {overall_mismatches} 處語意不一致，需進一步排查！")
    print("================================================================================")

    return overall_mismatches == 0


if __name__ == "__main__":
    success = run_exhaustive_verification()
    sys.exit(0 if success else 1)
