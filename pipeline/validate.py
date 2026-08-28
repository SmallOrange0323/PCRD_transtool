#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Validator (Single Source of Verification)
提供發布前與更新後的資料完整性自檢門禁。
"""

import os
import sys
import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
DIST_DIR = PROJECT_ROOT / "dist_story_map"

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

def validate_story_map(target_dir: Path = None, check_dist: bool = False) -> bool:
    """
    執行 Story Map 全量一致性檢查。
    :param target_dir: 檢查目標目錄，預設為 dashboard
    :param check_dist: 是否同時檢查 dist_story_map
    :return: True 通過, False 存在致命錯誤
    """
    base_dir = target_dir or DASHBOARD_DIR
    res = ValidationResult()
    print(f"\n🛡️  開始 Story Map 資料完整性驗證 (目標: {base_dir.name})...")

    # 1. 核心檔案存在性檢查
    required_files = [
        base_dir / "story_map.html" if base_dir == DASHBOARD_DIR else base_dir / "index.html",
        base_dir / "map.js",
        base_dir / "characters.js",
        base_dir / "avatar-service.js",
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

    # 2. 必備元數據 JSON 檢查
    data_dir = base_dir / "data"
    required_metadata = [
        "chapters.json",
        "extra_events.json",
        "story_thumbnails.json",
        "npc_avatars.json",
        "tracked_characters.json"
    ]
    for meta_name in required_metadata:
        mp = data_dir / meta_name
        if not mp.exists():
            res.error(f"必備元數據檔案缺失: data/{meta_name}")
            continue
        try:
            with open(mp, "r", encoding="utf-8") as f:
                data = json.load(f)
            res.ok(f"元數據 JSON 解析正常: data/{meta_name}")
        except Exception as e:
            res.error(f"元數據 JSON 格式損壞: data/{meta_name} - {e}")

    # 3. 資料庫連線與核心表格檢查
    db_path = base_dir / "redive_tw.db"
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM unit_data")
            unit_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM story_detail")
            story_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM event_story_data")
            event_count = cur.fetchone()[0]
            conn.close()
            res.ok(f"SQLite 資料庫正常 (角色: {unit_count}, 劇情話數: {story_count}, 活動: {event_count})")
        except Exception as e:
            res.error(f"SQLite 資料庫查詢失敗: {e}")
    else:
        res.error("資料庫檔案 redive_tw.db 不存在！")

    # 4. 對白劇本檢查 (取樣與完整性)
    story_dir = base_dir / "story"
    if story_dir.exists():
        story_files = list(story_dir.glob("*.json"))
        if len(story_files) < 100:
            res.error(f"對白劇本數量異常過少: 僅 {len(story_files)} 篇")
        else:
            res.ok(f"對白劇本目錄正常: 共 {len(story_files)} 篇對白 JSON")
            # 檢查最新重要話數是否存在 (例如主線三部與少戰聯動)
            must_check_sids = [2000001, 2001001, 5216001, 5216008, 1392001, 1394004]
            for sid in must_check_sids:
                sp = story_dir / f"{sid}.json"
                if not sp.exists():
                    res.warning(f"重要話數對白未找到: story/{sid}.json")
    else:
        res.error("對白劇本目錄 story/ 不存在！")

    # 5. 若檢查 dist，額外檢查 inline 狀態與 db_info.json
    if check_dist or base_dir == DIST_DIR:
        idx_path = DIST_DIR / "index.html"
        if idx_path.exists():
            content = idx_path.read_text(encoding="utf-8")
            if "window.PCRDatabase" in content or "window.ChapterDataService" in content:
                res.ok("dist_story_map/index.html 核心 JS 內嵌與 Cache-Busting 正常")
            else:
                res.warning("dist_story_map/index.html 未檢測到內嵌核心 JS")
        db_info_path = DIST_DIR / "data" / "db_info.json"
        if db_info_path.exists():
            try:
                db_info = json.loads(db_info_path.read_text(encoding="utf-8"))
                res.ok(f"db_info.json 版本正常: {db_info.get('db_version')}")
            except Exception as e:
                res.error(f"db_info.json 損壞: {e}")

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
