#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Update Workflow Audit (Phase C1 Final Release Reproducibility Polish)
靜態探勘與結構化稽核 Story Map 自動化增量更新管線 (Pipeline v1)：
1. 嚴謹區分「全流程更新命令 (Full Updater with Source Sync)」與「純發布命令 (Deploy-Only Primitive)」
2. 確立發布同步邊界 (Release Synchronization Boundary)：來源提交後禁止再次執行上游同步
3. 定義最佳可重現發布路徑：main 合併後由 pipeline.bundle + pipeline.validate + pipeline.deploy 決定性建置發布
4. 建立意外二次同步復原指引 (Accidental Post-Commit Sync Recovery)
5. 強化可重現性契約 (Approved Main SHA -> Deterministic Bundle -> Dist -> gh-pages)

輸出：
- docs/UPDATE_WORKFLOW_C1_AUDIT.md
- docs/DATA_UPDATE_RUNBOOK.md
- docs/data/update_workflow_c1_audit.json
"""

import os
import sys
import json
import sqlite3
import hashlib
from pathlib import Path
from typing import Dict, List, Set, Any, Tuple, Optional

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = REPO_ROOT / "dashboard"
DIST_DIR = REPO_ROOT / "dist_story_map"
DATA_DIR = DASHBOARD_DIR / "data"
DOCS_DIR = REPO_ROOT / "docs"
OUTPUT_JSON = DOCS_DIR / "data" / "update_workflow_c1_audit.json"
OUTPUT_MD = DOCS_DIR / "UPDATE_WORKFLOW_C1_AUDIT.md"
RUNBOOK_MD = DOCS_DIR / "DATA_UPDATE_RUNBOOK.md"

def audit_workflow() -> Dict[str, Any]:
    # 1. Authoritative Command Map
    commands = [
        {
            "role": "CANONICAL_UPDATE_ORCHESTRATOR",
            "command": "python update_story_map.py",
            "module": "pipeline.update:run_pipeline_update",
            "performs_upstream_sync": True,
            "target_repository": "SOURCE_REPO (Working Tree)",
            "dry_run_supported": True,
            "deploy_supported": True,
            "description": "標準日常更新入口：包含上游資料同步階段 (CDN 探測、DB/劇本同步、決定性打包、全量門禁自檢)"
        },
        {
            "role": "CANONICAL_DRY_RUN_SIMULATION",
            "command": "python update_story_map.py --dry-run",
            "module": "pipeline.update",
            "performs_upstream_sync": False,
            "target_repository": "SOURCE_REPO (Read-Only)",
            "dry_run_supported": True,
            "deploy_supported": False,
            "description": "零副作用模擬：執行唯讀 CDN 探測、打包體積預估與全量資料自檢，零檔案寫入與刪除"
        },
        {
            "role": "DEPLOY_ONLY_PRIMITIVE",
            "command": "python -m pipeline.deploy",
            "module": "pipeline.deploy:deploy_story_map",
            "performs_upstream_sync": False,
            "target_repository": "DEPLOYMENT_REPO (dist_story_map -> gh-pages)",
            "dry_run_supported": False,
            "deploy_supported": True,
            "description": "純發布指令 (Deploy-Only)：不抓取上游、不修改主倉庫，僅驗證並將已建置之 dist 提交推送至 gh-pages"
        },
        {
            "role": "DETERMINISTIC_BUNDLER_ONLY",
            "command": "python -m pipeline.bundle",
            "module": "pipeline.bundle:bundle_story_map",
            "performs_upstream_sync": False,
            "target_repository": "SOURCE_TO_DIST_BUILD",
            "dry_run_supported": True,
            "deploy_supported": False,
            "description": "純打包工具 (Bundle-Only)：不抓取上游，純粹基於本地已提交原始碼決定性生成 dist 產物"
        },
        {
            "role": "SINGLE_SOURCE_VALIDATOR",
            "command": "python -m pipeline.validate",
            "module": "pipeline.validate:validate_story_map",
            "performs_upstream_sync": False,
            "target_repository": "SOURCE_AND_DIST",
            "dry_run_supported": False,
            "deploy_supported": False,
            "description": "全專案唯一驗證門禁：檢驗核心檔案、DB 查詢正常、9000+ 劇本 list-root 結構、Schema 與部署體積"
        },
        {
            "role": "ONE_SHOT_CONVENIENCE_UPDATE_DEPLOY",
            "command": "python update_story_map.py --deploy",
            "module": "pipeline.update -> pipeline.deploy",
            "performs_upstream_sync": True,
            "target_repository": "SOURCE_AND_DIST",
            "status": "CONVENIENCE_ONLY_NOT_FOR_REVIEWED_RELEASE",
            "description": "單次一鍵更新並發布：包含上游同步，僅適用於免審查之應急或本地單機流程，不建議用於可重現之正式發布"
        }
    ]

    # 2. Repository Separation & Release Synchronization Boundary
    repo_architecture = {
        "source_repository": {
            "name": "Main Source Repository",
            "branch": "main / data update branches",
            "scope": "dashboard/redive_tw.db, dashboard/story/*.json, dashboard/data/*.json, dashboard/*.js, pipeline/*",
            "persistence_mechanism": "Targeted Git staging & commit by operator/workflow",
            "auto_committed_by_deploy": False
        },
        "deployment_repository": {
            "name": "Deployment Repository (Nested Worktree)",
            "path": "dist_story_map",
            "branch": "gh-pages",
            "scope": "Static deployment bundle artifact only",
            "persistence_mechanism": "pipeline.deploy automated git commit & push",
            "prohibited_action": "Never run 'git add dist_story_map' in source repository"
        },
        "synchronization_boundary": {
            "source_sync_before_commit": True,
            "full_update_after_commit_allowed": False,
            "deploy_only_after_commit": True,
            "preferred_final_flow": [
                "1. git merge to main & verify origin/main SHA",
                "2. python -m pipeline.bundle (rebuild dist strictly from committed main, zero upstream sync)",
                "3. python -m pipeline.validate",
                "4. python -m pipeline.deploy (publish dist to gh-pages)"
            ]
        },
        "release_consistency_invariant": "APPROVED_MAIN_SHA_DETERMINISTIC_REPRODUCIBILITY (The dist artifact deployed to gh-pages must be generated from the exact source state represented by the approved origin/main commit, with no upstream mutation step in between)"
    }

    # 3. Tool Duty Classification
    tool_classification = [
        {
            "tool_name": "scan-cdn",
            "command": "python -m pipeline.fetch scan-cdn",
            "classification": "DISCOVERY_ONLY",
            "scope": "探測 So-net CDN 是否有新 TruthVersion、檢查 manifest 是否有預上架素材，不下載對白 JSON"
        },
        {
            "tool_name": "fetch-stories",
            "command": "python -m pipeline.fetch fetch-stories --unit-id <unit_id>",
            "classification": "DOWNLOAD_JSON_CHARACTER_ONLY",
            "scope": "僅限依角色 unit_id 查詢 DB 並下載該角色的個人劇情對白 JSON"
        },
        {
            "tool_name": "sync-episode",
            "command": "python -m pipeline.fetch sync-episode --story-id <story_id>",
            "classification": "DOWNLOAD_JSON_SINGLE_EPISODE",
            "scope": "依單一 story_id 從 manifest 匹配 Hash，下載對白 JSON 並一併下載音訊與圖像素材"
        },
        {
            "tool_name": "fetch-story-voices",
            "command": "python -m pipeline.fetch fetch-story-voices --story-id <story_id>",
            "classification": "DOWNLOAD_MEDIA_ONLY",
            "scope": "僅下載指定話數的 M4A 語音音檔"
        },
        {
            "tool_name": "fetch-story-images",
            "command": "python -m pipeline.fetch fetch-story-images --story-id <story_id>",
            "classification": "DOWNLOAD_MEDIA_ONLY",
            "scope": "僅下載指定話數的背景與 CG WebP 大圖"
        },
        {
            "tool_name": "fetch-assets",
            "command": "python -m pipeline.fetch fetch-assets --unit-id <unit_id>",
            "classification": "DOWNLOAD_MEDIA_ONLY",
            "scope": "僅下載指定角色的頭像與卡面立繪素材"
        }
    ]

    # 4. Precise Story Type Acquisition & Discovery Matrix
    story_type_matrix = [
        {
            "story_type": "Character Story (個人劇情)",
            "frontend_discovery_if_local_exists": "YES (由 SQLite story_detail 驅動，未入庫角色由 pendingNewCharas 兜底)",
            "canonical_update_auto_fetches_json": "PARTIAL (僅自動增量下載 tracked_characters.json 中註冊之 unit_id 劇本)",
            "verified_acquisition_path": "python -m pipeline.fetch fetch-stories --unit-id <unit_id> (或 sync-episode --story-id)"
        },
        {
            "story_type": "Main Story (主線劇情)",
            "frontend_discovery_if_local_exists": "YES (由 SQLite story_detail 表自動建立章節目錄)",
            "canonical_update_auto_fetches_json": "NO (Canonical update 未涵蓋主線劇本批次掃描)",
            "verified_acquisition_path": "python -m pipeline.fetch sync-episode --story-id <story_id> (單話抓取；無專屬批次主線下載器)"
        },
        {
            "story_type": "Guild Story (公會劇情)",
            "frontend_discovery_if_local_exists": "YES (由 SQLite story_detail 驅動)",
            "canonical_update_auto_fetches_json": "NO",
            "verified_acquisition_path": "python -m pipeline.fetch sync-episode --story-id <story_id> (單話抓取；無專屬批次公會下載器)"
        },
        {
            "story_type": "Event Story (活動劇情)",
            "frontend_discovery_if_local_exists": "YES (由 SQLite story_detail 驅動，新形式活動由 extra_events.json 補充)",
            "canonical_update_auto_fetches_json": "NO",
            "verified_acquisition_path": "python -m pipeline.fetch sync-episode --story-id <story_id> (單話抓取；無專屬批次活動下載器)"
        },
        {
            "story_type": "Tower / System (露娜塔/系統)",
            "frontend_discovery_if_local_exists": "YES (由 SQLite story_detail 驅動)",
            "canonical_update_auto_fetches_json": "NO",
            "verified_acquisition_path": "python -m pipeline.fetch sync-episode --story-id <story_id> (單話抓取；無專屬批次露娜塔下載器)"
        },
        {
            "story_type": "Part 3 Branch (第 3 部分支補充)",
            "frontend_discovery_if_local_exists": "YES (由 branch_stories.json 補充載入)",
            "canonical_update_auto_fetches_json": "NO",
            "verified_acquisition_path": "MANUAL_CURATION (手動提取 JSON 並更新 branch_stories.json)"
        }
    ]

    # 5. Warning Condition & Pipeline Continuation Behavior
    warning_behavior_table = [
        {
            "warning_condition": "CDN TruthVersion probe network failure / timeout",
            "pipeline_continues": True,
            "exit_code_can_be_zero": True,
            "consequence": "Freshness uncertainty / Stale-success risk (若本地有 DB，管線使用舊版資料成功打包並通過驗證)"
        },
        {
            "warning_condition": "tracked_characters.json read exception",
            "pipeline_continues": True,
            "exit_code_can_be_zero": True,
            "consequence": "Degraded-success risk (跳過追蹤角色缺失對白檢查，繼續打包現有劇本)"
        },
        {
            "warning_condition": "Non-numeric story filename (e.g. story/speaker_appearance.json)",
            "pipeline_continues": True,
            "exit_code_can_be_zero": True,
            "consequence": "None (合法警告，驗證器正確跳過元數據檔案並檢查其餘數字劇本)"
        },
        {
            "warning_condition": "Metadata missing local dialogues (e.g. 17 historic un-fetched events)",
            "pipeline_continues": True,
            "exit_code_can_be_zero": True,
            "consequence": "Partial historic coverage (允許歷史少數可選劇本未下載)"
        },
        {
            "warning_condition": "Footprint Warning (750 MiB <= size < 900 MiB)",
            "pipeline_continues": True,
            "exit_code_can_be_zero": True,
            "consequence": "Approaching Pages hard limit, warning logged but deploy allowed"
        }
    ]

    # 6. Validator Coverage & DB Query Semantics
    validator_coverage = {
        "dist_relationship": "SOURCE_SUBSET_OF_DIST (Source ⊆ Dist, verifies all numeric source story IDs exist in dist, extras allowed)",
        "extra_dist_stories_rejected": False,
        "story_json_validation_depth": "JSON parseability + list-root structural verification (逐篇檢驗 JSON 可解析且根物件為 list)",
        "db_query_semantics": "Validator successfully queries unit_data count, story_detail IDs, event_story_data count, and reports dataset metrics.",
        "covered_checks": [
            "All 11 core files existence in dashboard (story_map.html, style.css, map.js, characters.js, avatar-service.js, story-asset-service.js, chapter-data.js, db.js, sql-wasm.js, sql-wasm.wasm, redive_tw.db)",
            "SQLite database tables exist and can be successfully queried (unit_data, story_detail, event_story_data)",
            "Required metadata JSON parsing and basic schema validation (chapters, extra_events, story_thumbnails, npc_avatars, tracked_characters, event_summaries, branch_stories)",
            "branch_stories.json strict schema contract (version 1, part 3, chapters 1-16, status validation)",
            "Full 9,033+ story JSON parsing and list-root structure check",
            "Dist index.html inlining verification (db.js, chapter-data.js)",
            "Dist db_info.json deterministic version format check (hash_*)",
            "Dist story JSON containment check (all numeric dashboard stories exist in dist)",
            "Deployment footprint gate (Warning 750 MiB, Hard Error 900 MiB)"
        ],
        "known_gaps": [
            "Validator does not enforce exact bidirectional equality (extras in dist are permitted)",
            "Validator does not inspect remote HTTP 200 availability of third-party CDN assets",
            "Validator does not verify audio codec integrity of local .m4a files",
            "Validator does not check semantic story text grammar or translation accuracy",
            "Validator does not enforce bidirectional file existence for optional historic event side-stories"
        ]
    }

    # 7. Metadata Regeneration Registry
    metadata_registry = [
        {
            "file": "dashboard/data/db_info.json",
            "generator": "pipeline.bundle:bundle_story_map",
            "category": "AUTOMATIC_IN_CANONICAL_UPDATE",
            "input": "dashboard/redive_tw.db (SHA-256 prefix & size)",
            "automatic": True,
            "deterministic": True,
            "required_by_validator": True
        },
        {
            "file": "dashboard/data/story_thumbnails.json",
            "generator": "tools/scan_story_thumbnails.py / tools.pcrd_fetch",
            "category": "MANUAL_MAINTENANCE_UTILITY",
            "input": "dashboard/story/*.json (Scanned still & bg IDs)",
            "automatic": False,
            "deterministic": True,
            "required_by_validator": True
        },
        {
            "file": "dashboard/data/speaker_appearance.json",
            "generator": "tools/rebuild_metadata.py",
            "category": "MANUAL_MAINTENANCE_UTILITY",
            "input": "dashboard/story/*.json (Speaker name appearances)",
            "automatic": False,
            "deterministic": True,
            "required_by_validator": False
        },
        {
            "file": "dashboard/data/chapters.json",
            "generator": "Static schema / Manual curation",
            "category": "MANUAL_CURATION",
            "input": "Official chapter navigation tree",
            "automatic": False,
            "deterministic": True,
            "required_by_validator": True
        },
        {
            "file": "dashboard/data/branch_stories.json",
            "generator": "Manual curation & Screenshot verification",
            "category": "MANUAL_CURATION",
            "input": "Part 3 Branch story supplemental titles",
            "automatic": False,
            "deterministic": True,
            "required_by_validator": True
        },
        {
            "file": "dashboard/data/npc_avatars.json",
            "generator": "So-net CDN manifest extractor",
            "category": "MANUAL_MAINTENANCE_UTILITY",
            "input": "storydata2_assetmanifest unit IDs",
            "automatic": False,
            "deterministic": True,
            "required_by_validator": True
        },
        {
            "file": "dashboard/data/tracked_characters.json",
            "generator": "Static configuration",
            "category": "MANUAL_CURATION",
            "input": "Tracked playable characters list",
            "automatic": False,
            "deterministic": True,
            "required_by_validator": True
        }
    ]

    return {
        "command_map": commands,
        "repo_architecture": repo_architecture,
        "tool_classification": tool_classification,
        "story_type_matrix": story_type_matrix,
        "warning_behavior_table": warning_behavior_table,
        "metadata_registry": metadata_registry,
        "validator_coverage": validator_coverage,
        "idempotence_status": "PARTIALLY_VERIFIED (Bundler is component-level deterministic via SHA-256; end-to-end network rerun not fully verified in live state)"
    }

def write_artifacts(data: Dict[str, Any]):
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "data").mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ 機器可讀 JSON 產物已寫入: {OUTPUT_JSON}")

    # Write Runbook
    runbook_lines = [
        "# PCRD Story Map — 資料更新標準作業程序手冊 (DATA_UPDATE_RUNBOOK.md)",
        "",
        "> [!IMPORTANT]",
        "> **本文件定義本專案（`PCRD_transtool`）在遊戲資料更新時的標準操作流程與規範。**",
        "> 專案架構包含**來源倉庫 (Source Repo: `main`)** 與**發布倉庫 (Deployment Repo: `dist_story_map` / `gh-pages`)**。",
        "> 正常發布必須嚴格遵守：**發布同步邊界 (Release Synchronization Boundary)** — 來源資料完成審查並合併至 `main` 後，禁止再次執行包含上游抓取的 full updater，必須使用純發布指令發布（Source Commit Precedes Deploy）。",
        "",
        "---",
        "",
        "## 一、 指令類型與發布同步邊界 (Command Types & Sync Boundary)",
        "",
        "| 指令角色 | 具體指令 | 是否觸發上游抓取？ | 適用時機與說明 |",
        "| :--- | :--- | :--- | :--- |",
        "| **全流程更新 (Full Updater)** | `python update_story_map.py` | **是 (YES)** | **來源同步階段**：探測 CDN、下載 DB 與劇本、生成初始 dist 並自檢 |",
        "| **純打包 (Bundle-Only)** | `python -m pipeline.bundle` | **否 (NO)** | **決定性建置**：基於當前本地原始碼重新決定性打包，不連線抓取上游 |",
        "| **全量門禁 (Validator)** | `python -m pipeline.validate` | **否 (NO)** | **門禁自檢**：驗證來源與 dist 資料完整性 |",
        "| **純發布 (Deploy-Only)** | `python -m pipeline.deploy` | **否 (NO)** | **正式發布唯一推薦**：將已驗證之 dist 提交並推送到 `gh-pages` |",
        "| **單次一鍵更新發布 (One-Shot)** | `python update_story_map.py --deploy` | **是 (YES)** | **不推薦用於審查發布**：因包含上游同步，可能破壞已審查 main 的可重現性 |",
        "",
        "---",
        "",
        "## 二、 變更類型分類 (Update Change Classification)",
        "",
        "| 變更類型 | 涵蓋情境 | 前端 Runtime 是否修改？ | 管線/工具代碼是否修改？ | 預期修改檔案範圍 |",
        "| :--- | :--- | :--- | :--- | :--- |",
        "| **TYPE A (Data Only)** | 遊戲日常換裝、新角色對白上線 (Schema 不變) | **否 (NO)** | **否 (NO)** | `redive_tw.db`, `dashboard/story/*.json`, `versions/` |",
        "| **TYPE B (Generated Metadata)** | 角色縮圖快取更新、話數索引重建 | **否 (NO)** | **否 (NO)** | `dashboard/data/*.json`, `dist_story_map/data/` |",
        "| **TYPE C (Upstream Contract Break)** | 官方 CDN 路徑變更、劇本欄位格式異動 | **通常否 (NO)** | **是 (YES)** | `pipeline/fetch.py`, `tools/pcrd_fetch.py` |",
        "| **TYPE D (Runtime Feature Change)** | 網站新增功能分頁、UI 改版、Normalizer 策略調整 | **是 (YES)** | **依需求** | `dashboard/*.js`, `dashboard/*.css`, `tests/` |",
        "",
        "---",
        "",
        "## 三、 發布前覆蓋面檢查 (Pre-Flight Coverage Check)",
        "",
        "在執行更新前，請先確認更新目標與涵蓋範圍：",
        "1. **TruthVersion 探測是否成功？** 檢查 `update_story_map.py --dry-run` 輸出中是否有 `[CDN] 線上最高 TruthVersion: 006xxxxx`。",
        "2. **資料庫是否最新？** 確認 `redive_tw.db` 版號是否與 CDN 一致。",
        "3. **目標故事是否由 Canonical Pipeline 自動涵蓋？**",
        "   - 若為**已追蹤角色個人劇情**：由 `tracked_characters.json` 自動增量下載。",
        "   - 若為**全新角色個人劇情**：需先將新角色 `unit_id` 與 `icon_ids` 加入 `tracked_characters.json`，或執行 `python -m pipeline.fetch fetch-stories --unit-id <unit_id>`。",
        "   - 若為**新主線/公會/活動/露娜塔劇情**：若需抓取該話對白，可執行單話同步指令 `python -m pipeline.fetch sync-episode --story-id <story_id>`。",
        "   - 若為**第 3 部分支劇情**：需在 `branch_stories.json` 補充副標題元數據。",
        "",
        "---",
        "",
        "## 四、 運維狀態判讀等級 (Update Success Levels)",
        "",
        "- 🟢 **GREEN (完整確認發布)**：CDN 探測成功且版號確認、目標劇本全數就緒、來源變更已 Commit/Push 至 main、驗證門禁 100% 通過。",
        "- 🟡 **YELLOW (陳舊/降級成功警示)**：本地驗證通過，但 CDN 探測超時（可能使用舊 DB 打包）或目標新劇本未在追蹤清單中。",
        "- 🔴 **RED (嚴重阻斷失敗)**：資料庫下載失敗、劇本檔案缺失、或全量驗證門禁未通過（Exit Code 1）。",
        "",
        "---",
        "",
        "## 五、 標準日常更新與可重現發布流程 (Authoritative Reproducible Release Path)",
        "",
        "### 階段一：來源資料同步與審查 (Source Synchronization Phase)",
        "",
        "#### 步驟 1：對齊 main 並建立資料更新分支",
        "```bash",
        "git switch main",
        "git pull --ff-only",
        "git switch -c data/update-YYYYMMDD",
        "```",
        "",
        "#### 步驟 2：執行零副作用 Dry-Run 模擬",
        "```bash",
        "python update_story_map.py --dry-run",
        "```",
        "",
        "#### 步驟 3：執行本地增量更新與決定性打包 (不發布)",
        "```bash",
        "python update_story_map.py",
        "```",
        "",
        "#### 步驟 4：審查來源資料變更 (Source Review Gate)",
        "```bash",
        "git status --short",
        "git diff --stat",
        "```",
        "* **資料庫審查**：對於二進位之 `redive_tw.db`，審查檔案大小、TruthVersion 與 DB hash，確認無異常縮水或損毀。",
        "* **劇本審查**：確認新增的 `dashboard/story/<id>.json` 檔案名稱與內容符合預期。",
        "* **代碼安全檢查**：若發現意外修改了 `dashboard/*.js` 等源碼檔案，**立即中止發布 (STOP)**！",
        "",
        "#### 步驟 5：執行資料完整性驗證",
        "```bash",
        "python -m pipeline.validate",
        "```",
        "",
        "#### 步驟 6：針對性 Stage 與 Commit 來源變更 (嚴禁全局暫存)",
        "> [!CAUTION]",
        "> **嚴格禁止執行 `git add .`、`git add -A`、`git clean` 或 `git stash -u`**！",
        "> **嚴格禁止執行 `git add dist_story_map`**（`dist_story_map` 為獨立 Git 工作區，絕不可被主倉庫暫存）！",
        "",
        "```bash",
        "# 僅針對實際更新的檔案進行精準暫存：",
        "git add dashboard/redive_tw.db",
        "git add dashboard/versions/version_history.json",
        "git add dashboard/story/<新增的story_id>.json",
        "# 若有更新元數據則暫存對應檔案",
        "",
        "git commit -m \"data: update story map data (TruthVersion 006xxxxx)\"",
        "```",
        "",
        "#### 步驟 7：推送來源分支並合併至 main (Source Push Gate)",
        "```bash",
        "git push -u origin data/update-YYYYMMDD",
        "# 經審查無誤後 Fast-Forward 合併至 main：",
        "git switch main",
        "git merge --ff-only data/update-YYYYMMDD",
        "git push origin main",
        "```",
        "",
        "---",
        "",
        "### 階段二：決定性發布階段 (Deterministic Release Phase — Zero Upstream Mutation)",
        "",
        "#### 步驟 8：確認 Working Tree 與 Authoritative Main SHA",
        "```bash",
        "git status --short",
        "# 確保除未追蹤之研究資料外，無任何意外修改的 tracked source 檔案",
        "git rev-parse HEAD",
        "git rev-parse origin/main",
        "# 兩者必須完全一致！",
        "```",
        "",
        "#### 步驟 9：純本地決定性建置 (Rebuild Dist strictly from committed main)",
        "```bash",
        "python -m pipeline.bundle",
        "python -m pipeline.validate",
        "```",
        "",
        "#### 步驟 10：純發布至生產環境 (Deploy-Only)",
        "> [!IMPORTANT]",
        "> **請使用純發布指令 `python -m pipeline.deploy`，嚴禁在已合併 main 後再次執行 `update_story_map.py --deploy`**（避免觸發二次上游同步破壞可重現性）。",
        "",
        "```bash",
        "python -m pipeline.deploy",
        "```",
        "",
        "#### 步驟 11：線上 Smoke Test 驗收",
        "* 檢查 GitHub Pages 部署狀態，確認線上網頁運作正常。",
        "",
        "---",
        "",
        "## 六、 發布一致性契約與異常復原 (Release Consistency & Recovery)",
        "",
        "### 發布一致性契約 (Release Consistency Invariant)",
        "> **正式生產環境 (`gh-pages`) 上的部署產物，必須 100% 能由主倉庫 (`main`) 上的已審查提交 SHA 決定性重現，且來源提交與線上發布之間嚴禁發生任何上游突變。**",
        "",
        "### 異常復原指南",
        "- **情境 A (來源已 Push，但 Deploy 失敗)**: **`SAFE`**。Main 分支已安全保留最新資料狀態。排查網路或部署目錄鎖定後，重新執行 `python -m pipeline.deploy` 即可。",
        "- **情境 B (Deploy 成功，但來源 Push 失敗)**: **`INCONSISTENT (不合規狀態)`**。此時線上產物領先於來源 main，不可視為發布完成！必須立即排除來源倉庫的網路或權限問題，完成 `git push origin main`，恢復 main 與 production 的嚴格對齊。",
        "- **情境 C (來源已提交，但誤跑 full updater 導致來源再度變更)**: **`STOP / DO NOT DEPLOY`**。執行 `git status --short`，若發現 tracked source 與 `origin/main` 不一致，**禁止直接發布**！應安全捨棄非預期變更，或將其視為全新更新重新建立分支審查。"
    ]

    with open(RUNBOOK_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(runbook_lines) + "\n")
    print(f"✅ 操作手冊已寫入: {RUNBOOK_MD}")

    # Write Audit Report
    audit_lines = [
        "# Character Identity C1 — Story Map Update Workflow Audit (Final Release Reproducibility Polish)",
        "",
        "> [!IMPORTANT]",
        "> **本報告為 PCRD Story Map 資料管線 (Pipeline v1) 之完整流程審計、發布同步邊界與可重現性評估報告 (Audit Only)**。未修改任何管線執行時代碼。",
        "",
        "## 1. Executive Summary",
        "",
        "本審計深入探勘了 `update_story_map.py` 與 `pipeline/` 自動化資料管線：",
        "- **發布同步邊界 (Release Synchronization Boundary)**: 確立了「全流程更新 (`update_story_map.py`，包含上游同步)」與「純發布命令 (`pipeline.deploy`，無上游同步)」的職責分離。來源合併至 main 後，必須使用純發布指令，禁止二次觸發上游同步。",
        "- **可重現性不變式 (Reproducibility Invariant)**: `Approved Main SHA -> Deterministic Bundle -> Validated Dist -> gh-pages Deploy`。部署產物保證 100% 決定性對齊已提交的 main 分支。",
        "- **雙倉庫架構分離**: 專案由**來源倉庫 (`main` 分支)** 與**發布倉庫 (`dist_story_map` 獨立 working tree / `gh-pages` 分支)** 組成。`pipeline.deploy` 僅負責推送 `gh-pages`，絕不觸碰主倉庫的 commit/push。",
        "- **前端故事發現與上游抓取**: 本地資料就緒時前端 100% 自動發現；Canonical Updater 增量抓取範圍限於 `tracked_characters.json`，非角色故事可透過 `sync-episode` 單話同步。",
        "",
        "---",
        "",
        "## 2. Release Synchronization Boundary & Reproducibility Flow",
        "",
        "```mermaid",
        "sequenceDiagram",
        "    autonumber",
        "    actor Op as Operator / Agent",
        "    participant Src as Source Repo (main)",
        "    participant Sync as Full Updater (update_story_map.py)",
        "    participant Build as Pure Bundler (pipeline.bundle)",
        "    participant Dist as Dist Repo (gh-pages)",
        "    ",
        "    Note over Op,Sync: Phase 1: Source Synchronization",
        "    Op->>Sync: 1. Run update_story_map.py (Fetch CDN & Local Build)",
        "    Sync->>Src: Writes redive_tw.db & story/*.json",
        "    Op->>Src: 2. Review diff & git commit/push to origin/main",
        "    Note over Src: Synchronization Boundary Established (Main SHA approved)",
        "    ",
        "    Note over Op,Dist: Phase 2: Deterministic Release (No Upstream Sync)",
        "    Op->>Build: 3. python -m pipeline.bundle & validate (Rebuild strictly from main)",
        "    Build->>Dist: Deterministic output to dist_story_map/",
        "    Op->>Dist: 4. python -m pipeline.deploy (Deploy-Only)",
        "    Dist-->>Op: 5. gh-pages updated (Exact match with origin/main)",
        "```",
        "",
        "---",
        "",
        "## 3. Tool Duty Classification (工具職責分類表)",
        "",
        "| 工具名稱 | 具體指令 | 職責分類 | 說明 |",
        "| :--- | :--- | :--- | :--- |",
    ]
    for tc in data["tool_classification"]:
        audit_lines.append(f"| **`{tc['tool_name']}`** | `{tc['command']}` | `{tc['classification']}` | {tc['scope']} |")

    audit_lines.extend([
        "",
        "---",
        "",
        "## 4. Story Type Acquisition & Discovery Matrix",
        "",
        "| 劇情類別 | 本地資料存在時前端是否自動發現？ | Canonical Update 是否自動抓取 JSON？ | 經實證之抓取路徑 (Verified Acquisition Path) |",
        "| :--- | :--- | :--- | :--- |",
    ])
    for row in data["story_type_matrix"]:
        audit_lines.append(f"| **{row['story_type']}** | {row['frontend_discovery_if_local_exists']} | **{row['canonical_update_auto_fetches_json']}** | `{row['verified_acquisition_path']}` |")

    audit_lines.extend([
        "",
        "---",
        "",
        "## 5. Warning Conditions & Degradation Behavior",
        "",
        "| 警告情境 | 管線是否繼續執行？ | Exit Code 是否仍可為 0？ | 新鮮度與涵蓋面後果 |",
        "| :--- | :--- | :--- | :--- |",
    ])
    for w in data["warning_behavior_table"]:
        audit_lines.append(f"| **{w['warning_condition']}** | `{'YES' if w['pipeline_continues'] else 'NO'}` | `{'YES' if w['exit_code_can_be_zero'] else 'NO'}` | {w['consequence']} |")

    audit_lines.extend([
        "",
        "---",
        "",
        "## 6. Validator Semantics & Known Gaps",
        "",
        f"- **Dist 集合關係**: **`{data['validator_coverage']['dist_relationship']}`**",
        f"- **額外 Dist 劇本是否阻斷 (Extra Dist Stories Rejected)**: **`{'YES' if data['validator_coverage']['extra_dist_stories_rejected'] else 'NO'}`**",
        f"- **劇本語法驗證深度**: **{data['validator_coverage']['story_json_validation_depth']}**",
        f"- **資料庫查詢語意**: **{data['validator_coverage']['db_query_semantics']}**",
        "",
        "---",
        "",
        "## 7. Key Questions & Direct Answers",
        "",
        "### Q1. 官方新增正常故事後，是否需要修改前端 JS？",
        "**【答】不需要 (NO)**。只要本地資料庫與劇本 JSON 齊全，前端由 SQLite `story_detail` 自動驅動發現與導航。",
        "",
        "### Q2. 是否能靠權威管線自動抓取所有新故事？",
        "**【答】部分支援 (NO / PARTIAL)**。`update_story_map.py` 自動同步 `tracked_characters.json` 中的個人劇本；非角色劇情（主線、活動、公會、露娜塔）前端可在資料就緒時自動渲染，但目前 Canonical Updater 未自動涵蓋其抓取路徑。",
        "",
        "### Q3. 目前還有哪些步驟需要人工記憶？",
        "**【答】**: 1. 新可玩角色需加入 `tracked_characters.json`；2. 非角色新故事若需對白需使用 `sync-episode` 單話同步；3. 第 3 部分支劇情需在 `branch_stories.json` 補充副標題；4. 來源資料必須在發布前手動執行針對性 `git commit` 與 `git push` 至 main，並使用純發布指令 `pipeline.deploy` 發布。",
        "",
        "### Q4. 是否有 Silent Failure (靜默失敗) 風險？",
        "**【答】存在陳舊成功風險 (Freshness Uncertainty / Stale-Success Risk)**。若 CDN 探測超時，管線會記錄 Warning 並以現有本地資料成功完成打包（不會損毀資料，但產物可能非最新）。",
        "",
        "### Q5. 最值得在 C2 改善的是什麼？",
        "**【答】排序維持不變**：",
        "1. **Freshness 探測確認策略 (Freshness Confirmation Policy)**：評估是否在 CDN 探測失敗時提供更明確的互動提示或可選的 fail-closed 模式。",
        "2. **通用劇本抓取原語 (Generic Story Acquisition Primitive)**：評估建立基於 `DB expected story IDs - local JSON IDs` 的全庫差集增量下載器，取代僅依賴 `tracked_characters`。",
        "3. **元數據自動化整合**：將 `story_thumbnails` 與 `speaker_appearance` 納入標準更新流程。",
        "",
        "### Q6. 目前是否已適合日常資料更新？",
        "**【答】YES WITH COVERAGE AWARENESS, BUT NON-CHARACTER STORY ACQUISITION REMAINS A KNOWN GAP**（已知角色劇情完全適合，非角色劇情需注意抓取覆蓋面缺口，且需遵循來源提交先於發布之規範）。",
        "",
        "---",
        "",
        "## 8. Final Recommendation",
        "",
        f"- **Idempotence Status**: **`{data['idempotence_status']}`**",
        "> [!TIP]",
        "> **C1 審計結論：PASS (管線架構與發布同步邊界高度完備，來源可重現性契約已嚴密規範，建議進入 C2 進行通用抓取與新鮮度策略規劃)**。"
    ])

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(audit_lines) + "\n")
    print(f"✅ 審計報告已寫入: {OUTPUT_MD}")

def main():
    print("============================================================")
    print("🔍 PCRD Story Map — 資料更新管線架構審計 (Phase C1 Polish)")
    print("============================================================")
    data = audit_workflow()
    write_artifacts(data)
    print("============================================================")
    print("🎉 Phase C1 發布同步邊界與可重現性修訂完成！")
    print("============================================================")

if __name__ == "__main__":
    main()
