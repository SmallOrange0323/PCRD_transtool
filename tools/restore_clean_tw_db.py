# -*- coding: utf-8 -*-
import os
import sys
import UnityPy
import urllib.request
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')

# UnityPy 設定
UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'
if hasattr(UnityPy, 'environment') and hasattr(UnityPy.environment, 'Environment'):
    UnityPy.environment.Environment.version_engine = '2021.3.20f1'

version = "00500024"
HEADER = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DEST_PATH = os.path.join(BASE_DIR, "dashboard", "redive_tw.db")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

def get_remote_db_hash(ver):
    manifest_url = f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/AssetBundles/Android/manifest/masterdata2_assetmanifest"
    print(f"🔍 正在獲取 manifest: {manifest_url}")
    try:
        req = urllib.request.Request(manifest_url, headers=HEADER)
        with urllib.request.urlopen(req, timeout=10) as res:
            content = res.read().decode('utf-8', errors='ignore')
            for line in content.splitlines():
                if "masterdata_master.unity3d" in line:
                    return line.split(',')[2]
    except Exception as e:
        print(f"[WARN] Failed to get database hash from manifest: {e}")
    return None

db_hash = get_remote_db_hash(version)
if not db_hash:
    print("❌ 無法獲取資料庫 hash。")
    sys.exit(1)

db_bundle_url = f"https://img-pc.so-net.tw/dl/pool/AssetBundles/{db_hash[:2]}/{db_hash}"
temp_bundle_path = os.path.join(TEMP_DIR, "masterdata_master.unity3d")

print(f"📥 正在從 pool 下載資料庫 Bundle: {db_bundle_url}")
try:
    req = urllib.request.Request(db_bundle_url, headers=HEADER)
    with urllib.request.urlopen(req, timeout=30) as response:
        with open(temp_bundle_path, 'wb') as out_file:
            out_file.write(response.read())
            
    print(f"📦 正在使用 UnityPy 解密還原並提取 SQLite 資料庫...")
    with open(temp_bundle_path, 'rb') as f:
        bundle_bytes = f.read()
    env = UnityPy.load(bundle_bytes)
    extracted = False
    for obj in env.objects:
        if obj.type.name == "TextAsset":
            if hasattr(obj, 'get_raw_data'):
                raw_bytes = obj.get_raw_data()
                idx = raw_bytes.find(b'SQLite format 3\x00')
                if idx != -1:
                    db_data = raw_bytes[idx:]
                    with open(DB_DEST_PATH, 'wb') as out_f:
                        out_f.write(db_data)
                    extracted = True
                    break
                
    if os.path.exists(temp_bundle_path):
        os.remove(temp_bundle_path)
        
    if extracted:
        print(f"✅ 資料庫下載並提取成功: {DB_DEST_PATH} (檔案大小: {os.path.getsize(DB_DEST_PATH)} 位元組)")
    else:
        print("❌ 未能在 bundle 中找到 SQLite 標頭。")
except Exception as e:
    print(f"❌ 還原下載失敗: {e}")
