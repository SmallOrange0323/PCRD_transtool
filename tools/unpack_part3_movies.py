# -*- coding: utf-8 -*-
"""
tools/unpack_part3_movies.py
批次將主線第三部 (.usm) 動畫解包並無損封裝為標準 .mp4 影片檔
支援：多音軌混音 (BGM + 語音)、無音軌相容、斷點略過、暫存檔自動清理
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import imageio_ffmpeg
from wannacri.usm import Usm

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MOVIES_DIR = ROOT / "downloads" / "movies" / "part3"


def convert_usm_to_mp4(usm_path, ffmpeg_exe, keep_temp=False):
    """將單一 .usm 解包並合成 .mp4"""
    usm_path = Path(usm_path)
    base_name = usm_path.stem
    target_mp4 = usm_path.parent / f"{base_name}.mp4"

    if target_mp4.exists() and target_mp4.stat().st_size > 0:
        return True, "EXISTS", target_mp4

    temp_dir = usm_path.parent / f"_temp_{base_name}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        usm = Usm.open(str(usm_path))
        videos, audios = usm.demux(str(temp_dir), folder_name="extracted")

        if not videos:
            return False, "NO_VIDEO_STREAM", None

        video_file = videos[0]
        cmd = [
            ffmpeg_exe,
            "-y",
            "-r", "29.97",
            "-i", str(video_file)
        ]

        if not audios:
            # 純靜音動畫
            cmd += ["-c:v", "copy", str(target_mp4)]
        elif len(audios) == 1:
            cmd += [
                "-i", str(audios[0]),
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                str(target_mp4)
            ]
        else:
            # 多音軌混音 (例如 BGM + 配音/SE)
            for a in audios:
                cmd += ["-i", str(a)]
            
            filter_inputs = "".join([f"[{i+1}:a]" for i in range(len(audios))])
            filter_complex = f"{filter_inputs}amix=inputs={len(audios)}:duration=longest[aout]"
            cmd += [
                "-filter_complex", filter_complex,
                "-map", "0:v:0",
                "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                str(target_mp4)
            ]

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            return False, f"FFMPEG_ERR: {res.stderr[-200:]}", None

        return True, "CONVERTED", target_mp4
    except Exception as e:
        return False, f"EXCEPTION: {e}", None
    finally:
        if not keep_temp and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    print("==================================================")
    print("🎬 PCRD 第三部官方動畫批次解包轉檔器 (.usm -> .mp4)")
    print("==================================================")

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    print(f"[FFmpeg] 就緒: {Path(ffmpeg_exe).name}")
    print(f"[來源目錄] {DEFAULT_MOVIES_DIR}")

    usm_files = sorted(list(DEFAULT_MOVIES_DIR.glob("**/*.usm")))
    total_count = len(usm_files)

    if total_count == 0:
        print("❌ 未在目錄中找到任何 .usm 檔案！")
        return

    print(f"[掃描] 找到待解包動畫: 共 {total_count} 部\n")

    converted_count = 0
    skipped_count = 0
    failed_count = 0

    start_time = time.time()

    for idx, usm_path in enumerate(usm_files, 1):
        rel_path = usm_path.relative_to(DEFAULT_MOVIES_DIR)
        print(f"[{idx:3d}/{total_count:3d}] {str(rel_path):<35} ... ", end="", flush=True)

        ok, status, out_file = convert_usm_to_mp4(usm_path, ffmpeg_exe)
        if ok:
            if status == "EXISTS":
                print("⚡ [已存在 MP4，略過]")
                skipped_count += 1
            else:
                sz_mb = out_file.stat().st_size / (1024 * 1024)
                print(f"✅ [成功 ({sz_mb:.1f} MB)]")
                converted_count += 1
        else:
            print(f"❌ [失敗: {status}]")
            failed_count += 1

    elapsed = time.time() - start_time
    print("\n==================================================")
    print(f"🎉 批次解包轉檔流程結束 (耗時: {elapsed:.1f} 秒)")
    print(f"   總計: {total_count} 部 | 新轉換: {converted_count} 部 | 略過: {skipped_count} 部 | 失敗: {failed_count} 部")
    print(f"   完成目錄: {DEFAULT_MOVIES_DIR}")
    print("==================================================")


if __name__ == "__main__":
    main()
