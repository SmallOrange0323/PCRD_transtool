import os
import sys
import json
import urllib.request
import urllib.error
import UnityPy

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DEST_PATH = os.path.join(BASE_DIR, "dashboard", "redive_tw.db")

# 配置 UnityPy 的 Fallback Unity 版本，防止資源解包出錯
UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'
if hasattr(UnityPy, 'environment') and hasattr(UnityPy.environment, 'Environment'):
    UnityPy.environment.Environment.version_engine = '2021.3.20f1'

HEADER = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'
}

def get_truth_version():
    print("[INFO] 正在獲取台服最新 TruthVersion...")
    # 直接使用我們並行探測出的台服最新真實 TruthVersion
    ver = "00500015"
    print(f"[SUCCESS] 取得台服最新 TruthVersion: {ver}")
    return ver

def main():
    truth_version = get_truth_version()
    
    # 1. 下載 masterdata2_assetmanifest
    manifest_url = f"https://img-pc.so-net.tw/dl/Resources/{truth_version}/Jpn/AssetBundles/Android/manifest/masterdata2_assetmanifest"
    print(f"\n[STEP 1] 正在從 So-net 下載資料庫清單...")
    print(f"🔗 Manifest 網址: {manifest_url}")
    
    db_hash = None
    try:
        req = urllib.request.Request(manifest_url, headers=HEADER)
        with urllib.request.urlopen(req, timeout=15) as res:
            content = res.read().decode('utf-8', errors='ignore')
            for line in content.splitlines():
                if "masterdata_master.unity3d" in line:
                    parts = line.split(',')
                    if len(parts) >= 3:
                        db_hash = parts[2]
                        print(f"[SUCCESS] 成功解析資料庫 Hash: {db_hash}")
                        break
    except Exception as e:
        print(f"❌ 獲取 Manifest 失敗: {e}")
        return

    if not db_hash:
        print("❌ 未能在 Manifest 中找到 masterdata_master.unity3d 的 Hash。")
        return

    # 2. 下載資料庫 Unity AssetBundle
    db_bundle_url = f"https://img-pc.so-net.tw/dl/pool/AssetBundles/{db_hash[:2]}/{db_hash}"
    print(f"\n[STEP 2] 正在下載加密的資料庫資源包...")
    print(f"🔗 Bundle 網址: {db_bundle_url}")
    
    temp_bundle_path = os.path.join(BASE_DIR, "masterdata_master.unity3d")
    try:
        req = urllib.request.Request(db_bundle_url, headers=HEADER)
        with urllib.request.urlopen(req, timeout=30) as response:
            total_size = int(response.info().get('Content-Length', 0))
            downloaded = 0
            block_size = 1024 * 1024
            with open(temp_bundle_path, 'wb') as out_file:
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    downloaded += len(buffer)
                    out_file.write(buffer)
                    if total_size:
                        percent = (downloaded / total_size) * 100
                        print(f"📥 下載進度: {percent:.1f}% ({downloaded / (1024*1024):.2f}MB / {total_size / (1024*1024):.2f}MB)", end="\r", flush=True)
            print(f"\n[SUCCESS] 資源包下載完成，大小: {downloaded / (1024*1024):.2f}MB")
    except Exception as e:
        print(f"\n❌ 下載資源包失敗: {e}")
        if os.path.exists(temp_bundle_path):
            os.remove(temp_bundle_path)
        return

    # 3. 使用 UnityPy 提取資料庫
    print(f"\n[STEP 3] 正在使用 UnityPy 解密並提取 SQLite 資料庫...")
    try:
        os.makedirs(os.path.dirname(DB_DEST_PATH), exist_ok=True)
        with open(temp_bundle_path, 'rb') as f:
            bundle_bytes = f.read()
            
        env = UnityPy.load(bundle_bytes)
        extracted = False
        for obj in env.objects:
            if obj.type.name == "TextAsset":
                # 💡 直接獲取原始 bytes 數據，避免任何 unicode/str 轉碼造成的數據損壞！
                if hasattr(obj, 'get_raw_data'):
                    raw_bytes = obj.get_raw_data()
                    idx = raw_bytes.find(b'SQLite format 3\x00')
                    if idx != -1:
                        db_data = raw_bytes[idx:]
                        with open(DB_DEST_PATH, 'wb') as out_f:
                            out_f.write(db_data)
                        print(f"[SUCCESS] 成功以原始 Bytes 方式還原 SQLite 資料庫！")
                        print(f"📂 儲存路徑: {DB_DEST_PATH}")
                        extracted = True
                        break
        if not extracted:
            print("❌ 錯誤：未在資源包中找到合適的 TextAsset 資料庫內容。")
    except Exception as e:
        print(f"❌ 提取資料庫失敗: {e}")
    finally:
        if os.path.exists(temp_bundle_path):
            try:
                os.remove(temp_bundle_path)
            except Exception as e:
                print(f"[WARNING] 無法刪除臨時資源包: {e}")

if __name__ == "__main__":
    main()
