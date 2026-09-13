#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 PCRD_DATA_VERSION 的決定性與完整性門禁 (Cache Version Safety)
包含：
A. Determinism: 連續執行兩次，version 完全相同。
B. Story-only Change: 僅修改單篇 story JSON 1 個字元，version 改變；復原後 version 100% 回到原值。
C. Summary-only Change: 僅修改 main_story_chapter_summaries.json，version 改變；復原後回到原值。
D. Branch-only Change: 僅修改 branch_stories.json，version 改變；復原後回到原值。
"""

import sys
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.bundle import render_index_html, compute_canonical_data_version, DASHBOARD_DIR

def extract_version(html: str) -> str:
    m = re.search(r'window\.PCRD_DATA_VERSION\s*=\s*"([^"]+)"', html)
    if not m:
        raise ValueError("在渲染的 HTML 中找不到 window.PCRD_DATA_VERSION")
    return m.group(1)

def run_tests():
    print("====================================================")
    print("🛡️  開始執行 Cache Version Safety 驗證測試套件...")
    print("====================================================")

    # ----------------------------------------------------
    # A. Determinism 測試
    # ----------------------------------------------------
    print("\n[Test A] Determinism (完全不修改資料，連續執行兩次)...")
    ver_a1 = compute_canonical_data_version(DASHBOARD_DIR)
    html_a1 = render_index_html(DASHBOARD_DIR)
    ext_a1 = extract_version(html_a1)

    ver_a2 = compute_canonical_data_version(DASHBOARD_DIR)
    html_a2 = render_index_html(DASHBOARD_DIR)
    ext_a2 = extract_version(html_a2)

    assert ver_a1 == ver_a2, f"Direct computation differs: {ver_a1} vs {ver_a2}"
    assert ext_a1 == ext_a2, f"Injected version differs: {ext_a1} vs {ext_a2}"
    assert ver_a1 == ext_a1, f"Computed and injected mismatch: {ver_a1} vs {ext_a1}"
    print(f"  [PASS] 兩次執行版本 100% 決定性吻合: {ext_a1}")

    base_version = ext_a1

    # ----------------------------------------------------
    # B. Story-only Change 測試
    # ----------------------------------------------------
    print("\n[Test B] Story-only Change (只改一篇 story JSON 1 個字元)...")
    test_story_file = DASHBOARD_DIR / "story" / "1001001.json"
    assert test_story_file.exists(), "測試檔案 1001001.json 不存在"
    orig_story_bytes = test_story_file.read_bytes()

    try:
        tampered_story_bytes = orig_story_bytes + b" "
        test_story_file.write_bytes(tampered_story_bytes)

        ver_b_tampered = compute_canonical_data_version(DASHBOARD_DIR)
        assert ver_b_tampered != base_version, f"Story 修改後版本未改變! ({ver_b_tampered} == {base_version})"
        print(f"  [PASS] 修改 story 後版本確實變更: {base_version} -> {ver_b_tampered}")
    finally:
        test_story_file.write_bytes(orig_story_bytes)

    ver_b_restored = compute_canonical_data_version(DASHBOARD_DIR)
    assert ver_b_restored == base_version, f"Story 復原後版本未回歸原值! ({ver_b_restored} != {base_version})"
    print(f"  [PASS] 復原 story 後版本精準回歸原值: {ver_b_restored}")

    # ----------------------------------------------------
    # C. Summary-only Change 測試
    # ----------------------------------------------------
    print("\n[Test C] Summary-only Change (只改 main_story_chapter_summaries.json)...")
    summary_file = DASHBOARD_DIR / "data" / "main_story_chapter_summaries.json"
    assert summary_file.exists(), "測試檔案 main_story_chapter_summaries.json 不存在"
    orig_summary_bytes = summary_file.read_bytes()

    try:
        tampered_summary_bytes = orig_summary_bytes + b" "
        summary_file.write_bytes(tampered_summary_bytes)

        ver_c_tampered = compute_canonical_data_version(DASHBOARD_DIR)
        assert ver_c_tampered != base_version, f"Summary 修改後版本未改變! ({ver_c_tampered} == {base_version})"
        print(f"  [PASS] 修改 summary 後版本確實變更: {base_version} -> {ver_c_tampered}")
    finally:
        summary_file.write_bytes(orig_summary_bytes)

    ver_c_restored = compute_canonical_data_version(DASHBOARD_DIR)
    assert ver_c_restored == base_version, f"Summary 復原後版本未回歸原值! ({ver_c_restored} != {base_version})"
    print(f"  [PASS] 復原 summary 後版本精準回歸原值: {ver_c_restored}")

    # ----------------------------------------------------
    # D. Branch-only Change 測試
    # ----------------------------------------------------
    print("\n[Test D] Branch-only Change (只改 branch_stories.json)...")
    branch_file = DASHBOARD_DIR / "data" / "branch_stories.json"
    assert branch_file.exists(), "測試檔案 branch_stories.json 不存在"
    orig_branch_bytes = branch_file.read_bytes()

    try:
        tampered_branch_bytes = orig_branch_bytes + b" "
        branch_file.write_bytes(tampered_branch_bytes)

        ver_d_tampered = compute_canonical_data_version(DASHBOARD_DIR)
        assert ver_d_tampered != base_version, f"Branch 修改後版本未改變! ({ver_d_tampered} == {base_version})"
        print(f"  [PASS] 修改 branch 後版本確實變更: {base_version} -> {ver_d_tampered}")
    finally:
        branch_file.write_bytes(orig_branch_bytes)

    ver_d_restored = compute_canonical_data_version(DASHBOARD_DIR)
    assert ver_d_restored == base_version, f"Branch 復原後版本未回歸原值! ({ver_d_restored} != {base_version})"
    print(f"  [PASS] 復原 branch 後版本精準回歸原值: {ver_d_restored}")

    print("\n====================================================")
    print("🎉 所有 Cache Version Safety 測試 100% 通過！")
    print(f"最終 Canonical Data Version: {base_version}")
    print("====================================================")

if __name__ == "__main__":
    run_tests()
