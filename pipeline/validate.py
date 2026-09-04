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
from typing import Tuple, Set, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
DIST_DIR = PROJECT_ROOT / "dist_story_map"

# 部署體積門禁閾值 (Bytes)
FOOTPRINT_WARN_BYTES = 750 * 1024 * 1024   # 750 MiB
FOOTPRINT_HARD_BYTES = 900 * 1024 * 1024   # 900 MiB

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
    排除本機快取目錄 (如 .git, sound, card)。
    """
    if not dist_dir.exists():
        return 0
    total = 0
    excl = exclude_subdirs or {".git", "sound", "card"}
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

    if mismatch_errors == 0:
        res.ok(f"Avatar Manifest 實體二進位對等校驗通過: {active_count} 個 active 檔案大小與 SHA-256 100% 吻合, {placeholder_count} 個 placeholder_only 規格正常")

    return res.is_valid


def validate_story_map(target_dir: Path = None, check_dist: bool = False) -> bool:
    """
    執行 Story Map 全量一致性檢查。
    :param target_dir: 檢查目標目錄，預設為 dashboard
    :param check_dist: 是否同時對 dist_story_map 進行完整部署集合驗證
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
        "chapters.json": lambda d: isinstance(d, dict) and len(d) > 0,
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
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DASHBOARD_DIR
    success = validate_story_map(target, check_dist=True)
    sys.exit(0 if success else 1)
