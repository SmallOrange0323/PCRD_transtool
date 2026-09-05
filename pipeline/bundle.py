#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Bundler (100% Deterministic & Controlled Deployment)
負責將 dashboard/ 原始碼與最新資料打包封裝至 dist_story_map/ 獨立部署目錄。
具備：
1. 嚴謹的 SHA-256 Content 比對（解決同 size 漏更新）
2. 100% 決定性構建（基於 JS / DB 的 SHA-256 前綴，完全移除 timestamp）
3. 嚴格部署體積控制（精準複製 tracked 角色與 NPC 素材；大體積 still/story CG 移交遠端 CDN）
4. 決定性清理機制 (Deterministic Pruning)：清理歷史殘留目錄、重複 DB 與無效鏡像檔案，保護 .git
5. 決定性 .nojekyll 標記建立與正規化 (0 bytes)
6. 完整支援 card/full 與 sound/story_vo 本機發布包同步（受 .gitignore 排除，不計入 Pages 體積）
7. 真正零副作用且 100% 決定性對齊的 --dry-run 精準預測
"""

import os
import sys
import stat
import shutil
import hashlib
import json
import re
from pathlib import Path
from typing import Set, Tuple, List, Dict, Optional

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
DIST_DIR = PROJECT_ROOT / "dist_story_map"

# 支援的圖片副檔名
IMAGE_EXTENSIONS = {".webp", ".png"}

def calc_sha256(filepath: Path) -> str:
    """統一計算檔案 SHA-256 Hash"""
    if not filepath.exists() or not filepath.is_file():
        return ""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def calc_sha256_bytes(data: bytes) -> str:
    """計算 byte string 的 SHA-256 Hash"""
    return hashlib.sha256(data).hexdigest()

def is_safe_dist_path(target: Path, dist_root: Path = DIST_DIR) -> bool:
    """
    驗證路徑是否安全位於 dist_root 內部，且絕不為 dist_root 本身或 .git 相關目錄。
    """
    try:
        resolved_target = target.resolve()
        resolved_dist = dist_root.resolve()
    except Exception:
        return False

    # 必須位於 dist_root 之下
    try:
        rel = resolved_target.relative_to(resolved_dist)
    except ValueError:
        return False

    # 拒絕 dist_root 本身
    if resolved_target == resolved_dist:
        return False

    # 拒絕 .git 本身或 .git 內部任何檔案
    parts = rel.parts
    if ".git" in parts or any(p.startswith(".git") for p in parts if p == ".git"):
        return False

    return True

def safe_prune_file(filepath: Path, dry_run: bool = False, dist_root: Path = DIST_DIR) -> Tuple[int, int]:
    """
    安全刪除單一檔案。
    :return: (pruned_count, pruned_bytes)
    """
    if not filepath.exists() or not filepath.is_file():
        return 0, 0
    if not is_safe_dist_path(filepath, dist_root):
        print(f"  [PRUNE REJECTED] 不安全的路徑，拒絕刪除: {filepath}", file=sys.stderr)
        return 0, 0

    try:
        size = filepath.stat().st_size
    except Exception:
        size = 0

    if not dry_run:
        try:
            try:
                filepath.unlink()
            except PermissionError:
                os.chmod(filepath, stat.S_IWRITE)
                filepath.unlink()
        except Exception as e:
            print(f"  [PRUNE ERROR] 刪除檔案失敗 {filepath}: {e}", file=sys.stderr)
            return 0, 0

    return 1, size

def safe_prune_dir(dirpath: Path, dry_run: bool = False, dist_root: Path = DIST_DIR) -> Tuple[int, int]:
    """
    安全遞迴清理目錄內的所有檔案，並在非 dry_run 時移除空目錄。
    :return: (pruned_count, pruned_bytes)
    """
    if not dirpath.exists() or not dirpath.is_dir():
        return 0, 0
    if not is_safe_dist_path(dirpath, dist_root):
        print(f"  [PRUNE REJECTED] 不安全的目錄路徑，拒絕刪除: {dirpath}", file=sys.stderr)
        return 0, 0

    pruned_count = 0
    pruned_bytes = 0

    # 遍歷子項目
    for root, dirs, files in os.walk(dirpath, topdown=False):
        for f in files:
            fp = Path(root) / f
            c, b = safe_prune_file(fp, dry_run=dry_run, dist_root=dist_root)
            pruned_count += c
            pruned_bytes += b

        if not dry_run:
            for d in dirs:
                dp = Path(root) / d
                if is_safe_dist_path(dp, dist_root):
                    try:
                        dp.rmdir()
                    except PermissionError:
                        try:
                            os.chmod(dp, stat.S_IWRITE)
                            dp.rmdir()
                        except Exception:
                            pass
                    except Exception:
                        pass

    if not dry_run:
        try:
            dirpath.rmdir()
        except PermissionError:
            try:
                os.chmod(dirpath, stat.S_IWRITE)
                dirpath.rmdir()
            except Exception:
                pass
        except Exception:
            pass

    return pruned_count, pruned_bytes

def copy_if_different(src: Path, dst: Path, force_overwrite: bool = False, dry_run: bool = False) -> bool:
    """
    使用 SHA-256 Content Hash 比對，若內容不同或目標不存在則複製。
    :return: True 代表有複製/更新，False 代表相同跳過
    """
    if not src.exists():
        return False
    if not dst.exists() or force_overwrite:
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        return True

    src_hash = calc_sha256(src)
    dst_hash = calc_sha256(dst)
    if src_hash != dst_hash:
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        return True
    return False

def sync_directory_assets(src_dir: Path, dst_dir: Path, ext_filter=None, dry_run: bool = False) -> int:
    """同步資料夾素材並回傳更新數量"""
    if not src_dir.exists():
        return 0
    if not dry_run:
        dst_dir.mkdir(parents=True, exist_ok=True)
    updated = 0
    for root, _, files in os.walk(src_dir):
        rel_root = Path(root).relative_to(src_dir)
        target_root = dst_dir / rel_root
        if not dry_run:
            target_root.mkdir(parents=True, exist_ok=True)
        for f in files:
            if ext_filter and not any(f.endswith(e) for e in ext_filter):
                continue
            sf = Path(root) / f
            df = target_root / f
            if copy_if_different(sf, df, dry_run=dry_run):
                updated += 1
    return updated

def get_directory_size(d: Path, exclude_subdirs: Optional[Set[str]] = None) -> int:
    """計算目錄總大小 (bytes)，可排除特定頂層子目錄（如 .git, sound, card）"""
    if not d.exists():
        return 0
    total = 0
    excl = exclude_subdirs or {".git"}
    for root, dirs, files in os.walk(d):
        rel = Path(root).relative_to(d)
        parts = rel.parts
        if any(p in excl for p in parts):
            continue
        for f in files:
            try:
                total += (Path(root) / f).stat().st_size
            except Exception:
                pass
    return total

def render_index_html(dashboard_dir: Path = DASHBOARD_DIR) -> str:
    """
    決定性生成/渲染 Story Map 的 index.html 內容。
    包含：
    1. 內嵌 db.js 與 chapter-data.js
    2. 基於各 JS 檔案內容 SHA-256 前 8 碼進行 Cache-Busting
    """
    html_src = dashboard_dir / "story_map.html"
    db_js_path = dashboard_dir / "db.js"
    ch_js_path = dashboard_dir / "chapter-data.js"
    char_js_path = dashboard_dir / "characters.js"
    avatar_js_path = dashboard_dir / "avatar-service.js"
    speaker_js_path = dashboard_dir / "speaker-view.js"
    modal_js_path = dashboard_dir / "chara-modal.js"
    norm_js_path = dashboard_dir / "dialogue-normalizer.js"
    media_js_path = dashboard_dir / "media-service.js"
    dialogue_js_path = dashboard_dir / "dialogue-view.js"
    map_js_path = dashboard_dir / "map.js"

    if not (html_src.exists() and db_js_path.exists() and ch_js_path.exists()):
        raise FileNotFoundError("找不到必要的 HTML 或 JS 檔案以渲染 index.html")

    html_content = html_src.read_text(encoding="utf-8")
    db_js_code = db_js_path.read_text(encoding="utf-8")
    ch_js_code = ch_js_path.read_text(encoding="utf-8")

    html_content = re.sub(
        r'<script src="db\.js(?:\?v=[^"]*)?"></script>',
        lambda m: f'<script>\n// === db.js INLINED ===\n{db_js_code}\n// === END db.js ===\n</script>',
        html_content
    )
    html_content = re.sub(
        r'<script src="chapter-data\.js(?:\?v=[^"]*)?"></script>',
        lambda m: f'<script>\n// === chapter-data.js INLINED ===\n{ch_js_code}\n// === END chapter-data.js ===\n</script>',
        html_content
    )

    char_hash = calc_sha256(char_js_path)[:8]
    avatar_hash = calc_sha256(avatar_js_path)[:8]
    speaker_hash = calc_sha256(speaker_js_path)[:8]
    modal_hash = calc_sha256(modal_js_path)[:8]
    norm_hash = calc_sha256(norm_js_path)[:8]
    media_hash = calc_sha256(media_js_path)[:8]
    dialogue_hash = calc_sha256(dialogue_js_path)[:8]
    map_hash = calc_sha256(map_js_path)[:8]

    html_content = re.sub(r'<script src="characters\.js(?:\?v=[^"]*)?"></script>', f'<script src="characters.js?v={char_hash}"></script>', html_content)
    html_content = re.sub(r'<script src="avatar-service\.js(?:\?v=[^"]*)?"></script>', f'<script src="avatar-service.js?v={avatar_hash}"></script>', html_content)
    html_content = re.sub(r'<script src="speaker-view\.js(?:\?v=[^"]*)?"></script>', f'<script src="speaker-view.js?v={speaker_hash}"></script>', html_content)
    html_content = re.sub(r'<script src="chara-modal\.js(?:\?v=[^"]*)?"></script>', f'<script src="chara-modal.js?v={modal_hash}"></script>', html_content)
    html_content = re.sub(r'<script src="dialogue-normalizer\.js(?:\?v=[^"]*)?"></script>', f'<script src="dialogue-normalizer.js?v={norm_hash}"></script>', html_content)
    html_content = re.sub(r'<script src="media-service\.js(?:\?v=[^"]*)?"></script>', f'<script src="media-service.js?v={media_hash}"></script>', html_content)
    html_content = re.sub(r'<script src="dialogue-view\.js(?:\?v=[^"]*)?"></script>', f'<script src="dialogue-view.js?v={dialogue_hash}"></script>', html_content)
    html_content = re.sub(r'<script src="map\.js(?:\?v=[^"]*)?"></script>', f'<script src="map.js?v={map_hash}"></script>', html_content)

    return html_content

def get_expected_icon_unit_mappings(dashboard_dir: Path = DASHBOARD_DIR) -> Dict[str, Path]:
    """
    計算 canonical dist icon/unit 檔名與其對應之 source 實體檔案 Path 映射。
    
    【Phase 5 架構升級：Manifest-First Authority】
    1. 唯一權威依據為 dashboard/data/avatar_assets.json
    2. 對於 status == 'active' 的資產（含 897 個對白頭像與 30 個 UI 頭像）：
       - 100% 精準映射至 dist_story_map/icon/unit/<filename>
       - 若 source 實體檔案缺失，立即拋出明確異常，絕不代換
    3. 對於 status == 'placeholder_only' 的實體（3 個無圖差分）：
       - 不要求二進位圖檔，不加入發布清單，亦不報錯
    4. 若 manifest 不存在，回退至 legacy fallback 模式並輸出警告
    """
    mappings: Dict[str, Path] = {}
    manifest_path = dashboard_dir / "data" / "avatar_assets.json"

    # 1. 權威路徑：Manifest 驅動發布 (Primary Authority)
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
            
            for asset in manifest_data.get("assets", []):
                status = asset.get("status")
                if status == "active":
                    fname = asset.get("filename")
                    if not fname:
                        raise ValueError(f"[ERROR] Active manifest asset missing filename (ID: {asset.get('unit_id')})")
                    src_path = dashboard_dir / "icon" / "unit" / fname
                    if not src_path.exists():
                        raise FileNotFoundError(f"[ERROR] Active manifest asset missing physical file: {src_path} (ID: {asset.get('unit_id')})")
                    mappings[fname] = src_path
                elif status == "placeholder_only":
                    # 預期無實體二進位，安全略過
                    continue

            return mappings
        except Exception as e:
            if isinstance(e, FileNotFoundError):
                raise
            print(f"  [WARN] 讀取 avatar_assets.json 失敗，回退至舊版發布規則: {e}", file=sys.stderr)

    # 2. 舊版備用規則 (Legacy Fallback - 僅在無 manifest 時生效)
    icon_src_dir = dashboard_dir / "icon" / "unit"
    tracked_path = dashboard_dir / "data" / "tracked_characters.json"
    if tracked_path.exists():
        try:
            with open(tracked_path, "r", encoding="utf-8") as f:
                tracked = json.load(f)
            for char in tracked.get("characters", []):
                for icon_id in char.get("icon_ids", []):
                    for ext in [".webp", ".png"]:
                        is_canon = icon_src_dir / f"{icon_id}{ext}"
                        is_legacy = icon_src_dir / f"unit_icon_{icon_id}{ext}"
                        if is_canon.exists():
                            mappings[f"{icon_id}{ext}"] = is_canon
                        if is_legacy.exists():
                            mappings[f"unit_icon_{icon_id}{ext}"] = is_legacy
                            if not is_canon.exists():
                                mappings[f"{icon_id}{ext}"] = is_legacy
        except Exception as e:
            print(f"  [WARN] 讀取 tracked_characters.json 異常: {e}", file=sys.stderr)

    REALITY_UNIT_IDS = {
        100132, 100232, 100332, 100432, 100531, 100632,
        100731, 100832, 100931, 101032, 101131, 101231,
        101332, 101431, 101533, 101632, 101732, 101832,
        102032, 102131, 102232, 102332, 102531, 102632,
        102732, 102832, 102931, 103031, 103132, 103232,
        103332, 103432, 103633, 103732, 103832, 104032,
        104232, 104331, 104431, 104532, 104632, 104732,
        104833, 104932, 105032, 105132, 105231, 105332,
        105432, 105532, 105632, 105731, 105831, 105932,
        106031, 106131, 106331, 106432, 106532, 106631,
        106731, 106832, 106931, 107032, 107131, 110832,
        110932, 111032, 111431, 112431, 112531, 112631,
        118031, 118131, 118231, 118531, 122332, 123331,
        125631, 125831, 126031, 126131, 126431, 126532,
        127731, 127831, 129031, 129631, 129731, 130031,
        130132, 130231, 130931, 132331, 132431, 132531,
        133032, 133131, 133631, 134031, 134731, 134931,
        135531, 135631, 135831, 135931, 136031, 136132,
        136231
    }
    if icon_src_dir.exists():
        for item in icon_src_dir.glob("*.*"):
            if item.suffix.lower() not in [".png", ".webp"]:
                continue
            clean_id = item.stem.replace("unit_icon_", "")
            if clean_id.isdigit():
                val = int(clean_id)
                if (190000 <= val <= 199999) or (val in [107411, 107412, 107431]) or (val in REALITY_UNIT_IDS):
                    mappings[item.name] = item
                    if val < 190000 and val not in REALITY_UNIT_IDS:
                        base_id = (val // 100) * 100
                        mappings[f"{base_id + 31}{item.suffix.lower()}"] = item

    return mappings

def build_expected_icon_unit_set(dashboard_dir: Path = DASHBOARD_DIR) -> Set[str]:
    """根據 get_expected_icon_unit_mappings 回傳所有 expected icon 檔名集合"""
    return set(get_expected_icon_unit_mappings(dashboard_dir).keys())

def get_expected_dialogue_override_mappings(dashboard_dir: Path = DASHBOARD_DIR) -> Dict[str, Path]:
    """
    計算由 avatar_assets.json 中 dialogue_asset 宣告的覆蓋頭像映射。
    :return: {rel_path_str: source_Path}
    """
    mappings: Dict[str, Path] = {}
    manifest_path = dashboard_dir / "data" / "avatar_assets.json"
    if not manifest_path.exists():
        return mappings

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
        for asset in manifest_data.get("assets", []):
            if asset.get("status") == "active" and "dialogue_asset" in asset:
                d_asset = asset["dialogue_asset"]
                p_str = d_asset.get("path")
                if not p_str:
                    continue
                # 路徑安全檢查
                if ".." in p_str or p_str.startswith(("/", "\\", "http://", "https://")):
                    raise ValueError(f"[ERROR] Insecure dialogue_asset path: {p_str}")
                if not p_str.startswith("icon/story_unit/"):
                    raise ValueError(f"[ERROR] dialogue_asset path must be under icon/story_unit/: {p_str}")
                
                src_path = dashboard_dir / p_str
                if not src_path.exists():
                    raise FileNotFoundError(f"[ERROR] Active dialogue_asset missing physical file: {src_path}")
                mappings[p_str] = src_path
    except Exception as e:
        if isinstance(e, (FileNotFoundError, ValueError)):
            raise
        print(f"  [WARN] 讀取 dialogue_asset 異常: {e}", file=sys.stderr)

    return mappings

def build_expected_story_unit_set(dashboard_dir: Path = DASHBOARD_DIR) -> Set[str]:
    """回傳所有 expected icon/story_unit 檔名集合"""
    return {p.name for p in get_expected_dialogue_override_mappings(dashboard_dir).values()}

def prune_stale_dist_assets(dashboard_dir: Path = DASHBOARD_DIR, dist_dir: Path = DIST_DIR, dry_run: bool = False) -> Dict[str, Tuple[int, int]]:
    """
    執行決定性清理 (Deterministic Pruning)：
    1. 清理 Production-excluded still/story
    2. 清理鏡像目錄中已在 source 消失的檔案 (story/*.json, data/*.json, still/bg/*, still/scenario/*)
    3. 清理 icon/unit 中不在 expected 集合的 .webp/.png
    4. 清理明確歷史殘留目錄 (icon/still_unit, icon/debug_new, icon/debug_specific)
    5. 清理明確重複 DB (redive_tw-DESKTOP-*.db)
    :return: 依類別記錄清理的 (數量, bytes)
    """
    prune_stats: Dict[str, Tuple[int, int]] = {}

    def record_prune(category: str, cnt: int, b: int):
        cur_cnt, cur_b = prune_stats.get(category, (0, 0))
        prune_stats[category] = (cur_cnt + cnt, cur_b + b)

    # 1. 清理仍然存在於 dist 的 still/story (正式生產包完全排除)
    dist_still_story = dist_dir / "still" / "story"
    if dist_still_story.exists():
        cnt, b = safe_prune_dir(dist_still_story, dry_run=dry_run, dist_root=dist_dir)
        record_prune("still/story", cnt, b)

    # 2. 清理明確歷史垃圾目錄
    for legacy_dir_name in ["icon/still_unit", "icon/debug_new", "icon/debug_specific"]:
        ld = dist_dir / legacy_dir_name
        if ld.exists():
            cnt, b = safe_prune_dir(ld, dry_run=dry_run, dist_root=dist_dir)
            record_prune(legacy_dir_name, cnt, b)

    # 3. 清理明確重複 DB
    for dup_db_name in ["redive_tw-DESKTOP-N6EC182.db", "redive_tw-DESKTOP-N6EC182-2.db"]:
        dup_db_path = dist_dir / dup_db_name
        if dup_db_path.exists():
            cnt, b = safe_prune_file(dup_db_path, dry_run=dry_run, dist_root=dist_dir)
            record_prune("duplicate DB", cnt, b)

    # 4. 清理鏡像目錄中的孤立檔案
    # 4A. story/*.json
    dist_story_dir = dist_dir / "story"
    src_story_dir = dashboard_dir / "story"
    if dist_story_dir.exists() and src_story_dir.exists():
        src_story_names = {p.name for p in src_story_dir.glob("*.json")}
        for df in list(dist_story_dir.glob("*.json")):
            if df.name not in src_story_names:
                cnt, b = safe_prune_file(df, dry_run=dry_run, dist_root=dist_dir)
                record_prune("stale story JSON", cnt, b)

    # 4B. data/*.json
    dist_data_dir = dist_dir / "data"
    src_data_dir = dashboard_dir / "data"
    if dist_data_dir.exists() and src_data_dir.exists():
        src_data_names = {p.name for p in src_data_dir.glob("*.json")}
        src_data_names.add("db_info.json")  # bundler 產生物件
        for df in list(dist_data_dir.glob("*.json")):
            if df.name not in src_data_names:
                cnt, b = safe_prune_file(df, dry_run=dry_run, dist_root=dist_dir)
                record_prune("stale data JSON", cnt, b)

    # 4C. still/bg/*
    dist_bg_dir = dist_dir / "still" / "bg"
    src_bg_dir = dashboard_dir / "still" / "bg"
    if dist_bg_dir.exists() and src_bg_dir.exists():
        src_bg_names = {p.name for p in src_bg_dir.glob("*.*") if p.suffix.lower() in IMAGE_EXTENSIONS}
        for df in list(dist_bg_dir.glob("*.*")):
            if df.suffix.lower() in IMAGE_EXTENSIONS and df.name not in src_bg_names:
                cnt, b = safe_prune_file(df, dry_run=dry_run, dist_root=dist_dir)
                record_prune("stale still/bg", cnt, b)

    # 4D. still/scenario/*
    dist_sc_dir = dist_dir / "still" / "scenario"
    src_sc_dir = dashboard_dir / "still" / "scenario"
    if dist_sc_dir.exists() and src_sc_dir.exists():
        src_sc_names = {p.name for p in src_sc_dir.glob("*.*") if p.suffix.lower() in IMAGE_EXTENSIONS}
        for df in list(dist_sc_dir.glob("*.*")):
            if df.suffix.lower() in IMAGE_EXTENSIONS and df.name not in src_sc_names:
                cnt, b = safe_prune_file(df, dry_run=dry_run, dist_root=dist_dir)
                record_prune("stale still/scenario", cnt, b)

    # 4E. icon/story/*.webp (官方劇情專屬縮圖鏡像清理)
    dist_icon_story_dir = dist_dir / "icon" / "story"
    src_icon_story_dir = dashboard_dir / "icon" / "story"
    if dist_icon_story_dir.exists() and src_icon_story_dir.exists():
        src_story_icons = {p.name for p in src_icon_story_dir.glob("*.webp")}
        for df in list(dist_icon_story_dir.glob("*.webp")):
            if df.name not in src_story_icons:
                cnt, b = safe_prune_file(df, dry_run=dry_run, dist_root=dist_dir)
                record_prune("stale icon/story", cnt, b)

    # 5. 清理 icon/unit/ 中不在 expected set 的圖片
    dist_icon_unit_dir = dist_dir / "icon" / "unit"
    if dist_icon_unit_dir.exists():
        expected_icons = build_expected_icon_unit_set(dashboard_dir)
        for item in list(dist_icon_unit_dir.glob("*.*")):
            if item.suffix.lower() in IMAGE_EXTENSIONS and item.name not in expected_icons:
                cnt, b = safe_prune_file(item, dry_run=dry_run, dist_root=dist_dir)
                record_prune("icon/unit surplus", cnt, b)

    # 5B. 清理 icon/story_unit/ 中不在 expected story_unit 集合的圖片
    dist_story_unit_dir = dist_dir / "icon" / "story_unit"
    if dist_story_unit_dir.exists():
        expected_story_units = build_expected_story_unit_set(dashboard_dir)
        for item in list(dist_story_unit_dir.glob("*.*")):
            if item.suffix.lower() in IMAGE_EXTENSIONS and item.name not in expected_story_units:
                cnt, b = safe_prune_file(item, dry_run=dry_run, dist_root=dist_dir)
                record_prune("icon/story_unit surplus", cnt, b)

    return prune_stats

def sync_nojekyll(dist_dir: Path = DIST_DIR, dry_run: bool = False) -> Tuple[str, int]:
    """
    決定性 .nojekyll 管理：
    - absent: 建立空檔案 (0 bytes)
    - exists and size > 0: 截斷正規化為 0 bytes
    - exists and size == 0: 保持不變
    :return: (action_status, size)
    """
    nojekyll_path = dist_dir / ".nojekyll"
    if not nojekyll_path.exists():
        if not dry_run:
            nojekyll_path.parent.mkdir(parents=True, exist_ok=True)
            nojekyll_path.write_bytes(b"")
        return "created", 0
    else:
        sz = nojekyll_path.stat().st_size
        if sz > 0:
            if not dry_run:
                try:
                    nojekyll_path.write_bytes(b"")
                except PermissionError:
                    os.chmod(nojekyll_path, stat.S_IWRITE)
                    nojekyll_path.write_bytes(b"")
            return "normalized", 0
        return "unchanged", 0

def calculate_expected_additions_and_deltas(dashboard_dir: Path = DASHBOARD_DIR, dist_dir: Path = DIST_DIR) -> Tuple[int, int]:
    """
    計算如果執行打包，預計新增的檔案 bytes (additions) 與修改檔案的 size 變化 (deltas)。
    僅計算 Canonical Production 範圍（排除 .git, sound, card）。
    :return: (additions_bytes, deltas_bytes)
    """
    additions = 0
    deltas = 0

    # 1. 核心檔案
    core_files = [
        "style.css", "db.js", "avatar-service.js", "story-asset-service.js",
        "chapter-data.js", "characters.js", "speaker-view.js", "chara-modal.js",
        "dialogue-normalizer.js", "media-service.js", "dialogue-view.js",
        "map.js", "sql-wasm.js", "sql-wasm.wasm", "redive_tw.db"
    ]
    for cf in core_files:
        sf = dashboard_dir / cf
        df = dist_dir / cf
        if sf.exists():
            s_sz = sf.stat().st_size
            if not df.exists():
                additions += s_sz
            else:
                d_sz = df.stat().st_size
                if calc_sha256(sf) != calc_sha256(df):
                    deltas += (s_sz - d_sz)

    # 2. data/*.json (排除由步驟 3 動態生成的 db_info.json)
    src_data = dashboard_dir / "data"
    dst_data = dist_dir / "data"
    if src_data.exists():
        for jf in src_data.glob("*.json"):
            if jf.name == "db_info.json":
                continue
            df = dst_data / jf.name
            s_sz = jf.stat().st_size
            if not df.exists():
                additions += s_sz
            else:
                d_sz = df.stat().st_size
                if calc_sha256(jf) != calc_sha256(df):
                    deltas += (s_sz - d_sz)

    # 3. db_info.json (精確計算 bytes)
    db_src = dashboard_dir / "redive_tw.db"
    db_sz = db_src.stat().st_size if db_src.exists() else 0
    db_hash = calc_sha256(db_src)[:12] if db_src.exists() else "nodata"
    sim_db_info = json.dumps({"db_version": f"hash_{db_hash}", "tw_size": db_sz, "jp_size": 0}, ensure_ascii=False, indent=2).encode("utf-8")
    db_info_dst = dst_data / "db_info.json"
    if not db_info_dst.exists():
        additions += len(sim_db_info)
    else:
        d_sz = db_info_dst.stat().st_size
        if db_info_dst.read_bytes() != sim_db_info:
            deltas += (len(sim_db_info) - d_sz)

    # 4. index.html (精確渲染計算 bytes，不使用任何 hardcoded 大小)
    try:
        rendered_html = render_index_html(dashboard_dir)
        rendered_bytes = rendered_html.encode("utf-8")
        html_dst = dist_dir / "index.html"
        if not html_dst.exists():
            additions += len(rendered_bytes)
        else:
            d_sz = html_dst.stat().st_size
            if calc_sha256_bytes(rendered_bytes) != calc_sha256(html_dst):
                deltas += (len(rendered_bytes) - d_sz)
    except Exception:
        pass

    # 5. story/*.json
    src_story = dashboard_dir / "story"
    dst_story = dist_dir / "story"
    if src_story.exists():
        for sf in src_story.glob("*.json"):
            df = dst_story / sf.name
            s_sz = sf.stat().st_size
            if not df.exists():
                additions += s_sz
            else:
                d_sz = df.stat().st_size
                if calc_sha256(sf) != calc_sha256(df):
                    deltas += (s_sz - d_sz)

    # 6. still/bg & still/scenario
    for sub in ["still/bg", "still/scenario"]:
        sd = dashboard_dir / sub
        dd = dist_dir / sub
        if sd.exists():
            for sf in sd.glob("*.*"):
                if sf.suffix.lower() in IMAGE_EXTENSIONS:
                    df = dd / sf.name
                    s_sz = sf.stat().st_size
                    if not df.exists():
                        additions += s_sz
                    else:
                        d_sz = df.stat().st_size
                        if calc_sha256(sf) != calc_sha256(df):
                            deltas += (s_sz - d_sz)

    # 7. icon/unit (使用 get_expected_icon_unit_mappings 精確計算，涵蓋 legacy->canonical 與 NPC 規整化)
    icon_mappings = get_expected_icon_unit_mappings(dashboard_dir)
    dst_icon = dist_dir / "icon" / "unit"
    for dst_name, sf in icon_mappings.items():
        if sf.exists():
            df = dst_icon / dst_name
            s_sz = sf.stat().st_size
            if not df.exists():
                additions += s_sz
            else:
                d_sz = df.stat().st_size
                if calc_sha256(sf) != calc_sha256(df):
                    deltas += (s_sz - d_sz)

    # 7B. icon/story (官方劇情專屬縮圖)
    src_icon_story = dashboard_dir / "icon" / "story"
    dst_icon_story = dist_dir / "icon" / "story"
    if src_icon_story.exists():
        for sf in src_icon_story.glob("*.webp"):
            df = dst_icon_story / sf.name
            s_sz = sf.stat().st_size
            if not df.exists():
                additions += s_sz
            else:
                d_sz = df.stat().st_size
                if calc_sha256(sf) != calc_sha256(df):
                    deltas += (s_sz - d_sz)

    # 7C. icon/story_unit (對白專屬覆蓋頭像)
    story_overrides = get_expected_dialogue_override_mappings(dashboard_dir)
    for rel_path, sf in story_overrides.items():
        if sf.exists():
            df = dist_dir / rel_path
            s_sz = sf.stat().st_size
            if not df.exists():
                additions += s_sz
            else:
                d_sz = df.stat().st_size
                if calc_sha256(sf) != calc_sha256(df):
                    deltas += (s_sz - d_sz)

    return additions, deltas

def bundle_story_map(dry_run: bool = False) -> bool:
    """
    封裝 Story Map 至 dist_story_map/
    :param dry_run: 模擬運行模式（零副作用）：完整計算同步與清理計畫，不寫入或刪除任何實體檔案
    """
    mode_str = "[DRY-RUN 模擬運行模式]" if dry_run else "[實體封裝發布模式]"
    print(f"\n📦 開始封裝 Story Map 獨立發布包... {mode_str}")
    print(f"  [Root] 專案根目錄: {PROJECT_ROOT}")
    print(f"  [Src]  源碼目錄: {DASHBOARD_DIR}")
    print(f"  [Dst]  輸出目錄: {DIST_DIR}")

    if not DASHBOARD_DIR.exists():
        print(f"  [ERROR] dashboard 目錄不存在: {DASHBOARD_DIR}", file=sys.stderr)
        return False

    if not dry_run:
        DIST_DIR.mkdir(parents=True, exist_ok=True)

    # 計算初始符合部署條件的大小 (排除 .git, sound, card)
    initial_deployment_size = get_directory_size(DIST_DIR, exclude_subdirs={".git", "sound", "card"})

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
    core_updated = 0
    for src_name, dst_name in core_files:
        sf = DASHBOARD_DIR / src_name
        df = DIST_DIR / dst_name
        if sf.exists():
            if copy_if_different(sf, df, force_overwrite=True, dry_run=dry_run):
                core_updated += 1

    # 2. 同步資料庫 (redive_tw.db)
    db_src = DASHBOARD_DIR / "redive_tw.db"
    db_dst = DIST_DIR / "redive_tw.db"
    db_hash = calc_sha256(db_src)[:12] if db_src.exists() else "nodata"
    db_updated = 0
    if db_src.exists():
        if copy_if_different(db_src, db_dst, dry_run=dry_run):
            db_updated += 1

    # 3. 同步 data/ 下所有 JSON 元數據 (排除由步驟 4 動態生成的 db_info.json)
    src_data_dir = DASHBOARD_DIR / "data"
    dst_data_dir = DIST_DIR / "data"
    data_updated = 0
    if src_data_dir.exists():
        for jf in src_data_dir.glob("*.json"):
            if jf.name == "db_info.json":
                continue
            if copy_if_different(jf, dst_data_dir / jf.name, force_overwrite=True, dry_run=dry_run):
                data_updated += 1

    # 4. 計算決定性 db_version
    db_size = db_src.stat().st_size if db_src.exists() else 0
    db_info_bytes = json.dumps({
        "db_version": f"hash_{db_hash}",
        "tw_size": db_size,
        "jp_size": 0
    }, ensure_ascii=False, indent=2).encode("utf-8")
    db_info_path = dst_data_dir / "db_info.json"
    if not dry_run:
        dst_data_dir.mkdir(parents=True, exist_ok=True)
        db_info_path.write_bytes(db_info_bytes)
    print(f"  [DB Info] 決定性 db_version: hash_{db_hash} (檔案大小: {db_size} bytes)")

    # 5. 同步劇情 JSON (全量 9000+ 對白)
    story_copied = sync_directory_assets(DASHBOARD_DIR / "story", DIST_DIR / "story", [".json"], dry_run=dry_run)

    # 6. 同步輕量背景與場景圖 (still/bg, still/scenario)
    # 注意：大體積 still/story (~1.24 GB) 已完全移交遠端 CDN，不再打包至發布包！
    bg_copied = sync_directory_assets(DASHBOARD_DIR / "still" / "bg", DIST_DIR / "still" / "bg", [".webp", ".png"], dry_run=dry_run)
    scenario_copied = sync_directory_assets(DASHBOARD_DIR / "still" / "scenario", DIST_DIR / "still" / "scenario", [".webp", ".png"], dry_run=dry_run)

    # 7. 精準同步角色卡面與頭像 (使用 get_expected_icon_unit_mappings 精準同步)
    card_copied = 0
    icon_copied = 0
    tracked_path = DASHBOARD_DIR / "data" / "tracked_characters.json"
    if tracked_path.exists():
        try:
            with open(tracked_path, "r", encoding="utf-8") as f:
                tracked = json.load(f)
            for char in tracked.get("characters", []):
                # 卡面立繪同步 (支援 canonical 與 legacy)
                for card_id in char.get("card_ids", []):
                    for ext in [".webp", ".png"]:
                        cs_canon = DASHBOARD_DIR / "card" / "full" / f"{card_id}{ext}"
                        cs_legacy = DASHBOARD_DIR / "card" / "full" / f"card_full_{card_id}{ext}"
                        if cs_canon.exists():
                            if copy_if_different(cs_canon, DIST_DIR / "card" / "full" / f"{card_id}{ext}", dry_run=dry_run):
                                card_copied += 1
                        if cs_legacy.exists():
                            if copy_if_different(cs_legacy, DIST_DIR / "card" / "full" / f"card_full_{card_id}{ext}", dry_run=dry_run):
                                card_copied += 1
                            if not cs_canon.exists():
                                if copy_if_different(cs_legacy, DIST_DIR / "card" / "full" / f"{card_id}{ext}", dry_run=dry_run):
                                    card_copied += 1
        except Exception as e:
            print(f"  [WARN] 卡面素材同步異常: {e}", file=sys.stderr)

    # 精準頭像同步
    icon_mappings = get_expected_icon_unit_mappings(DASHBOARD_DIR)
    for dst_name, src_file in icon_mappings.items():
        df = DIST_DIR / "icon" / "unit" / dst_name
        if copy_if_different(src_file, df, dry_run=dry_run):
            icon_copied += 1

    # 7B. 同步官方劇情專屬縮圖 (icon/story)
    icon_story_copied = sync_directory_assets(DASHBOARD_DIR / "icon" / "story", DIST_DIR / "icon" / "story", [".webp"], dry_run=dry_run)
    if icon_story_copied > 0:
        print(f"  [Thumb] 官方劇情專屬縮圖: {'預計同步' if dry_run else '已同步'} {icon_story_copied} 個檔案")

    # 7C. 同步對白專屬覆蓋頭像 (icon/story_unit)
    story_override_copied = 0
    story_overrides = get_expected_dialogue_override_mappings(DASHBOARD_DIR)
    for rel_path, src_file in story_overrides.items():
        df = DIST_DIR / rel_path
        df.parent.mkdir(parents=True, exist_ok=True)
        if copy_if_different(src_file, df, dry_run=dry_run):
            story_override_copied += 1
    if story_override_copied > 0:
        print(f"  [Avatar Override] 對白專屬覆蓋頭像: {'預計同步' if dry_run else '已同步'} {story_override_copied} 個檔案")

    # 8. 同步語音音檔 (sound/story_vo) - 本機發布包同步，受 .gitignore 排除
    voice_copied = sync_directory_assets(DASHBOARD_DIR / "sound" / "story_vo", DIST_DIR / "sound" / "story_vo", [".m4a"], dry_run=dry_run)

    # 9. 決定性 .nojekyll 管理
    nojekyll_act, _ = sync_nojekyll(DIST_DIR, dry_run=dry_run)
    if nojekyll_act == "created":
        print(f"  [Pages] .nojekyll 標記{'預計建立' if dry_run else '已建立'} (0 bytes)")
    elif nojekyll_act == "normalized":
        print(f"  [Pages] .nojekyll 標記非空，{'預計正規化' if dry_run else '已正規化'}為 0 bytes")
    else:
        print("  [Pages] .nojekyll 標記已就緒 (0 bytes)")

    # 10. 決定性 index.html 生成與 Cache-Busting (共用 render_index_html 邏輯)
    try:
        rendered_html = render_index_html(DASHBOARD_DIR)
        html_dst = DIST_DIR / "index.html"
        if not dry_run:
            html_dst.write_bytes(rendered_html.encode("utf-8"))
        print(f"  [HTML] 決定性內嵌與 Cache-Busting 完成 (渲染大小: {len(rendered_html.encode('utf-8'))} bytes)")
    except Exception as e:
        print(f"  [ERROR] index.html 渲染失敗: {e}", file=sys.stderr)
        return False

    # 11. 執行決定性清理 (Deterministic Pruning)
    print("\n🧹 執行發布包決定性清理 (Deterministic Pruning)...")
    prune_stats = prune_stale_dist_assets(DASHBOARD_DIR, DIST_DIR, dry_run=dry_run)

    total_pruned_cnt = sum(cnt for cnt, _ in prune_stats.values())
    total_pruned_bytes = sum(b for _, b in prune_stats.values())
    print(f"  [Prune] 清理項目摘要 ({'預計清理' if dry_run else '已清理'}): 共 {total_pruned_cnt} 個檔案, {total_pruned_bytes / (1024*1024):.2f} MiB ({total_pruned_bytes:,} bytes)")
    for cat, (cnt, b) in sorted(prune_stats.items()):
        if cnt > 0:
            print(f"    - {cat:<22}: {cnt:>5} files | {b:>12,} bytes | {b / (1024*1024):>8.2f} MiB")

    # 12. 計算最終與預估體積 (精準反映 additions/deltas)
    if dry_run:
        additions_bytes, deltas_bytes = calculate_expected_additions_and_deltas(DASHBOARD_DIR, DIST_DIR)
        net_delta_bytes = additions_bytes + deltas_bytes
        projected_deployment_size = initial_deployment_size - total_pruned_bytes + net_delta_bytes

        print(f"\n📊 [DRY-RUN 部署體積精準預估報表]")
        print(f"  Current deployment footprint:    {initial_deployment_size:>12,} bytes ({initial_deployment_size / (1024*1024):>8.2f} MiB)")
        print(f"  Planned prune:                   {total_pruned_bytes:>12,} bytes ({total_pruned_bytes / (1024*1024):>8.2f} MiB)")
        print(f"  Planned additions/updates delta: {net_delta_bytes:>12,} bytes ({net_delta_bytes / (1024*1024):>8.2f} MiB)")
        print(f"  Projected deployment footprint:  {projected_deployment_size:>12,} bytes ({projected_deployment_size / (1024*1024):>8.2f} MiB)")
        print("  [DRY-RUN] 模擬運行模式（零副作用）：未寫入或修改任何實體檔案。")
    else:
        final_deployment_size = get_directory_size(DIST_DIR, exclude_subdirs={".git", "sound", "card"})
        print(f"\n  [Dist Size] 發布包最終體積: {final_deployment_size / (1024*1024):.2f} MiB (清理前: {initial_deployment_size / (1024*1024):.2f} MiB, 淨減量: {(initial_deployment_size - final_deployment_size) / (1024*1024):.2f} MiB)")
        print("✅ Story Map 封裝與瘦身清理完成！")

    return True

if __name__ == "__main__":
    dry_run_mode = "--dry-run" in sys.argv
    success = bundle_story_map(dry_run=dry_run_mode)
    sys.exit(0 if success else 1)
