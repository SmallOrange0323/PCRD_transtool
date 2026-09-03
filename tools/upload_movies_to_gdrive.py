# -*- coding: utf-8 -*-
"""
tools/upload_movies_to_gdrive.py
使用本機 rclone 將 1080p 帶字幕動畫批次同步至 Google Drive，
並自動提取 Google Drive File ID 輸出為 dashboard/data/movie_links.json。
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
RCLONE_EXE = ROOT / "tools" / "bin" / "rclone.exe"
MOVIES_DIR = ROOT / "downloads" / "movies"
OUTPUT_JSON = ROOT / "dashboard" / "data" / "movie_links.json"
REMOTE_NAME = "gdrive"
REMOTE_FOLDER = "PCRD_Movies"


def check_rclone():
    if not RCLONE_EXE.exists():
        print(f"❌ 找不到 rclone.exe: {RCLONE_EXE}")
        return False
    try:
        res = subprocess.run([str(RCLONE_EXE), "listremotes"], capture_output=True, text=True)
        remotes = [r.strip().replace(":", "") for r in res.stdout.splitlines() if r.strip()]
        if REMOTE_NAME not in remotes:
            print(f"❌ 在 rclone 配置中找不到 [{REMOTE_NAME}]。現有 remotes: {remotes}")
            return False
        return True
    except Exception as e:
        print(f"❌ 檢查 rclone 失敗: {e}")
        return False


def upload_movies():
    print("==================================================")
    print("🚀 PCRD 動畫 Google Drive 自動化同步與 ID 導出管線")
    print("==================================================")
    print(f"[本地目錄] {MOVIES_DIR}")
    print(f"[雲端目標] {REMOTE_NAME}:{REMOTE_FOLDER}/")

    target_remote = f"{REMOTE_NAME}:{REMOTE_FOLDER}/"

    cmd = [
        str(RCLONE_EXE),
        "copy",
        str(MOVIES_DIR),
        target_remote,
        "--progress",
        "--stats-one-line",
        "--transfers", "4",
        "--checkers", "8",
        "--fast-list"
    ]

    print("\n[1/2] 正在透過 rclone 增量同步檔案至 Google Drive...")
    print("提示：已存在之檔案會自動比對雜湊略過，絕不重複上傳。\n")

    proc = subprocess.Popen(cmd)
    proc.wait()

    if proc.returncode != 0:
        print(f"❌ rclone 同步失敗，退出碼: {proc.returncode}")
        return False

    print("\n✅ 檔案同步完畢！")
    return True


def export_file_ids():
    print("\n[2/2] 正在檢索雲端硬碟檔案清單並提取 Google Drive File ID...")
    target_remote = f"{REMOTE_NAME}:{REMOTE_FOLDER}"

    cmd = [
        str(RCLONE_EXE),
        "lsjson",
        target_remote,
        "--recursive",
        "--files-only"
    ]

    res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
    if res.returncode != 0:
        print(f"❌ 讀取雲端清單失敗: {res.stderr}")
        return False

    try:
        items = json.loads(res.stdout)
    except Exception as e:
        print(f"❌ 解析 rclone lsjson 輸出失敗: {e}")
        return False

    movie_links = {}
    valid_count = 0

    for item in items:
        name = item.get("Name", "")
        file_id = item.get("ID", "")
        if name.endswith(".mp4") and file_id:
            stem = Path(name).stem
            movie_links[stem] = file_id
            m = re.search(r'(\d+)', stem)
            if m:
                clean_id = m.group(1)
                movie_links[clean_id] = file_id
            valid_count += 1

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(movie_links, f, ensure_ascii=False, indent=2)

    print(f"🎉 成功導出 {valid_count} 部動畫之 Google Drive 連結！")
    print(f"[映射表存檔] {OUTPUT_JSON} (大小: {OUTPUT_JSON.stat().st_size / 1024:.1f} KB)")
    return True


def main():
    if not check_rclone():
        sys.exit(1)

    if "--export-only" in sys.argv:
        export_file_ids()
        return

    if upload_movies():
        export_file_ids()


if __name__ == "__main__":
    main()
