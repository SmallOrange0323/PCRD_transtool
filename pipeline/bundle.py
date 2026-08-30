#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Bundler (100% Deterministic & Controlled Deployment)
負責將 dashboard/ 原始碼與最新資料打包封裝至 dist_story_map/ 獨立部署目錄。
具備：
1. 嚴謹的 SHA-256 Content 比對（解決同 size 漏更新）
2. 100% 決定性構建（基於 JS / DB 的 SHA-256 前綴，完全移除 timestamp）
3. 嚴格部署體積控制（精準複製 tracked 角色與 NPC 素材，不無條件複製全量圖片）
4. 完整資產覆蓋（still/story, still/scenario, still/bg, sound/story_vo, data/*.json）
5. 真正零副作用的 --dry-run 支援
"""

import os
import sys
import shutil
import hashlib
import json
import re
from pathlib import Path

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

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

def get_directory_size(d: Path) -> int:
    """計算目錄總大小 (bytes)"""
    if not d.exists():
        return 0
    total = 0
    for root, _, files in os.walk(d):
        if ".git" in root:
            continue
        for f in files:
            try:
                total += (Path(root) / f).stat().st_size
            except Exception:
                pass
    return total

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
    initial_dist_size = get_directory_size(DIST_DIR)

    # 1. 同步核心 HTML、CSS、JS
    core_files = [
        ("style.css", "style.css"),
        ("db.js", "db.js"),
        ("avatar-service.js", "avatar-service.js"),
        ("story-asset-service.js", "story-asset-service.js"),
        ("chapter-data.js", "chapter-data.js"),
        ("characters.js", "characters.js"),
        ("speaker-view.js", "speaker-view.js"),
        ("chara-modal.js", "chara-modal.js"),
        ("dialogue-normalizer.js", "dialogue-normalizer.js"),
        ("media-service.js", "media-service.js"),
        ("dialogue-view.js", "dialogue-view.js"),
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

    # 5. 同步劇情 JSON (全量 9000+ 對白)
    story_copied = sync_directory_assets(DASHBOARD_DIR / "story", DIST_DIR / "story", [".json"])

    # 6. 同步劇照與背景 (P1-1: 完整涵蓋 still/story, still/scenario, still/bg)
    bg_copied = sync_directory_assets(DASHBOARD_DIR / "still" / "bg", DIST_DIR / "still" / "bg", [".webp", ".png"])
    scenario_copied = sync_directory_assets(DASHBOARD_DIR / "still" / "scenario", DIST_DIR / "still" / "scenario", [".webp", ".png"])
    story_still_copied = sync_directory_assets(DASHBOARD_DIR / "still" / "story", DIST_DIR / "still" / "story", [".webp", ".png"])

    # 7. 精準同步角色卡面與頭像 (P1-2 體積控制：只同步 tracked_characters 與 NPC)
    card_copied = 0
    icon_copied = 0
    tracked_path = DASHBOARD_DIR / "data" / "tracked_characters.json"
    if tracked_path.exists():
        with open(tracked_path, "r", encoding="utf-8") as f:
            tracked = json.load(f)
        for char in tracked.get("characters", []):
            # 卡面立繪 (支援 canonical: <card_id> 與 legacy: card_full_<card_id>)
            for card_id in char.get("card_ids", []):
                for ext in [".webp", ".png"]:
                    cs_canon = DASHBOARD_DIR / "card" / "full" / f"{card_id}{ext}"
                    cs_legacy = DASHBOARD_DIR / "card" / "full" / f"card_full_{card_id}{ext}"
                    if cs_canon.exists():
                        if copy_if_different(cs_canon, DIST_DIR / "card" / "full" / f"{card_id}{ext}"):
                            card_copied += 1
                    if cs_legacy.exists():
                        if copy_if_different(cs_legacy, DIST_DIR / "card" / "full" / f"card_full_{card_id}{ext}"):
                            card_copied += 1
                        # 亦複製一份至 canonical
                        if not cs_canon.exists():
                            if copy_if_different(cs_legacy, DIST_DIR / "card" / "full" / f"{card_id}{ext}"):
                                card_copied += 1

            # 角色頭像 (支援 canonical: <icon_id> 與 legacy: unit_icon_<icon_id>)
            for icon_id in char.get("icon_ids", []):
                for ext in [".webp", ".png"]:
                    is_canon = DASHBOARD_DIR / "icon" / "unit" / f"{icon_id}{ext}"
                    is_legacy = DASHBOARD_DIR / "icon" / "unit" / f"unit_icon_{icon_id}{ext}"
                    if is_canon.exists():
                        if copy_if_different(is_canon, DIST_DIR / "icon" / "unit" / f"{icon_id}{ext}"):
                            icon_copied += 1
                    if is_legacy.exists():
                        if copy_if_different(is_legacy, DIST_DIR / "icon" / "unit" / f"unit_icon_{icon_id}{ext}"):
                            icon_copied += 1
                        # 亦複製一份至 canonical
                        if not is_canon.exists():
                            if copy_if_different(is_legacy, DIST_DIR / "icon" / "unit" / f"{icon_id}{ext}"):
                                icon_copied += 1

    # 同步 NPC 頭像 (190000~199999 及特例 NPC)
    icon_src_dir = DASHBOARD_DIR / "icon" / "unit"
    if icon_src_dir.exists():
        for item in icon_src_dir.glob("*.*"):
            if item.suffix not in [".png", ".webp"]:
                continue
            clean_id = item.stem.replace("unit_icon_", "")
            if clean_id.isdigit():
                val = int(clean_id)
                if (190000 <= val <= 199999) or (val in [107411, 107412, 107431]):
                    dst_icon = DIST_DIR / "icon" / "unit" / item.name
                    if copy_if_different(item, dst_icon):
                        icon_copied += 1
                    # 規整化 ID (如 107431)
                    if val < 190000:
                        base_id = (val // 100) * 100
                        norm_dst = DIST_DIR / "icon" / "unit" / f"{base_id + 31}{item.suffix}"
                        if copy_if_different(item, norm_dst):
                            icon_copied += 1

    # 8. 同步語音音檔 (sound/story_vo)
    voice_copied = sync_directory_assets(DASHBOARD_DIR / "sound" / "story_vo", DIST_DIR / "sound" / "story_vo", [".m4a"])

    print(f"  [Assets] 同步更新統計: 對白 JSON +{story_copied}, CG/劇照 +{scenario_copied + story_still_copied}, 背景 +{bg_copied}, 精準頭像 +{icon_copied}, 精準卡面 +{card_copied}, 語音 +{voice_copied}")

    # 9. 100% 決定性 index.html 生成與 Cache-Busting (P2: 使用 Content SHA-256 前 8 碼)
    html_src = DASHBOARD_DIR / "story_map.html"
    html_dst = DIST_DIR / "index.html"
    db_js_path = DASHBOARD_DIR / "db.js"
    ch_js_path = DASHBOARD_DIR / "chapter-data.js"
    char_js_path = DASHBOARD_DIR / "characters.js"
    avatar_js_path = DASHBOARD_DIR / "avatar-service.js"
    speaker_js_path = DASHBOARD_DIR / "speaker-view.js"
    modal_js_path = DASHBOARD_DIR / "chara-modal.js"
    norm_js_path = DASHBOARD_DIR / "dialogue-normalizer.js"
    media_js_path = DASHBOARD_DIR / "media-service.js"
    dialogue_js_path = DASHBOARD_DIR / "dialogue-view.js"
    map_js_path = DASHBOARD_DIR / "map.js"

    if html_src.exists() and db_js_path.exists() and ch_js_path.exists():
        html_content = html_src.read_text(encoding="utf-8")
        db_js_code = db_js_path.read_text(encoding="utf-8")
        ch_js_code = ch_js_path.read_text(encoding="utf-8")

        # 內嵌 db.js
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

        # 決定性 Content Cache-Busting (使用各自檔案的 SHA-256 前 8 碼)
        char_hash = calc_sha256(char_js_path)[:8]
        avatar_hash = calc_sha256(avatar_js_path)[:8]
        speaker_hash = calc_sha256(speaker_js_path)[:8]
        modal_hash = calc_sha256(modal_js_path)[:8]
        norm_hash = calc_sha256(norm_js_path)[:8]
        media_hash = calc_sha256(media_js_path)[:8]
        dialogue_hash = calc_sha256(dialogue_js_path)[:8]
        map_hash = calc_sha256(map_js_path)[:8]

        html_content = re.sub(
            r'<script src="characters\.js(?:\?v=[^"]*)?"></script>',
            f'<script src="characters.js?v={char_hash}"></script>',
            html_content
        )
        html_content = re.sub(
            r'<script src="avatar-service\.js(?:\?v=[^"]*)?"></script>',
            f'<script src="avatar-service.js?v={avatar_hash}"></script>',
            html_content
        )
        html_content = re.sub(
            r'<script src="speaker-view\.js(?:\?v=[^"]*)?"></script>',
            f'<script src="speaker-view.js?v={speaker_hash}"></script>',
            html_content
        )
        html_content = re.sub(
            r'<script src="chara-modal\.js(?:\?v=[^"]*)?"></script>',
            f'<script src="chara-modal.js?v={modal_hash}"></script>',
            html_content
        )
        html_content = re.sub(
            r'<script src="dialogue-normalizer\.js(?:\?v=[^"]*)?"></script>',
            f'<script src="dialogue-normalizer.js?v={norm_hash}"></script>',
            html_content
        )
        html_content = re.sub(
            r'<script src="media-service\.js(?:\?v=[^"]*)?"></script>',
            f'<script src="media-service.js?v={media_hash}"></script>',
            html_content
        )
        html_content = re.sub(
            r'<script src="dialogue-view\.js(?:\?v=[^"]*)?"></script>',
            f'<script src="dialogue-view.js?v={dialogue_hash}"></script>',
            html_content
        )
        html_content = re.sub(
            r'<script src="map\.js(?:\?v=[^"]*)?"></script>',
            f'<script src="map.js?v={map_hash}"></script>',
            html_content
        )

        html_dst.write_text(html_content, encoding="utf-8")
        print(f"  [HTML] 決定性內嵌與 Cache-Busting 完成 (Hash: char={char_hash}, avatar={avatar_hash}, map={map_hash})！最終大小: {html_dst.stat().st_size} bytes")
    else:
        print(f"  [ERROR] 內嵌失敗，找不到必要的 HTML 或 JS 檔案", file=sys.stderr)
        return False

    final_dist_size = get_directory_size(DIST_DIR)
    print(f"  [Dist Size] dist_story_map 總體積: {final_dist_size / (1024*1024):.2f} MB (變更前: {initial_dist_size / (1024*1024):.2f} MB)")
    print("✅ Story Map 封裝完成！")
    return True

if __name__ == "__main__":
    success = bundle_story_map()
    sys.exit(0 if success else 1)
