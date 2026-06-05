import os
import sys
import sqlite3
import hashlib
import urllib.request
import urllib.error
import subprocess

# 解決 Windows cp950 編碼問題
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# 1. 確保依賴已安裝
def bootstrap_dependencies():
    required_libs = [("PyCriCodecsEx", "PyCriCodecsEx"), ("requests", "requests"), ("imageio-ffmpeg", "imageio_ffmpeg"), ("ffmpeg-python", "ffmpeg")]
    missing_libs = []
    for pip_name, import_name in required_libs:
        try:
            __import__(import_name)
        except ImportError:
            missing_libs.append("PyCriCodecsEx[usm]" if pip_name == "PyCriCodecsEx" else pip_name)
            
    if missing_libs:
        print(f"正在自動安裝缺失的依賴: {missing_libs}...")
        try:
            missing_libs = list(set(missing_libs))
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_libs)
        except Exception as e:
            print(f"安裝失敗: {e}")
            sys.exit(1)

bootstrap_dependencies()

import requests
import imageio_ffmpeg
from PyCriCodecsEx.usm import USM

USER_PROFILE = os.environ.get("USERPROFILE")
GAME_DIR = os.path.join(USER_PROFILE, "AppData", "LocalLow", "Cygames", "PrincessConnectReDive")
MANIFEST_PATH = os.path.join(GAME_DIR, "manifest.db")
M_DIR = os.path.join(GAME_DIR, "m")

OUTPUT_DIR = "scratch/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

TEMP_DIR = "scratch/temp_demux"
os.makedirs(TEMP_DIR, exist_ok=True)

GITHUB_SUBTITLE_RAW_URL = "https://raw.githubusercontent.com/KiruyaMomochi/RediveData/master/subtitle/movie_{movie_id}.vtt"

def get_downloaded_story_movies():
    """查詢所有在 manifest.db 中的主線劇情動畫資源 (即使本地無快取也列出以供下載)"""
    if not os.path.exists(MANIFEST_PATH):
        print("錯誤: 找不到 manifest.db")
        return []
        
    temp_db = "scratch/manifest_batch_temp.db"
    import shutil
    shutil.copyfile(MANIFEST_PATH, temp_db)
    
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 嚴格只搜尋第三部主線劇情影片 (ID 格式為 22 開頭的 story，如 story_22xxxxxxx.usm)
    cursor.execute("SELECT k, v FROM t WHERE k LIKE 'm/t/story_22%.usm'")
    rows = cursor.fetchall()
    conn.close()
    
    try:
        os.remove(temp_db)
    except Exception:
        pass
        
    cache_files = set(os.listdir(M_DIR)) if os.path.exists(M_DIR) else set()
    movies = []
    
    for row in rows:
        k = row['k']
        v = row['v']
        base_name = os.path.basename(k)
        sha = hashlib.sha1(base_name.encode('utf-8')).hexdigest()
        movie_id = base_name.replace("story_", "").replace(".usm", "")
        
        movies.append({
            "movie_id": movie_id,
            "key": k,
            "manifest_hash": v,
            "local_path": os.path.join(M_DIR, sha) if sha in cache_files else None
        })
            
    return movies

def download_subtitle(movie_id):
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

def download_usm_from_cdn(manifest_hash, dest_path):
    """自日服官方 CDN 下載 USM 影片"""
    if not manifest_hash:
        return False
    prefix = manifest_hash[:2]
    url = f"https://prd-priconne-redive.akamaized.net/dl/pool/Movie/{prefix}/{manifest_hash}"
    print(f"📥 正在從日服官方 CDN 下載電影檔...")
    print(f"🔗 URL: {url}")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=60) as response:
            with open(dest_path, 'wb') as f:
                f.write(response.read())
        print("✅ 下載成功！")
        return True
    except Exception as e:
        print(f"❌ 下載電影檔失敗: {e}")
        return False

def synthesize_one(movie_data):
    movie_id = movie_data["movie_id"]
    local_path = movie_data["local_path"]
    manifest_hash = movie_data["manifest_hash"]
    
    print(f"\n──────────────────────────────────────────")
    print(f"🎬 正在處理影片: {movie_id} ({os.path.basename(movie_data['key'])})")
    
    # 1. 確保電影檔案存在 (若本地快取無，則從 CDN 下載)
    temp_usm = os.path.join(TEMP_DIR, f"temp_{movie_id}.usm")
    if local_path and os.path.exists(local_path):
        print("💾 找到本地 DMM 快取檔案。")
        import shutil
        shutil.copyfile(local_path, temp_usm)
    else:
        print("🌐 本地快取無此電影，嘗試自官方 CDN 獲取...")
        success = download_usm_from_cdn(manifest_hash, temp_usm)
        if not success:
            print(f"❌ 跳過影片 {movie_id} (無法取得影片來源)")
            return False
            
    # 2. 下載字幕
    vtt_path = download_subtitle(movie_id)
    if vtt_path:
        print("✅ 成功獲取繁中字幕！")
    else:
        print("⚠️ 未找到此影片的繁中字幕，將僅進行原音畫合成。")
        
    video_file = os.path.join(TEMP_DIR, f"video_{movie_id}.h264")
    audio_files = []
    output_mp4 = os.path.join(OUTPUT_DIR, f"movie_{movie_id}_subtitled.mp4")
    
    try:
        usm_obj = USM(temp_usm)
        usm_obj._demux()
        
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
            with open(video_file, "wb") as f:
                f.write(video_data)
        else:
            print("❌ 錯誤: 未提取到視訊軌")
            return False
            
        for idx, audio_data in audio_datas.items():
            a_file = os.path.join(TEMP_DIR, f"audio_{movie_id}_{idx}.hca")
            with open(a_file, "wb") as f:
                f.write(audio_data)
            audio_files.append(a_file)
            
    except Exception as e:
        print(f"❌ 解碼失敗: {e}")
        return False
        
    # 3. FFmpeg 合成
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg_exe, "-y", "-i", video_file]
    for a_file in audio_files:
        cmd += ["-i", a_file]
        
    if vtt_path:
        # 燒錄硬字幕
        escaped_vtt = vtt_path.replace("\\", "/").replace(":", "\\:")
        cmd += ["-vf", f"subtitles='{escaped_vtt}'", "-c:v", "libx264", "-preset", "fast", "-crf", "20"]
    else:
        # 無字幕時直接無損封裝
        cmd += ["-c:v", "copy"]
        
    if len(audio_files) > 1:
        filter_inputs = "".join(f"[{i+1}:a]" for i in range(len(audio_files)))
        filter_complex_str = f"{filter_inputs}amix=inputs={len(audio_files)}:duration=longest[a]"
        cmd += ["-filter_complex", filter_complex_str, "-map", "0:v", "-map", "[a]"]
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    elif len(audio_files) == 1:
        cmd += ["-map", "0:v", "-map", "1:a"]
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-map", "0:v"]
        
    cmd.append(output_mp4)
    
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            print(f"🎉 影片合成成功！檔案：{output_mp4}")
            return True
        else:
            print(f"❌ FFmpeg 失敗: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ 合成出錯: {e}")
        return False
    finally:
        # 清理該影片的臨時檔
        try:
            files_to_remove = [temp_usm, video_file, vtt_path] + audio_files
            for f in files_to_remove:
                if f and os.path.exists(f):
                    os.remove(f)
        except Exception:
            pass

def main():
    print("🔍 正在掃描 manifest.db 以獲取第 3 部所有主線劇情動畫...")
    downloaded = get_downloaded_story_movies()
    
    if not downloaded:
        print("\n⚠️ manifest.db 中目前沒有找到任何第 3 部主線劇情動畫 (story_22*.usm)。")
        return
        
    print(f"\n📂 找到 {len(downloaded)} 個第 3 部主線劇情影片，開始批次合成...")
    
    success = 0
    for movie in downloaded:
        if synthesize_one(movie):
            success += 1
            
    print(f"\n==========================================")
    print(f"🏁 批次處理完畢！成功合成 {success}/{len(downloaded)} 部劇情影片！")
    print(f"📂 輸出檔案皆已保存在: {os.path.abspath(OUTPUT_DIR)}")

if __name__ == "__main__":
    main()
