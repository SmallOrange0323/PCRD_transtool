#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Bundler
負責將 dashboard/ 原始碼與最新資料打包封裝至 dist_story_map/ 獨立部署目錄。
具備：
1. 嚴謹的 SHA-256 Content 比對（徹底解決同 size 漏更新問題）
2. 基於資料庫 SHA-256 的決定性 db_version（避免無謂清空前端快取）
3. 內嵌核心 JS 與動態 Cache-Busting
4. 真正零副作用的 --dry-run 支援
"""

import os
import sys
import shutil
import hashlib
import json
import re
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
DIST_DIR = PROJECT_ROOT / "dist_story_map"

def calc_sha256(filepath: Path) -> str:
    """統一計算檔案 SHA-256 Hash"""
    if not filepath.exists():
        return ""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def copy_if_different(src: Path, dst: Path, force_overwrite: bool = False) -> bool:
    """
    使用 SHA-256 Content Hash 比對，若內容不同或目標不存在則複製。
    :return: True 代表有複製/更新，False 代表相同跳過
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists() or force_overwrite:
        shutil.copy2(src, dst)
        return True
    
    src_hash = calc_sha256(src)
    dst_hash = calc_sha256(dst)
    if src_hash != dst_hash:
        shutil.copy2(src, dst)
        return True
    return False

def sync_directory_assets(src_dir: Path, dst_dir: Path, ext_filter=None) -> int:
    """同步資料夾素材並回傳更新數量"""
    if not src_dir.exists():
        return 0
    dst_dir.mkdir(parents=True, exist_ok=True)
    updated = 0
    for root, _, files in os.walk(src_dir):
        rel_root = Path(root).relative_to(src_dir)
        target_root = dst_dir / rel_root
        target_root.mkdir(parents=True, exist_ok=True)
        for f in files:
            if ext_filter and not any(f.endswith(e) for e in ext_filter):
                continue
            sf = Path(root) / f
            df = target_root / f
            if copy_if_different(sf, df):
                updated += 1
    return updated

def bundle_story_map(dry_run: bool = False) -> bool:
    """
    封裝 Story Map 至 dist_story_map/
    :param dry_run: 真正零副作用模式，只輸出計畫與比對統計，不寫入任何檔案
    """
    print(f"\n📦 開始封裝 Story Map 獨立發布包...")
    print(f"  [Root] 專案根目錄: {PROJECT_ROOT}")
    print(f"  [Src]  源碼目錄: {DASHBOARD_DIR}")
    print(f"  [Dst]  輸出目錄: {DIST_DIR}")

    if not DASHBOARD_DIR.exists():
        print(f"  [ERROR] dashboard 目錄不存在: {DASHBOARD_DIR}", file=sys.stderr)
        return False

    db_src = DASHBOARD_DIR / "redive_tw.db"
    db_hash = calc_sha256(db_src)[:12] if db_src.exists() else "nodata"

    if dry_run:
        print("  [DRY-RUN] 模擬運行模式（零副作用）：不寫入、不修改任何實體檔案。")
        print(f"  [DRY-RUN] 預期 db_version: hash_{db_hash}")
        return True

    DIST_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 同步核心 HTML、CSS、JS
    core_files = [
        ("style.css", "style.css"),
        ("db.js", "db.js"),
        ("avatar-service.js", "avatar-service.js"),
        ("story-asset-service.js", "story-asset-service.js"),
        ("chapter-data.js", "chapter-data.js"),
        ("characters.js", "characters.js"),
        ("map.js", "map.js"),
        ("sql-wasm.js", "sql-wasm.js"),
        ("sql-wasm.wasm", "sql-wasm.wasm"),
    ]
    for src_name, dst_name in core_files:
        sf = DASHBOARD_DIR / src_name
        df = DIST_DIR / dst_name
        if sf.exists():
            copy_if_different(sf, df, force_overwrite=True)

    # 2. 同步資料庫 (redive_tw.db)
    db_dst = DIST_DIR / "redive_tw.db"
    if db_src.exists():
        copy_if_different(db_src, db_dst)

    # 3. 同步 data/ 下所有 JSON 元數據 (強制使用 SHA-256 比對覆寫)
    src_data_dir = DASHBOARD_DIR / "data"
    dst_data_dir = DIST_DIR / "data"
    if src_data_dir.exists():
        for jf in src_data_dir.glob("*.json"):
            copy_if_different(jf, dst_data_dir / jf.name, force_overwrite=True)

    # 4. 計算決定性 db_version (基於資料庫 SHA-256 前 12 碼)
    db_size = db_src.stat().st_size if db_src.exists() else 0
    db_info = {
        "db_version": f"hash_{db_hash}",
        "tw_size": db_size,
        "jp_size": 0
    }
    db_info_path = dst_data_dir / "db_info.json"
    with open(db_info_path, "w", encoding="utf-8") as f:
        json.dump(db_info, f, ensure_ascii=False, indent=2)
    print(f"  [DB Info] 決定性 db_version: {db_info['db_version']} (檔案大小: {db_size} bytes)")

    # 5. 同步劇情 JSON、CG、背景、頭像、語音等素材
    story_copied = sync_directory_assets(DASHBOARD_DIR / "story", DIST_DIR / "story", [".json"])
    bg_copied = sync_directory_assets(DASHBOARD_DIR / "still" / "bg", DIST_DIR / "still" / "bg", [".webp", ".png"])
    cg_copied = sync_directory_assets(DASHBOARD_DIR / "still" / "scenario", DIST_DIR / "still" / "scenario", [".webp", ".png"])
    icon_copied = sync_directory_assets(DASHBOARD_DIR / "icon", DIST_DIR / "icon", [".png", ".webp"])
    card_copied = sync_directory_assets(DASHBOARD_DIR / "card", DIST_DIR / "card", [".webp", ".png"])
    voice_copied = sync_directory_assets(DASHBOARD_DIR / "sound" / "story_vo", DIST_DIR / "sound" / "story_vo", [".m4a"])

    print(f"  [Assets] 同步更新統計: 對白 JSON +{story_copied}, CG +{cg_copied}, 背景 +{bg_copied}, 頭像 +{icon_copied}, 卡面 +{card_copied}, 語音 +{voice_copied}")

    # 6. 生成 index.html 並內嵌核心腳本以避免 CDN 快取遺留
    html_src = DASHBOARD_DIR / "story_map.html"
    html_dst = DIST_DIR / "index.html"
    db_js_path = DASHBOARD_DIR / "db.js"
    ch_js_path = DASHBOARD_DIR / "chapter-data.js"

    if html_src.exists() and db_js_path.exists() and ch_js_path.exists():
        html_content = html_src.read_text(encoding="utf-8")
        db_js_code = db_js_path.read_text(encoding="utf-8")
        ch_js_code = ch_js_path.read_text(encoding="utf-8")

        # 內嵌 db.js (支援正則匹配帶版本參數的 script 標籤)
        html_content = re.sub(
            r'<script src="db\.js(?:\?v=[^"]*)?"></script>',
            lambda m: f'<script>\n// === db.js INLINED ===\n{db_js_code}\n// === END db.js ===\n</script>',
            html_content
        )

        # 內嵌 chapter-data.js
        html_content = re.sub(
            r'<script src="chapter-data\.js(?:\?v=[^"]*)?"></script>',
            lambda m: f'<script>\n// === chapter-data.js INLINED ===\n{ch_js_code}\n// === END chapter-data.js ===\n</script>',
            html_content
        )

        # 動態 Cache-Busting (characters.js, avatar-service.js, map.js)
        v_ts = int(time.time())
        html_content = re.sub(
            r'<script src="characters\.js(?:\?v=[^"]*)?"></script>',
            f'<script src="characters.js?v={v_ts}"></script>',
            html_content
        )
        html_content = re.sub(
            r'<script src="avatar-service\.js(?:\?v=[^"]*)?"></script>',
            f'<script src="avatar-service.js?v={v_ts}"></script>',
            html_content
        )
        html_content = re.sub(
            r'<script src="map\.js(?:\?v=[^"]*)?"></script>',
            f'<script src="map.js?v={v_ts}"></script>',
            html_content
        )

        html_dst.write_text(html_content, encoding="utf-8")
        print(f"  [HTML] 內嵌與 Cache-Busting 完成！最終 index.html 大小: {html_dst.stat().st_size} bytes")
    else:
        print(f"  [ERROR] 內嵌失敗，找不到必要的 HTML 或 JS 檔案", file=sys.stderr)
        return False

    print("✅ Story Map 封裝完成！")
    return True

if __name__ == "__main__":
    success = bundle_story_map()
    sys.exit(0 if success else 1)
