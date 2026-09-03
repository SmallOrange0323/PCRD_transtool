# -*- coding: utf-8 -*-
"""
tools/process_hd_subtitled_movies.py
主線第一部、第二部、第三部 PC (DMM) 高畫質動畫 1080p 升頻與遊戲原生風格繁中字幕壓制管線
特色：
1. 視訊源：PC High (DMM) 原生高碼率未過度壓縮串流
2. 影音同步：動態讀取官方原生 24fps 影格率，嚴格杜絕搶拍與脫節
3. 畫面升頻：採用 Lanczos 高階演算法升頻至標準 1920x1080 (Full HD)
4. 字幕渲染：在 1080p 向量畫布上以 ASS 格式繪製 (50pt, 2.8 描邊, 55 邊距, 遊戲 1:1 樣式)
5. 音訊合成：自動將 BGM、SE、配音對白進行三軌/多軌立體聲混音
6. 支援全章節批次處理與跨部支援 (--part 1, --part 2, --part 3)
"""

import argparse
import os
import re
import shutil
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

DEFAULT_OUT_BASE = ROOT / "downloads" / "movies"


def fmt_ass_time(seconds):
    """將秒數轉為 ASS 時間字串 (H:MM:SS.cs，精確到百分之一秒)"""
    centis = int((seconds - int(seconds)) * 100)
    s = int(seconds) % 60
    m = (int(seconds) // 60) % 60
    h = int(seconds) // 3600
    return f"{h}:{m:02d}:{s:02d}.{centis:02d}"


def generate_game_style_ass(records, ass_path):
    """生成 1:1 對齊遊戲實機視覺樣式的 ASS 字幕檔 (1080p 基準，50pt，2.8 描邊)"""
    ass_header = """[Script Info]
Title: PCRD Movie Official Subtitle
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


def get_manifests(ver):
    """獲取 PC High 動畫清單與台版字幕 Bundle 清單"""
    url_pc = f"{SONET_CDN}/Resources/{ver}/Jpn/Movie/PC/High/manifest/movie2manifest"
    url_sub = f"{SONET_CDN}/Resources/{ver}/Jpn/AssetBundles/Android/manifest/storydata2_assetmanifest"

    req_pc = urllib.request.Request(url_pc, headers=WEB_HEADER)
    with urllib.request.urlopen(req_pc, timeout=20) as res:
        data_pc = res.read().decode("utf-8", errors="ignore")

    req_sub = urllib.request.Request(url_sub, headers=WEB_HEADER)
    with urllib.request.urlopen(req_sub, timeout=20) as res:
        data_sub = res.read().decode("utf-8", errors="ignore")

    pc_movies = []
    for line in data_pc.splitlines():
        p = line.strip().split(",")
        if len(p) >= 5 and p[0].startswith("m/t/story_"):
            fn = Path(p[0]).name
            # 解析部數與章節:
            # 第一部: story_20XX (Part 1)
            # 第二部: story_21XX (Part 2)
            # 第三部: story_22XX (Part 3)
            m = re.match(r'story_(\d{2})(\d{2})', fn)
            if m:
                part_tag = m.group(1)
                ch_num = int(m.group(2))
                part_num = None
                if part_tag == "20":
                    part_num = 1
                elif part_tag == "21":
                    part_num = 2
                elif part_tag == "22":
                    part_num = 3

                if part_num is not None:
                    pc_movies.append({
                        "raw_path": p[0],
                        "filename": fn,
                        "part": part_num,
                        "chapter": ch_num,
                        "pool_hash": p[2],
                        "size_bytes": int(p[4])
                    })

    sub_bundles = {}
    for line in data_sub.splitlines():
        p = line.strip().split(",")
        if len(p) >= 3 and "movie" in p[0]:
            sub_bundles[p[0]] = p[2]

    return pc_movies, sub_bundles


def extract_subtitles_from_bundle(bundle_hash, ass_path):
    """從官方 Unity AssetBundle 下載並抽取繁體中文字幕轉存為 ASS"""
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
    """下載 PC High USM，先升頻 1080p 再以 1080p 基準加上對齊遊戲之字幕"""
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
        # 1. 下載 PC High USM
        url_movie = f"{SONET_CDN}/pool/Movie/{item['pool_hash'][:2]}/{item['pool_hash']}"
        req_movie = urllib.request.Request(url_movie, headers=WEB_HEADER)
        with urllib.request.urlopen(req_movie, timeout=30) as res:
            temp_usm.write_bytes(res.read())

        # 2. 檢索並解析字幕 (支援 storydata_movie 與 storydata_tw_movie)
        sub_key1 = f"a/storydata_movie_{base_id}.unity3d"
        sub_key2 = f"a/storydata_tw_movie_{base_id}.unity3d"
        sub_hash = sub_bundles.get(sub_key1) or sub_bundles.get(sub_key2)
        has_sub = False
        sub_count = 0

        if sub_hash:
            sub_count, status = extract_subtitles_from_bundle(sub_hash, temp_ass)
            if status == "OK" and sub_count > 0:
                has_sub = True

        # 3. 解包 USM 並讀取原生精確幀率
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

        # 4. 構建 FFmpeg 指令 (嚴格以原生幀率讀取，先 Lanczos 升頻至 1920x1080，再渲染 ASS 字幕)
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

        # 音訊 Filter (雙軌/三軌全量混音)
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

        msg = f"完成 ({fps_str}fps, {sub_count} 句字幕)" if has_sub else f"完成 ({fps_str}fps, 純配樂/無字幕)"
        return True, msg, target_mp4

    except Exception as e:
        return False, f"異常: {e}", None
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="PCRD PC版高畫質動畫 1080p 升頻與原生字幕壓制工具 (支援第 1、2、3 部)")
    parser.add_argument("--part", type=int, choices=[1, 2, 3], default=1, help="指定主線部數: 1=第一部, 2=第二部, 3=第三部 (預設: 1)")
    parser.add_argument("--chapter", type=int, default=None, help="指定下載與壓制的單一章節 (如 1)")
    parser.add_argument("--force", action="store_true", default=False, help="強制重新壓制 (覆蓋現有檔案)")
    args = parser.parse_args()

    part = args.part
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    ver = _get_sonet_ver()
    print("==================================================")
    print(f"🎬 PCRD 主線第 {part} 部 PC 高畫質 1080p 原生字體壓制管線")
    print("==================================================")
    print(f"[CDN] 台服 TruthVersion: {ver}")
    print("[Manifest] 正在獲取高畫質動畫清單與台版字幕對照表...")

    pc_movies, sub_bundles = get_manifests(ver)

    # 篩選指定部數
    target_movies = [m for m in pc_movies if m["part"] == part]
    if args.chapter is not None:
        target_movies = [m for m in target_movies if m["chapter"] == args.chapter]
        mode_desc = f"第 {part} 部第 {args.chapter} 章"
    else:
        mode_desc = f"第 {part} 部全量"

    total_count = len(target_movies)
    total_raw_sz = sum(m["size_bytes"] for m in target_movies)

    out_base_dir = DEFAULT_OUT_BASE / f"part{part}_hd_subtitled"
    out_base_dir.mkdir(parents=True, exist_ok=True)

    print(f"[目標] {mode_desc} 共檢索到 {total_count} 部動畫")
    print(f"[原始體積] 約 {total_raw_sz / (1024*1024*1024):.2f} GB")
    print(f"[輸出基準] 1920x1080 Lanczos 升頻 + 50PT 遊戲原生 ASS 字幕")
    print(f"[輸出目錄] {out_base_dir}\n")

    start_time = time.time()
    success_count = 0
    skipped_count = 0
    failed_count = 0

    for idx, item in enumerate(target_movies, 1):
        ch = item["chapter"]
        fn = item["filename"]
        sz_mb = item["size_bytes"] / (1024 * 1024)
        out_dir = out_base_dir / f"ch{ch:02d}"
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"[{idx:3d}/{total_count:3d}] 第 {ch:2d} 章 | {fn:<25} ({sz_mb:>6.2f} MB)... ", end="", flush=True)

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
    print(f"🎉 第 {part} 部批次壓制流程結束！(總耗時: {elapsed/60:.1f} 分鐘)")
    print(f"   總計: {total_count} 部 | 成功: {success_count} 部 (含已略過: {skipped_count} 部) | 失敗: {failed_count} 部")
    print(f"   存放路徑: {out_base_dir}")
    print("==================================================")


if __name__ == "__main__":
    main()
