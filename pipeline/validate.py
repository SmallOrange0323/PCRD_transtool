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
            d.get("version") == 1 and
            d.get("part") == 3 and
            isinstance(d.get("stories"), list) and
            len(d.get("stories")) > 0 and
            all(
                isinstance(s.get("story_id"), int) and
                isinstance(s.get("chapter"), int) and 1 <= s.get("chapter") <= 16 and
                s.get("metadata_status") in ("resolved_official_screenshot", "unresolved") and
                (
                    (s.get("metadata_status") == "resolved_official_screenshot" and s.get("title") and s.get("subtitle")) or
                    (s.get("metadata_status") == "unresolved" and s.get("title") is None and s.get("subtitle") is None and s.get("branch_label") is None)
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
            res.ok(f"元數據映射表解析成功 (story_thumbnails 包含 {len(thumbs)} 筆章節劇照關聯)")
        except Exception as e:
            res.warning(f"story_thumbnails 解析異常: {e}")

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

        # 深度比對 dist/story 對白集合
        dist_story_dir = DIST_DIR / "story"
        if dist_story_dir.exists():
            dist_story_files = list(dist_story_dir.glob("*.json"))
            dist_sids = set()
            dist_corrupt = 0
            for dsf in dist_story_files:
                try:
                    dsid = int(dsf.stem)
                    dist_sids.add(dsid)
                    with open(dsf, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if not isinstance(data, list):
                        dist_corrupt += 1
                        res.error(f"dist 對白非陣列: dist_story_map/story/{dsf.name}")
                except ValueError:
                    pass
                except Exception as e:
                    dist_corrupt += 1
                    res.error(f"dist 對白 JSON 損壞: dist_story_map/story/{dsf.name} - {e}")

            missing_in_dist = actual_story_ids - dist_sids
            if missing_in_dist:
                res.error(f"dist_story_map 缺失 {len(missing_in_dist)} 篇對白 (Bundler 漏同步): 範例 {list(missing_in_dist)[:5]}")
            else:
                res.ok(f"dist_story_map/story/ 與源碼對白集合完全一致 (共 {len(dist_sids)} 篇)")
        else:
            res.error("dist_story_map/story/ 目錄不存在！")

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
