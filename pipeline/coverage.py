#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Coverage & Freshness Analysis (Phase C2 Minimal Runtime)
提供結構化新鮮度判定 (FreshnessResult) 與具備來源完整性檢驗之唯讀劇本覆蓋率分析 (CoverageResult)。
嚴格區分上游 CDN 探測與第三方鏡像 DB 下載之信任邊界，不捏造版本證明，不吞沒錯誤，不執行自動抓取。
"""

import os
import sys
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Any, Tuple, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
DATA_DIR = DASHBOARD_DIR / "data"
STORY_DIR = DASHBOARD_DIR / "story"
DB_PATH = DASHBOARD_DIR / "redive_tw.db"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

# ─────────────────────────── 新鮮度狀態模型 ───────────────────────────

class FreshnessStatus:
    CONFIRMED_CURRENT = "CONFIRMED_CURRENT"
    UPDATE_AVAILABLE = "UPDATE_AVAILABLE"
    UPDATED_SUCCESSFULLY = "UPDATED_SUCCESSFULLY"
    UPDATE_DOWNLOADED_UNCONFIRMED = "UPDATE_DOWNLOADED_UNCONFIRMED"
    REMOTE_UNREACHABLE = "REMOTE_UNREACHABLE"
    LOCAL_STATE_MISSING = "LOCAL_STATE_MISSING"
    UPDATE_FAILED = "UPDATE_FAILED"

@dataclass
class FreshnessResult:
    status: str
    remote_version: Optional[str]
    local_version: Optional[str]
    confirmed: bool
    update_required: bool
    degraded: bool
    message: str

def evaluate_freshness(remote_tv: Optional[str], local_tv: Optional[str], db_exists: bool) -> FreshnessResult:
    """
    評估當前管線新鮮度狀態 (純粹邏輯判定，無副作用)
    """
    if remote_tv is not None:
        if not db_exists:
            return FreshnessResult(
                status=FreshnessStatus.UPDATE_AVAILABLE,
                remote_version=remote_tv,
                local_version=local_tv,
                confirmed=True,
                update_required=True,
                degraded=False,
                message=f"本地資料庫缺失，需從鏡像下載 (線上 TruthVersion: {remote_tv})"
            )
        elif local_tv and remote_tv == local_tv:
            return FreshnessResult(
                status=FreshnessStatus.CONFIRMED_CURRENT,
                remote_version=remote_tv,
                local_version=local_tv,
                confirmed=True,
                update_required=False,
                degraded=False,
                message=f"線上 CDN 版號與本地記錄一致 ({remote_tv})，新鮮度已確認"
            )
        else:
            return FreshnessResult(
                status=FreshnessStatus.UPDATE_AVAILABLE,
                remote_version=remote_tv,
                local_version=local_tv,
                confirmed=True,
                update_required=True,
                degraded=False,
                message=f"線上 CDN 有新版本 (線上: {remote_tv}, 本地: {local_tv or '未記錄'})"
            )
    else:
        # remote_tv is None (探測失敗或離線)
        if db_exists:
            return FreshnessResult(
                status=FreshnessStatus.REMOTE_UNREACHABLE,
                remote_version=None,
                local_version=local_tv,
                confirmed=False,
                update_required=False,
                degraded=True,
                message=f"無法連接 CDN 探測版號 (降級為離線模式，使用本地 DB: {local_tv or '未知版號'})"
            )
        else:
            return FreshnessResult(
                status=FreshnessStatus.LOCAL_STATE_MISSING,
                remote_version=None,
                local_version=None,
                confirmed=False,
                update_required=True,
                degraded=True,
                message="無法連接 CDN 且本地資料庫不存在，管線無法執行"
            )

# ─────────────────────────── 覆蓋率分析模型 ───────────────────────────

class CoverageAnalysisStatus:
    VALID = "VALID"
    DEGRADED = "DEGRADED"
    INVALID = "INVALID"

@dataclass
class CoverageResult:
    analysis_status: str  # VALID, DEGRADED, INVALID
    analysis_errors: List[str]
    source_status: Dict[str, str]
    local_present_count: int
    required_total_count: int
    optional_total_count: int
    unknown_expected_count: int
    missing_required_count: int
    missing_optional_count: int
    missing_unknown_count: int
    missing_required_ids: List[int]
    missing_optional_ids: List[int]
    missing_unknown_ids: List[int]
    metrics: Dict[str, Any] = field(default_factory=dict)
    overlaps: Dict[str, int] = field(default_factory=dict)
    policy_status: Dict[str, str] = field(default_factory=dict)

def analyze_coverage() -> CoverageResult:
    """
    動態分析當前資料庫與元數據之劇本覆蓋現況 (具備來源健康度與完整性檢驗，純讀取零副作用)
    """
    analysis_errors: List[str] = []
    source_status: Dict[str, str] = {
        "database": "OK",
        "tracked_characters": "OK",
        "branch_stories": "OK",
        "extra_events": "OK"
    }

    # 1. 本地數字劇本
    local_present: Set[int] = set()
    if STORY_DIR.exists():
        for p in STORY_DIR.glob("*.json"):
            if p.stem.isdigit():
                local_present.add(int(p.stem))

    # 2. 資料庫查詢 (權威來源 1: DB)
    db_story_detail_ids: Set[int] = set()
    db_main_ids: Set[int] = set()
    db_character_ids: Set[int] = set()
    db_guild_ids: Set[int] = set()
    db_tower_ids: Set[int] = set()
    db_special_other_ids: Set[int] = set()

    if not DB_PATH.exists():
        source_status["database"] = "MISSING (redive_tw.db not found)"
        analysis_errors.append("SQLite 資料庫 redive_tw.db 不存在")
    else:
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cur = conn.cursor()
            cur.execute("SELECT story_id FROM story_detail")
            for (sid,) in cur.fetchall():
                db_story_detail_ids.add(sid)
                s_str = str(sid)
                if s_str.startswith("1"):
                    db_character_ids.add(sid)
                elif s_str.startswith("2"):
                    db_main_ids.add(sid)
                elif s_str.startswith("3"):
                    db_guild_ids.add(sid)
                elif s_str.startswith("4"):
                    db_tower_ids.add(sid)
                elif s_str.startswith("9"):
                    db_special_other_ids.add(sid)
                else:
                    db_special_other_ids.add(sid)
            conn.close()
        except Exception as e:
            source_status["database"] = f"ERROR ({e})"
            analysis_errors.append(f"查詢 SQLite story_detail 失敗: {e}")

    # 3. 追蹤角色 (權威來源 2: tracked_characters.json & helper)
    tracked_units_count = 0
    tracked_char_required_ids: Set[int] = set()
    tracked_file = DATA_DIR / "tracked_characters.json"

    if not tracked_file.exists():
        source_status["tracked_characters"] = "MISSING (tracked_characters.json not found)"
        analysis_errors.append("配置檔案 tracked_characters.json 不存在")
    else:
        try:
            with open(tracked_file, "r", encoding="utf-8") as f:
                tracked_data = json.load(f)
            from tools.pcrd_fetch import _get_story_ids_from_db
            tracked_uids = [c["unit_id"] for c in tracked_data.get("characters", []) if "unit_id" in c]
            tracked_units_count = len(tracked_uids)
            for uid in tracked_uids:
                tracked_char_required_ids.update(_get_story_ids_from_db(uid))
        except Exception as e:
            source_status["tracked_characters"] = f"ERROR ({e})"
            analysis_errors.append(f"解析 tracked_characters 或計算話數失敗: {e}")

    # 4. 元數據 (權威來源 3 & 4: branch_stories.json & extra_events.json)
    branch_expected_ids: Set[int] = set()
    branch_file = DATA_DIR / "branch_stories.json"
    if not branch_file.exists():
        source_status["branch_stories"] = "MISSING (branch_stories.json not found)"
        analysis_errors.append("元數據 branch_stories.json 不存在")
    else:
        try:
            with open(branch_file, "r", encoding="utf-8") as f:
                b_data = json.load(f)
            stories = b_data.get("stories")
            if not isinstance(stories, list):
                raise ValueError("頂層 'stories' 欄位非列表或缺失")
            for item in stories:
                sid = item.get("story_id")
                if isinstance(sid, int):
                    branch_expected_ids.add(sid)
        except Exception as e:
            source_status["branch_stories"] = f"ERROR ({e})"
            analysis_errors.append(f"解析 branch_stories.json 失敗: {e}")

    extra_event_expected_ids: Set[int] = set()
    extra_file = DATA_DIR / "extra_events.json"
    if not extra_file.exists():
        source_status["extra_events"] = "MISSING (extra_events.json not found)"
        analysis_errors.append("元數據 extra_events.json 不存在")
    else:
        try:
            with open(extra_file, "r", encoding="utf-8") as f:
                e_data = json.load(f)
            stories = e_data.get("stories")
            if not isinstance(stories, list):
                raise ValueError("頂層 'stories' 欄位非列表或缺失")
            for item in stories:
                sid = item.get("id") or item.get("story_id")
                if isinstance(sid, int):
                    extra_event_expected_ids.add(sid)
        except Exception as e:
            source_status["extra_events"] = f"ERROR ({e})"
            analysis_errors.append(f"解析 extra_events.json 失敗: {e}")

    # 5. 分析完整性評估 (Integrity Evaluation)
    if source_status["database"] != "OK":
        analysis_status = CoverageAnalysisStatus.INVALID
    elif any(st != "OK" for st in source_status.values()):
        analysis_status = CoverageAnalysisStatus.DEGRADED
    else:
        analysis_status = CoverageAnalysisStatus.VALID

    # 6. 互斥覆蓋集合建構
    main_required_ids = set(db_main_ids)
    guild_required_ids = set(db_guild_ids)
    tower_required_ids = set(db_tower_ids)
    branch_required_ids = set(branch_expected_ids)
    extra_event_required_ids = set(extra_event_expected_ids)

    required_story_ids = (
        main_required_ids |
        guild_required_ids |
        tower_required_ids |
        tracked_char_required_ids |
        branch_required_ids |
        extra_event_required_ids
    )

    untracked_character_optional_ids = db_character_ids - tracked_char_required_ids
    optional_historic_ids = untracked_character_optional_ids | db_special_other_ids

    all_known_sources = (
        db_story_detail_ids |
        branch_expected_ids |
        extra_event_expected_ids |
        tracked_char_required_ids
    )
    unknown_expected_ids = all_known_sources - (required_story_ids | optional_historic_ids)

    missing_required = required_story_ids - local_present
    missing_optional = optional_historic_ids - local_present
    missing_unknown = unknown_expected_ids - local_present

    overlaps = {
        "branch_vs_main": len(branch_expected_ids & db_main_ids),
        "extra_vs_story_detail": len(extra_event_expected_ids & db_story_detail_ids),
        "tracked_vs_story_detail": len(tracked_char_required_ids & db_character_ids)
    }

    metrics = {
        "tracked_units_count": tracked_units_count,
        "tracked_character_required_count": len(tracked_char_required_ids),
        "main_required_count": len(main_required_ids),
        "guild_required_count": len(guild_required_ids),
        "tower_system_required_count": len(tower_required_ids),
        "branch_expected_count": len(branch_expected_ids),
        "extra_event_expected_count": len(extra_event_expected_ids),
        "db_story_detail_total": len(db_story_detail_ids),
    }

    # 政策狀態評估 (Policy Status)
    if analysis_status == CoverageAnalysisStatus.VALID:
        policy_status = {
            "required_policy_status": "DEFINED" if len(unknown_expected_ids) == 0 else "PARTIAL",
            "optional_policy_status": "DEFINED" if len(unknown_expected_ids) == 0 else "PARTIAL"
        }
    elif analysis_status == CoverageAnalysisStatus.DEGRADED:
        policy_status = {
            "required_policy_status": "PARTIAL",
            "optional_policy_status": "PARTIAL"
        }
    else:  # INVALID
        policy_status = {
            "required_policy_status": "UNRESOLVED",
            "optional_policy_status": "UNRESOLVED"
        }

    return CoverageResult(
        analysis_status=analysis_status,
        analysis_errors=analysis_errors,
        source_status=source_status,
        local_present_count=len(local_present),
        required_total_count=len(required_story_ids),
        optional_total_count=len(optional_historic_ids),
        unknown_expected_count=len(unknown_expected_ids),
        missing_required_count=len(missing_required),
        missing_optional_count=len(missing_optional),
        missing_unknown_count=len(missing_unknown),
        missing_required_ids=sorted(list(missing_required)),
        missing_optional_ids=sorted(list(missing_optional)),
        missing_unknown_ids=sorted(list(missing_unknown)),
        metrics=metrics,
        overlaps=overlaps,
        policy_status=policy_status
    )
