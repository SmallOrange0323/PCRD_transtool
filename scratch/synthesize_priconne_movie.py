import os
import sys
import sqlite3
import hashlib
import urllib.request
import urllib.error
import subprocess

# 解決 Windows cp950 編碼不支援 emoji 的問題
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# 1. 自動安裝/檢測依賴函式庫
def bootstrap_dependencies():
    # 檢查時使用正常的模組引入名稱
    required_libs = [("PyCriCodecsEx", "PyCriCodecsEx"), ("requests", "requests"), ("imageio-ffmpeg", "imageio_ffmpeg"), ("ffmpeg-python", "ffmpeg")]
    missing_libs = []
    for pip_name, import_name in required_libs:
        try:
            __import__(import_name)
        except ImportError:
            # 如果是 PyCriCodecsEx，我們安裝 PyCriCodecsEx[usm]
            missing_libs.append("PyCriCodecsEx[usm]" if pip_name == "PyCriCodecsEx" else pip_name)
            
    if missing_libs:
        print(f"正在自動安裝缺失的 Python 依賴庫: {missing_libs}...")
        try:
            # 去除重複
            missing_libs = list(set(missing_libs))
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_libs)
            print("依賴庫安裝成功！")
        except Exception as e:
            print(f"自動安裝依賴庫失敗，請手動執行: pip install {' '.join(missing_libs)}")
            print(f"錯誤訊息: {e}")
            sys.exit(1)

bootstrap_dependencies()

import requests
import imageio_ffmpeg
from PyCriCodecsEx.usm import USM

# 2. 常量配置
USER_PROFILE = os.environ.get("USERPROFILE")
GAME_DIR = os.path.join(USER_PROFILE, "AppData", "LocalLow", "Cygames", "PrincessConnectReDive")
MANIFEST_PATH = os.path.join(GAME_DIR, "manifest.db")
M_DIR = os.path.join(GAME_DIR, "m")

OUTPUT_DIR = "scratch/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

TEMP_DIR = "scratch/temp_demux"
os.makedirs(TEMP_DIR, exist_ok=True)

GITHUB_SUBTITLE_RAW_URL = "https://raw.githubusercontent.com/KiruyaMomochi/RediveData/master/subtitle/movie_{movie_id}.vtt"

def get_movie_hash_path(movie_id):
    """從 manifest.db 查詢影片的 SHA-1 快取檔名"""
    if not os.path.exists(MANIFEST_PATH):
        print(f"錯誤: 找不到日服的 manifest.db 檔案 (路徑: {MANIFEST_PATH})")
        return None
        
    temp_db_path = "scratch/manifest_movie_temp.db"
    import shutil
    shutil.copyfile(MANIFEST_PATH, temp_db_path)
    
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    
    # 更加通用的匹配規則，支援 story_、character_、cutin_、arcade_ 等所有影片 ID
    movie_pattern = f"%{movie_id}%.usm"
    cursor.execute("SELECT k, v FROM t WHERE k LIKE ? AND k LIKE 'm/%'", (movie_pattern,))
    row = cursor.fetchone()
    
    conn.close()
    try:
        os.remove(temp_db_path)
    except Exception:
        pass
        
    if not row:
        print(f"⚠️ 在 manifest.db 中找不到 movie_id: {movie_id} 的影片記錄")
        return None
        
    k, v = row
    base_name = os.path.basename(k)
    sha1_filename = hashlib.sha1(base_name.encode('utf-8')).hexdigest()
    full_path = os.path.join(M_DIR, sha1_filename)
    
    print(f"🎬 尋找到影片資源: {k}")
    print(f"💾 本地快取哈希檔名: {sha1_filename}")
    return full_path

def download_taiwan_subtitle(movie_id):
    """自 GitHub / jsDelivr 下載台版繁中 .vtt 字幕"""
    vtt_path = os.path.join(TEMP_DIR, f"movie_{movie_id}.vtt")
    
    # 優先使用 jsDelivr CDN，速度極快且穩定，失敗時再 fallback 到 GitHub Raw
    urls = [
        f"https://cdn.jsdelivr.net/gh/KiruyaMomochi/RediveData@master/subtitle/movie_{movie_id}.vtt",
        f"https://raw.githubusercontent.com/KiruyaMomochi/RediveData/master/subtitle/movie_{movie_id}.vtt"
    ]
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    for url in urls:
        print(f"🌐 正在嘗試下載繁中字幕 (來源: {url})...")
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as response:
                with open(vtt_path, 'wb') as out_file:
                    out_file.write(response.read())
            print(f"✅ 字幕下載成功！")
            return vtt_path
        except Exception as e:
            # 判斷是否為 404
            if isinstance(e, urllib.error.HTTPError) and e.code == 404:
                print(f"ℹ️ 倉庫中未收錄此影片的繁中字幕 (HTTP 404)")
                return None
            print(f"⚠️ 嘗試此來源下載失敗: {e}")
            
    print(f"❌ 所有來源下載台版字幕均失敗。")
    return None

def synthesize_movie(movie_id, hardcode_sub=False):
    # 1. 尋找影片快取
    usm_filepath = get_movie_hash_path(movie_id)
    if not usm_filepath or not os.path.exists(usm_filepath):
        print(f"❌ 錯誤: 本地影片快取不存在。請確認您是否已在日版 DMM 下載了此章節的資源。")
        return
        
    # 2. 下載字幕
    vtt_subtitle_path = download_taiwan_subtitle(movie_id)
    
    # 3. 解析 USM 影片與音軌
    print(f"📦 正在使用 PyCriCodecs 解碼與分離 USM 影片流...")
    try:
        # 將快取檔案複製到臨時目錄並重新命名為 .usm 方便 PyCriCodecs 解析
        temp_usm = os.path.join(TEMP_DIR, f"temp_{movie_id}.usm")
        import shutil
        shutil.copyfile(usm_filepath, temp_usm)
        
        # 進行分離 (Demux)
        usm_obj = USM(temp_usm)
        usm_obj._demux()
        
        video_file = os.path.join(TEMP_DIR, f"video_{movie_id}.h264")
        audio_files = []
        
        video_data = None
        audio_datas = {}
        
        for k_key, v_bytes in usm_obj.output.items():
            if "SFV" in k_key:
                video_data = v_bytes
            elif "SFA" in k_key:
                import re
                idx_match = re.search(r'\d+', k_key)
                idx = idx_match.group(0) if idx_match else str(len(audio_datas))
                audio_datas[idx] = v_bytes
                
        if video_data:
            with open(video_file, "wb") as f_out:
                f_out.write(video_data)
            print(f"📹 成功分離視訊軌: {os.path.basename(video_file)}")
        else:
            video_file = None
            print("❌ 錯誤: 解包後未找到有效的視訊軌資料。")
            return
            
        for idx, audio_data in audio_datas.items():
            a_file = os.path.join(TEMP_DIR, f"audio_{movie_id}_{idx}.hca")
            with open(a_file, "wb") as f_out:
                f_out.write(audio_data)
            audio_files.append(a_file)
            print(f"🎵 成功分離音訊軌 {idx}: {os.path.basename(a_file)}")
            
        if not audio_files:
            print("⚠️ 未找到音訊軌檔案 (此影片可能為無聲動畫)。")
            
    except Exception as e:
        print(f"❌ 解碼 USM 失敗: {e}")
        return

    # 4. 調用 FFmpeg 合成
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    output_mp4 = os.path.join(OUTPUT_DIR, f"movie_{movie_id}_subtitled.mp4")
    
    print(f"⚙️ 正在調用 FFmpeg 進行視音訊與字幕合成...")
    
    # 建構 FFmpeg 命令
    cmd = [ffmpeg_exe, "-y"]
    
    # 輸入 0：視訊軌
    cmd += ["-i", video_file]
    
    # 輸入 1~N：音訊軌
    for a_file in audio_files:
        cmd += ["-i", a_file]
        
    # 輸入 N+1 (如果是軟字幕)：字幕軌
    if vtt_subtitle_path and not hardcode_sub:
        cmd += ["-i", vtt_subtitle_path]
        
    # 影像編碼與硬字幕處理
    if vtt_subtitle_path and hardcode_sub:
        # 燒錄硬字幕需要重新編碼影片軌
        escaped_vtt = vtt_subtitle_path.replace("\\", "/").replace(":", "\\:")
        cmd += ["-vf", f"subtitles='{escaped_vtt}'", "-c:v", "libx264", "-preset", "fast", "-crf", "20"]
    else:
        # 軟字幕或無字幕時，視訊採用無損 copy
        cmd += ["-c:v", "copy"]
        
    # 音訊編碼與多音軌混音處理
    if len(audio_files) > 1:
        # 使用 filter_complex amix 進行混音
        filter_inputs = "".join(f"[{i+1}:a]" for i in range(len(audio_files)))
        filter_complex_str = f"{filter_inputs}amix=inputs={len(audio_files)}:duration=longest[a]"
        cmd += ["-filter_complex", filter_complex_str, "-map", "0:v", "-map", "[a]"]
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    elif len(audio_files) == 1:
        # 只有單音軌，直接 map 視訊與該音軌
        cmd += ["-map", "0:v", "-map", "1:a"]
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    else:
        # 無音訊軌，僅 map 視訊
        cmd += ["-map", "0:v"]
        
    # 軟字幕封裝處理與對應的 map
    if vtt_subtitle_path and not hardcode_sub:
        # 軟字幕的輸入索引為：1 (視訊) + len(audio_files) (音訊數)
        sub_input_idx = 1 + len(audio_files)
        cmd += ["-map", f"{sub_input_idx}:s", "-c:s", "mov_text", "-metadata:s:s:0", "language=chi", "-metadata:s:s:0", "title=繁體中文"]
        
    cmd.append(output_mp4)
    
    try:
        # 執行命令，隱藏一些冗長的 banner 資訊
        print(f"🚀 開始合成指令: {' '.join(cmd)}")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if result.returncode == 0:
            print(f"\n🎉 恭喜！影片合成成功！")
            print(f"💾 輸出檔案路徑: {os.path.abspath(output_mp4)}")
            print(f"💡 溫馨提示: " + ("此影片已將繁中字幕燒錄進畫面中。" if hardcode_sub else "此影片為軟字幕封裝，推薦使用 PotPlayer 或者是 VLC 播放，並手動啟用字幕軌。"))
        else:
            print(f"❌ FFmpeg 合成失敗，錯誤代碼: {result.returncode}")
            print(f"錯誤日誌:\n{result.stderr}")
    except Exception as e:
        print(f"❌ 執行合成命令失敗: {e}")
    finally:
        # 清理臨時資料夾
        cleanup_temp()

def cleanup_temp():
    """清理解包產生的臨時檔案"""
    print("🧹 正在清理臨時快取...")
    try:
        for f in os.listdir(TEMP_DIR):
            os.remove(os.path.join(TEMP_DIR, f))
        os.rmdir(TEMP_DIR)
    except Exception:
        pass

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="公主連結高清 DMM 影片與台版字幕合成工具 (預設直接燒錄硬字幕)")
    parser.add_argument("--movie_id", required=True, type=str, help="動畫電影 ID，例如 200100101")
    parser.add_argument("--softcode", action="store_true", help="啟用軟字幕快速封裝 (僅做音視頻封裝與外掛字幕軌，只需2秒)")
    
    args = parser.parse_args()
    # 預設為硬字幕燒錄 (hardcode = not softcode)
    synthesize_movie(args.movie_id, not args.softcode)
