# -*- coding: utf-8 -*-
import os
import sys
import json
import sqlite3
import urllib.request
import urllib.error
import datetime
import shutil
import UnityPy

sys.stdout.reconfigure(encoding='utf-8')

# Configure UnityPy
UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'
if hasattr(UnityPy, 'environment') and hasattr(UnityPy.environment, 'Environment'):
    UnityPy.environment.Environment.version_engine = '2021.3.20f1'

HEADER = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSIONS_DIR = os.path.join(BASE_DIR, "dashboard", "versions")
HISTORY_FILE = os.path.join(VERSIONS_DIR, "version_history.json")
LOG_MD_FILE = os.path.join(VERSIONS_DIR, "update_log.md")
GLOBAL_DB_PATH = os.path.join(BASE_DIR, "dashboard", "redive_tw.db")
STORY_DIR = os.path.join(BASE_DIR, "dashboard", "story")

os.makedirs(VERSIONS_DIR, exist_ok=True)
os.makedirs(STORY_DIR, exist_ok=True)

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"processed_versions": [], "last_version": "00500015"}

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def probe_new_version(current_ver):
    print(f"[INFO] Probing new version. Start from: {current_ver}")
    ver_prefix = current_ver[:-4] # "0050"
    ver_num = int(current_ver[-4:]) # 15
    
    latest_found = current_ver
    
    # probe next 15 version numbers
    for i in range(1, 15):
        next_ver = f"{ver_prefix}{ver_num + i:04d}"
        url = f"https://img-pc.so-net.tw/dl/Resources/{next_ver}/Jpn/AssetBundles/Android/manifest/masterdata2_assetmanifest"
        
        req = urllib.request.Request(url, headers=HEADER, method='HEAD')
        try:
            with urllib.request.urlopen(req, timeout=5) as res:
                if res.status == 200:
                    print(f"🔥 Found new TruthVersion: {next_ver}")
                    latest_found = next_ver
        except urllib.error.HTTPError as e:
            if e.code == 404:
                break
        except Exception:
            break
            
    return latest_found

def get_remote_db_hash(version):
    manifest_url = f"https://img-pc.so-net.tw/dl/Resources/{version}/Jpn/AssetBundles/Android/manifest/masterdata2_assetmanifest"
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

def download_database(version, temp_bundle_dir, db_dest_path, db_hash=None):
    if not db_hash:
        db_hash = get_remote_db_hash(version)
        
    if not db_hash:
        print("❌ Cannot resolve database hash. Exiting.")
        return False
        
    db_bundle_url = f"https://img-pc.so-net.tw/dl/pool/AssetBundles/{db_hash[:2]}/{db_hash}"
    temp_bundle_path = os.path.join(temp_bundle_dir, "masterdata_master.unity3d")
    
    print(f"[INFO] Downloading encrypted database bundle...")
    try:
        req = urllib.request.Request(db_bundle_url, headers=HEADER)
        with urllib.request.urlopen(req, timeout=30) as response:
            with open(temp_bundle_path, 'wb') as out_file:
                out_file.write(response.read())
                
        print(f"[INFO] Decrypting database with UnityPy...")
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
                        os.makedirs(os.path.dirname(db_dest_path), exist_ok=True)
                        with open(db_dest_path, 'wb') as out_f:
                            out_f.write(db_data)
                        extracted = True
                        break
                    
        if os.path.exists(temp_bundle_path):
            os.remove(temp_bundle_path)
            
        if extracted:
            print(f"✅ Database updated successfully: {db_dest_path}")
            return True
    except Exception as e:
        print(f"❌ Failed to download database: {e}")
        
    return False

def find_new_characters(new_db, old_db):
    t_new = None
    uid_col = None
    
    conn = sqlite3.connect(new_db)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'v1_%';")
    tables = [r[0] for r in cur.fetchall()]
    
    for t in tables:
        try:
            cur.execute(f"PRAGMA table_info({t});")
            cols = [c[1] for c in cur.fetchall()]
            for col in cols:
                # 105801 represents the primary ID of Pecorine
                cur.execute(f'SELECT count(*) FROM "{t}" WHERE "{col}" = 105801;')
                if cur.fetchone()[0] > 0:
                    cur.execute(f'SELECT count(*) FROM "{t}" WHERE "{col}" >= 100000 AND "{col}" < 200000;')
                    if cur.fetchone()[0] > 50:
                        t_new = t
                        uid_col = col
                        break
            if t_new:
                break
        except:
            pass
    conn.close()
        
    if not t_new or not uid_col:
        print("❌ Cannot locate character table in database.")
        return []
        
    print(f"🎯 Located character table: {t_new} (column: {uid_col})")
        
    # Get all character IDs
    new_ids = set()
    conn = sqlite3.connect(new_db)
    cur = conn.cursor()
    try:
        cur.execute(f'SELECT DISTINCT "{uid_col}" FROM "{t_new}" WHERE "{uid_col}" >= 100000 AND "{uid_col}" < 200000;')
        new_ids = {r[0] for r in cur.fetchall()}
    except Exception as e:
        print(f"Failed to read new character IDs: {e}")
    conn.close()
    
    old_ids = set()
    if old_db and os.path.exists(old_db):
        conn = sqlite3.connect(old_db)
        cur = conn.cursor()
        try:
            cur.execute(f'SELECT DISTINCT "{uid_col}" FROM "{t_new}" WHERE "{uid_col}" >= 100000 AND "{uid_col}" < 200000;')
            old_ids = {r[0] for r in cur.fetchall()}
        except Exception as e:
            print(f"Failed to read old character IDs: {e}")
        conn.close()
        
    added_ids = sorted(list(new_ids - old_ids))
    added = []
    
    # Mapping table for new characters
    KNOWN_NAMES = {
        138301: "貪吃佩可（阿斯特賴亞）",
        138331: "貪吃佩可（阿斯特賴亞）",
        138001: "薇歐莉特（黃泉鯨命）",
        138101: "萊拉耶爾（完美帕菲）",
        138201: "涅妃＝涅羅（鬼面佛心）",
    }
    
    conn = sqlite3.connect(new_db)
    cur = conn.cursor()
    
    for uid in added_ids:
        name = KNOWN_NAMES.get(uid)
        if not name:
            for t in tables:
                try:
                    cur.execute(f"PRAGMA table_info({t});")
                    cols = [c[1] for c in cur.fetchall()]
                    if len(cols) >= 3:
                        for col in cols:
                            cur.execute(f'SELECT * FROM "{t}" WHERE "{col}" = ? LIMIT 1;', (uid,))
                            row = cur.fetchone()
                            if row:
                                for val in row:
                                    if isinstance(val, str) and len(val) > 1 and not val.startswith("vo_") and not val.startswith("bgm_"):
                                        name = val
                                        break
                            if name: break
                    if name: break
                except:
                    pass
        if not name:
            name = f"未命名角色 ({uid})"
            
        added.append((uid, name))
        
    conn.close()
    return added

def download_assets_for_chara(version, chara_id, chara_name, target_dir):
    print(f"\n[INFO] Start downloading assets for {chara_name} (ID: {chara_id})...")
    os.makedirs(target_dir, exist_ok=True)
    
    u1 = chara_id
    u3 = chara_id + 30
    
    # 1. Download card/icon webp
    assets = {
        f"unit_icon_{u1}.webp": f"https://img-pc.so-net.tw/dl/Resources/{version}/Jpn/Unit/Icon/unit_icon_{u1}.webp",
        f"unit_icon_{u3}.webp": f"https://img-pc.so-net.tw/dl/Resources/{version}/Jpn/Unit/Icon/unit_icon_{u3}.webp",
        f"card_full_{u3}.webp": f"https://img-pc.so-net.tw/dl/Resources/{version}/Jpn/Card/Full/card_full_{u3}.webp",
    }
    
    # 2. Download Spine battle sprites
    for ext in [".atlas", ".png", ".skel"]:
        assets[f"sdbattle_{u1}{ext}"] = f"https://img-pc.so-net.tw/dl/Resources/{version}/Jpn/Spine/SDBattle/sdbattle_{u1}{ext}"
        assets[f"sdhall_{u3}{ext}"] = f"https://img-pc.so-net.tw/dl/Resources/{version}/Jpn/Spine/SDHall/sdhall_{u3}{ext}"
        
    downloaded_files = []
    
    for filename, url in assets.items():
        out_path = os.path.join(target_dir, filename)
        try:
            req = urllib.request.Request(url, headers=HEADER)
            with urllib.request.urlopen(req, timeout=5) as response:
                with open(out_path, "wb") as f:
                    f.write(response.read())
            downloaded_files.append(filename)
        except Exception:
            pass
            
    print(f"  - Downloaded {len(downloaded_files)} files successfully.")
    return downloaded_files

def update_markdown_log(version, date_str, added_charas, downloaded_map):
    log_content = f"""# So-net CDN 更新日誌

## 📅 版本更新：{date_str} (TruthVersion: {version})

### 👥 本次新增角色與實裝狀態：
"""
    if added_charas:
        for uid, name in added_charas:
            log_content += f"- **{name}** (ID: `{uid}`)\n"
            files = downloaded_map.get(uid, [])
            if files:
                log_content += "  - 📥 **本地下載素材**:\n"
                for f in files:
                    log_content += f"    - `{f}`\n"
            else:
                log_content += "  - ❌ CDN 尚未上架該角色的美術或 Spine 資源。\n"
    else:
        log_content += "- 本次更新未在角色表中發現新增角色（可能為純數據、關卡、或活動文本更新）。\n"
        
    log_content += "\n---\n\n"
    
    existing_content = ""
    if os.path.exists(LOG_MD_FILE):
        try:
            with open(LOG_MD_FILE, "r", encoding="utf-8") as f:
                existing_content = f.read()
                if "# So-net CDN 更新日誌\n\n" in existing_content:
                    existing_content = existing_content.replace("# So-net CDN 更新日誌\n\n", "")
        except:
            pass
            
    with open(LOG_MD_FILE, "w", encoding="utf-8") as f:
        f.write("# So-net CDN 更新日誌\n\n" + log_content + existing_content)
        
    print(f"✅ Update log written to: {LOG_MD_FILE}")

def main():
    force_run = "--force" in sys.argv
    history = load_history()
    last_ver = history.get("last_version", "00500015")
    last_db_hash = history.get("last_db_hash", "")
    
    new_ver = probe_new_version(last_ver)
    current_db_hash = get_remote_db_hash(new_ver)
    
    # Check if up-to-date (both version and db hash must match)
    if new_ver == last_ver and current_db_hash == last_db_hash and not force_run:
        print("[SUCCESS] Version and database hash are up-to-date. Exiting.")
        return
        
    if new_ver == last_ver and current_db_hash != last_db_hash:
        print(f"🔥 Silent update detected on version {new_ver}! Hash changed from {last_db_hash[:8]}... to {current_db_hash[:8]}...")
        
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    version_dir_name = f"{date_str}_{new_ver}"
    target_dir = os.path.join(VERSIONS_DIR, version_dir_name)
    os.makedirs(target_dir, exist_ok=True)
    
    print(f"\n[STEP 1] Creating asset bundle directory: {target_dir}")
    
    # Backup old database to compare
    old_db_path = os.path.join(target_dir, "redive_tw_old_temp.db")
    if os.path.exists(GLOBAL_DB_PATH):
        print(f"[INFO] Backing up old database for diff check...")
        shutil.copy(GLOBAL_DB_PATH, old_db_path)
        
    # Download database to global path
    success = download_database(new_ver, target_dir, GLOBAL_DB_PATH, current_db_hash)
    if not success:
        print("❌ Cannot download database. Exiting.")
        if os.path.exists(old_db_path):
            os.remove(old_db_path)
        return
        
    # Diff characters
    added_charas = find_new_characters(GLOBAL_DB_PATH, old_db_path if os.path.exists(old_db_path) else None)
    print(f"\n[STEP 2] Character diff result: Found {len(added_charas)} new characters")
    for uid, name in added_charas:
        print(f"  - New Chara ID: {uid} | Name: {name}")
        
    # Download assets
    downloaded_map = {}
    for uid, name in added_charas:
        files = download_assets_for_chara(new_ver, uid, name, target_dir)
        downloaded_map[uid] = files
        
    # Write log
    update_markdown_log(new_ver, date_str, added_charas, downloaded_map)
    
    # Cleanup temp old database
    if os.path.exists(old_db_path):
        os.remove(old_db_path)
        
    # Update history
    if new_ver not in history["processed_versions"]:
        history["processed_versions"].append(new_ver)
    history["last_version"] = new_ver
    if current_db_hash:
        history["last_db_hash"] = current_db_hash
    save_history(history)
    
    print("\n🎉 So-net CDN Auto-update complete!")

if __name__ == "__main__":
    main()
