# -*- coding: utf-8 -*-
"""
tools/process_hd_event_movies.py
新版活動劇情 PC (DMM) 高畫質動畫 1080p 升頻與官方繁中字幕壓制管線
支援：
1. 動態自資料庫提取最新活動中文標題，依活動名稱自動建立資料夾歸檔
2. PC High 原生碼流 + 動態 24fps 原生影格率同步
3. 1920x1080 Lanczos 升頻 + 50PT 遊戲原生樣式 ASS 官方繁中字幕
4. BGM、SE、配音對白智慧多軌立體聲混音
5. 斷點續傳略過機制
"""

import argparse
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import imageio_ffmpeg
import UnityPy
UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'
from wannacri.usm import Usm

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.pcrd_fetch import _get_sonet_ver, WEB_HEADER, SONET_CDN

DEFAULT_OUT_BASE = ROOT / "downloads" / "movies" / "events_hd_subtitled"
DB_PATH = ROOT / "dashboard" / "redive_tw.db"


def sanitize_folder_name(name):
    clean = re.sub(r'[\r\n\t]+', ' ', name)
    for ch in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
        clean = clean.replace(ch, '_')
    return clean.strip()


def fmt_ass_time(seconds):
    centis = int((seconds - int(seconds)) * 100)
    s = int(seconds) % 60
    m = (int(seconds) // 60) % 60
    h = int(seconds) // 3600
    return f"{h}:{m:02d}:{s:02d}.{centis:02d}"


def generate_game_style_ass(records, ass_path):
    ass_header = """[Script Info]
Title: PCRD Event Movie Official Subtitle
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft JhengHei UI,50,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0.5,0,1,2.8,0,2,20,20,55,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    dialogue_lines = []
    for r in records:
        t_start = fmt_ass_time(r["startTime"])
        t_end = fmt_ass_time(r["endTime"])
        txt = r["text"].strip().replace("\n", "\\N")
        dialogue_lines.append(f"Dialogue: 0,{t_start},{t_end},Default,,0,0,0,,{txt}")

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_header + "\n".join(dialogue_lines) + "\n")


def get_event_dict(min_gid=5120):
    event_dict = {}
    if not DB_PATH.exists():
        return event_dict

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT story_group_id, title FROM event_story_data WHERE story_group_id >= ? GROUP BY story_group_id ORDER BY story_group_id ASC", (min_gid,))
    for gid, title in c.fetchall():
        event_dict[gid] = sanitize_folder_name(title)
    conn.close()
    return event_dict


def get_manifests(ver, event_dict):
    url_pc = f"{SONET_CDN}/Resources/{ver}/Jpn/Movie/PC/High/manifest/movie2manifest"
    url_sub = f"{SONET_CDN}/Resources/{ver}/Jpn/AssetBundles/Android/manifest/storydata2_assetmanifest"

    req_pc = urllib.request.Request(url_pc, headers=WEB_HEADER)
    with urllib.request.urlopen(req_pc, timeout=20) as res:
        data_pc = res.read().decode("utf-8", errors="ignore")

    req_sub = urllib.request.Request(url_sub, headers=WEB_HEADER)
    with urllib.request.urlopen(req_sub, timeout=20) as res:
        data_sub = res.read().decode("utf-8", errors="ignore")

    event_movies = []
    for line in data_pc.splitlines():
        p = line.strip().split(",")
        if len(p) >= 5 and p[0].startswith("m/t/story_5"):
            fn = Path(p[0]).name
            m = re.match(r'story_(\d{4})', fn)
            if m:
                gid = int(m.group(1))
                if gid in event_dict:
                    event_movies.append({
                        "raw_path": p[0],
                        "filename": fn,
                        "group_id": gid,
                        "event_title": event_dict[gid],
                        "pool_hash": p[2],
                        "size_bytes": int(p[4])
                    })

    sub_bundles = {}
    for line in data_sub.splitlines():
        p = line.strip().split(",")
        if len(p) >= 3 and "movie" in p[0]:
            sub_bundles[p[0]] = p[2]

    return event_movies, sub_bundles


def extract_subtitles_from_bundle(bundle_hash, ass_path):
    url = f"{SONET_CDN}/pool/AssetBundles/{bundle_hash[:2]}/{bundle_hash}"
    req = urllib.request.Request(url, headers=WEB_HEADER)
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            bdata = res.read()
    except Exception as e:
        return 0, f"下載字幕失敗: {e}"

    try:
        bundle = UnityPy.load(bdata)
        records = []
        for obj in bundle.objects:
            if obj.type.name == "MonoBehaviour":
                data = obj.read_typetree()
                records = data.get("recordList", [])
                break

        if not records:
            return 0, "無字幕記錄"

        generate_game_style_ass(records, ass_path)
        return len(records), "OK"
    except Exception as e:
        return 0, f"解析字幕失敗: {e}"


def process_movie(item, sub_bundles, out_dir, ffmpeg_exe, force=False):
    fn = item["filename"]
    base_id = re.search(r'(\d+)', fn).group(1)
    target_mp4 = out_dir / f"{Path(fn).stem}.mp4"

    if not force and target_mp4.exists() and target_mp4.stat().st_size > 500000:
        return True, "EXISTS", target_mp4

    temp_dir = out_dir / f"_temp_{base_id}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_usm = temp_dir / fn
    temp_ass = temp_dir / f"{base_id}.ass"

    try:
        url_movie = f"{SONET_CDN}/pool/Movie/{item['pool_hash'][:2]}/{item['pool_hash']}"
        req_movie = urllib.request.Request(url_movie, headers=WEB_HEADER)
        with urllib.request.urlopen(req_movie, timeout=30) as res:
            temp_usm.write_bytes(res.read())

        sub_key1 = f"a/storydata_movie_{base_id}.unity3d"
        sub_key2 = f"a/storydata_tw_movie_{base_id}.unity3d"
        sub_hash = sub_bundles.get(sub_key1) or sub_bundles.get(sub_key2)
        has_sub = False
        sub_count = 0

        if sub_hash:
            sub_count, status = extract_subtitles_from_bundle(sub_hash, temp_ass)
            if status == "OK" and sub_count > 0:
                has_sub = True

        usm = Usm.open(str(temp_usm))
        v = usm.videos[0]
        vd = v.crid_page._dict
        fn_num = vd.get("framerate_n").val if "framerate_n" in vd else 24
        fd_num = vd.get("framerate_d").val if "framerate_d" in vd else 1
        fps_str = f"{fn_num}/{fd_num}" if fd_num != 0 else "24/1"

        videos, audios = usm.demux(str(temp_dir), folder_name="demux")
        if not videos:
            return False, "無視訊軌", None

        video_raw = videos[0]

        cmd = [
            ffmpeg_exe,
            "-y",
            "-r", fps_str,
            "-i", str(video_raw),
        ]
        for a in audios:
            cmd += ["-i", str(a)]

        filter_complex_parts = []
        if has_sub:
            escaped_ass = str(temp_ass).replace("\\", "/").replace(":", "\\:")
            video_filter = f"[0:v]scale=1920:1080:flags=lanczos,subtitles='{escaped_ass}'[vout]"
        else:
            video_filter = "[0:v]scale=1920:1080:flags=lanczos[vout]"
        filter_complex_parts.append(video_filter)

        if len(audios) > 1:
            filter_inputs = "".join([f"[{i+1}:a]" for i in range(len(audios))])
            filter_complex_parts.append(f"{filter_inputs}amix=inputs={len(audios)}:duration=longest[aout]")
        elif len(audios) == 1:
            filter_complex_parts.append("[1:a]anull[aout]")

        filter_complex_str = ";".join(filter_complex_parts)

        cmd += [
            "-filter_complex", filter_complex_str,
            "-map", "[vout]",
        ]
        if audios:
            cmd += ["-map", "[aout]"]

        cmd += [
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
        ]
        if audios:
            cmd += [
                "-c:a", "aac",
                "-b:a", "256k"
            ]

        cmd.append(str(target_mp4))

        res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
        if res.returncode != 0:
            return False, f"FFmpeg 失敗: {res.stderr[-200:]}", None

        msg = f"完成 ({fps_str}fps, {sub_count} 句字幕)" if has_sub else f"完成 ({fps_str}fps, 純ED歌曲/無字幕)"
        return True, msg, target_mp4

    except Exception as e:
        return False, f"異常: {e}", None
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="PCRD 新版活動劇情 PC 高畫質 1080p 動畫壓制工具")
    parser.add_argument("--min-group-id", type=int, default=5120, help="最低活動群組 ID (預設: 5120，即近兩年最新活動)")
    parser.add_argument("--force", action="store_true", default=False, help="強制重新壓制 (覆蓋現有檔案)")
    args = parser.parse_args()

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    ver = _get_sonet_ver()
    print("==================================================")
    print("🎬 PCRD 新版活動劇情 PC 高畫質 1080p 原生字體壓制管線")
    print("==================================================")
    print(f"[CDN] 台服 TruthVersion: {ver}")
    print(f"[篩選] 活動群組 ID >= {args.min_group_id} (近兩年最新大型活動)")
    print("[Manifest] 正在獲取活動中文名稱、高畫質動畫清單與台版字幕對照表...")

    event_dict = get_event_dict(args.min_group_id)
    event_movies, sub_bundles = get_manifests(ver, event_dict)

    total_count = len(event_movies)
    total_raw_sz = sum(m["size_bytes"] for m in event_movies)

    DEFAULT_OUT_BASE.mkdir(parents=True, exist_ok=True)

    print(f"[目標] 涵蓋 {len(event_dict)} 個最新大型活動，共檢索到 {total_count} 部動畫")
    print(f"[原始體積] 約 {total_raw_sz / (1024*1024*1024):.2f} GB")
    print(f"[輸出基準] 1920x1080 Lanczos 升頻 + 50PT 遊戲原生 ASS 字幕")
    print(f"[輸出目錄] {DEFAULT_OUT_BASE}\n")

    start_time = time.time()
    success_count = 0
    skipped_count = 0
    failed_count = 0

    for idx, item in enumerate(event_movies, 1):
        gid = item["group_id"]
        title = item["event_title"]
        fn = item["filename"]
        sz_mb = item["size_bytes"] / (1024 * 1024)

        folder_name = f"{gid}_{title}"
        out_dir = DEFAULT_OUT_BASE / folder_name
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"[{idx:3d}/{total_count:3d}] [{gid}] {title[:16]:<16} | {fn:<25} ({sz_mb:>6.2f} MB)... ", end="", flush=True)

        ok, status, out_file = process_movie(item, sub_bundles, out_dir, ffmpeg_exe, force=args.force)
        if ok:
            if status == "EXISTS":
                print("⚡ [已存在 1080p，略過]")
                skipped_count += 1
                success_count += 1
            else:
                out_sz_mb = out_file.stat().st_size / (1024 * 1024)
                print(f"✅ [{status} -> 1080p ({out_sz_mb:.1f} MB)]")
                success_count += 1
        else:
            print(f"❌ [失敗: {status}]")
            failed_count += 1

    elapsed = time.time() - start_time
    print("\n==================================================")
    print(f"🎉 新版活動批次壓制流程結束！(總耗時: {elapsed/60:.1f} 分鐘)")
    print(f"   總計: {total_count} 部 | 成功: {success_count} 部 (含已略過: {skipped_count} 部) | 失敗: {failed_count} 部")
    print(f"   存放路徑: {DEFAULT_OUT_BASE}")
    print("==================================================")


if __name__ == "__main__":
    main()
