# -*- coding: utf-8 -*-
import os
import sys
import json
import sqlite3
import urllib.request
import urllib.error
import datetime
import UnityPy

sys.stdout.reconfigure(encoding='utf-8')

# 配置 UnityPy
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

os.makedirs(VERSIONS_DIR, exist_ok=True)

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
    """
    從目前版號開始，暴力遞增探測 So-net 是否有新發布的 TruthVersion。
    """
    print(f"[INFO] 開始探測是否有新版本。目前版本起點: {current_ver}")
    ver_prefix = current_ver[:-4] # "0050"
    ver_num = int(current_ver[-4:]) # 15
    
    latest_found = current_ver
    
    # 探測接下來的 10 個版號
    for i in range(1, 15):
        next_ver = f"{ver_prefix}{ver_num + i:04d}"
        url = f"https://img-pc.so-net.tw/dl/Resources/{next_ver}/Jpn/AssetBundles/Android/manifest/masterdata2_assetmanifest"
        
        req = urllib.request.Request(url, headers=HEADER, method='HEAD')
        try:
            with urllib.request.urlopen(req, timeout=5) as res:
                if res.status == 200:
                    print(f"🔥 探測到新 TruthVersion 發布: {next_ver}")
                    latest_found = next_ver
        except urllib.error.HTTPError as e:
            if e.code == 404:
                break
        except Exception:
            break
            
    return latest_found

def download_database(version, target_dir):
    manifest_url = f"https://img-pc.so-net.tw/dl/Resources/{version}/Jpn/AssetBundles/Android/manifest/masterdata2_assetmanifest"
    db_hash = None
    
    print(f"[INFO] 正在解析 {version} 的資料庫 Hash...")
    try:
        req = urllib.request.Request(manifest_url, headers=HEADER)
        with urllib.request.urlopen(req, timeout=15) as res:
            content = res.read().decode('utf-8', errors='ignore')
            for line in content.splitlines():
                if "masterdata_master.unity3d" in line:
                    db_hash = line.split(',')[2]
                    break
    except Exception as e:
        print(f"❌ 解析 Manifest 失敗: {e}")
        return None
        
    if not db_hash:
        print("❌ 未在 Manifest 中找到資料庫 Hash。")
        return None
        
    db_bundle_url = f"https://img-pc.so-net.tw/dl/pool/AssetBundles/{db_hash[:2]}/{db_hash}"
    temp_bundle_path = os.path.join(target_dir, "masterdata_master.unity3d")
    db_out_path = os.path.join(target_dir, "redive_tw.db")
    
    print(f"[INFO] 正在下載加密資料庫...")
    try:
        req = urllib.request.Request(db_bundle_url, headers=HEADER)
        with urllib.request.urlopen(req, timeout=30) as response:
            with open(temp_bundle_path, 'wb') as out_file:
                out_file.write(response.read())
                
        print(f"[INFO] 正在使用 UnityPy 解密還原資料庫...")
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
                        with open(db_out_path, 'wb') as out_f:
                            out_f.write(db_data)
                        extracted = True
                        break
                    
        if os.path.exists(temp_bundle_path):
            os.remove(temp_bundle_path)
            
        if extracted:
            print(f"✅ 資料庫下載並解密成功: {db_out_path}")
            return db_out_path
    except Exception as e:
        print(f"❌ 下載資料庫失敗: {e}")
        
    return None

def find_new_characters(new_db, old_db):
    """
    比對新舊資料庫，找出新增的 unit_id。
    """
    t_new = None
    uid_col = None
    
    # 1. 以 105801 (貪吃佩可本尊 ID) 為特徵定位角色 ID 表與混淆列
    conn = sqlite3.connect(new_db)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'v1_%';")
    tables = [r[0] for r in cur.fetchall()]
    
    for t in tables:
        try:
            cur.execute(f"PRAGMA table_info({t});")
            cols = [c[1] for c in cur.fetchall()]
            for col in cols:
                cur.execute(f'SELECT count(*) FROM "{t}" WHERE "{col}" = 105801;')
                if cur.fetchone()[0] > 0:
                    # 進一步驗證該表是否大於 100 行，且該欄位主要是角色 ID
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
        print("❌ 無法定位角色資料表，跳過新角色分析。")
        return []
        
    print(f"🎯 成功定位角色資料表: {t_new} (列: {uid_col})")
        
    # 2. 獲取新舊資料庫的所有角色 ID
    new_ids = set()
    conn = sqlite3.connect(new_db)
    cur = conn.cursor()
    try:
        cur.execute(f'SELECT DISTINCT "{uid_col}" FROM "{t_new}" WHERE "{uid_col}" >= 100000 AND "{uid_col}" < 200000;')
        new_ids = {r[0] for r in cur.fetchall()}
    except Exception as e:
        print(f"讀取新資料庫角色 ID 失敗: {e}")
    conn.close()
    
    old_ids = set()
    if old_db and os.path.exists(old_db):
        conn = sqlite3.connect(old_db)
        cur = conn.cursor()
        try:
            cur.execute(f'SELECT DISTINCT "{uid_col}" FROM "{t_new}" WHERE "{uid_col}" >= 100000 AND "{uid_col}" < 200000;')
            old_ids = {r[0] for r in cur.fetchall()}
        except Exception as e:
            print(f"讀取舊資料庫角色 ID 失敗: {e}")
        conn.close()
        
    added_ids = sorted(list(new_ids - old_ids))
    added = []
    
    # 3. 獲取新增角色的名字 (關聯查詢或本地譯名 fallback)
    # 本地已知的重要新角色譯名對照
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
            # 嘗試在資料庫其他含有該 ID 和文字名字的表中尋找
            for t in tables:
                try:
                    cur.execute(f"PRAGMA table_info({t});")
                    cols = [c[1] for c in cur.fetchall()]
                    if len(cols) >= 3:
                        # 尋找是否有一列是這個 ID，且另一列是字串名字
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
    """
    增量下載特定新角色的卡面 WebP、Spine 骨架、以及重要語音。
    """
    print(f"\n[INFO] 開始為新角色『{chara_name}』(ID: {chara_id}) 下載 CDN 素材...")
    os.makedirs(target_dir, exist_ok=True)
    
    u1 = chara_id
    u3 = chara_id + 30  # 3星的 ID
    
    # 1. 下載卡面與頭像
    assets = {
        f"unit_icon_{u1}.webp": f"https://img-pc.so-net.tw/dl/Resources/{version}/Jpn/Unit/Icon/unit_icon_{u1}.webp",
        f"unit_icon_{u3}.webp": f"https://img-pc.so-net.tw/dl/Resources/{version}/Jpn/Unit/Icon/unit_icon_{u3}.webp",
        f"card_full_{u3}.webp": f"https://img-pc.so-net.tw/dl/Resources/{version}/Jpn/Card/Full/card_full_{u3}.webp",
    }
    
    # 2. 下載 Spine 戰鬥骨架
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
            
    print(f"  - 成功下載 {len(downloaded_files)} 個素材檔案。")
    return downloaded_files

def update_markdown_log(version, date_str, added_charas, downloaded_map):
    """
    將本次更新日誌前置追加（Prepend）到 update_log.md 中。
    """
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
    
    # 讀取現有日誌內容
    existing_content = ""
    if os.path.exists(LOG_MD_FILE):
        try:
            with open(LOG_MD_FILE, "r", encoding="utf-8") as f:
                existing_content = f.read()
                if "# So-net CDN 更新日誌\n\n" in existing_content:
                    existing_content = existing_content.replace("# So-net CDN 更新日誌\n\n", "")
        except:
            pass
            
    # 前置追加
    with open(LOG_MD_FILE, "w", encoding="utf-8") as f:
        f.write("# So-net CDN 更新日誌\n\n" + log_content + existing_content)
        
    print(f"✅ 更新日誌已寫入: {LOG_MD_FILE}")

def main():
    force_run = "--force" in sys.argv
    history = load_history()
    last_ver = history.get("last_version", "00500015")
    
    # 1. 探測新版號
    new_ver = probe_new_version(last_ver)
    
    if new_ver == last_ver and not force_run:
        print("[SUCCESS] 目前已是最新版本，且未指定 --force，程式結束。")
        return
        
    # 2. 準備建立版本目錄
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    version_dir_name = f"{date_str}_{new_ver}"
    target_dir = os.path.join(VERSIONS_DIR, version_dir_name)
    os.makedirs(target_dir, exist_ok=True)
    
    print(f"\n[STEP 1] 正在為版本 {new_ver} 建立目錄: {target_dir}")
    
    # 3. 下載最新資料庫
    new_db_path = download_database(new_ver, target_dir)
    if not new_db_path:
        print("❌ 無法獲取新版本資料庫，終止更新流程。")
        return
        
    # 4. 尋找前一個版本的資料庫路徑進行比對
    old_db_path = None
    if history.get("processed_versions"):
        prev_ver = history["processed_versions"][-1]
        for d in os.listdir(VERSIONS_DIR):
            if d.endswith(prev_ver) and os.path.isdir(os.path.join(VERSIONS_DIR, d)):
                db_candidate = os.path.join(VERSIONS_DIR, d, "redive_tw.db")
                if os.path.exists(db_candidate):
                    old_db_path = db_candidate
                    break
                    
    # 5. 分析新增角色
    added_charas = find_new_characters(new_db_path, old_db_path)
    print(f"\n[STEP 2] 新舊資料庫角色比對結果: 發現 {len(added_charas)} 個新角色")
    for uid, name in added_charas:
        print(f"  - 新增角色 ID: {uid} | 名稱: {name}")
        
    # 6. 增量下載新角色素材
    downloaded_map = {}
    for uid, name in added_charas:
        files = download_assets_for_chara(new_ver, uid, name, target_dir)
        downloaded_map[uid] = files
        
    # 7. 更新 Markdown 日誌
    update_markdown_log(new_ver, date_str, added_charas, downloaded_map)
    
    # 8. 更新歷史紀錄
    if new_ver not in history["processed_versions"]:
        history["processed_versions"].append(new_ver)
    history["last_version"] = new_ver
    save_history(history)
    
    print("\n🎉 So-net CDN 自動增量下載與版本比對更新成功完成！")

if __name__ == "__main__":
    main()
