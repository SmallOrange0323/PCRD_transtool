#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Validator (Single Source of Verification)
提供發布前與更新後的資料完整性自檢門禁。全專案唯一的驗證邏輯來源。
包含：
1. 核心檔案與 WASM/DB 存在性
2. 元數據 JSON 解析與 Schema 檢驗
3. 全量 9000+ 對白 JSON 語法與完整性
4. 決定性 Cache-Busting 與內嵌標記檢驗
5. 部署體積門禁 (Deployment Footprint Gate: Warning 750 MiB, Hard Error 900 MiB)
"""

import os
import sys
import json
import sqlite3
import hashlib
from pathlib import Path
from typing import Tuple, Set, Optional, List, Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
DIST_DIR = PROJECT_ROOT / "dist_story_map"

# 部署體積門禁閾值 (Bytes)
FOOTPRINT_WARN_BYTES = 750 * 1024 * 1024   # 750 MiB
FOOTPRINT_HARD_BYTES = 900 * 1024 * 1024   # 900 MiB

# 歷史已知之偽造大綱完整文字 (Anti-Hallucination Guard)
KNOWN_FAKE_SYNOPSES_EXACT = {
    "本話為重要主線劇情，美食殿堂的羈絆在此得到了進一步的昇華。",
}

class ValidationResult:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, msg: str):
        self.errors.append(msg)
        print(f"  [ERROR] {msg}")

    def warning(self, msg: str):
        self.warnings.append(msg)
        print(f"  [WARN]  {msg}")

    def ok(self, msg: str):
        print(f"  [OK]    {msg}")

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

def calc_sha256(filepath: Path) -> str:
    if not filepath.exists():
        return ""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def calculate_deployment_footprint(dist_dir: Path = DIST_DIR, exclude_subdirs: Optional[Set[str]] = None) -> int:
    """
    計算預期部署至 GitHub Pages 的實際資產總大小 (bytes)。
    .git  → excluded
    card  → excluded (本機卡面完整大圖，不納入部署)
    sound → INCLUDED (sound/story_vo/*.m4a 包含正式發布的 Gap 語音集合)
    """
    if not dist_dir.exists():
        return 0
    total = 0
    excl = exclude_subdirs or {".git", "card"}
    for root, dirs, files in os.walk(dist_dir):
        rel = Path(root).relative_to(dist_dir)
        parts = rel.parts
        if any(p in excl for p in parts):
            continue
        for f in files:
            try:
                total += (Path(root) / f).stat().st_size
            except Exception:
                pass
    return total

def check_footprint_gate(dist_dir: Path = DIST_DIR, footprint_bytes: Optional[int] = None) -> Tuple[bool, str, int]:
    """
    檢查部署體積門禁。
    :return: (is_pass, status_msg, actual_bytes)
    """
    actual_bytes = footprint_bytes if footprint_bytes is not None else calculate_deployment_footprint(dist_dir)
    actual_mib = actual_bytes / (1024 * 1024)
    warn_mib = FOOTPRINT_WARN_BYTES / (1024 * 1024)
    hard_mib = FOOTPRINT_HARD_BYTES / (1024 * 1024)

    msg = f"Deployment footprint: {actual_mib:.1f} MiB ({actual_bytes:,} bytes) | Warning: {warn_mib:.0f} MiB | Hard limit: {hard_mib:.0f} MiB"
    if actual_bytes >= FOOTPRINT_HARD_BYTES:
        return False, f"{msg} -> HARD ERROR (超過 900 MiB 上限！)", actual_bytes
    elif actual_bytes >= FOOTPRINT_WARN_BYTES:
        return True, f"{msg} -> WARNING (已超過 750 MiB 預警線)", actual_bytes
    else:
        return True, f"{msg} -> PASS", actual_bytes

def validate_story_source_dist_parity(
    src_story_dir: Path,
    dist_story_dir: Path,
    result: Optional[ValidationResult] = None,
    verbose: bool = True
) -> Tuple[bool, dict]:
    """
    Permanent validation gate ensuring semantic parity between source and dist stories.
    Validates:
    1. Numeric story file set parity (source IDs == dist IDs)
    2. Unit ID sequence parity (source unit_id sequence == dist unit_id sequence)
    3. Dialogue type parity (source dialogue count == dist dialogue count)
    4. Movie command sequence parity (source movie_ids sequence == dist movie_ids sequence)
    """
    res = result or ValidationResult()
    stats = {
        "source_stories": 0,
        "dist_stories": 0,
        "unit_id_mismatches": 0,
        "dialogue_mismatches": 0,
        "movie_mismatches": 0,
        "missing_in_dist": [],
        "extra_in_dist": [],
        "unit_id_mismatch_samples": [],
        "dialogue_mismatch_samples": [],
        "movie_mismatch_samples": []
    }

    if not src_story_dir.exists():
        res.error(f"源碼對白目錄不存在: {src_story_dir}")
        return False, stats

    if not dist_story_dir.exists():
        res.error(f"發布對白目錄不存在: {dist_story_dir}")
        return False, stats

    # 1. 蒐集數值型故事集合 (排除非數值輔助 JSON)
    src_files = {}
    for p in src_story_dir.glob("*.json"):
        if p.stem.isdigit():
            src_files[int(p.stem)] = p

    dist_files = {}
    for p in dist_story_dir.glob("*.json"):
        if p.stem.isdigit():
            dist_files[int(p.stem)] = p

    src_sids = set(src_files.keys())
    dist_sids = set(dist_files.keys())
    stats["source_stories"] = len(src_sids)
    stats["dist_stories"] = len(dist_sids)

    missing = sorted(list(src_sids - dist_sids))
    extra = sorted(list(dist_sids - src_sids))

    if missing:
        stats["missing_in_dist"] = missing
        sample = missing[:5]
        res.error(f"發布對白 (dist) 缺失 {len(missing)} 篇數值型故事 (範例: {sample})")

    if extra:
        stats["extra_in_dist"] = extra
        sample = extra[:5]
        res.error(f"發布對白 (dist) 多出 {len(extra)} 篇未在源碼之數值型故事 (範例: {sample})")

    # 2. 逐篇深入比對共同話數的語意合約
    common_sids = sorted(list(src_sids.intersection(dist_sids)))
    for sid in common_sids:
        src_path = src_files[sid]
        dist_path = dist_files[sid]

        try:
            with open(src_path, "r", encoding="utf-8") as f:
                s_data = json.load(f)
        except Exception as e:
            res.error(f"源碼對白 JSON 損壞: {src_path.name} - {e}")
            continue

        try:
            with open(dist_path, "r", encoding="utf-8") as f:
                d_data = json.load(f)
        except Exception as e:
            res.error(f"發布對白 JSON 損壞: {dist_path.name} - {e}")
            continue

        if not isinstance(s_data, list):
            res.error(f"源碼對白根結構非陣列: {src_path.name}")
            continue
        if not isinstance(d_data, list):
            res.error(f"發布對白根結構非陣列: {dist_path.name}")
            continue

        # A. Unit ID 序列循序比對
        s_uids = [x.get("unit_id") for x in s_data if isinstance(x, dict) and x.get("unit_id") is not None]
        d_uids = [x.get("unit_id") for x in d_data if isinstance(x, dict) and x.get("unit_id") is not None]
        if s_uids != d_uids:
            stats["unit_id_mismatches"] += 1
            if len(stats["unit_id_mismatch_samples"]) < 5:
                stats["unit_id_mismatch_samples"].append((sid, len(s_uids), len(d_uids)))

        # B. Dialogue 類型筆數比對
        s_diag_count = sum(1 for x in s_data if isinstance(x, dict) and x.get("type") == "dialogue")
        d_diag_count = sum(1 for x in d_data if isinstance(x, dict) and x.get("type") == "dialogue")
        if s_diag_count != d_diag_count:
            stats["dialogue_mismatches"] += 1
            if len(stats["dialogue_mismatch_samples"]) < 5:
                stats["dialogue_mismatch_samples"].append((sid, s_diag_count, d_diag_count))

        # C. Movie 指令循序比對
        s_movies = [x.get("movie_id") for x in s_data if isinstance(x, dict) and x.get("type") == "movie"]
        d_movies = [x.get("movie_id") for x in d_data if isinstance(x, dict) and x.get("type") == "movie"]
        if s_movies != d_movies:
            stats["movie_mismatches"] += 1
            if len(stats["movie_mismatch_samples"]) < 5:
                stats["movie_mismatch_samples"].append((sid, s_movies, d_movies))

    # 3. 回報失配錯誤
    if stats["unit_id_mismatches"] > 0:
        for sid, s_len, d_len in stats["unit_id_mismatch_samples"]:
            res.error(f"story/{sid} unit_id parity mismatch: source={s_len} dist={d_len}")
        res.error(f"發現 {stats['unit_id_mismatches']} 篇故事 unit_id 序列不一致！")

    if stats["dialogue_mismatches"] > 0:
        for sid, s_cnt, d_cnt in stats["dialogue_mismatch_samples"]:
            res.error(f"story/{sid} dialogue parity mismatch: source={s_cnt} dist={d_cnt}")
        res.error(f"發現 {stats['dialogue_mismatches']} 篇故事 dialogue 筆數不一致！")

    if stats["movie_mismatches"] > 0:
        for sid, s_mov, d_mov in stats["movie_mismatch_samples"]:
            res.error(f"story/{sid} movie parity mismatch: source={s_mov} dist={d_mov}")
        res.error(f"發現 {stats['movie_mismatches']} 篇故事 movie 指令不一致！")

    is_parity_pass = (
        len(missing) == 0 and
        len(extra) == 0 and
        stats["unit_id_mismatches"] == 0 and
        stats["dialogue_mismatches"] == 0 and
        stats["movie_mismatches"] == 0
    )

    if is_parity_pass and verbose:
        res.ok(
            f"Story source/dist parity:\n"
            f"    source stories: {stats['source_stories']}\n"
            f"    dist stories: {stats['dist_stories']}\n"
            f"    unit_id mismatches: {stats['unit_id_mismatches']}\n"
            f"    dialogue mismatches: {stats['dialogue_mismatches']}\n"
            f"    movie mismatches: {stats['movie_mismatches']}\n"
            f"    PASS"
        )

    return is_parity_pass, stats

def validate_avatar_manifest_and_assets(dashboard_dir: Path, res: ValidationResult) -> bool:
    """
    【Phase 5 架構門禁】驗證 Avatar Manifest 與實體二進位資產不變量：
    1. dashboard/data/avatar_assets.json 存在且格式合法 (單一資產登錄表)
    2. 全量正規劇本 (story/*.json) 的所有 canonical dialogue unit_id (>= 100000) 必須 100% 登錄在 manifest
    3. 每個 dialogue asset 的 status 必須為 'active' 或 'placeholder_only'
    4. 每個 active asset 必須具有實體二進位檔案，且其真實 size_bytes 與 sha256 必須與 manifest 100% 相符
    5. 每個 placeholder_only asset 不得宣告二進位屬性 (filename, size_bytes, sha256 均為 null)
    6. 不得有重複的 active asset 指向同一個 unit_id
    """
    manifest_path = dashboard_dir / "data" / "avatar_assets.json"
    if not manifest_path.exists():
        res.error(f"Avatar assets manifest 不存在: {manifest_path}")
        return False

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
    except Exception as e:
        res.error(f"Avatar assets manifest JSON 損壞: {e}")
        return False

    assets = manifest_data.get("assets", [])
    if not assets:
        res.error("Avatar assets manifest 為空！")
        return False

    # 1. 對白話數語意對等 (Story Semantic Parity)
    story_dir = dashboard_dir / "story"
    canonical_dialogue_uids = set()
    if story_dir.exists():
        for f in story_dir.glob("*.json"):
            if f.name.endswith(("_parsed.json", ".min.json")):
                continue
            try:
                with open(f, "r", encoding="utf-8") as jf:
                    data = json.load(jf)
                rows = data if isinstance(data, list) else data.get("dialogue", [])
                for r in rows:
                    uid = r.get("unit_id") if r.get("unit_id") is not None else r.get("speaker_id")
                    if uid is not None:
                        try:
                            n = int(uid)
                            if n >= 100000:
                                canonical_dialogue_uids.add(n)
                        except:
                            pass
            except:
                pass

    manifest_uids = {a.get("unit_id") for a in assets if a.get("unit_id") is not None and a.get("usage") == "dialogue"}
    missing_dialogue_in_manifest = canonical_dialogue_uids - manifest_uids
    if missing_dialogue_in_manifest:
        res.error(f"劇情對白要求的 unit_id 未在 avatar_assets.json 中登錄: {len(missing_dialogue_in_manifest)} 個 (範例: {sorted(list(missing_dialogue_in_manifest))[:5]})")
    else:
        res.ok(f"全量劇情對白要求的 {len(canonical_dialogue_uids)} 個 unit_id 皆已完整登錄於 Manifest")

    # 2. 不變量與實體檔案雜湊/大小校驗
    seen_active_dialogue_uids = set()
    icon_unit_dir = dashboard_dir / "icon" / "unit"
    active_count = 0
    placeholder_count = 0
    mismatch_errors = 0

    for asset in assets:
        uid = asset.get("unit_id")
        usage = asset.get("usage")
        status = asset.get("status")

        if status not in ["active", "placeholder_only"]:
            res.error(f"Asset ID {uid} 狀態非法: '{status}'")
            continue

        if status == "placeholder_only":
            placeholder_count += 1
            if asset.get("filename") is not None or asset.get("size_bytes") is not None or asset.get("sha256") is not None:
                res.error(f"Placeholder-only 資產不得宣告二進位屬性: ID {uid}")
            continue

        # Active 資產校驗
        active_count += 1
        if usage == "dialogue":
            if uid in seen_active_dialogue_uids:
                res.error(f"重複的 active dialogue asset: unit_id {uid}")
            seen_active_dialogue_uids.add(uid)

        fname = asset.get("filename")
        if not fname:
            res.error(f"Active 資產缺失 filename: ID {uid}")
            continue

        src_path = icon_unit_dir / fname
        if not src_path.exists():
            res.error(f"Active 資產實體檔案缺失: {src_path}")
            continue

        actual_size = src_path.stat().st_size
        declared_size = asset.get("size_bytes")
        if actual_size != declared_size:
            res.error(f"檔案大小失配: {fname} (硬碟={actual_size}, manifest={declared_size})")
            mismatch_errors += 1

        actual_sha = calc_sha256(src_path)
        declared_sha = asset.get("sha256")
        if actual_sha != declared_sha:
            res.error(f"SHA-256 雜湊失配: {fname} (硬碟={actual_sha}, manifest={declared_sha})")
            mismatch_errors += 1

        # Dialogue Override 資產校驗 (可選)
        if "dialogue_asset" in asset:
            d_asset = asset["dialogue_asset"]
            d_path_str = d_asset.get("path")
            if not d_path_str:
                res.error(f"dialogue_asset 缺失 path: ID {uid}")
                mismatch_errors += 1
            elif ".." in d_path_str or d_path_str.startswith(("/", "\\", "http://", "https://")):
                res.error(f"dialogue_asset 路徑不安全: ID {uid}, path='{d_path_str}'")
                mismatch_errors += 1
            elif not d_path_str.startswith("icon/story_unit/"):
                res.error(f"dialogue_asset 必須位於 icon/story_unit/ 底下: ID {uid}, path='{d_path_str}'")
                mismatch_errors += 1
            else:
                d_src_path = dashboard_dir / d_path_str
                if not d_src_path.exists():
                    res.error(f"dialogue_asset 實體檔案缺失: {d_src_path} (ID {uid})")
                    mismatch_errors += 1
                else:
                    d_actual_size = d_src_path.stat().st_size
                    d_declared_size = d_asset.get("size_bytes")
                    if d_actual_size != d_declared_size:
                        res.error(f"dialogue_asset 檔案大小失配: {d_path_str} (硬碟={d_actual_size}, manifest={d_declared_size})")
                        mismatch_errors += 1

                    d_actual_sha = calc_sha256(d_src_path)
                    d_declared_sha = d_asset.get("sha256")
                    if d_actual_sha != d_declared_sha:
                        res.error(f"dialogue_asset SHA-256 雜湊失配: {d_path_str} (硬碟={d_actual_sha}, manifest={d_declared_sha})")
                        mismatch_errors += 1

    if mismatch_errors == 0:
        res.ok(f"Avatar Manifest 實體二進位對等校驗通過: {active_count} 個 active 檔案大小與 SHA-256 100% 吻合, {placeholder_count} 個 placeholder_only 規格正常")

    return res.is_valid


# ==============================================================================
# Gap Voice 權威清單與資產校驗門禁 (Phase Gap-Voice)
# ==============================================================================
EXPECTED_GAP_VOICE_COUNT = 236
EXPECTED_GAP_VOICE_TOTAL_BYTES = 25051018

def load_and_validate_gap_voice_manifest(
    manifest_path: Path,
    sound_dir: Optional[Path] = None,
    verify_hashes: bool = False
) -> Tuple[List[dict], Dict[str, Path]]:
    """
    載入並嚴格驗證 Gap Voice 權威清單 (voice_gap_assets.json)。
    若清單缺失、損壞、欄位不合法、檔名不安全、包含重複檔名，或指定的音檔不存在，拋出明確異常 (Fail Loudly)。
    返回: (assets_list, {filename: physical_path})
    """
    if not manifest_path.exists():
        raise FileNotFoundError(f"[ERROR] Gap Voice 權威清單不存在: {manifest_path}")

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise ValueError(f"[ERROR] Gap Voice 清單 JSON 損壞: {e}")

    if not isinstance(data, dict):
        raise ValueError("[ERROR] Gap Voice 清單根結構必須為 JSON 物件")

    assets = data.get("assets")
    if not isinstance(assets, list):
        raise ValueError("[ERROR] Gap Voice 清單缺少 'assets' 陣列")

    declared_count = data.get("count")
    if declared_count != len(assets):
        raise ValueError(f"[ERROR] Gap Voice 清單宣告 count={declared_count} 但實際含有 {len(assets)} 筆資料")

    declared_bytes = data.get("total_bytes")
    actual_bytes = sum(a.get("size", 0) for a in assets if isinstance(a, dict))
    if declared_bytes != actual_bytes:
        raise ValueError(f"[ERROR] Gap Voice 清單宣告 total_bytes={declared_bytes} 但資產總和為 {actual_bytes}")

    seen_filenames = set()
    mappings: Dict[str, Path] = {}

    for idx, item in enumerate(assets):
        if not isinstance(item, dict):
            raise ValueError(f"[ERROR] 第 {idx} 筆資產非 JSON 物件")

        fname = item.get("filename")
        voice = item.get("voice")
        size = item.get("size")
        sha256 = item.get("sha256")

        if not isinstance(fname, str) or not fname.strip():
            raise ValueError(f"[ERROR] 第 {idx} 筆資產 filename 缺失或無效")

        # 安全性與檔名規範檢查 (防止路徑穿越與非規範檔名)
        if "/" in fname or "\\" in fname or ".." in fname:
            raise ValueError(f"[ERROR] 不安全的檔名 (包含路徑分隔符或穿越符號): {fname}")
        if os.path.isabs(fname) or "://" in fname or Path(fname).name != fname:
            raise ValueError(f"[ERROR] 不安全的檔名 (絕對路徑、URL 或非單一 basename): {fname}")
        if not fname.endswith(".m4a"):
            raise ValueError(f"[ERROR] 檔名非 .m4a 副檔名: {fname}")

        if not isinstance(voice, str) or f"{voice}.m4a" != fname:
            raise ValueError(f"[ERROR] voice 識別碼 '{voice}' 與 filename '{fname}' 不相符")

        if not isinstance(size, int) or size <= 0:
            raise ValueError(f"[ERROR] 檔案大小無效或為 0-byte: {fname} (size={size})")

        if not isinstance(sha256, str) or len(sha256) != 64:
            raise ValueError(f"[ERROR] SHA-256 格式無效: {fname}")

        if fname in seen_filenames:
            raise ValueError(f"[ERROR] 清單包含重複檔名: {fname}")
        seen_filenames.add(fname)

        if sound_dir is not None:
            phys_path = sound_dir / fname
            if not phys_path.exists():
                raise FileNotFoundError(f"[ERROR] Gap Voice 本地實體檔案缺失: {phys_path}")
            act_size = phys_path.stat().st_size
            if act_size != size:
                raise ValueError(f"[ERROR] 檔案大小不吻合: {fname} (硬碟={act_size}, 清單={size})")
            if verify_hashes:
                act_sha = calc_sha256(phys_path)
                if act_sha != sha256:
                    raise ValueError(f"[ERROR] SHA-256 雜湊不吻合: {fname} (硬碟={act_sha}, 清單={sha256})")
            mappings[fname] = phys_path

    return assets, mappings


def validate_voice_gap_manifest_and_assets(
    dashboard_dir: Path,
    dist_dir: Optional[Path] = None,
    res: Optional[ValidationResult] = None,
    check_dist: bool = False,
    verbose: bool = True
) -> bool:
    """
    驗證 Gap Voice 權威清單與二進位資產不變量：
    1. Source: voice_gap_assets.json 不變量校驗 (236 檔 / 25,051,018 bytes / 安全檔名 / SHA256)
    2. Dist (若 check_dist=True): dist/sound/story_vo/*.m4a 必須與 manifest 100% 精準對齊
    """
    if res is None:
        res = ValidationResult()

    manifest_path = dashboard_dir / "data" / "voice_gap_assets.json"
    src_sound_dir = dashboard_dir / "sound" / "story_vo"

    # 1. 來源端 Manifest 與實體資產檢驗
    try:
        assets, mappings = load_and_validate_gap_voice_manifest(
            manifest_path, sound_dir=src_sound_dir, verify_hashes=True
        )
    except Exception as e:
        res.error(str(e))
        return False

    # 生產標準常數驗證
    if len(assets) != EXPECTED_GAP_VOICE_COUNT:
        res.error(f"Gap Voice 檔案數量與生產基準不符: 實際={len(assets)}, 預期={EXPECTED_GAP_VOICE_COUNT}")
    total_bytes = sum(a["size"] for a in assets)
    if total_bytes != EXPECTED_GAP_VOICE_TOTAL_BYTES:
        res.error(f"Gap Voice 總體積與生產基準不符: 實際={total_bytes}, 預期={EXPECTED_GAP_VOICE_TOTAL_BYTES}")

    if res.is_valid:
        if verbose:
            res.ok(f"Gap Voice 權威清單與來源資產校驗通過: {len(assets)} 個音檔 ({total_bytes:,} bytes) 雜湊大小 100% 吻合")

    # 2. 發布端 Dist Parity 檢驗 (若指定 check_dist)
    if check_dist and dist_dir is not None:
        dist_sound_dir = dist_dir / "sound" / "story_vo"
        if not dist_sound_dir.exists():
            res.error(f"dist_story_map 缺失語音目錄: {dist_sound_dir}")
            return False

        dist_m4a_files = {f.name: f for f in dist_sound_dir.glob("*.m4a")}
        manifest_filenames = {a["filename"]: a for a in assets}

        missing_in_dist = set(manifest_filenames.keys()) - set(dist_m4a_files.keys())
        extra_in_dist = set(dist_m4a_files.keys()) - set(manifest_filenames.keys())

        if missing_in_dist:
            res.error(f"dist Gap Voice 缺失檔案 ({len(missing_in_dist)} 個): 範例 {sorted(list(missing_in_dist))[:5]}")
        if extra_in_dist:
            res.error(f"dist Gap Voice 含有非白名單多餘音檔 ({len(extra_in_dist)} 個): 範例 {sorted(list(extra_in_dist))[:5]}")

        # 檢驗交集檔案的大小與 SHA-256
        corrupted_in_dist = []
        for fname in sorted(set(manifest_filenames.keys()) & set(dist_m4a_files.keys())):
            df = dist_m4a_files[fname]
            exp_info = manifest_filenames[fname]
            if df.stat().st_size != exp_info["size"] or calc_sha256(df) != exp_info["sha256"]:
                corrupted_in_dist.append(fname)

        if corrupted_in_dist:
            res.error(f"dist Gap Voice 檔案內容損壞或大小/雜湊不吻合 ({len(corrupted_in_dist)} 個): 範例 {corrupted_in_dist[:5]}")

        if not missing_in_dist and not extra_in_dist and not corrupted_in_dist:
            if verbose:
                res.ok(
                    f"Gap Voice dist parity:\n"
                    f"    expected: {len(manifest_filenames)}\n"
                    f"    actual:   {len(dist_m4a_files)}\n"
                    f"    bytes:    {total_bytes:,}\n"
                    f"    PASS"
                )

    return res.is_valid


def validate_official_story_metadata(
    dashboard_dir: Path,
    dist_dir: Optional[Path] = None,
    check_dist: bool = False,
    res: Optional[ValidationResult] = None,
    allow_bootstrap_incomplete: bool = True,
    verbose: bool = True
) -> bool:
    """
    官方故事元數據 (Official Story Metadata Manifest) 專屬門禁檢驗：
    1. 來源檔案存在性與契約檢驗 (若不存在且 allow_bootstrap_incomplete 則標記 BOOTSTRAP_INCOMPLETE 狀態)
    2. validate_manifest_dict_contract 契約檢驗
    3. episode_count 與 len(episodes) 一致性
    4. 數字話數 ID 鍵名檢驗
    5. Anti-Hallucination / Fake Synopsis Regression Guard (嚴禁「美食殿堂的羈絆」、「進一步的昇華」)
    6. 覆蓋度狀態模型 (Coverage State Model: BOOTSTRAP_INCOMPLETE vs COMPLETE)
    7. 若 check_dist=True 且來源存在：
       - dist/data/official_story_metadata.json 必須存在且 SHA-256 與 source 100% 一致 (SHA Parity Gate)
       - dist/data/db_info.json 必須包含 metadata_version 且嚴格等於 sha256(source)[:12]
    """
    if res is None:
        res = ValidationResult()

    source_manifest = dashboard_dir / "data" / "official_story_metadata.json"

    # 1. 來源 Manifest 存在性檢驗
    if not source_manifest.exists():
        if allow_bootstrap_incomplete:
            res.warning("[Metadata Gate] official_story_metadata.json 尚未建立 (狀態: BOOTSTRAP_INCOMPLETE)")
            return True
        else:
            res.error("[Metadata Gate] 來源 official_story_metadata.json 不存在且不允許未完成狀態！")
            return False

    # 2. 來源 JSON 解析與 Schema 契約驗證
    try:
        source_bytes = source_manifest.read_bytes()
        source_data = json.loads(source_bytes.decode("utf-8"))
    except Exception as e:
        res.error(f"[Metadata Gate] 來源 official_story_metadata.json 解析失敗: {e}")
        return False

    try:
        from pipeline.metadata_manifest import validate_manifest_dict_contract
        validate_manifest_dict_contract(source_data)
    except Exception as e:
        res.error(f"[Metadata Gate] 來源 official_story_metadata.json 契約校驗失敗: {e}")
        return False

    # 3. episode_count 與鍵名數字格式
    episodes = source_data.get("episodes", {})
    count = source_data.get("episode_count", 0)
    if count != len(episodes):
        res.error(f"[Metadata Gate] episode_count ({count}) 與實際話數 ({len(episodes)}) 不符！")

    # 4. Anti-Hallucination / Fake Synopsis Regression Guard (精確比對歷史偽造大綱)
    for sid, ep in episodes.items():
        synopsis = ep.get("official_synopsis")
        if synopsis and isinstance(synopsis, str):
            normalized = synopsis.strip()
            if normalized in KNOWN_FAKE_SYNOPSES_EXACT:
                res.error(
                    f"[Metadata Gate] 話數 {sid} 包含已確認之假大綱/幻覺文字 (Regression Guard): '{normalized}'"
                )

    # 4.1 Runtime Regression Guard: 檢查 map.js 是否重新出現完整 fake fallback
    map_js_path = dashboard_dir / "map.js"
    if map_js_path.exists():
        map_content = map_js_path.read_text(encoding="utf-8")
        for fake_text in KNOWN_FAKE_SYNOPSES_EXACT:
            if fake_text in map_content:
                res.error(
                    f"[Metadata Gate] map.js 包含已確認之假大綱完整文字 (Runtime Regression Guard): '{fake_text}'"
                )

    # 5. 覆蓋度與話數宇宙狀態模型 (Metadata Eligible Universe & Coverage Gate)
    from pipeline.coverage import build_metadata_eligible_story_universe
    metadata_univ = build_metadata_eligible_story_universe(dashboard_dir)
    canonical_univ = metadata_univ.canonical

    if canonical_univ.analysis_status != "VALID":
        u_msg = f"[Metadata Gate] Canonical Universe 來源健康狀態異常: {canonical_univ.analysis_status} ({canonical_univ.analysis_errors})"
        if allow_bootstrap_incomplete:
            res.warning(u_msg)
        else:
            res.error(u_msg)

    if metadata_univ.missing_required_local_ids:
        req_msg = f"[Metadata Gate] 核心必備劇本缺少本地 JSON ({len(metadata_univ.missing_required_local_ids)} 話): {sorted(list(metadata_univ.missing_required_local_ids))[:10]}"
        if allow_bootstrap_incomplete:
            res.warning(req_msg)
        else:
            res.error(req_msg)

    expected_metadata_ids = metadata_univ.eligible_ids
    manifest_sids = set(int(sid) for sid in episodes.keys())

    missing_ids = expected_metadata_ids - manifest_sids
    unexpected_ids = manifest_sids - expected_metadata_ids

    if unexpected_ids:
        unexp_msg = f"[Metadata Gate] 發現 {len(unexpected_ids)} 話未知/非 Eligible 話數元數據: {sorted(list(unexpected_ids))[:10]}"
        if allow_bootstrap_incomplete:
            res.warning(unexp_msg)
        else:
            res.error(unexp_msg)

    if len(missing_ids) == 0 and len(unexpected_ids) == 0 and len(expected_metadata_ids) > 0 and len(metadata_univ.missing_required_local_ids) == 0:
        if verbose:
            res.ok(
                f"[Metadata Gate] official_story_metadata 覆蓋狀態: COMPLETE "
                f"(共 {len(manifest_sids)} 話，包含所有本地適用預期話數)"
            )
    elif missing_ids:
        msg = (
            f"[Metadata Gate] official_story_metadata 覆蓋不足: "
            f"缺失 {len(missing_ids)} 話 (現有 {len(manifest_sids)}/{len(expected_metadata_ids)} 話)"
        )
        if allow_bootstrap_incomplete:
            res.warning(f"{msg} (狀態: BOOTSTRAP_INCOMPLETE)")
        else:
            res.error(f"{msg} (未達到嚴格發布要求！)")

    # 6. 若 check_dist=True，執行 Source/Dist SHA Parity 與 db_info.json 門禁
    if check_dist and dist_dir is not None:
        dist_manifest = dist_dir / "data" / "official_story_metadata.json"
        if not dist_manifest.exists():
            res.error("[Metadata Gate] dist_story_map/data/official_story_metadata.json 不存在！")
        else:
            dist_bytes = dist_manifest.read_bytes()
            src_sha = hashlib.sha256(source_bytes).hexdigest()
            dist_sha = hashlib.sha256(dist_bytes).hexdigest()
            if src_sha == dist_sha:
                if verbose:
                    res.ok(f"[Metadata Gate] official_story_metadata.json Source/Dist SHA-256 100% 一致 (SHA: {src_sha[:12]})")
            else:
                res.error(f"[Metadata Gate] official_story_metadata.json Source/Dist SHA-256 不一致！(Source: {src_sha[:12]}, Dist: {dist_sha[:12]})")

        # 檢驗 dist db_info.json 的 metadata_version
        dist_db_info_path = dist_dir / "data" / "db_info.json"
        if dist_db_info_path.exists():
            try:
                dist_db_info = json.loads(dist_db_info_path.read_text(encoding="utf-8"))
                dist_meta_ver = dist_db_info.get("metadata_version")
                expected_meta_ver = hashlib.sha256(source_bytes).hexdigest()[:12]
                if dist_meta_ver == expected_meta_ver:
                    if verbose:
                        res.ok(f"[Metadata Gate] dist db_info.json metadata_version 匹配正常: {dist_meta_ver}")
                else:
                    res.error(
                        f"[Metadata Gate] dist db_info.json metadata_version 不符合預期！"
                        f"(dist: {dist_meta_ver}, expected: {expected_meta_ver})"
                    )
            except Exception as e:
                res.error(f"[Metadata Gate] 讀取 dist db_info.json 失敗: {e}")
        else:
            res.error("[Metadata Gate] dist db_info.json 不存在！")

    return res.is_valid


VALID_CHAPTER_TITLE_PROVENANCE = {"official_tw_game_ui", "official_tw_localized_asset", "unresolved"}
VALID_CHAPTER_SUMMARY_PROVENANCE = {"legacy_unverified", "legacy_curated", "curated_manual", "ai_generated", "official", "unresolved"}

def validate_chapters_metadata(data: dict) -> Tuple[bool, str]:
    """
    驗證 chapters.json 的主線章節元數據與來源隔離性 (Provenance Quarantine)。
    嚴格規範：
    1. key: 非空字串
    2. order: 整數
    3. title_locale: 必須為 "zh-TW"
    4. title_provenance: official_tw_game_ui | official_tw_localized_asset | unresolved
    5. summary_provenance: legacy_curated | curated_manual | ai_generated | official | unresolved
    6. official 來源時 title 必須為非空字串；unresolved 時 title 必須為 None
    7. Part / Group ID 一致性
    """
    if not isinstance(data, dict):
        return False, "chapters.json 根物件必須為字典"

    parts = ["1", "2", "3"]
    for p in parts:
        if p not in data:
            return False, f"缺少部別 {p} 節點"
        part_data = data[p]
        if not isinstance(part_data, dict):
            return False, f"部別 {p} 內容必須為字典"
        if "game_world" not in part_data:
            return False, f"部別 {p} 缺少 game_world 節點"

        gw = part_data["game_world"]
        if not isinstance(gw, dict) or len(gw) == 0:
            return False, f"部別 {p} 的 game_world 必須為非空字典"

        for gid_str, entry in gw.items():
            if not gid_str.isdigit():
                return False, f"部別 {p} 包含非數字 group_id: {gid_str}"
            gid = int(gid_str)

            # Part / group_id 範圍一致性檢驗
            if p == "1" and not (2000 <= gid <= 2099):
                return False, f"第 1 部包含非預期 group_id: {gid}"
            elif p == "2" and not (2100 <= gid <= 2199):
                return False, f"第 2 部包含非預期 group_id: {gid}"
            elif p == "3" and not (2200 <= gid <= 2299):
                return False, f"第 3 部包含非預期 group_id: {gid}"

            if not isinstance(entry, dict):
                return False, f"章節 {gid} 內容必須為字典"

            key = entry.get("key")
            if not isinstance(key, str) or len(key.strip()) == 0:
                return False, f"章節 {gid} key 必須為非空字串"

            order = entry.get("order")
            if not isinstance(order, int) or isinstance(order, bool):
                return False, f"章節 {gid} order 必須為整數"

            locale = entry.get("title_locale")
            if locale != "zh-TW":
                return False, f"章節 {gid} title_locale 必須為 'zh-TW'，當前為: {locale}"

            title_prov = entry.get("title_provenance")
            if title_prov not in VALID_CHAPTER_TITLE_PROVENANCE:
                return False, f"章節 {gid} title_provenance 不合法: {title_prov}"

            summary_prov = entry.get("summary_provenance")
            if summary_prov not in VALID_CHAPTER_SUMMARY_PROVENANCE:
                return False, f"章節 {gid} summary_provenance 不合法: {summary_prov}"

            title = entry.get("title")
            if title_prov in ("official_tw_game_ui", "official_tw_localized_asset"):
                if not isinstance(title, str) or len(title.strip()) == 0:
                    return False, f"章節 {gid} 來源為 {title_prov}，但 title 為空或非字串"
            elif title_prov == "unresolved":
                if title is not None:
                    return False, f"章節 {gid} 來源為 unresolved，但 title 非 null (值為: {title})"

    return True, ""

def validate_story_map(
    target_dir: Path = None,
    check_dist: bool = False,
    allow_metadata_bootstrap_incomplete: bool = True
) -> bool:
    """
    執行 Story Map 全量一致性檢查。
    :param target_dir: 檢查目標目錄，預設為 dashboard
    :param check_dist: 是否同時對 dist_story_map 進行完整部署集合驗證
    :param allow_metadata_bootstrap_incomplete: 是否允許官方故事元數據處於引導未完成 (BOOTSTRAP_INCOMPLETE) 狀態
    :return: True 通過, False 存在致命錯誤
    """
    base_dir = target_dir or DASHBOARD_DIR
    res = ValidationResult()
    print(f"\n🛡️  開始 Story Map 資料完整性驗證 (目標: {base_dir.name})...")

    # 1. 核心檔案存在性檢查
    is_dashboard = (base_dir == DASHBOARD_DIR)
    entry_html = base_dir / ("story_map.html" if is_dashboard else "index.html")
    
    required_files = [
        entry_html,
        base_dir / "style.css",
        base_dir / "map.js",
        base_dir / "characters.js",
        base_dir / "avatar-service.js",
        base_dir / "story-asset-service.js",
        base_dir / "story-data-service.js",
        base_dir / "reader-navigation.js",
        base_dir / "chapter-data.js",
        base_dir / "db.js",
        base_dir / "sql-wasm.js",
        base_dir / "sql-wasm.wasm",
        base_dir / "redive_tw.db",
    ]
    for rf in required_files:
        if rf.exists() and rf.stat().st_size > 0:
            res.ok(f"核心檔案存在: {rf.name} ({rf.stat().st_size} bytes)")
        else:
            res.error(f"核心檔案缺失或為空: {rf}")

    # 2. 必備元數據 JSON 檢查與 Schema 驗證
    data_dir = base_dir / "data"
    required_metadata = {
        "chapters.json": lambda d: validate_chapters_metadata(d)[0],
        "extra_events.json": lambda d: isinstance(d, dict) and "events" in d and "stories" in d,
        "story_thumbnails.json": lambda d: isinstance(d, dict) and len(d) > 0,
        "npc_avatars.json": lambda d: isinstance(d, dict) and len(d) > 0,
        "tracked_characters.json": lambda d: isinstance(d, dict) and len(d) > 0,
        "event_summaries.json": lambda d: isinstance(d, dict) and len(d) > 0,
        "branch_stories.json": lambda d: (
            isinstance(d, dict) and
            d.get("version") in (1, 2) and
            d.get("part") == 3 and
            isinstance(d.get("stories"), list) and
            len(d.get("stories")) > 0 and
            all(
                isinstance(s.get("story_id"), int) and
                isinstance(s.get("chapter"), int) and 1 <= s.get("chapter") <= 16 and
                (
                    (
                        d.get("version") == 2 and
                        s.get("category") in ("ordinary", "reality") and
                        isinstance(s.get("branch_label"), str) and len(s.get("branch_label").strip()) > 0 and
                        s.get("title") == f"分支劇情 {s.get('branch_label')}" and
                        isinstance(s.get("subtitle"), str) and len(s.get("subtitle").strip()) > 0 and
                        isinstance(s.get("provenance"), dict) and
                        s["provenance"].get("subtitle") == "PROVEN_FROM_STORY_BUNDLE" and
                        s["provenance"].get("category") == "DERIVED_FROM_CURRENT_DATASET_RULE" and
                        s["provenance"].get("branch_label") == "DERIVED_FROM_CATEGORY_AND_GLOBAL_SEQUENCE" and
                        s["provenance"].get("title") == "DERIVED_FROM_BRANCH_LABEL" and
                        s["provenance"].get("official_ui") in ("VERIFIED_BY_OFFICIAL_UI", None)
                    )
                    or
                    (
                        d.get("version") == 1 and
                        s.get("metadata_status") in ("resolved_official_bundle", "resolved_official_screenshot", "unresolved") and
                        (
                            (s.get("metadata_status") in ("resolved_official_bundle", "resolved_official_screenshot") and s.get("title") and s.get("subtitle")) or
                            (s.get("metadata_status") == "unresolved" and s.get("title") is None and s.get("subtitle") is None and s.get("branch_label") is None)
                        )
                    )
                )
                for s in d.get("stories")
            )
        )
    }
    
    for meta_name, schema_validator in required_metadata.items():
        mp = data_dir / meta_name
        if not mp.exists():
            res.error(f"必備元數據檔案缺失: data/{meta_name}")
            continue
        try:
            with open(mp, "r", encoding="utf-8") as f:
                data = json.load(f)
            if schema_validator(data):
                res.ok(f"元數據 JSON 解析與 Schema 驗證正常: data/{meta_name}")
            else:
                if meta_name == "chapters.json":
                    _, err = validate_chapters_metadata(data)
                    res.error(f"元數據 Schema 結構不符合預期: data/{meta_name} ({err})")
                else:
                    res.error(f"元數據 Schema 結構不符合預期: data/{meta_name}")
        except Exception as e:
            res.error(f"元數據 JSON 格式損壞: data/{meta_name} - {e}")

    # 3. 資料庫連線與核心表格檢查
    db_path = base_dir / "redive_tw.db"
    db_story_ids = set()
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM unit_data")
            unit_count = cur.fetchone()[0]
            cur.execute("SELECT story_id FROM story_detail")
            db_story_ids = set(row[0] for row in cur.fetchall())
            cur.execute("SELECT COUNT(*) FROM event_story_data")
            event_count = cur.fetchone()[0]
            conn.close()
            res.ok(f"SQLite 資料庫正常 (角色: {unit_count}, 劇情話數: {len(db_story_ids)}, 活動: {event_count})")
        except Exception as e:
            res.error(f"SQLite 資料庫查詢失敗: {e}")
    else:
        res.error("資料庫檔案 redive_tw.db 不存在！")

    # 4. 全量對白劇本逐份解析 (逐檔 json.loads 語法驗證)
    story_dir = base_dir / "story"
    actual_story_ids = set()
    if story_dir.exists():
        story_files = list(story_dir.glob("*.json"))
        corrupted_count = 0
        for sf in story_files:
            try:
                sid = int(sf.stem)
                actual_story_ids.add(sid)
                with open(sf, "r", encoding="utf-8") as f:
                    dialogues = json.load(f)
                if not isinstance(dialogues, list):
                    corrupted_count += 1
                    res.error(f"對白劇本根結構非陣列: story/{sf.name}")
            except ValueError:
                res.warning(f"對白劇本檔名非數字 ID: story/{sf.name}")
            except Exception as e:
                corrupted_count += 1
                res.error(f"對白劇本 JSON 解析損壞: story/{sf.name} - {e}")

        if corrupted_count == 0:
            res.ok(f"全量對白劇本逐份驗證通過: 共 {len(story_files)} 篇 JSON 均格式合法")
        else:
            res.error(f"發現 {corrupted_count} 篇損壞之對白劇本！")

        # 5. 比對 Expected vs Actual 話數集合 (涵蓋 DB 主線、extra_events 與 branch_stories)
        extra_story_ids = set()
        extra_path = data_dir / "extra_events.json"
        if extra_path.exists():
            try:
                with open(extra_path, "r", encoding="utf-8") as f:
                    extra_data = json.load(f)
                extra_story_ids = set(s.get("id") for s in extra_data.get("stories", []) if s.get("id"))
            except Exception:
                pass

        branch_story_ids = set()
        branch_path = data_dir / "branch_stories.json"
        if branch_path.exists():
            try:
                with open(branch_path, "r", encoding="utf-8") as f:
                    branch_data = json.load(f)
                branch_story_ids = set(s.get("story_id") for s in branch_data.get("stories", []) if s.get("story_id"))
            except Exception:
                pass

        expected_story_ids = db_story_ids.union(extra_story_ids).union(branch_story_ids)
        missing_in_disk = expected_story_ids - actual_story_ids
        if missing_in_disk:
            res.warning(f"元數據中尚有 {len(missing_in_disk)} 話未下載本機對白 (例如部分歷史活動)")
        else:
            res.ok(f"元數據定義之重要話數本機對白皆已具備")
    else:
        res.error("對白劇本目錄 story/ 不存在！")

    # 6. 元數據映射解析
    thumb_path = data_dir / "story_thumbnails.json"
    if thumb_path.exists():
        try:
            with open(thumb_path, "r", encoding="utf-8") as f:
                thumbs = json.load(f)
        except Exception as e:
            res.warning(f"story_thumbnails 解析異常: {e}")

    # 6B. Avatar Manifest 與實體二進位資產門禁 (Phase 5)
    print(f"\n🎭 執行 Avatar Manifest 與實體二進位資產門禁驗證...")
    validate_avatar_manifest_and_assets(DASHBOARD_DIR, res)

    # 6C. Gap Voice 權威清單與來源二進位資產門禁
    print(f"\n🔊 執行 Gap Voice 權威清單與來源二進位資產門禁驗證...")
    validate_voice_gap_manifest_and_assets(DASHBOARD_DIR, dist_dir=None, res=res, check_dist=False)

    # 6D. 官方故事元數據側車門禁 (Official Story Metadata Manifest Gate)
    print(f"\n📜 執行官方故事元數據側車門禁驗證...")
    src_board_dir = base_dir if is_dashboard else DASHBOARD_DIR
    validate_official_story_metadata(
        src_board_dir,
        dist_dir=None,
        check_dist=False,
        res=res,
        allow_bootstrap_incomplete=allow_metadata_bootstrap_incomplete
    )

    # 7. 若 check_dist=True，執行 dist_story_map 專屬集合與檔案深度驗證
    if check_dist or base_dir == DIST_DIR:
        print(f"\n🔍 執行 dist_story_map 專屬部署結構與對白集合驗證...")
        dist_idx = DIST_DIR / "index.html"
        if dist_idx.exists():
            content = dist_idx.read_text(encoding="utf-8")
            if "// === db.js INLINED ===" in content:
                res.ok("dist_story_map/index.html 已成功內嵌 db.js")
            else:
                res.error("dist_story_map/index.html 缺少 db.js 內嵌標記！")

            if "// === chapter-data.js INLINED ===" in content:
                res.ok("dist_story_map/index.html 已成功內嵌 chapter-data.js")
            else:
                res.error("dist_story_map/index.html 缺少 chapter-data.js 內嵌標記！")
        else:
            res.error("dist_story_map/index.html 不存在！")

        db_info_path = DIST_DIR / "data" / "db_info.json"
        if db_info_path.exists():
            try:
                db_info = json.loads(db_info_path.read_text(encoding="utf-8"))
                v = db_info.get("db_version", "")
                if v.startswith("hash_") and len(v) >= 10:
                    res.ok(f"dist_story_map db_info.json 決定性版本號正常: {v}")
                else:
                    res.error(f"dist_story_map db_info.json 版本號格式不合規: {v}")
            except Exception as e:
                res.error(f"dist_story_map db_info.json 損壞: {e}")
        else:
            res.error("dist_story_map/data/db_info.json 不存在！")

        # 深度比對 dist/story 對白集合與語意對等門禁 (Parity Gate)
        src_story_dir = base_dir / "story" if is_dashboard else DASHBOARD_DIR / "story"
        dist_story_dir = DIST_DIR / "story"
        validate_story_source_dist_parity(src_story_dir, dist_story_dir, result=res, verbose=True)

        # 深度驗證 dist/data 元數據
        for meta_name in required_metadata.keys():
            dmp = DIST_DIR / "data" / meta_name
            if not dmp.exists():
                res.error(f"dist_story_map 必備元數據缺失: data/{meta_name}")
            else:
                try:
                    with open(dmp, "r", encoding="utf-8") as f:
                        json.load(f)
                except Exception as e:
                    res.error(f"dist_story_map 元數據損壞: data/{meta_name} - {e}")

        # 深度驗證 dist/icon/story_unit 對白覆蓋資產
        manifest_path = DASHBOARD_DIR / "data" / "avatar_assets.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
                for asset in manifest_data.get("assets", []):
                    if asset.get("status") == "active" and "dialogue_asset" in asset:
                        d_asset = asset["dialogue_asset"]
                        p_str = d_asset.get("path")
                        if p_str:
                            dist_d_path = DIST_DIR / p_str
                            if not dist_d_path.exists():
                                res.error(f"dist_story_map 缺失 dialogue_asset: {p_str}")
                            else:
                                d_act_sz = dist_d_path.stat().st_size
                                d_exp_sz = d_asset.get("size_bytes")
                                if d_act_sz != d_exp_sz:
                                    res.error(f"dist dialogue_asset 檔案大小失配: {p_str} ({d_act_sz} != {d_exp_sz})")
                                d_act_sha = calc_sha256(dist_d_path)
                                d_exp_sha = d_asset.get("sha256")
                                if d_act_sha != d_exp_sha:
                                    res.error(f"dist dialogue_asset SHA-256 失配: {p_str}")
            except Exception as e:
                res.error(f"校驗 dist dialogue_asset 失敗: {e}")

        # 深度驗證 dist/sound/story_vo Gap 語音對等性 (Parity Gate)
        print(f"\n🔊 執行 dist_story_map Gap Voice 對等性門禁驗證...")
        validate_voice_gap_manifest_and_assets(DASHBOARD_DIR, dist_dir=DIST_DIR, res=res, check_dist=True)

        # 深度驗證 dist official_story_metadata.json 與 metadata_version 對齊門禁
        print(f"\n📜 執行 dist_story_map 官方故事元數據與 metadata_version 對齊門禁驗證...")
        validate_official_story_metadata(
            src_board_dir,
            dist_dir=DIST_DIR,
            check_dist=True,
            res=res,
            allow_bootstrap_incomplete=allow_metadata_bootstrap_incomplete
        )

        # 8. 部署體積門禁檢驗 (Deployment Footprint Gate)
        print(f"\n📦 執行 GitHub Pages 部署體積門禁 (Footprint Gate)...")
        is_pass, gate_msg, _ = check_footprint_gate(DIST_DIR)
        if not is_pass:
            res.error(f"體積門禁失敗: {gate_msg}")
        elif "WARNING" in gate_msg:
            res.warning(f"體積門禁預警: {gate_msg}")
        else:
            res.ok(f"體積門禁正常: {gate_msg}")

    # 總結
    print(f"\n📋 驗證總結: {len(res.errors)} 個錯誤, {len(res.warnings)} 個警告")
    if res.is_valid:
        print("✅ 驗證門禁通過！")
    else:
        print("❌ 驗證門禁未通過，請修正上述錯誤！")
    return res.is_valid

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="PCRD Story Map 一致性驗證門禁")
    parser.add_argument("target", nargs="?", default=str(DASHBOARD_DIR), help="驗證目標目錄 (預設 dashboard)")
    parser.add_argument("--no-dist", action="store_true", help="不執行 dist_story_map 深度驗證")
    parser.add_argument("--strict-metadata", action="store_true", help="啟用官方故事元數據嚴格發布門禁 (拒絕 BOOTSTRAP_INCOMPLETE)")
    args = parser.parse_args()

    target_path = Path(args.target)
    success = validate_story_map(
        target_path,
        check_dist=not args.no_dist,
        allow_metadata_bootstrap_incomplete=not args.strict_metadata
    )
    sys.exit(0 if success else 1)
