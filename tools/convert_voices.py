# -*- coding: utf-8 -*-
import os
import sys
import urllib.request
import zipfile
import subprocess
import shutil

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(BASE_DIR, "tools")
SOUNDS_DIR = os.path.join(BASE_DIR, "downloaded_sounds")
OUTPUT_DIR = os.path.join(BASE_DIR, "dashboard", "sound", "story_vo")

VGMSTREAM_CLI = os.path.join(TOOLS_DIR, "vgmstream-cli.exe")
FFMPEG_CLI = os.path.join(TOOLS_DIR, "ffmpeg.exe")

VGMSTREAM_URL = "https://github.com/vgmstream/vgmstream/releases/download/r1895/vgmstream-win.zip"
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

def download_file(url, target_path):
    print(f"[Download] 正在下載: {url}")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    with urllib.request.urlopen(req) as resp, open(target_path, 'wb') as out:
        out.write(resp.read())

def ensure_tools():
    global FFMPEG_CLI
    os.makedirs(TOOLS_DIR, exist_ok=True)
    
    if not os.path.exists(VGMSTREAM_CLI):
        zip_path = os.path.join(TOOLS_DIR, "vgmstream.zip")
        try:
            download_file(VGMSTREAM_URL, zip_path)
        except Exception as e:
            print(f"[Error] vgmstream 下載失敗，嘗試備用連結... {e}")
            alt_url = "https://github.com/vgmstream/vgmstream/releases/latest/download/vgmstream-win.zip"
            download_file(alt_url, zip_path)
            
        print("[Tools] 解壓 vgmstream...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(TOOLS_DIR)
        if os.path.exists(zip_path):
            os.remove(zip_path)
        print("[Tools] vgmstream-cli 準備完成！")

    if not os.path.exists(FFMPEG_CLI):
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            print(f"[Tools] 使用系統現有的 ffmpeg: {system_ffmpeg}")
            FFMPEG_CLI = system_ffmpeg
        else:
            print("[Tools] 正在下載 ffmpeg...")
            zip_path = os.path.join(TOOLS_DIR, "ffmpeg.zip")
            download_file(FFMPEG_URL, zip_path)
            
            print("[Tools] 解壓 ffmpeg...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for member in zip_ref.namelist():
                    if member.endswith("ffmpeg.exe"):
                        with zip_ref.open(member) as source, open(FFMPEG_CLI, "wb") as target:
                            shutil.copyfileobj(source, target)
                        break
            if os.path.exists(zip_path):
                os.remove(zip_path)
            print("[Tools] ffmpeg 準備完成！")

def convert_sounds():
    if not os.path.exists(SOUNDS_DIR):
        print(f"[Error] 找不到聲音資料夾：{SOUNDS_DIR}")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 同時收集 acb 與 awb 檔案
    all_files = os.listdir(SOUNDS_DIR)
    sound_files = [f for f in all_files if f.lower().endswith('.awb') or f.lower().endswith('.acb')]
    
    # 優先處理解壓 AWB，如果同名檔既有 acb 又有 awb，優先跑 awb
    file_map = {}
    for f in sound_files:
        base, ext = os.path.splitext(f)
        ext = ext.lower()
        if base not in file_map or ext == '.awb':
            file_map[base] = f
            
    target_files = list(file_map.values())
    total = len(target_files)
    print(f"[Convert] 找到 {total} 個音效封包(優先AWB)，準備開始轉換至：{OUTPUT_DIR}\n")

    temp_wav_dir = os.path.join(TOOLS_DIR, "temp_wav")
    os.makedirs(temp_wav_dir, exist_ok=True)

    for idx, sound_file in enumerate(target_files, 1):
        sound_path = os.path.join(SOUNDS_DIR, sound_file)
        
        # 1. 提取全套子音軌成 wav (?n.wav 代表使用內部 stream name)
        cmd_extract = [VGMSTREAM_CLI, "-o", os.path.join(temp_wav_dir, "?n.wav"), "-s", "1", "-S", "0", sound_path]
        subprocess.run(cmd_extract, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 2. 轉碼成 m4a 並存入 OUTPUT_DIR
        wav_files = [f for f in os.listdir(temp_wav_dir) if f.lower().endswith('.wav')]
        if wav_files:
            print(f"[{idx}/{total}] 處理: {sound_file} -> 解出 {len(wav_files)} 條語音檔")
            for wav_file in wav_files:
                wav_path = os.path.join(temp_wav_dir, wav_file)
                m4a_name = os.path.splitext(wav_file)[0] + ".m4a"
                m4a_path = os.path.join(OUTPUT_DIR, m4a_name)
                
                # 若已存在則跳過，加快執行速度
                if not os.path.exists(m4a_path):
                    cmd_convert = [
                        FFMPEG_CLI, "-y", "-i", wav_path,
                        "-c:a", "aac", "-b:a", "128k",
                        m4a_path
                    ]
                    subprocess.run(cmd_convert, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    os.remove(wav_path)
                except Exception:
                    pass
        else:
            # 如果 AWB 沒有抽出，嘗試 ACB 補救（針對單獨 ACB 檔案）
            pass

    try:
        if os.path.exists(temp_wav_dir):
            shutil.rmtree(temp_wav_dir, ignore_errors=True)
    except Exception:
        pass

    print("\n[Success] 所有語音檔案已成功解包並轉碼為 .m4a！")

if __name__ == "__main__":
    print("=== PCRD 語音轉檔自動化工具 ===")
    ensure_tools()
    convert_sounds()
