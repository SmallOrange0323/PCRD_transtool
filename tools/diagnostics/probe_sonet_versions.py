#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Direct So-net CDN Candidate Scanner (Phase F1 Diagnostic Prototype)

目的：
唯讀探測 So-net CDN 上特定 TruthVersion 的 masterdata2_assetmanifest 是否存在，
並驗證其清單完整性，解析出 masterdata_master.unity3d 的 Bundle Hash。

嚴格規則：
- 僅做 HEAD / 輕量 Manifest GET，不下載大型 AssetBundle
- 不修改 production pipeline 或本地 DB
- 區分 CDN_AVAILABLE_VERSION 與 ACTIVE_TRUTH_VERSION
"""

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Any

sys.stdout.reconfigure(encoding='utf-8')

SONET_CDN = "https://img-pc.so-net.tw/dl"
WEB_HEADER = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'
}

def probe_single_version(version: str, timeout: int = 6) -> Dict[str, Any]:
    """
    探測單一版本號之 masterdata2_assetmanifest。
    狀態分類:
      - EXISTS: HEAD 200 且 GET 成功解析 masterdata_master.unity3d
      - NOT_FOUND: HTTP 404
      - INVALID_MANIFEST: HTTP 200 但 Manifest 格式損壞或未含 masterdata_master
      - NETWORK_ERROR: 超時、連線重設或其他例外
    """
    manifest_url = f"{SONET_CDN}/Resources/{version}/Jpn/AssetBundles/Android/manifest/masterdata2_assetmanifest"
    result: Dict[str, Any] = {
        "version": version,
        "url": manifest_url,
        "status": "UNKNOWN",
        "http_code": None,
        "manifest_size": 0,
        "manifest_sha256": None,
        "masterdata_md5": None,
        "masterdata_hash": None,
        "duration_ms": 0,
        "error": None
    }

    start_time = time.perf_counter()

    # Step 1: HEAD 請求初篩
    try:
        req_head = urllib.request.Request(manifest_url, headers=WEB_HEADER, method='HEAD')
        with urllib.request.urlopen(req_head, timeout=timeout) as res:
            result["http_code"] = res.status
    except urllib.error.HTTPError as e:
        result["http_code"] = e.code
        result["duration_ms"] = int((time.perf_counter() - start_time) * 1000)
        if e.code == 404:
            result["status"] = "NOT_FOUND"
        else:
            result["status"] = "NETWORK_ERROR"
            result["error"] = f"HTTP {e.code}: {e.reason}"
        return result
    except Exception as e:
        result["duration_ms"] = int((time.perf_counter() - start_time) * 1000)
        result["status"] = "NETWORK_ERROR"
        result["error"] = str(e)
        return result

    if result["http_code"] != 200:
        result["duration_ms"] = int((time.perf_counter() - start_time) * 1000)
        result["status"] = "NETWORK_ERROR"
        return result

    # Step 2: GET 輕量下載 Manifest 並校驗內容
    try:
        req_get = urllib.request.Request(manifest_url, headers=WEB_HEADER, method='GET')
        with urllib.request.urlopen(req_get, timeout=timeout) as res:
            content_bytes = res.read()
            result["manifest_size"] = len(content_bytes)
            result["manifest_sha256"] = hashlib.sha256(content_bytes).hexdigest()

            content_text = content_bytes.decode('utf-8', errors='ignore')
            for line in content_text.splitlines():
                if "masterdata_master.unity3d" in line:
                    parts = line.split(',')
                    if len(parts) >= 3:
                        result["masterdata_md5"] = parts[1].strip()
                        result["masterdata_hash"] = parts[2].strip()
                        break

        result["duration_ms"] = int((time.perf_counter() - start_time) * 1000)

        if result["manifest_size"] > 0 and result["masterdata_hash"]:
            result["status"] = "EXISTS"
        else:
            result["status"] = "INVALID_MANIFEST"
            result["error"] = "masterdata_master.unity3d hash missing or manifest empty"
    except Exception as e:
        result["duration_ms"] = int((time.perf_counter() - start_time) * 1000)
        result["status"] = "NETWORK_ERROR"
        result["error"] = f"GET read error: {e}"

    return result

def run_probe_sequence(versions: List[str]) -> List[Dict[str, Any]]:
    results = []
    print(f"[*] 開始依序探測 {len(versions)} 個 TruthVersion 候選點...")
    print(f"{'Version':<10} | {'Status':<16} | {'HTTP':<5} | {'Size':<8} | {'Bundle Hash':<34} | {'Latency':<8}")
    print("-" * 92)
    for v in versions:
        r = probe_single_version(v)
        results.append(r)
        hash_disp = r['masterdata_hash'] or '-'
        size_disp = f"{r['manifest_size']}B" if r['manifest_size'] else '-'
        print(f"{r['version']:<10} | {r['status']:<16} | {str(r['http_code'] or '-'):<5} | {size_disp:<8} | {hash_disp:<34} | {r['duration_ms']}ms")
    print("-" * 92)
    return results

def main():
    parser = argparse.ArgumentParser(description="Direct So-net CDN Candidate Scanner Prototype")
    parser.add_argument("--base-version", type=str, default="00610007", help="Base version to scan around")
    parser.add_argument("--versions", nargs="*", help="Explicit versions list to probe")
    parser.add_argument("--window", type=int, default=10, help="Number of forward versions to scan")
    parser.add_argument("--json", action="store_true", help="Output raw JSON format")
    args = parser.parse_args()

    target_versions: List[str] = []
    if args.versions:
        target_versions = args.versions
    else:
        # 預設基準測試：包含關鍵對照點
        base = args.base_version
        prefix = base[:-4]
        num = int(base[-4:])
        
        # 包含已知的 00600025，以及 00610002～00610007 及其後續 bounded window
        initial_set = ["00600025"]
        for n in range(max(1, num - 5), num + args.window + 1):
            initial_set.append(f"{prefix}{n:04d}")
        # 去重保序
        seen = set()
        for v in initial_set:
            if v not in seen:
                seen.add(v)
                target_versions.append(v)

    results = run_probe_sequence(target_versions)

    existing = [r for r in results if r["status"] == "EXISTS"]
    highest_cdn = existing[-1]["version"] if existing else None

    print(f"\n[總結]")
    print(f"  總探測版本數: {len(results)}")
    print(f"  實際存在 (EXISTS): {len(existing)} 個 ({', '.join([r['version'] for r in existing])})")
    print(f"  不存在 (NOT_FOUND): {len([r for r in results if r['status'] == 'NOT_FOUND'])} 個")
    print(f"  最高可觀察 CDN 版本 (highest_observed_cdn_version): {highest_cdn}")

    if args.json:
        print("\n[JSON Output]")
        print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
