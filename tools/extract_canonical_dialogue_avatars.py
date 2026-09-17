#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCRD Story Map Pipeline - Canonical Dialogue Avatar Extractor
從官方 So-net CDN storydata2_assetmanifest 批次下載、解包並登錄缺失的 dialogue avatar。
"""

import os
import sys
import json
import hashlib
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, List, Optional

import UnityPy
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# 注意若在 scratch 執行，需要確保根目錄正確
if not (PROJECT_ROOT / "dashboard").exists():
    PROJECT_ROOT = Path("e:/OneDrive - 寰宇知識科技股份有限公司/PCRD_tool")

DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
DIST_DIR = PROJECT_ROOT / "dist_story_map"
ICON_DIR = DASHBOARD_DIR / "icon" / "unit"
DIST_ICON_DIR = DIST_DIR / "icon" / "unit"
REGISTRY_PATH = DASHBOARD_DIR / "data" / "avatar_assets.json"
DIST_REGISTRY_PATH = DIST_DIR / "data" / "avatar_assets.json"
MANIFEST_PATH = DASHBOARD_DIR / "versions" / "cached_manifests" / "storydata2_assetmanifest.txt"
INPUT_IDS_FILE = PROJECT_ROOT / "docs" / "avatar_needs_unpack_ids.txt"
MISSING_IDS_FILE = PROJECT_ROOT / "docs" / "avatar_official_asset_missing_ids.txt"

SONET_HEADER = {"User-Agent": "Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL)"}
UnityPy.config.FALLBACK_UNITY_VERSION = "2021.3.20f1"


def calc_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest_map() -> Dict[str, str]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Manifest cache not found: {MANIFEST_PATH}")

    manifest_map = {}
    with open(MANIFEST_PATH, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) >= 3 and parts[0].startswith("a/storydata_icon_unit_"):
                key = parts[0].split("a/storydata_icon_unit_")[1].replace(".unity3d", "")
                manifest_map[key] = parts[2]
    return manifest_map


def download_and_extract_avatar(
    unit_id: int, asset_key: str, pool_hash: str, overwrite: bool = False
) -> Optional[Dict[str, Any]]:
    png_filename = f"{asset_key}.png"
    out_path = ICON_DIR / png_filename
    dist_out_path = DIST_ICON_DIR / png_filename

    if out_path.exists() and not overwrite:
        size = out_path.stat().st_size
        sha = calc_sha256(out_path)
        if not dist_out_path.exists():
            dist_out_path.parent.mkdir(parents=True, exist_ok=True)
            dist_out_path.write_bytes(out_path.read_bytes())
        return {
            "unit_id": unit_id,
            "asset_key": asset_key,
            "filename": png_filename,
            "format": "png",
            "usage": "dialogue",
            "status": "active",
            "size_bytes": size,
            "sha256": sha,
            "provenance": "storydata2_assetmanifest",
        }

    url = f"https://img-pc.so-net.tw/dl/pool/AssetBundles/{pool_hash[:2]}/{pool_hash}"
    req = urllib.request.Request(url, headers=SONET_HEADER)
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            bundle_data = res.read()
    except Exception as e:
        print(f"[ERROR] download failed (ID {unit_id}, key {asset_key}): {e}", file=sys.stderr)
        return None

    try:
        env = UnityPy.load(bundle_data)
        extracted_img = None
        for obj in env.objects:
            if obj.type.name in {"Texture2D", "Sprite"}:
                data = obj.read()
                extracted_img = data.image
                break

        if extracted_img is None:
            print(f"[ERROR] No Texture2D/Sprite in bundle (ID {unit_id}, key {asset_key})", file=sys.stderr)
            return None

        ICON_DIR.mkdir(parents=True, exist_ok=True)
        DIST_ICON_DIR.mkdir(parents=True, exist_ok=True)

        extracted_img.save(out_path, format="PNG")
        dist_out_path.write_bytes(out_path.read_bytes())

        size = out_path.stat().st_size
        sha = calc_sha256(out_path)

        return {
            "unit_id": unit_id,
            "asset_key": asset_key,
            "filename": png_filename,
            "format": "png",
            "usage": "dialogue",
            "status": "active",
            "size_bytes": size,
            "sha256": sha,
            "provenance": "storydata2_assetmanifest",
        }
    except Exception as e:
        print(f"[ERROR] UnityPy extract failed (ID {unit_id}, key {asset_key}): {e}", file=sys.stderr)
        return None


def run_extraction(max_workers: int = 16) -> bool:
    print("Starting Canonical Dialogue Avatar Extractor...")

    if not INPUT_IDS_FILE.exists():
        print(f"[ERROR] Input file not found: {INPUT_IDS_FILE}", file=sys.stderr)
        return False

    with open(INPUT_IDS_FILE, "r", encoding="utf-8") as f:
        req_ids = [int(line.strip()) for line in f if line.strip() and not line.startswith("#")]

    unique_req_ids = sorted(list(set(req_ids)))
    print(f"Requested IDs: {len(unique_req_ids)} unique IDs")

    manifest_map = load_manifest_map()
    print(f"Manifest loaded: {len(manifest_map)} assets")

    matched = []
    missing_in_manifest = []

    for uid in unique_req_ids:
        key = f"{uid:06d}"
        if key in manifest_map:
            matched.append((uid, key, manifest_map[key]))
        else:
            missing_in_manifest.append(uid)

    print(f"Manifest match result: Matched={len(matched)}, Missing={len(missing_in_manifest)}")

    if missing_in_manifest:
        print(f"Missing IDs in official manifest: {missing_in_manifest}")
        with open(MISSING_IDS_FILE, "w", encoding="utf-8") as f:
            for m in sorted(missing_in_manifest):
                f.write(f"{m}\n")
        print(f"Wrote missing report: {MISSING_IDS_FILE}")
    else:
        if MISSING_IDS_FILE.exists():
            MISSING_IDS_FILE.unlink()

    print(f"Extracting {len(matched)} assets with {max_workers} workers...")
    extracted_entries = []
    failed_extractions = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(download_and_extract_avatar, uid, key, pool_hash): (uid, key)
            for uid, key, pool_hash in matched
        }

        completed_count = 0
        total_count = len(futures)
        for future in as_completed(futures):
            uid, key = futures[future]
            completed_count += 1
            entry = future.result()
            if entry:
                extracted_entries.append(entry)
            else:
                failed_extractions.append(uid)

            if completed_count % 50 == 0 or completed_count == total_count:
                percent = completed_count * 100 // total_count
                print(f"  Progress: {completed_count}/{total_count} ({percent}%)")

    print(f"\nExtraction completed. Succeeded: {len(extracted_entries)}, Failed: {len(failed_extractions)}")

    if failed_extractions:
        print(f"[ERROR] Failed IDs: {failed_extractions}", file=sys.stderr)
        return False

    print("\nUpdating avatar_assets.json...")
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        registry_data = json.load(f)

    existing_assets = registry_data.get("assets", [])
    existing_uids = {a.get("unit_id") for a in existing_assets if a.get("unit_id") is not None}

    new_assets_added = 0
    updated_assets_list = list(existing_assets)

    for entry in extracted_entries:
        uid = entry["unit_id"]
        if uid in existing_uids:
            for idx, a in enumerate(updated_assets_list):
                if a.get("unit_id") == uid:
                    updated_assets_list[idx] = entry
                    break
        else:
            updated_assets_list.append(entry)
            existing_uids.add(uid)
            new_assets_added += 1

    updated_assets_list.sort(key=lambda a: (a.get("unit_id", 0), a.get("usage", ""), a.get("filename", "")))

    total_assets = len(updated_assets_list)
    dialogue_assets_count = sum(1 for a in updated_assets_list if a.get("usage") == "dialogue")
    active_dialogue_count = sum(1 for a in updated_assets_list if a.get("usage") == "dialogue" and a.get("status") == "active")
    placeholder_only_count = sum(1 for a in updated_assets_list if a.get("status") == "placeholder_only")
    ui_assets_count = sum(1 for a in updated_assets_list if a.get("usage") == "ui")
    dialogue_overrides_count = sum(1 for a in updated_assets_list if "dialogue_asset" in a)
    total_active_bytes = sum(a.get("size_bytes", 0) for a in updated_assets_list if a.get("status") == "active")
    total_active_mib = round(total_active_bytes / (1024 * 1024), 4)

    updated_registry = {
        "version": 1,
        "metadata": {
            "description": "PCRD Story Map - Canonical Avatar Asset Registry",
            "total_assets": total_assets,
            "dialogue_assets_count": dialogue_assets_count,
            "active_dialogue_count": active_dialogue_count,
            "placeholder_only_count": placeholder_only_count,
            "ui_assets_count": ui_assets_count,
            "dialogue_overrides_count": dialogue_overrides_count,
            "total_active_bytes": total_active_bytes,
            "total_active_mib": total_active_mib,
        },
        "assets": updated_assets_list,
    }

    with open(REGISTRY_PATH, "w", encoding="utf-8") as fe:
        json.dump(updated_registry, fe, indent=2, ensure_ascii=False)

    DIST_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DIST_REGISTRY_PATH, "w", encoding="utf-8") as fd:
        json.dump(updated_registry, fd, indent=2, ensure_ascii=False)

    print(f"Registry updated:")
    print(f"  - New assets added: {new_assets_added}")
    print(f"  - Total assets: {total_assets}")
    print(f"  - Active dialogue assets: {active_dialogue_count}")
    print(f"  - Placeholder assets: {placeholder_only_count}")
    print(f"  - Total active bytes: {total_active_bytes} ({total_active_mib} MiB)")

    return True


if __name__ == "__main__":
    success = run_extraction()
    sys.exit(0 if success else 1)
