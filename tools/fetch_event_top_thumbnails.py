# -*- coding: utf-8 -*-
"""
fetch_event_top_thumbnails.py — 官方活動頂層專屬縮圖下載與轉檔工具
從 So-net CDN 的 icon2_assetmanifest 解析官方活動頂層專屬縮圖 (256x128)，
使用 UnityPy 提取 Texture2D 並轉換為高品質 WebP 儲存至 dashboard/icon/event_top/。
"""

import argparse
import concurrent.futures
import hashlib
import io
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from pipeline.extract_chapter_titles import get_current_truth_version

SONET_CDN = "https://img-pc.so-net.tw/dl"
SONET_HEADER = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'
}

DASHBOARD_DIR = BASE_DIR / "dashboard"
OUTPUT_DIR = DASHBOARD_DIR / "icon" / "event_top"
MANIFEST_CONTRACT_PATH = BASE_DIR / "pipeline" / "manifests" / "official_event_top_manifest.json"
REPORT_PATH = BASE_DIR / "tools" / "event_top_thumb_report.json"


def download_cdn_manifest(truth_version: str, timeout: int = 20) -> str:
    """
    從 CDN 下載指定 TruthVersion 之 icon2_assetmanifest 明文內容。
    若請求失敗或回傳非 200 則拋出 RuntimeError (Fail-Closed)。
    嚴禁使用本地根目錄未經驗證之任意 manifest。
    """
    url = f"{SONET_CDN}/Resources/{truth_version}/Jpn/AssetBundles/Android/manifest/icon2_assetmanifest"
    req = urllib.request.Request(url, headers=SONET_HEADER)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            return data.decode("utf-8", errors="ignore")
    except Exception as e:
        raise RuntimeError(f"無法從 CDN 下載 TruthVersion {truth_version} 之 icon2_assetmanifest: {e}")


def parse_event_top_targets_from_manifest(manifest_content: str) -> Dict[str, Dict[str, Any]]:
    """
    解析 icon2_assetmanifest 字串內容，過濾出所有 icon_thumb_event_story_top_*.unity3d 目標。
    """
    targets = {}
    for line in manifest_content.splitlines():
        parts = line.strip().split(",")
        if len(parts) >= 5 and "icon_thumb_event_story_top_" in parts[0]:
            bundle_name = parts[0]
            bundle_md5 = parts[1]
            pool_hash = parts[2]
            bundle_size = int(parts[4]) if parts[4].isdigit() else None
            stem = bundle_name.replace("a/icon_thumb_event_story_top_", "").replace(".unity3d", "")
            targets[stem] = {
                "bundle_name": bundle_name,
                "bundle_md5": bundle_md5,
                "pool_hash": pool_hash,
                "bundle_size": bundle_size,
                "relative_output_path": f"dashboard/icon/event_top/{stem}.webp"
            }
    return dict(sorted(targets.items(), key=lambda x: int(x[0]) if x[0].isdigit() else x[0]))


def write_contract_manifest(
    truth_version: str,
    targets: Dict[str, Dict[str, Any]],
    contract_path: Path = MANIFEST_CONTRACT_PATH
) -> Path:
    """寫入/更新決定性 official_event_top_manifest.json (純相對路徑)"""
    contract_data = {
        "title": "PCRD Official TW Event Story Top Thumbnail Source Manifest",
        "description": "官方台版活動頂層專屬縮圖來源與資源對照清單",
        "schema_version": "1.0.0",
        "locale": "zh-TW",
        "source_type": "official_tw_localized_asset",
        "truth_version": truth_version,
        "manifest_name": "icon2_assetmanifest",
        "total_targets": len(targets),
        "asset_relative_dir": "dashboard/icon/event_top",
        "targets": targets
    }
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    with open(contract_path, "w", encoding="utf-8") as f:
        json.dump(contract_data, f, ensure_ascii=False, indent=2)
    return contract_path


def load_pinned_contract(contract_path: Path = MANIFEST_CONTRACT_PATH) -> Tuple[str, Dict[str, Dict[str, Any]]]:
    """從官方 tracked contract 讀取 pinned version 與 targets"""
    if not contract_path.exists():
        raise FileNotFoundError(f"找不到決定性清單檔案: {contract_path}")
    with open(contract_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    truth_version = data.get("truth_version")
    targets = data.get("targets", {})
    if not truth_version or not targets:
        raise ValueError(f"決定性清單資料無效或缺少必要欄位: {contract_path}")
    return truth_version, targets


def download_and_extract_event_top(
    event_id: str,
    target_info: Dict[str, Any],
    output_dir: Path = OUTPUT_DIR,
    force: bool = False
) -> Tuple[str, bool, Optional[str]]:
    """
    下載單一活動頂層縮圖 AssetBundle，執行 integrity (size & md5) 檢查，
    再使用 UnityPy 提取 Texture2D 轉成 WebP。
    :return: (event_id, success, error_message)
    """
    out_file = output_dir / f"{event_id}.webp"
    if not force and out_file.exists() and out_file.stat().st_size > 0:
        return event_id, True, "cached"

    bundle_hash = target_info.get("pool_hash")
    if not bundle_hash:
        return event_id, False, "Missing pool_hash in target info"

    expected_size = target_info.get("bundle_size")
    expected_md5 = target_info.get("bundle_md5")

    url = f"{SONET_CDN}/pool/AssetBundles/{bundle_hash[:2]}/{bundle_hash}"
    req = urllib.request.Request(url, headers=SONET_HEADER)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            bundle_bytes = resp.read()
    except Exception as e:
        return event_id, False, f"HTTP error: {e}"

    # 1. 檔案大小完整性檢查 (Gate)
    if expected_size is not None and len(bundle_bytes) != expected_size:
        return event_id, False, f"Size mismatch: expected {expected_size}, got {len(bundle_bytes)}"

    # 2. MD5 雜湊完整性檢查 (Gate)
    if expected_md5:
        actual_md5 = hashlib.md5(bundle_bytes).hexdigest()
        if actual_md5.lower() != expected_md5.lower():
            return event_id, False, f"MD5 mismatch: expected {expected_md5}, got {actual_md5}"

    try:
        import UnityPy

        UnityPy.config.FALLBACK_UNITY_VERSION = "2020.3.34f1"
        env = UnityPy.load(bundle_bytes)

        found_img = None
        for obj in env.objects:
            if obj.type.name == "Texture2D":
                t2d = obj.read()
                found_img = t2d.image
                break

        if not found_img:
            return event_id, False, "No Texture2D found in bundle"

        out_file.parent.mkdir(parents=True, exist_ok=True)
        found_img.save(out_file, format="WEBP", quality=85)
        return event_id, True, None
    except Exception as e:
        return event_id, False, f"UnityPy extract error: {e}"


def verify_local_assets(
    expected_targets: Dict[str, Any],
    asset_dir: Path = OUTPUT_DIR
) -> Dict[str, Any]:
    """
    精準驗證本地素材集合。
    PASS 條件：missing_count == 0 AND extra_count == 0。
    """
    expected_ids = set(expected_targets.keys())

    local_files = set()
    if asset_dir.exists():
        for p in asset_dir.glob("*.webp"):
            if p.is_file() and p.stat().st_size > 0:
                local_files.add(p.stem)

    matched = sorted(list(expected_ids.intersection(local_files)))
    missing = sorted(list(expected_ids.difference(local_files)))
    extra = sorted(list(local_files.difference(expected_ids)))

    is_pass = (len(missing) == 0 and len(extra) == 0)

    result = {
        "status": "PASS" if is_pass else "FAIL",
        "total_expected": len(expected_ids),
        "matched_count": len(matched),
        "missing_count": len(missing),
        "extra_count": len(extra),
        "missing_ids": missing,
        "extra_ids": extra,
        "asset_relative_dir": "dashboard/icon/event_top"
    }

    print("\n" + "=" * 60)
    print(f"[FetchEventTop:Verify] 本地 event_top 素材驗證結果: {result['status']}")
    print(f"  - 預期總數: {result['total_expected']}")
    print(f"  - 完整匹配: {result['matched_count']}")
    print(f"  - 缺失數量: {result['missing_count']}")
    print(f"  - 額外數量: {result['extra_count']}")
    if missing:
        print(f"  - 缺失清單: {missing}")
    if extra:
        print(f"  - 額外清單: {extra}")
    print("=" * 60)

    return result


def run_pipeline(
    from_contract: bool = False,
    specified_truth_version: Optional[str] = None,
    force: bool = False,
    max_workers: int = 8,
    contract_path: Path = MANIFEST_CONTRACT_PATH,
    output_dir: Path = OUTPUT_DIR,
    report_path: Path = REPORT_PATH
) -> Dict[str, Any]:
    """
    執行活動頂層專屬縮圖下載/重建管線。
    支援模式：
    - ONLINE UPDATE MODE (from_contract=False): 線上探測 TruthVersion (Fail-Closed) ➡️ 下載 manifest ➡️ 更新 contract ➡️ 下載解密
    - PINNED CONTRACT MODE (from_contract=True): 讀取已追蹤之 contract ➡️ 離線重建
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if from_contract:
        mode = "pinned_contract"
        source_truth_version, targets = load_pinned_contract(contract_path)
        print(f"[FetchEventTop] 執行模式: PINNED CONTRACT (版本: {source_truth_version})")
    else:
        mode = "online_update"
        if specified_truth_version and str(specified_truth_version).strip():
            source_truth_version = str(specified_truth_version).strip()
        else:
            source_truth_version = get_current_truth_version()
        print(f"[FetchEventTop] 執行模式: ONLINE UPDATE (線上 TruthVersion: {source_truth_version})")

        manifest_text = download_cdn_manifest(source_truth_version)
        targets = parse_event_top_targets_from_manifest(manifest_text)
        write_contract_manifest(source_truth_version, targets, contract_path)

    print(f"[FetchEventTop] 目標活動頂層專屬縮圖數: {len(targets)} 筆")
    tasks = [(eid, info) for eid, info in targets.items()]

    success_count = 0
    cached_count = 0
    failed_list = []

    start_time = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(download_and_extract_event_top, eid, info, output_dir, force): eid
            for eid, info in tasks
        }
        completed = 0
        total = len(futures)
        for future in concurrent.futures.as_completed(futures):
            completed += 1
            eid, ok, err = future.result()
            if ok:
                if err == "cached":
                    cached_count += 1
                else:
                    success_count += 1
            else:
                failed_list.append({"event_id": eid, "error": err})

            if completed % 20 == 0 or completed == total:
                print(f"  ▶ 進度: {completed}/{total} (成功: {success_count}, 快取: {cached_count}, 失敗: {len(failed_list)})")

    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"[FetchEventTop] 活動頂層專屬縮圖處理完成！總耗時: {elapsed:.2f} 秒")
    print(f"  - 新下載轉檔: {success_count} 張")
    print(f"  - 本地快取保留: {cached_count} 張")
    print(f"  - 處理失敗: {len(failed_list)} 張")
    print("=" * 60)

    # 執行結果報告：truth_version 嚴格來自實際執行的 source_truth_version
    report_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": mode,
        "truth_version": source_truth_version,
        "total_targets": len(tasks),
        "downloaded": success_count,
        "cached": cached_count,
        "failed": failed_list,
        "output_dir": "dashboard/icon/event_top"
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    print(f"[FetchEventTop] 執行報告已儲存至: {report_path}")

    # 驗證本地狀態 (Exact Local Verification)
    verify_result = verify_local_assets(targets, asset_dir=output_dir)
    report_data["verify_result"] = verify_result

    # 若有下載失敗，或本地不完全符合 expected (missing > 0 或 extra > 0)，Fail-Closed
    if len(failed_list) > 0 or verify_result["status"] != "PASS":
        report_data["success"] = False
    else:
        report_data["success"] = True

    return report_data


def main():
    parser = argparse.ArgumentParser(description="下載、轉檔與驗證 So-net 官方活動頂層專屬縮圖 (WebP 256x128)")
    parser.add_argument("--from-contract", action="store_true", help="使用本機已追蹤之官方規格清單 (離線/Pinned 重建模式)")
    parser.add_argument("--truth-version", type=str, default=None, help="手動指定 TruthVersion (覆寫線上探測)")
    parser.add_argument("--force", action="store_true", help="強制重新下載現有已快取的縮圖")
    parser.add_argument("--workers", type=int, default=8, help="下載線程數 (預設: 8)")
    parser.add_argument("--verify-only", action="store_true", help="僅執行本地素材一致性驗證，不發送下載請求")

    args = parser.parse_args()

    if args.verify_only:
        _, targets = load_pinned_contract()
        res = verify_local_assets(targets)
        if res["status"] != "PASS":
            sys.exit(1)
        return

    result = run_pipeline(
        from_contract=args.from_contract,
        specified_truth_version=args.truth_version,
        force=args.force,
        max_workers=args.workers
    )

    if not result.get("success", False):
        print("[FetchEventTop] 執行失敗或本地資產集合未達完全精準狀態，終止 (Fail-Closed)！", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
