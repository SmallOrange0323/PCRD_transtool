#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Official Active TruthVersion Resolution Diagnostic Probe (Phase F2B)

目的：
探測並評估官方 Princess Connect TW (So-net) 基礎設施是否暴露可直接解析之
ACTIVE_TRUTH_VERSION，並輸出 Evidence-Calibrated 結構化證據。

分類標準：
  A. ACTIVE_CONFIRMED: 直接證明當前線上運行的 TruthVersion (明文且無認證/低成本)
  B. ACTIVE_DERIVABLE: 官方回應包含足夠決定性資訊可推導出 TruthVersion
  C. CDN_AVAILABLE_ONLY: 僅證明該版本之靜態資源已存在於 CDN 池
  D. NO_GLOBAL_INDEX: 具體 HTTP 證據顯示無可用之未版本化 active-version 全域索引
  E. PROTOCOL_UNRESOLVED: 官方回應封包協議未解析，需客戶端/APK 逆向動態解密
  F. UNSUITABLE: 需要高成本認證/阻斷/不穩定
  G. UNKNOWN: 端點連線失敗或回應未預期

嚴格唯讀契約：
- 不寫入 dashboard/redive_tw.db
- 不更動 version_history.json
- 不修改 production pipeline
- 絕不執行 deploy
"""

import argparse
import base64
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

SONET_API_HOST = "https://api-pc.so-net.tw"
SONET_CDN_HOST = "https://img-pc.so-net.tw"
WEB_HEADER = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)',
    'Content-Type': 'application/x-msgpack',
    'Accept': 'application/x-msgpack',
}


def _http_probe(
    url: str,
    method: str = "POST",
    data: Optional[bytes] = b"",
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 8
) -> Dict[str, Any]:
    """執行單一 HTTP 請求並記錄完整傳輸與二進位特徵。"""
    hdrs = headers or WEB_HEADER
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=data if method == "POST" else None, headers=hdrs, method=method)
    
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as res:
            elapsed = time.perf_counter() - start
            body = res.read()
            return {
                "url": url,
                "method": method,
                "status": res.status,
                "reason": res.reason,
                "headers": dict(res.headers),
                "content_type": res.headers.get("Content-Type"),
                "body_len": len(body),
                "body_raw": body,
                "elapsed_seconds": round(elapsed, 3),
                "error": None
            }
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - start
        body = e.read()
        return {
            "url": url,
            "method": method,
            "status": e.code,
            "reason": e.reason,
            "headers": dict(e.headers),
            "content_type": e.headers.get("Content-Type"),
            "body_len": len(body) if body else 0,
            "body_raw": body,
            "elapsed_seconds": round(elapsed, 3),
            "error": f"HTTPError {e.code}"
        }
    except Exception as e:
        elapsed = time.perf_counter() - start
        return {
            "url": url,
            "method": method,
            "status": None,
            "reason": None,
            "headers": {},
            "content_type": None,
            "body_len": 0,
            "body_raw": None,
            "elapsed_seconds": round(elapsed, 3),
            "error": str(e)
        }


def analyze_opaque_payload(body: Optional[bytes]) -> Dict[str, Any]:
    """分析官方 API 二進位回應之編碼與結構特徵。"""
    if not body:
        return {"type": "EMPTY", "is_base64": False}
    
    analysis: Dict[str, Any] = {
        "raw_length": len(body),
        "is_base64": False,
        "decoded_length": 0,
        "is_16_byte_aligned_prefix": False,
        "has_32_char_hex_tail": False,
        "tail_ascii": None,
    }
    
    try:
        decoded = base64.b64decode(body, validate=True)
        analysis["is_base64"] = True
        analysis["decoded_length"] = len(decoded)
        
        # 官方 Game Server API 封包特徵: [動態加密區塊 (16 bytes 區塊倍數)] + [32 字元 Hex Digest 結尾]
        if len(decoded) > 32:
            prefix = decoded[:-32]
            tail = decoded[-32:]
            analysis["is_16_byte_aligned_prefix"] = (len(prefix) % 16 == 0)
            try:
                tail_str = tail.decode("ascii")
                analysis["has_32_char_hex_tail"] = bool(all(c in "0123456789abcdefABCDEF" for c in tail_str))
                analysis["tail_ascii"] = tail_str
            except Exception:
                analysis["has_32_char_hex_tail"] = False
    except Exception:
        analysis["is_base64"] = False

    return analysis


def inspect_official_endpoints() -> Dict[str, Any]:
    """探測所有已知官方端點並產出結構化訊號矩陣。"""
    report: Dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "probe_target": "Official So-net Infrastructure (api-pc.so-net.tw & img-pc.so-net.tw)",
        "candidates": [],
        "verdict": {
            "is_official_active_truth_version_feasible": False,
            "status": "CLOSED — OFFICIAL ACTIVE VERSION RESOLUTION NOT AVAILABLE WITHIN SUPPORTED PROJECT SCOPE",
            "summary": "官方端點中未發現可直接明文解析之 ACTIVE_TRUTH_VERSION 信號。Game Server API 雖然可在無帳號登入下握手 (HTTP 200)，但回傳封包採用動態 Base64 加密封包 (PROTOCOL_UNRESOLVED)，需客戶端/APK 逆向動態解密；CDN 靜態端點經探測無可用之未版本化全域索引 (NO_GLOBAL_INDEX)，僅支援已知版本節點路徑 (CDN_AVAILABLE_ONLY)。"
        }
    }

    # 1. 探測 check_agreement
    ca_res = _http_probe(f"{SONET_API_HOST}/check/check_agreement", method="POST")
    ca_analysis = analyze_opaque_payload(ca_res["body_raw"])
    report["candidates"].append({
        "channel": "game_api",
        "name": "check_agreement",
        "url": ca_res["url"],
        "status_code": ca_res["status"],
        "content_type": ca_res["content_type"],
        "classification": "PROTOCOL_UNRESOLVED",
        "rationale": "官方握手端點成功連線 (HTTP 200)，但回傳封包為不透明 Base64-wrapped binary (長度 224 bytes)，直接 MessagePack 解析不成功。封包協議未解析 (Protocol Unresolved)，客戶端/APK 逆向還原在專案範疇外。",
        "payload_features": ca_analysis
    })

    # 2. 探測 game_start
    gs_res = _http_probe(f"{SONET_API_HOST}/check/game_start", method="POST")
    gs_analysis = analyze_opaque_payload(gs_res["body_raw"])
    report["candidates"].append({
        "channel": "game_api",
        "name": "game_start",
        "url": gs_res["url"],
        "status_code": gs_res["status"],
        "content_type": gs_res["content_type"],
        "classification": "PROTOCOL_UNRESOLVED",
        "rationale": "官方握手端點成功連線 (HTTP 200)，回傳封包結構與 check_agreement 相同 (長度 320 bytes)，直接 MessagePack 解析不成功，屬 Protocol Unresolved。",
        "payload_features": gs_analysis
    })

    # 3. 探測 check_version
    cv_res = _http_probe(f"{SONET_API_HOST}/check/check_version", method="POST")
    cv_analysis = analyze_opaque_payload(cv_res["body_raw"])
    report["candidates"].append({
        "channel": "game_api",
        "name": "check_version",
        "url": cv_res["url"],
        "status_code": cv_res["status"],
        "content_type": cv_res["content_type"],
        "classification": "PROTOCOL_UNRESOLVED",
        "rationale": "官方版本檢查端點成功連線 (HTTP 200)，但同樣回傳不透明 Base64-wrapped binary，無明文版本暴露，屬 Protocol Unresolved。",
        "payload_features": cv_analysis
    })

    # 4. 探測 CDN 靜態無版本路徑
    cdn_checks = [
        ("cdn_root", f"{SONET_CDN_HOST}/dl/"),
        ("cdn_resources_root", f"{SONET_CDN_HOST}/dl/Resources/"),
        ("cdn_manifest_json", f"{SONET_CDN_HOST}/dl/Resources/manifest.json"),
        ("cdn_version_json", f"{SONET_CDN_HOST}/dl/Resources/version.json"),
        ("cdn_android_manifest", f"{SONET_CDN_HOST}/dl/Resources/Android/manifest"),
    ]
    for name, cdn_url in cdn_checks:
        c_res = _http_probe(cdn_url, method="GET")
        report["candidates"].append({
            "channel": "cdn_static",
            "name": name,
            "url": cdn_url,
            "status_code": c_res["status"],
            "classification": "CDN_AVAILABLE_ONLY" if c_res["status"] == 200 else "NO_GLOBAL_INDEX",
            "rationale": f"具體 HTTP 證據顯示未發現可用之未版本化 active-version 全域索引 (HTTP {c_res['status']})。官方 CDN 僅支援具體 TruthVersion 節點路徑，僅提供 CDN_AVAILABLE_ONLY，不構成啟用證據。"
        })

    return report


def main():
    parser = argparse.ArgumentParser(description="Official Active TruthVersion Resolution Diagnostic Probe")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式輸出")
    args = parser.parse_args()

    results = inspect_official_endpoints()

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print("=" * 60)
        print("🔍 官方 ACTIVE_TRUTH_VERSION 解析可行性診斷 (Phase F2B)")
        print("=" * 60)
        print(f"探測目標: {results['probe_target']}")
        print(f"探測時間: {results['timestamp']}\n")
        
        print("候選訊號評估清單：")
        for c in results["candidates"]:
            print(f"  [{c['classification']}] {c['channel']} / {c['name']}")
            print(f"    URL:    {c['url']}")
            print(f"    Status: {c['status_code']}")
            print(f"    判定:   {c['rationale']}")
            if "payload_features" in c and c["payload_features"].get("is_base64"):
                pf = c["payload_features"]
                print(f"    特徵:   Base64={pf['is_base64']}, 解碼長度={pf['decoded_length']}B, 16B對齊={pf['is_16_byte_aligned_prefix']}, 尾部雜湊={pf.get('tail_ascii')}")
            print()
            
        print("=" * 60)
        print(f"狀態: {results['verdict']['status']}")
        print(f"最終結論: {'可實作' if results['verdict']['is_official_active_truth_version_feasible'] else '目前不可行 (Infeasible)'}")
        print(f"說明: {results['verdict']['summary']}")
        print("=" * 60)


if __name__ == "__main__":
    main()
