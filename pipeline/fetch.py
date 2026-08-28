#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Fetcher
負責與 So-net CDN 進行資料探測、下載與解密。
提供與 tools/pcrd_fetch.py 100% 相容之模組函式與 CLI 入口。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

# 匯入現有成熟之 pcrd_fetch 核心功能
try:
    from pcrd_fetch import (
        cmd_update_db as update_db,
        cmd_fetch_stories as fetch_stories,
        cmd_fetch_assets as fetch_assets,
        cmd_scan_cdn as scan_cdn,
        cmd_fetch_story_voices as fetch_story_voices,
        cmd_fetch_story_images as fetch_story_images,
        cmd_sync_episode as sync_episode,
        _get_sonet_ver as get_truth_version,
        _get_story_ids_from_db,
        main as pcrd_fetch_main
    )
except ImportError as e:
    print(f"[ERROR] 無法載入 tools/pcrd_fetch.py: {e}", file=sys.stderr)
    sys.exit(1)

def get_story_ids_for_unit(unit_id: int) -> list[int]:
    """
    取得指定角色的標準劇情話數 ID 列表 (使用 legacy canonical 規則，包含 7/8 位相容與 fallback)。
    """
    return _get_story_ids_from_db(unit_id)

def run_fetch_cli():
    """CLI 入口"""
    pcrd_fetch_main()

if __name__ == "__main__":
    run_fetch_cli()
