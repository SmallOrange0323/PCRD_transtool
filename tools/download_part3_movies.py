# -*- coding: utf-8 -*-
"""
tools/download_part3_movies.py
批次下載公主連結 Re:Dive 主線第三部 (Part 3) 全量官方過場動畫 (.usm 格式)
支援：按章節歸檔、斷點續傳、大小校驗、網路超時重試與即時進度顯示
"""

import os
import re
import sys
import time
import urllib.request
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.pcrd_fetch import _get_sonet_ver, WEB_HEADER, SONET_CDN

DEFAULT_OUT_DIR = ROOT / "downloads" / "movies" / "part3"


def fetch_part3_movie_manifest(ver):
    """獲取台服 CDN 高畫質 movie2manifest 並篩選出第三部主線過場動畫"""
    manifest_url = f"{SONET_CDN}/Resources/{ver}/Jpn/Movie/SP/High/manifest/movie2manifest"
    req = urllib.request.Request(manifest_url, headers=WEB_HEADER)
    with urllib.request.urlopen(req, timeout=15) as res:
        content = res.read().decode("utf-8", errors="ignore")

    part3_movies = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) >= 5:
            fn = parts[0]
            # 篩選 m/t/story_22XXXXXXX.usm
            m = re.match(r'm/t/(story_22(\d{2})\d+\.usm)', fn)
            if m:
                clean_name = m.group(1)
                ch_num = int(m.group(2))
                part3_movies.append({
                    "raw_path": fn,
                    "filename": clean_name,
                    "chapter": ch_num,
                    "pool_hash": parts[2],
                    "size_bytes": int(parts[4])
                })
    return part3_movies


def download_file(url, target_path, expected_size, max_retries=3):
    """下載單一檔案，支援斷點續傳與大小校驗"""
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if target_path.exists():
        cur_size = target_path.stat().st_size
        if cur_size == expected_size:
            return True, "EXISTS"
        elif cur_size > expected_size:
            target_path.unlink()
            cur_size = 0
    else:
        cur_size = 0

    headers = dict(WEB_HEADER)
    if cur_size > 0:
        headers["Range"] = f"bytes={cur_size}-"

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as res:
                mode = "ab" if cur_size > 0 and res.status == 206 else "wb"
                if mode == "wb":
                    cur_size = 0

                with open(target_path, mode) as f:
                    while True:
                        chunk = res.read(1024 * 512)
                        if not chunk:
                            break
                        f.write(chunk)
                        cur_size += len(chunk)

            if target_path.stat().st_size == expected_size:
                return True, "DOWNLOADED"
            else:
                print(f"\n  [警告] 檔案大小不符 (本機: {target_path.stat().st_size} != 期望: {expected_size})，重試中...")
        except Exception as e:
            if attempt == max_retries:
                return False, f"ERROR: {e}"
            time.sleep(2)

    return False, "FAILED_VERIFY"


def main():
    print("==================================================")
    print("🎬 PCRD 第三部官方主線過場動畫批次下載器")
    print("==================================================")

    ver = _get_sonet_ver()
    print(f"[CDN] 當前台服 TruthVersion: {ver}")
    print("[Manifest] 正在取得官方動畫清單 (movie2manifest)...")

    movies = fetch_part3_movie_manifest(ver)
    total_count = len(movies)
    total_size = sum(m["size_bytes"] for m in movies)

    print(f"[統計] 成功檢索到第三部主線動畫: 共 {total_count} 部")
    print(f"[體積] 總下載體積預估: {total_size / (1024*1024):.2f} MB ({total_size / (1024*1024*1024):.2f} GB)")
    print(f"[目標目錄] {DEFAULT_OUT_DIR}\n")

    downloaded_count = 0
    skipped_count = 0
    failed_count = 0

    start_time = time.time()

    for idx, item in enumerate(movies, 1):
        ch = item["chapter"]
        fn = item["filename"]
        sz_mb = item["size_bytes"] / (1024 * 1024)
        h = item["pool_hash"]
        url = f"{SONET_CDN}/pool/Movie/{h[:2]}/{h}"

        ch_dir = DEFAULT_OUT_DIR / f"ch{ch:02d}"
        target_path = ch_dir / fn

        print(f"[{idx:3d}/{total_count:3d}] 第 {ch:2d} 章 | {fn:<25} ({sz_mb:>6.2f} MB)... ", end="", flush=True)

        ok, status = download_file(url, target_path, item["size_bytes"])
        if ok:
            if status == "EXISTS":
                print("⚡ [已存在，略過]")
                skipped_count += 1
            else:
                print("✅ [下載完成]")
                downloaded_count += 1
        else:
            print(f"❌ [失敗: {status}]")
            failed_count += 1

    elapsed = time.time() - start_time
    print("\n==================================================")
    print(f"🎉 批次下載流程結束 (耗時: {elapsed:.1f} 秒)")
    print(f"   總計: {total_count} 部 | 新下載: {downloaded_count} 部 | 跳過(已存在): {skipped_count} 部 | 失敗: {failed_count} 部")
    print(f"   存放路徑: {DEFAULT_OUT_DIR}")
    print("==================================================")


if __name__ == "__main__":
    main()
