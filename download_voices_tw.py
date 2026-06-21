import os
import sys
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEADER = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'
}

def get_truth_version():
    # 預設使用最新探測到的台服 TruthVersion
    return "00500015"

def download_file(url, dest_path):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    
    # 支援斷點續傳與防重置
    temp_path = dest_path + ".tmp"
    try:
        req = urllib.request.Request(url, headers=HEADER)
        with urllib.request.urlopen(req, timeout=15) as res:
            with open(temp_path, 'wb') as out_f:
                out_f.write(res.read())
        if os.path.exists(dest_path):
            os.remove(dest_path)
        os.rename(temp_path, dest_path)
        return True
    except Exception as e:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        return False

def main():
    truth_ver = get_truth_version()
    manifest_url = f"https://img-pc.so-net.tw/dl/Resources/{truth_ver}/Jpn/Sound/manifest/soundmanifest"
    
    print("="*60)
    print("         公主連結 (PCRD) 台服官方 CDN 語音下載工具")
    print("="*60)
    print(f"[1] 正在下載 soundmanifest 資料...")
    print(f"🔗 Manifest 網址: {manifest_url}")
    
    sound_entries = []
    try:
        req = urllib.request.Request(manifest_url, headers=HEADER)
        with urllib.request.urlopen(req, timeout=15) as res:
            content = res.read().decode('utf-8', errors='ignore')
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split(',')
                if len(parts) >= 5:
                    filename = parts[0]
                    file_hash = parts[2]
                    file_size = int(parts[4])
                    if filename.startswith("v/"):
                        sound_entries.append({
                            'filename': filename,
                            'hash': file_hash,
                            'size': file_size
                        })
        print(f"[SUCCESS] 成功讀取到 {len(sound_entries)} 個語音庫資源。")
    except Exception as e:
        print(f"❌ 獲取 Manifest 失敗: {e}")
        return

    # 支援命令列參數以利自動化執行
    choice = None
    group_id = None
    if len(sys.argv) > 1:
        if sys.argv[1] == "--all":
            choice = "1"
        elif sys.argv[1] == "--group" and len(sys.argv) > 2:
            choice = "2"
            group_id = sys.argv[2]
    
    if choice is None:
        # 提供使用者下載選項
        print("\n[2] 請選擇下載範圍:")
        print(" 1. 下載所有語音庫 (.acb / .awb) [注意：總大小可能超過 15GB+]")
        print(" 2. 依劇情代號 (Group ID) 下載特定話數 [例如: 1001 (主線第一章), 5031 (特定活動)]")
        
        try:
            choice = input("請輸入選項 (1 或 2): ").strip()
        except KeyboardInterrupt:
            return

    to_download = []
    if choice == "1":
        to_download = sound_entries
    elif choice == "2":
        if group_id is None:
            group_id = input("請輸入劇情 Group ID (例如 1001 或 5031): ").strip()
        if not group_id:
            print("❌ 輸入無效。")
            return
        
        # 匹配檔名中含有 group_id 的項目，例如 vo_1001 或 vo_5031
        to_download = [e for e in sound_entries if f"vo_{group_id}" in e['filename'].lower()]
        if not to_download:
            print(f"⚠️ 在 manifest 中找不到包含 'vo_{group_id}' 的語音檔案。")
            return
        print(f"🔍 找到匹配的語音檔案共 {len(to_download)} 個。")
    else:
        print("❌ 選項錯誤。")
        return

    total_files = len(to_download)
    print(f"\n[3] 開始下載作業，預計下載 {total_files} 個檔案...")
    
    output_dir = os.path.join(BASE_DIR, "downloaded_sounds")
    os.makedirs(output_dir, exist_ok=True)

    success_count = 0
    skip_count = 0
    fail_count = 0

    # 使用多執行緒並行下載以大幅提高效率
    max_workers = 8
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for entry in to_download:
            filename = entry['filename']
            file_hash = entry['hash']
            # 保留原目錄結構，將斜線取代或保留
            local_name = filename.replace("/", "_")
            dest_path = os.path.join(output_dir, local_name)
            
            # 若檔案已存在且大小相符則跳過
            if os.path.exists(dest_path) and os.path.getsize(dest_path) == entry['size']:
                skip_count += 1
                continue
                
            cdn_url = f"https://img-pc.so-net.tw/dl/pool/Sound/{file_hash[:2]}/{file_hash}"
            futures[executor.submit(download_file, cdn_url, dest_path)] = filename

        for future in as_completed(futures):
            filename = futures[future]
            try:
                res = future.result()
                if res:
                    success_count += 1
                    print(f"📥 [成功] 下載: {filename} ({success_count + skip_count}/{total_files})")
                else:
                    fail_count += 1
                    print(f"❌ [失敗] 下載: {filename}")
            except Exception as e:
                fail_count += 1
                print(f"❌ [異常] {filename}: {e}")

    print("\n" + "="*50)
    print(f"🎉 下載任務結束！")
    print(f"📂 儲存資料夾: {output_dir}")
    print(f"✨ 成功: {success_count} 個")
    print(f"⏭️ 跳過: {skip_count} 個 (已存在)")
    print(f"❌ 失敗: {fail_count} 個")
    print("="*50)
    print("\n💡 備註: 下載下來的 .acb/.awb 檔案為 Criware 封包，")
    print("未來可用解密工具提取 HCA/ADX 格式音訊並轉成 m4a 播音。")

if __name__ == "__main__":
    main()
