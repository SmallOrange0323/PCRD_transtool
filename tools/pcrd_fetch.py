# -*- coding: utf-8 -*-
"""
pcrd_fetch.py — PCRD 台版資料抓取 CLI 工具
用途: 從 So-net CDN 與 wthee 鏡像站下載新角色劇情、素材、資料庫

子命令:
  update-db       更新台版明文資料庫 (wthee)
  fetch-stories   下載並解密角色個人劇情 JSON
  fetch-assets    下載立繪與頭像素材
  report          產出驗證報告 Markdown
  scan-cdn        手動探測 So-net CDN 是否有新版本或預上架素材
"""

import argparse
import base64
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
from struct import unpack

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# ─────────────────────────── 常數 ───────────────────────────

SONET_CDN = "https://img-pc.so-net.tw/dl"
WTHEE_DB_URL = "https://wthee.xyz/db/redive_tw.db"

SONET_HEADER = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'
}
WEB_HEADER = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD_DIR = os.path.join(BASE_DIR, "dashboard")
STORY_DIR = os.path.join(DASHBOARD_DIR, "story")
ICON_DIR = os.path.join(DASHBOARD_DIR, "icon", "unit")
CARD_DIR = os.path.join(DASHBOARD_DIR, "card", "full")
DB_PATH = os.path.join(DASHBOARD_DIR, "redive_tw.db")
TRACKED_CHARS_PATH = os.path.join(DASHBOARD_DIR, "data", "tracked_characters.json")

# ─────────────────────────── 工具函式 ───────────────────────────

def _http_get(url, headers, timeout=15, retries=3):
    """帶重試與指數退避的 HTTP GET，返回 bytes。"""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as res:
                return res.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise  # 404 直接拋出，不重試
            if attempt < retries - 1:
                wait = 2 ** attempt
                print(f"  ⚠️ HTTP {e.code}，{wait}s 後重試 (第 {attempt + 1}/{retries} 次)...", file=sys.stderr)
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            if attempt < retries - 1:
                wait = 2 ** attempt
                print(f"  ⚠️ 請求失敗 ({e})，{wait}s 後重試...", file=sys.stderr)
                time.sleep(wait)
            else:
                raise


def _load_tracked_chars():
    """讀取已追蹤角色設定檔。"""
    if os.path.exists(TRACKED_CHARS_PATH):
        with open(TRACKED_CHARS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"characters": []}


def _save_tracked_chars(data):
    """儲存已追蹤角色設定檔。"""
    os.makedirs(os.path.dirname(TRACKED_CHARS_PATH), exist_ok=True)
    with open(TRACKED_CHARS_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _lookup_db_names(unit_ids=(), story_ids=()):
    """
    從 redive_tw.db 查詢名稱，回傳：
      unit_names  : {unit_id: '貪吃佩可（阿斯特萊亞）'}
      story_titles: {story_id: '日和 第1話 / 副標題'}
    """
    unit_names   = {}
    story_titles = {}

    if not os.path.exists(DB_PATH):
        return unit_names, story_titles

    try:
        conn = sqlite3.connect(DB_PATH)
        cur  = conn.cursor()

        # ── 角色名稱 ──────────────────────────────────────────
        if unit_ids:
            placeholders = ",".join("?" * len(unit_ids))
            cur.execute(
                f"SELECT unit_id, unit_name FROM unit_data WHERE unit_id IN ({placeholders})",
                list(unit_ids)
            )
            for uid, name in cur.fetchall():
                unit_names[uid] = name

        # ── 劇情標題（story_detail 涵蓋個人劇情與主線）────────
        if story_ids:
            placeholders = ",".join("?" * len(story_ids))
            cur.execute(
                f"SELECT story_id, title, sub_title FROM story_detail "
                f"WHERE story_id IN ({placeholders})",
                list(story_ids)
            )
            for sid, title, sub in cur.fetchall():
                label = title or ""
                if sub:
                    label = f"{label}／{sub}" if label else sub
                story_titles[sid] = label

            # 活動劇情補查 event_story_detail
            missing = [s for s in story_ids if s not in story_titles]
            if missing:
                placeholders = ",".join("?" * len(missing))
                cur.execute(
                    f"SELECT story_id, title, sub_title FROM event_story_detail "
                    f"WHERE story_id IN ({placeholders})",
                    missing
                )
                for sid, title, sub in cur.fetchall():
                    label = title or ""
                    if sub:
                        label = f"{label}／{sub}" if label else sub
                    story_titles[sid] = label

        conn.close()
    except Exception as e:
        print(f"  ⚠️ DB 查詢名稱失敗：{e}", file=sys.stderr)

    return unit_names, story_titles


def _query_game_snapshot(top_n=10):
    """
    從本地 DB 查詢目前遊戲內容快照：
      - 最新角色（unit_id 最大的前 top_n 個）
      - 最新主線章節（story_id 2XXXXXX 最大的前 5 集）
      - 最新活動劇情（start_time 最新的前 5 個活動）
    回傳 dict：
      latest_chars  : [(unit_id, unit_name), ...]
      latest_main   : [(story_id, title, sub_title), ...]
      latest_events : [(story_group_id, title, start_time), ...]
    """
    result = {"latest_chars": [], "latest_main": [], "latest_events": []}
    if not os.path.exists(DB_PATH):
        return result
    try:
        conn = sqlite3.connect(DB_PATH)
        cur  = conn.cursor()

        # 最新角色（rarity >= 1 排除 NPC；unit_id < 180000 排除故事版本）
        cur.execute(
            "SELECT unit_id, unit_name FROM unit_data "
            "WHERE unit_id >= 100000 AND unit_id < 180000 AND rarity >= 1 "
            "ORDER BY unit_id DESC LIMIT ?",
            (top_n,)
        )
        result["latest_chars"] = cur.fetchall()

        # 最新主線章節（story_id 2000000-2999999，取最大的前 5）
        cur.execute(
            "SELECT story_id, title, sub_title FROM story_detail "
            "WHERE story_id >= 2000000 AND story_id < 3000000 "
            "ORDER BY story_id DESC LIMIT 5"
        )
        result["latest_main"] = cur.fetchall()

        # 最新活動：舊活動（event_story_data）＋ 新形式活動（extra_events.json）合併
        # 舊活動：取 start_time 最新 5 筆
        cur.execute(
            "SELECT story_group_id, title, start_time FROM event_story_data "
            "ORDER BY start_time DESC LIMIT 5"
        )
        old_events = [
            (gid, (t or "").replace("\\n", " ").replace("\n", " ").strip(), st[:10])
            for gid, t, st in cur.fetchall()
        ]

        # 新形式活動：讀 extra_events.json，取最後 5 筆（最新在末尾）
        extra_path = os.path.join(DASHBOARD_DIR, "data", "extra_events.json")
        new_events = []
        if os.path.exists(extra_path):
            with open(extra_path, "r", encoding="utf-8") as f:
                extra = json.load(f)
            for ev in extra.get("events", [])[-5:]:
                title = (ev.get("title") or "").replace("\\n", " ").replace("\n", " ").strip()
                new_events.append((ev["story_group_id"], title, "新形式活動"))
            new_events.reverse()   # 最新排最前

        result["latest_events"] = (new_events + old_events)[:5]


        conn.close()
    except Exception as e:
        print(f"  ⚠️ 快照查詢失敗：{e}", file=sys.stderr)
    return result


def _get_sonet_ver():
    """取得台版目前實際使用的 So-net TruthVersion。"""
    # wthee 的版本 API 反映當前台版 CDN；本地歷史僅能當離線備援。
    # 不能讓舊的 version_history.json 蓋過線上已更新的 TruthVersion。
    try:
        payload = json.dumps({"regionCode": "tw"}).encode("utf-8")
        req = urllib.request.Request(
            "https://wthee.xyz/pcr/api/v1/db/info/v2",
            data=payload,
            headers={"Content-Type": "application/json", **WEB_HEADER},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as res:
            data = json.loads(res.read().decode("utf-8"))
        version = data.get("data", {}).get("truthVersion")
        if version:
            return version
    except Exception:
        pass

    # 離線時才使用 monitor 產生的歷史記錄。
    try:
        hist_path = os.path.join(os.path.dirname(DB_PATH), "versions", "version_history.json")
        if os.path.exists(hist_path):
            with open(hist_path, "r", encoding="utf-8") as f:
                hist = json.load(f)
                if hist.get("last_version"):
                    return hist["last_version"]
    except Exception:
        pass

    if not os.path.exists(DB_PATH):
        return "00500024"  # fallback
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT string_value FROM app_version WHERE key='asset_version' LIMIT 1")
        row = cur.fetchone()
        conn.close()
        if row:
            return row[0]
    except Exception:
        pass
    return "00500030"  # 提高預設 fallback 至當前版本



def _get_story_ids_from_db(unit_id):
    """從 DB 查詢角色個人劇情的 story_id 清單。"""
    if not os.path.exists(DB_PATH):
        return []
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        # chara_story_status 存放每話劇情
        cur.execute(
            "SELECT story_id FROM chara_story_status WHERE story_id LIKE ? ORDER BY story_id",
            (f"{unit_id // 100}%",)  # 使用模糊比對，包容 7 位與 8 位數
        )
        rows = cur.fetchall()
        conn.close()
        if rows:
            # CDN 已上架時資料庫偶爾會暫缺第 1 話；補入同角色的標準四話
            # 範圍，避免新角色故事在網站上少第一話。
            base_7 = (unit_id // 100) * 1000 + 1
            expected = {base_7 + i for i in range(4)}
            return sorted({r[0] for r in rows} | expected)
    except Exception:
        pass
        
    # Fallback：用規則推算，同時包含 7 位數（新型態）與 8 位數（舊版）
    base_7 = (unit_id // 100) * 1000 + 1  # 138701 -> 1387001
    ids = []
    # 產生 7 位數 ID (1387001 ~ 1387004)
    ids.extend([base_7 + i for i in range(4)])
    # 產生 8 位數 ID (1387011 ~ 1387014)
    ids.extend([unit_id * 10 + i for i in range(1, 5)])
    return ids



# ─────────────────────────── 劇情解密 ───────────────────────────

def _deserialize_command(data):
    index = data[0]
    array = []
    for arg in data[1:]:
        array2 = [255 - b if b > 127 else b for b in arg]
        try:
            decoded = base64.b64decode(bytearray(array2)).decode('utf-8', errors='ignore')
            array.append(decoded)
        except Exception:
            array.append("")
    return index, array


def _deserialize_story_raw(bytes_):
    commands = []
    fs = 0
    raw_commands = []
    i = 2
    while i < len(bytes_):
        if fs + 2 > len(bytes_):
            break
        index = int(unpack(">H", bytes_[fs: fs + 2])[0])
        fs += 2
        args = [index]
        num = i
        while True:
            if fs + 4 > len(bytes_):
                break
            length = int(unpack(">l", bytes_[fs: fs + 4])[0])
            fs += 4
            if length == 0:
                break
            if fs + length > len(bytes_):
                break
            args.append(bytes_[fs: fs + length])
            fs += length
            num += 4 + length
        i = num + 4
        raw_commands.append(args)
        i += 2
    for rc in raw_commands:
        if len(rc) > 1:
            commands.append(_deserialize_command(rc))
    return commands


SPEAKER_MAP = {
    "コッコロ": "可可蘿",
    "ペコリーヌ": "貪吃佩可",
    "キャル": "凱留",
    "ユウキ": "佑樹",
    "祐樹": "佑樹",
    "騎士君": "佑樹",
    "可可蘿": "可可蘿",
    "佩可": "貪吃佩可",
    "凱留": "凱留",
}


def _parse_bundle_dialogues(bundle_data):
    """解析 AssetBundle bytes，返回對白列表。"""
    try:
        import UnityPy
        UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'
    except ImportError:
        raise RuntimeError("UnityPy 未安裝，請執行: pip install UnityPy")

    dialogues = []
    bundle = UnityPy.load(bundle_data)
    for obj in bundle.objects:
        if obj.type.name == "TextAsset":
            data = obj.read()
            script = getattr(data, 'script', None) or getattr(data, 'm_Script', None)
            if not script:
                continue
            if isinstance(script, str):
                script = bytes(script, 'utf-8', 'surrogateescape')
            commands = _deserialize_story_raw(script)
            current_voice = None
            for idx, args in commands:
                # The scenario format interleaves dialogue with presentation
                # commands.  Keeping these commands in the exported JSON is
                # essential: otherwise the reader has no place to show a
                # background change, a CG, or a movie transition.
                still_match = None
                if idx != 6:
                    for arg in args:
                        still_match = re.search(r'(?:storydata_)?still[_-]?(\d+)', str(arg), re.I)
                        if still_match:
                            break

                if still_match:
                    dialogues.append({"type": "still", "still": still_match.group(1), "still_id": still_match.group(1)})
                elif idx == 49 and args:
                    still_val = str(args[0])
                    if still_val.lower() == "end":
                        dialogues.append({"type": "still", "still": "end"})
                    else:
                        m_sid = re.search(r'(\d+)', still_val)
                        sid = m_sid.group(1) if m_sid else still_val
                        dialogues.append({"type": "still", "still": sid, "still_id": sid})
                elif idx == 5 and args:
                    dialogues.append({"type": "background", "bg_id": str(args[0])})
                elif idx == 46 and args:
                    # So-net's recent main-story bundles use command 46 for
                    # movie transitions (for example 221600601).  The ID is
                    # also used by the matching storydata_still bundle when a
                    # static preview is available.
                    movie_id = str(args[0])
                    dialogues.append({"type": "movie", "movie_id": movie_id})
                    preview_path = os.path.join(
                        DASHBOARD_DIR, "still", "story", f"{movie_id}.webp"
                    )
                    if os.path.exists(preview_path):
                        dialogues.append({"type": "still", "still": movie_id, "still_id": movie_id})
                elif idx == 12 and args:
                    current_voice = args[0]
                elif idx == 6 and len(args) >= 2:
                    speaker = SPEAKER_MAP.get(args[0], args[0])
                    words = args[1]
                    if speaker == "可可蘿":
                        words = words.replace("主人", "主公大人")
                    dialogues.append({"name": speaker, "words": words, "voice": current_voice})
                    current_voice = None
    return dialogues


# ─────────────────────────── 子命令實作 ───────────────────────────

def cmd_update_db(args):
    """更新台版明文資料庫。"""
    print("📥 從 wthee 下載最新台服明文資料庫...")
    results = {"status": "ok", "db_path": DB_PATH, "checks": []}

    try:
        data = _http_get(WTHEE_DB_URL, WEB_HEADER, timeout=60, retries=2)
        with open(DB_PATH, 'wb') as f:
            f.write(data)
        print(f"  ✅ 下載完成，大小: {len(data):,} bytes")
        results["size_bytes"] = len(data)
    except Exception as e:
        results["status"] = "error"
        results["error"] = str(e)
        print(f"  ❌ 下載失敗: {e}", file=sys.stderr)
        _write_output(args.output, results)
        sys.exit(1)

    # 驗證資料表
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        for table in ["unit_data", "chara_story_status", "unit_skill_data"]:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            results["checks"].append({"table": table, "count": count})
            print(f"  - {table}: {count} 筆")
        conn.close()
    except Exception as e:
        results["checks_error"] = str(e)
        print(f"  ⚠️ 資料表驗證失敗: {e}", file=sys.stderr)

    _write_output(args.output, results)
    print(f"\n✅ DB 更新完成！報告已寫入 {args.output}")


def cmd_fetch_stories(args):
    """下載並解密角色個人劇情 JSON。"""
    unit_id = args.unit_id
    print(f"📖 開始下載 unit_id={unit_id} 的個人劇情...")

    # 從 DB 查詢 story_id 清單
    story_ids = _get_story_ids_from_db(unit_id)
    if not story_ids:
        print(f"  ⚠️ 在 DB 中找不到 unit_id={unit_id} 的劇情資料，使用推算規則")
        story_ids = [unit_id * 10 + i for i in range(1, 5)]
    print(f"  找到 {len(story_ids)} 話: {story_ids}")

    ver = _get_sonet_ver()
    manifest_url = f"{SONET_CDN}/Resources/{ver}/Jpn/AssetBundles/Android/manifest/storydata2_assetmanifest"

    # 載入 manifest 取得 hash
    print(f"  📋 載入 Manifest: {manifest_url}")
    try:
        manifest_data = _http_get(manifest_url, WEB_HEADER)
        hash_map = {}
        for line in manifest_data.decode('utf-8').splitlines():
            parts = line.strip().split(",")
            if len(parts) >= 3:
                path, _, h = parts[0], parts[1], parts[2]
                for sid in story_ids:
                    if f"storydata_{sid}.unity3d" in path:
                        hash_map[sid] = h
    except Exception as e:
        print(f"  ❌ 載入 Manifest 失敗: {e}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(STORY_DIR, exist_ok=True)
    results = {"unit_id": unit_id, "stories": []}

    for sid in story_ids:
        h = hash_map.get(sid)
        if not h:
            results["stories"].append({"story_id": sid, "status": "hash_not_found"})
            print(f"  ⚠️ story_id={sid} 未找到 hash，跳過")
            continue

        url = f"{SONET_CDN}/pool/AssetBundles/{h[:2]}/{h}"
        print(f"  📥 下載 story_id={sid}...")
        time.sleep(0.5)  # 限速：每次請求間隔 0.5s

        try:
            bundle_data = _http_get(url, WEB_HEADER)
            dialogues = _parse_bundle_dialogues(bundle_data)
            out_path = os.path.join(STORY_DIR, f"{sid}.json")
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(dialogues, f, ensure_ascii=False, indent=2)
            results["stories"].append({
                "story_id": sid,
                "status": "ok",
                "dialogue_count": len(dialogues),
                "output": out_path
            })
            print(f"    ✅ {sid}: {len(dialogues)} 句對白 → {out_path}")
        except Exception as e:
            results["stories"].append({"story_id": sid, "status": "error", "error": str(e)})
            print(f"    ❌ story_id={sid} 解析失敗: {e}", file=sys.stderr)

    _write_output(args.output, results)
    print(f"\n✅ 劇情下載完成！報告已寫入 {args.output}")


def cmd_fetch_assets(args):
    """下載立繪與頭像素材。"""
    unit_id = args.unit_id
    # 根據公連 7 位數命名特徵，將 138701 規整為 138711 (1星) 與 138731 (3星)
    u1 = (unit_id // 100) * 100 + 11
    u3 = (unit_id // 100) * 100 + 31
    ver = _get_sonet_ver()

    print(f"🎨 開始下載 unit_id={unit_id} 的美術素材（ver={ver}）...")
    os.makedirs(ICON_DIR, exist_ok=True)
    os.makedirs(CARD_DIR, exist_ok=True)

    # 載入 manifests
    hash_map = {}
    
    # 1. 載入 unit2_assetmanifest (用於頭像)
    unit_manifest_url = f"{SONET_CDN}/Resources/{ver}/Jpn/AssetBundles/Android/manifest/unit2_assetmanifest"
    try:
        data = _http_get(unit_manifest_url, WEB_HEADER)
        for line in data.decode('utf-8').splitlines():
            parts = line.strip().split(",")
            if len(parts) >= 3:
                path, _, h = parts[0], parts[1], parts[2]
                if f"unit_icon_unit_{u1}.unity3d" in path:
                    hash_map[f"icon_{u1}"] = h
                if f"unit_icon_unit_{u3}.unity3d" in path:
                    hash_map[f"icon_{u3}"] = h
    except Exception as e:
        print(f"  ⚠️ 載入 unit2_assetmanifest 失敗: {e}")

    # 2. 載入 bg2_assetmanifest (用於高清立繪)
    bg_manifest_url = f"{SONET_CDN}/Resources/{ver}/Jpn/AssetBundles/Android/manifest/bg2_assetmanifest"
    try:
        data = _http_get(bg_manifest_url, WEB_HEADER)
        for line in data.decode('utf-8').splitlines():
            parts = line.strip().split(",")
            if len(parts) >= 3:
                path, _, h = parts[0], parts[1], parts[2]
                if f"bg_still_unit_{u3}.unity3d" in path:
                    hash_map[f"still_{u3}"] = h
    except Exception as e:
        print(f"  ⚠️ 載入 bg2_assetmanifest 失敗: {e}")

    assets = [
        {
            "key": f"icon_{u1}",
            "dest": os.path.join(ICON_DIR, f"unit_icon_{u1}.webp"),
            "fallback_url": f"https://redive.estertion.win/icon/unit/{u1}.png",
            "desc": "1星頭像"
        },
        {
            "key": f"icon_{u3}",
            "dest": os.path.join(ICON_DIR, f"unit_icon_{u3}.webp"),
            "fallback_url": f"https://redive.estertion.win/icon/unit/{u3}.png",
            "desc": "3星頭像"
        },
        {
            "key": f"still_{u3}",
            "dest": os.path.join(CARD_DIR, f"card_full_{u3}.webp"),
            "fallback_url": f"https://redive.estertion.win/card/full/{u3}.webp",
            "desc": "3星立繪大圖"
        },
    ]

    results = {"unit_id": unit_id, "assets": []}
    for item in assets:
        time.sleep(0.3)
        h = hash_map.get(item["key"])
        downloaded = False
        
        # 1. 嘗試從 So-net CDN pool 解密下載
        if h:
            url = f"{SONET_CDN}/pool/AssetBundles/{h[:2]}/{h}"
            try:
                print(f"  📥 下載並解密 {item['desc']} ({url})...")
                bundle_data = _http_get(url, WEB_HEADER, timeout=15)
                
                # 使用 UnityPy 解密提取
                import UnityPy
                UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'
                env = UnityPy.load(bundle_data)
                
                extracted = False
                for obj in env.objects:
                    if obj.type.name in ['Texture2D', 'Sprite']:
                        d = obj.read()
                        # 儲存為 WebP
                        d.image.save(item["dest"], format="WEBP")
                        results["assets"].append({"desc": item["desc"], "status": "ok", "dest": item["dest"]})
                        print(f"    ✅ {item['desc']} 解密儲存成功 → {os.path.basename(item['dest'])}")
                        extracted = True
                        downloaded = True
                        break
                
                if not extracted:
                    print(f"    ⚠️ Bundle 中未找到圖片對象")
            except Exception as e:
                print(f"    ⚠️ 從 CDN 解密失敗: {e}")
                
        # 2. 備用方案：從 Estertion 鏡像下載明文
        if not downloaded:
            print(f"  🌐 嘗試備用下載鏡像明文 ({item['fallback_url']})...")
            try:
                # 為了避免鏡像站封防爬蟲，我們使用 WEB_HEADER (帶 Mozilla)
                data = _http_get(item["fallback_url"], WEB_HEADER, timeout=10)
                # 為了確保寫入的是網頁能播放的 WebP，如果是 PNG (頭像) 則利用 PIL 進行轉碼
                if item["fallback_url"].endswith(".png"):
                    from PIL import Image
                    import io
                    im = Image.open(io.BytesIO(data))
                    im.save(item["dest"], "WEBP")
                else:
                    with open(item["dest"], 'wb') as f:
                        f.write(data)
                results["assets"].append({"desc": item["desc"], "status": "ok", "dest": item["dest"]})
                print(f"    ✅ {item['desc']} 鏡像下載成功 → {os.path.basename(item['dest'])}")
            except Exception as e:
                results["assets"].append({"desc": item["desc"], "status": "error", "error": str(e)})
                print(f"    ❌ {item['desc']} 下載失敗: {e}", file=sys.stderr)


    # 登錄到追蹤設定檔
    tracked = _load_tracked_chars()
    existing_ids = [c["unit_id"] for c in tracked["characters"]]
    if unit_id not in existing_ids:
        # 嘗試從 DB 取得角色名稱
        char_name = f"角色_{unit_id}"
        if os.path.exists(DB_PATH):
            try:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute("SELECT unit_name FROM unit_data WHERE unit_id = ?", (unit_id,))
                row = cur.fetchone()
                if row:
                    char_name = row[0]
                conn.close()
            except Exception:
                pass
        tracked["characters"].append({
            "unit_id": unit_id,
            "name": char_name,
            "icon_ids": [u1, u3],
            "card_ids": [u3]
        })
        _save_tracked_chars(tracked)
        print(f"  📝 已將 {char_name} ({unit_id}) 登錄至 tracked_characters.json")

    _write_output(args.output, results)
    print(f"\n✅ 素材下載完成！報告已寫入 {args.output}")


def cmd_report(args):
    """產出 Markdown 驗證報告。"""
    unit_id = args.unit_id
    story_ids = _get_story_ids_from_db(unit_id)
    if not story_ids:
        story_ids = [unit_id * 10 + i for i in range(1, 5)]

    lines = [
        f"# 資料驗證報告 — unit_id={unit_id}",
        f"",
        f"產出時間：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
        f"## 資料庫",
    ]

    # DB 查詢
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT unit_id, unit_name FROM unit_data WHERE unit_id = ?", (unit_id,))
            row = cur.fetchone()
            if row:
                lines.append(f"- ✅ `unit_data` 中找到角色：**{row[1]}** (ID: {row[0]})")
            else:
                lines.append(f"- ⚠️ `unit_data` 中尚無 unit_id={unit_id}，wthee 可能尚未更新")
            cur.execute(
                "SELECT COUNT(*) FROM chara_story_status WHERE unit_id = ?", (unit_id,)
            )
            cnt = cur.fetchone()[0]
            lines.append(f"- 劇情話數（DB）：**{cnt} 話**")
            conn.close()
        except Exception as e:
            lines.append(f"- ❌ DB 查詢失敗: {e}")
    else:
        lines.append("- ❌ 找不到 redive_tw.db")

    lines += ["", "## 個人劇情 JSON"]
    for sid in story_ids:
        path = os.path.join(STORY_DIR, f"{sid}.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            lines.append(f"- ✅ `story/{sid}.json` — {len(data)} 句對白")
        else:
            lines.append(f"- ❌ `story/{sid}.json` 不存在")

    lines += ["", "## 美術素材"]
    u3 = unit_id + 30
    for fname, desc in [
        (f"icon/unit/unit_icon_{unit_id}.webp", "1星頭像"),
        (f"icon/unit/unit_icon_{u3}.webp", "3星頭像"),
        (f"card/full/card_full_{u3}.webp", "3星立繪"),
    ]:
        path = os.path.join(DASHBOARD_DIR, fname)
        status = "✅" if os.path.exists(path) else "❌"
        lines.append(f"- {status} `{fname}` ({desc})")

    report = "\n".join(lines)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"✅ 驗證報告已寫入 {args.output}")
    print("\n" + report)



def _write_output(path, data):
    """將結果寫入 JSON 檔案。"""
    if path:
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def cmd_scan_cdn(args):
    """
    手動探測 So-net CDN 是否有新版本或預上架素材（Manifest diff 版）。
    策略：
      1. 探測目前最新版本號（向上試探至多 20 個號碼）
      2. 下載 storydata2_assetmanifest 與本機快取做 diff
      3. 從新增行的檔名（storydata_XXXXXXX.unity3d）精準提取新 unit_id
      4. HEAD request 確認美術素材是否已預上架
      5. 有素材 → 下載到 dashboard/versions/{date}_{ver}/
      6. 更新 Manifest 快取，輸出 Markdown 報告
    """
    import datetime
    import re
    import urllib.error

    print("=" * 56)
    print("🔍 So-net CDN 手動偵測啟動（Manifest diff 模式）")
    print("=" * 56)

    VERSIONS_DIR = os.path.join(DASHBOARD_DIR, "versions")
    CACHE_DIR    = os.path.join(VERSIONS_DIR, "cached_manifests")
    HISTORY_FILE = os.path.join(VERSIONS_DIR, "version_history.json")
    CACHE_FILE   = os.path.join(CACHE_DIR, "storydata2_assetmanifest.txt")
    os.makedirs(CACHE_DIR, exist_ok=True)

    # 讀取歷史
    history = {}
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            history = json.load(f)
    last_ver = history.get("last_version") or _get_sonet_ver()
    print(f"  上次已知版本：{last_ver}")

    # ── Step 1：探測最新版本號 ────────────────────────────────
    ver_prefix = last_ver[:-4]
    ver_num    = int(last_ver[-4:])
    latest_ver = last_ver

    print(f"\n[Step 1] 探測新版本號（從 {last_ver} 往後試探最多 20 個）...")
    for i in range(1, 21):
        candidate = f"{ver_prefix}{ver_num + i:04d}"
        url = (f"{SONET_CDN}/Resources/{candidate}/Jpn/AssetBundles/Android"
               f"/manifest/masterdata2_assetmanifest")
        try:
            req = urllib.request.Request(url, headers=WEB_HEADER, method='HEAD')
            with urllib.request.urlopen(req, timeout=5) as res:
                if res.status == 200:
                    latest_ver = candidate
                    print(f"  🔥 發現新版本：{candidate}")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                break
        except Exception:
            break

    ver_changed = latest_ver != last_ver
    print(f"  {'🆕 最新版本：' + latest_ver + '（上次：' + last_ver + '）' if ver_changed else '✅ 版本號未變動，目前仍為 ' + last_ver}")

    # ── Step 2：下載 storydata Manifest ──────────────────────
    manifest_url = (f"{SONET_CDN}/Resources/{latest_ver}/Jpn/AssetBundles/Android"
                    f"/manifest/storydata2_assetmanifest")
    print(f"\n[Step 2] 下載 storydata Manifest 並比對差異...")

    new_manifest_text = ""
    try:
        data = _http_get(manifest_url, WEB_HEADER, timeout=15)
        new_manifest_text = data.decode('utf-8', errors='ignore')
        print(f"  ✅ 取得 Manifest（{len(new_manifest_text.splitlines())} 行）")
    except Exception as e:
        print(f"  ❌ 下載 Manifest 失敗: {e}", file=sys.stderr)

    # 讀取舊快取
    old_manifest_text = ""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            old_manifest_text = f.read()
        print(f"  📋 讀取舊快取（{len(old_manifest_text.splitlines())} 行）")
    else:
        print("  ℹ️ 無舊快取，本次結果將作為初始基準儲存")

    # 計算新增行
    old_lines = set(old_manifest_text.splitlines())
    new_lines_set = set(new_manifest_text.splitlines()) if new_manifest_text else set()
    added_lines = sorted(new_lines_set - old_lines)
    print(f"  🆕 新增 Manifest 行數：{len(added_lines)}")

    # ── 首次執行保護：無舊快取時只建立基準，不進行探測 ──────
    is_first_run = not old_manifest_text
    if is_first_run:
        print("\n  ℹ️ 初次執行：Manifest 已儲存為基準快取。")
        print("     下次執行 scan-cdn 才會開始偵測新增內容。")

    # ── Step 3：分類解析所有新增 storydata 行 ───────────────
    # story_id 規則（7位數）：
    #   0XXXXXX           → 教學（tutorial）
    #   1XXXXXX，base//10 在 100000-199999 → 角色個人劇情
    #   2XXXXXX           → 主線劇情
    #   3XXXXXX-9XXXXXX   → 活動/特殊劇情
    new_unit_ids      = set()
    new_story_entries = []   # (story_id, unit_id) — 個人劇情
    new_main_stories  = []   # story_id — 主線
    new_event_stories = []   # story_id — 活動/特殊
    new_tutorial      = []   # story_id — 教學

    # 1. 首先，從本地 DB 中查詢最大的主線 story_id 做為安全防漏比對基準
    max_db_main_story_id = 0
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT MAX(story_id) FROM story_detail WHERE story_id >= 2000000 AND story_id < 3000000")
            row = cur.fetchone()
            if row and row[0]:
                max_db_main_story_id = int(row[0])
            conn.close()
        except Exception:
            pass

    # 2. 除了比對新增行 (added_lines)，我們也直接掃描整個最新 Manifest，
    # 只要發現有任何大於本地 DB 最大主線 ID 的項目，就主動判定為新劇情，防止 So-net 預熱替換導致無行數 diff 的漏看！
    scanned_story_ids = set()
    if new_manifest_text:
        for line in new_manifest_text.splitlines():
            m = re.search(r'storydata_(\d{7})\.unity3d', line)
            if m:
                scanned_story_ids.add(int(m.group(1)))

    if not is_first_run:
        # 先以 added_lines 為基礎
        for line in added_lines:
            m = re.search(r'storydata_(\d{7})\.unity3d', line)
            if not m:
                continue
            story_id = int(m.group(1))
            first_digit = story_id // 1000000

            if first_digit == 0:
                new_tutorial.append(story_id)
            elif first_digit == 1:
                base_id = story_id // 10
                if 100000 <= base_id < 200000:
                    unit_id = base_id + 1
                    new_unit_ids.add(unit_id)
                    new_story_entries.append((story_id, unit_id))
            elif first_digit == 2:
                new_main_stories.append(story_id)
            else:
                new_event_stories.append(story_id)

        # 防漏雙重安全網：將所有大於 DB 最大主線 ID 且未被加入的 story_id 自動補入新主線清單
        if max_db_main_story_id > 0:
            for sid in sorted(scanned_story_ids):
                # 屬於主線且大於 DB 進度，且目前未被加入
                if (sid // 1000000 == 2) and (sid > max_db_main_story_id) and (sid not in new_main_stories):
                    new_main_stories.append(sid)
                    print(f"  🔍 [防漏機制] 成功偵測到無 diff 的預上架新主線話數：{sid}")
            # 重新排序確保流暢展示
            new_main_stories.sort()


    # ── Step 3b：從 DB 查詢名稱 ─────────────────────────────
    all_story_ids_to_lookup = (
        [sid for sid, _ in new_story_entries] +
        new_main_stories[:10] +       # 主線取前 10 集查標題
        new_event_stories[:10]        # 活動取前 10 集查標題
    )
    unit_names, story_titles = _lookup_db_names(
        unit_ids=list(new_unit_ids),
        story_ids=all_story_ids_to_lookup
    )

    # ── 輸出分類摘要（帶名稱版）──────────────────────────────
    if new_story_entries:
        shown = {}
        for sid, uid in new_story_entries:
            shown.setdefault(uid, sid)
        print(f"\n  👤 新角色個人劇情：{len(shown)} 個角色")
        for uid, first_sid in sorted(shown.items()):
            char_name  = unit_names.get(uid, f"unit_{uid}")
            ep_title   = story_titles.get(first_sid, "")
            print(f"    {char_name}（unit_id={uid}）：{ep_title}")

    if new_main_stories:
        print(f"\n  📖 新主線劇情：{len(new_main_stories)} 個 bundle")
        for sid in sorted(new_main_stories)[:5]:
            title = story_titles.get(sid, f"story_id={sid}")
            print(f"    {title}")
        if len(new_main_stories) > 5:
            print(f"    ...（共 {len(new_main_stories)} 個）")

    if new_event_stories:
        print(f"\n  🎉 新活動/特殊劇情：{len(new_event_stories)} 個 bundle")
        for sid in sorted(new_event_stories)[:5]:
            title = story_titles.get(sid, f"story_id={sid}")
            print(f"    {title}")
        if len(new_event_stories) > 5:
            print(f"    ...（共 {len(new_event_stories)} 個）")

    if new_tutorial:
        print(f"\n  📚 新教學內容：{len(new_tutorial)} 個 bundle")

    # 加入使用者手動指定的 ID
    extra_ids = set()
    if args.probe_ids:
        for x in args.probe_ids.split(","):
            x = x.strip()
            if x.isdigit():
                extra_ids.add(int(x))
        if extra_ids:
            print(f"  ➕ 加入手動指定的 unit_id：{sorted(extra_ids)}")

    all_probe_ids = sorted(new_unit_ids | extra_ids)
    if not all_probe_ids and not is_first_run:
        print("\n  ✅ 無新角色，跳過美術素材探測")

    # ── Step 4：HEAD request 確認美術是否預上架 ──────────────
    ASSET_TEMPLATES = [
        ("1星頭像", "Unit/Icon/unit_icon_{u1}.webp"),
        ("3星頭像", "Unit/Icon/unit_icon_{u3}.webp"),
        ("3星立繪", "Card/Full/card_full_{u3}.webp"),
    ]
    date_str     = datetime.datetime.now().strftime("%Y%m%d")
    found_results = []

    if all_probe_ids:
        print(f"\n[Step 3] 確認美術素材是否預上架（{len(all_probe_ids)} 個 unit_id）...")
        for uid in all_probe_ids:
            u1, u3    = uid, uid + 30
            uid_found = []
            for desc, tmpl in ASSET_TEMPLATES:
                path_part = tmpl.format(u1=u1, u3=u3)
                url = f"{SONET_CDN}/Resources/{latest_ver}/Jpn/{path_part}"
                time.sleep(0.3)
                try:
                    req = urllib.request.Request(url, headers=SONET_HEADER, method='HEAD')
                    with urllib.request.urlopen(req, timeout=5) as res:
                        if res.status == 200:
                            uid_found.append((desc, path_part, url))
                except urllib.error.HTTPError as e:
                    if e.code != 404:
                        print(f"    ⚠️ {desc} HTTP {e.code}")
                except Exception:
                    pass

            if uid_found:
                print(f"  🎨 unit_id={uid}：{len(uid_found)} 項美術素材已預上架！")
                for desc, _, _ in uid_found:
                    print(f"    ✅ {desc}")
                found_results.append({"unit_id": uid, "assets": uid_found})
            else:
                print(f"  　unit_id={uid}：劇情已上架，美術尚未預上架")

    # ── Step 5：下載找到的素材 ────────────────────────────────
    downloaded_map = {}
    if args.download and found_results:
        ver_dir = os.path.join(VERSIONS_DIR, f"{date_str}_{latest_ver}")
        os.makedirs(ver_dir, exist_ok=True)
        print(f"\n[Step 4] 下載素材到 {ver_dir}...")
        for item in found_results:
            uid = item["unit_id"]
            downloaded = []
            for desc, path_part, url in item["assets"]:
                fname = os.path.basename(path_part)
                dest  = os.path.join(ver_dir, fname)
                time.sleep(0.3)
                try:
                    data = _http_get(url, SONET_HEADER, timeout=10)
                    with open(dest, 'wb') as f:
                        f.write(data)
                    downloaded.append(fname)
                    print(f"    💾 {fname} 下載完成")
                except Exception as e:
                    print(f"    ❌ {fname} 下載失敗: {e}", file=sys.stderr)
            downloaded_map[uid] = downloaded

    # ── Step 5a：儲存新 Manifest 快取（下次 diff 的基準）────────
    if new_manifest_text:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            f.write(new_manifest_text)
        print(f"\n  💾 Manifest 快取已更新（{len(new_manifest_text.splitlines())} 行）")

    # ── Step 5b：更新版本歷史 ─────────────────────────────────
    history["last_version"] = latest_ver
    if latest_ver != last_ver:
        processed = history.get("processed_versions", [])
        if latest_ver not in processed:
            processed.append(latest_ver)
        history["processed_versions"] = processed
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


    # ── Step 6：輸出 Markdown 報告 ───────────────────────────
    snapshot = _query_game_snapshot(top_n=10)

    lines = [
        "# So-net CDN 偵測報告",
        "",
        f"偵測時間：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 版本號",
        f"- 上次版本：`{last_ver}`",
        f"- 最新版本：`{latest_ver}` {'🆕 **有更新！**' if ver_changed else '（未變動）'}",
        "",
        "## Manifest Diff 結果",
    ]

    if is_first_run:
        lines.append("- ⚙️ **初次執行**：Manifest 快取已建立，下次掃描才會開始偵測差異。")
    else:
        total_new = len(new_story_entries) + len(new_main_stories) + len(new_event_stories) + len(new_tutorial)
        lines.append(f"- 新增行數：**{len(added_lines)}**")
        if total_new == 0:
            lines.append("- 無新增任何劇情（純數值 / 資料庫更新）")
        else:
            # 角色個人劇情
            if new_story_entries:
                shown = {}
                for sid, uid in new_story_entries:
                    shown.setdefault(uid, sid)
                lines.append(f"- 👤 新角色個人劇情：**{len(shown)}** 個角色")
                for uid, sid in sorted(shown.items()):
                    char_name = unit_names.get(uid, f"unit_{uid}")
                    ep_title  = story_titles.get(sid, "")
                    label = f"**{char_name}**（unit_id={uid}）"
                    if ep_title:
                        label += f"，首集：{ep_title}"
                    lines.append(f"  - {label}")
            # 主線劇情
            if new_main_stories:
                lines.append(f"- 📖 新主線劇情：**{len(new_main_stories)}** 個 bundle")
                for sid in sorted(new_main_stories)[:5]:
                    title = story_titles.get(sid, f"story_id={sid}")
                    lines.append(f"  - {title}")
                if len(new_main_stories) > 5:
                    lines.append(f"  - ...（共 {len(new_main_stories)} 個）")
            # 活動/特殊劇情
            if new_event_stories:
                lines.append(f"- 🎉 新活動/特殊劇情：**{len(new_event_stories)}** 個 bundle")
                for sid in sorted(new_event_stories)[:5]:
                    title = story_titles.get(sid, f"story_id={sid}")
                    lines.append(f"  - {title}")
                if len(new_event_stories) > 5:
                    lines.append(f"  - ...（共 {len(new_event_stories)} 個）")
            # 教學
            if new_tutorial:
                lines.append(f"- 📚 新教學內容：**{len(new_tutorial)}** 個 bundle")

        lines += ["", "## 美術素材預上架狀態"]
        if found_results:
            for item in found_results:
                uid = item["unit_id"]
                char_name = unit_names.get(uid, f"unit_{uid}")
                lines.append(f"\n### {char_name}（unit_id={uid}）")
                for desc, path_part, _ in item["assets"]:
                    lines.append(f"- ✅ **{desc}**：`{os.path.basename(path_part)}`")
                dl = downloaded_map.get(uid, [])
                if dl:
                    lines.append(f"- 📥 已下載 {len(dl)} 個檔案至 `versions/{date_str}_{latest_ver}/`")
            lines += ["", f"> ⚡ 發現新素材！可執行 `fetch-stories --unit-id {{uid}}` 取得個人劇情。"]
        elif all_probe_ids:
            lines.append("- 劇情資料已預上架，但美術素材尚未同步，可稍後再掃一次。")
        else:
            lines.append("- 無新角色美術，CDN 目前無角色預上架內容。")

    # ── 固定快照區段（每次都顯示，來自本地 DB）──────────────
    lines += ["", "---", "", "## 📌 目前遊戲內容（本地 DB 快照）"]

    # 最新角色
    lines.append("\n### 最新角色（unit_id 最大的前 10 個）")
    if snapshot["latest_chars"]:
        for uid, name in snapshot["latest_chars"]:
            lines.append(f"- **{name}**（unit_id={uid}）")
    else:
        lines.append("- （DB 無資料）")

    # 最新主線章節
    lines.append("\n### 主線最新章節")
    if snapshot["latest_main"]:
        for sid, title, sub in snapshot["latest_main"]:
            label = title or f"story_id={sid}"
            if sub:
                label = f"{label}／{sub}"
            lines.append(f"- {label}（story_id={sid}）")
    else:
        lines.append("- （DB 無資料）")

    # 最新活動劇情
    lines.append("\n### 最新活動劇情（依開始時間）")
    if snapshot["latest_events"]:
        for gid, title, start in snapshot["latest_events"]:
            lines.append(f"- **{title or '（無標題）'}**（group_id={gid}，{start[:10]}）")
    else:
        lines.append("- （DB 無資料）")

    report = "\n".join(lines)
    if args.output:
        os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n✅ 偵測報告已寫入 {args.output}")

    print("\n" + report)
    print("\n" + "=" * 56)


def cmd_fetch_story_voices(args):
    """下載指定主線劇情話數的所有語音音檔。"""
    story_id = args.story_id
    json_path = os.path.join(STORY_DIR, f"{story_id}.json")
    
    print(f"🔊 開始下載劇情話數 story_id={story_id} 的語音音檔...")
    if not os.path.exists(json_path):
        print(f"  ❌ 錯誤：找不到已解密的劇情對白 JSON 檔案，請先執行 fetch-stories 下載！")
        sys.exit(1)
        
    with open(json_path, "r", encoding="utf-8") as f:
        dialogues = json.load(f)
        
    # 提取所有不重複的語音 ID
    voice_ids = sorted(list(set([d["voice"] for d in dialogues if d.get("voice")])))
    print(f"  該話共包含 {len(voice_ids)} 個語音音檔項目。")
    
    voice_dir = os.path.join(DASHBOARD_DIR, "sound", str(story_id))
    os.makedirs(voice_dir, exist_ok=True)
    
    results = {"story_id": story_id, "dialogue_count": len(dialogues), "voices": []}
    
    # estertion 的劇情語音鏡像池
    estertion_pool = "https://redive.estertion.win/sound/vo_adv"
    
    downloaded_count = 0
    for voice_id in voice_ids:
        # 下載 M4A 格式
        url = f"{estertion_pool}/{voice_id}.m4a"
        dest_path = os.path.join(voice_dir, f"{voice_id}.m4a")
        
        # 冪等保護：如果已下載且有檔案大小，跳過
        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
            results["voices"].append({"voice_id": voice_id, "status": "exists", "dest": dest_path})
            continue
            
        time.sleep(0.3)  # 限速避開阻擋
        try:
            req = urllib.request.Request(url, headers=WEB_HEADER)
            with urllib.request.urlopen(req, timeout=15) as res:
                with open(dest_path, "wb") as f_out:
                    f_out.write(res.read())
            results["voices"].append({"voice_id": voice_id, "status": "ok", "dest": dest_path})
            print(f"  ✅ 下載成功: {voice_id}.m4a")
            downloaded_count += 1
        except Exception as e:
            results["voices"].append({"voice_id": voice_id, "status": "error", "error": str(e)})
            print(f"  ⚠️ 下載失敗 {voice_id}: {e}")
            
    _write_output(args.output, results)
    print(f"\n✅ 語音下載整合完成！共下載 {downloaded_count} 筆，報告寫入 {args.output}")


def cmd_fetch_story_images(args):
    """下載指定劇情話數的 CG 與背景圖片。"""
    import re
    story_id = args.story_id
    ver = _get_sonet_ver()

    
    print(f"🖼️ 開始下載劇情話數 story_id={story_id} 的背景與 CG 圖片（Resources={ver}）...")
    
    # 1. 下載背景 Manifest 與 角色/CG Manifest
    bg_manifest_path = os.path.join(DASHBOARD_DIR, "versions", "cached_manifests", "bg2_assetmanifest_latest.txt")
    unit_manifest_path = os.path.join(DASHBOARD_DIR, "versions", "cached_manifests", "unit2_assetmanifest_latest.txt")
    os.makedirs(os.path.dirname(bg_manifest_path), exist_ok=True)
    
    # 取得最新背景 Manifest
    try:
        url_bg_m = f"{SONET_CDN}/Resources/{ver}/Jpn/AssetBundles/Android/manifest/bg2_assetmanifest"
        data = _http_get(url_bg_m, SONET_HEADER, timeout=15)
        with open(bg_manifest_path, "w", encoding="utf-8") as f:
            f.write(data.decode('utf-8', errors='ignore'))
        print("  ✅ 背景 Manifest 下載成功。")
    except Exception as e:
        print(f"  ⚠️ 下載背景 Manifest 失敗: {e}")

    # 取得最新角色/CG Manifest
    try:
        url_unit_m = f"{SONET_CDN}/Resources/{ver}/Jpn/AssetBundles/Android/manifest/unit2_assetmanifest"
        data = _http_get(url_unit_m, SONET_HEADER, timeout=15)
        with open(unit_manifest_path, "w", encoding="utf-8") as f:
            f.write(data.decode('utf-8', errors='ignore'))
        print("  ✅ 角色/CG Manifest 下載成功。")
    except Exception as e:
        print(f"  ⚠️ 下載角色/CG Manifest 失敗: {e}")

    # 2. 下載劇情引導 Bundle，提取該話使用的背景圖與 CG 圖 ID
    manifest_path = os.path.join(DASHBOARD_DIR, "versions", "cached_manifests", "storydata2_assetmanifest.txt")
    # Keep the story, background, and CG manifests on the same resource
    # version; a stale story cache makes newly released events look absent.
    try:
        url_story_m = f"{SONET_CDN}/Resources/{ver}/Jpn/AssetBundles/Android/manifest/storydata2_assetmanifest"
        data = _http_get(url_story_m, SONET_HEADER, timeout=15)
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(data.decode('utf-8', errors='ignore'))
        print("  ✅ 劇情 Manifest 下載成功。")
    except Exception as e:
        print(f"  ⚠️ 劇情 Manifest 更新失敗，改用本機快取: {e}")
    h = None
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if f"storydata_{story_id}.unity3d" in line:
                    h = line.strip().split(",")[2]
                    break
                    
    if not h:
        print(f"  ❌ 錯誤：無法在 Manifest 中找到 story_id={story_id} 的 Hash，可能是該劇情尚未實裝。")
        sys.exit(1)
        
    url = f"{SONET_CDN}/pool/AssetBundles/{h[:2]}/{h}"
    print(f"  📥 下載劇情引導 Bundle: {url} ...")
    
    import UnityPy
    import base64
    from struct import unpack
    UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'
    
    bg_ids = set()
    still_ids = set()
    
    try:
        req = urllib.request.Request(url, headers=SONET_HEADER)
        with urllib.request.urlopen(req, timeout=15) as res:
            bundle_data = res.read()
            
        env = UnityPy.load(bundle_data)
        for obj in env.objects:
            if obj.type.name == "TextAsset":
                data = obj.read()
                script = getattr(data, 'script', None) or getattr(data, 'm_Script', None)
                if script:
                    if isinstance(script, str):
                        script = bytes(script, 'utf-8', 'surrogateescape')
                    commands = _deserialize_story_raw(script)
                    for cmd_idx, args_list in commands:
                        if cmd_idx == 5 and args_list:
                            bg_ids.add(str(args_list[0]))
                        # Main-story movie transitions use the same numeric
                        # resource ID for their optional still preview.
                        if cmd_idx == 46 and args_list:
                            still_ids.add(str(args_list[0]))
                        for arg in args_list:
                            arg_str = str(arg)
                            if "still" in arg_str.lower():
                                still_ids.add(arg_str)
    except Exception as e:
        print(f"  ❌ 提取 Bundle 指令失敗: {e}")
        sys.exit(1)
        
    print(f"  解析成功！發現背景圖 ID: {bg_ids}，發現 CG 圖 ID: {still_ids}")
    
    bg_dir = os.path.join(DASHBOARD_DIR, "still", "bg")
    still_dir = os.path.join(DASHBOARD_DIR, "still", "story")
    os.makedirs(bg_dir, exist_ok=True)
    os.makedirs(still_dir, exist_ok=True)
    
    results = {"story_id": story_id, "bg_images": [], "still_images": []}
    
    # 3. 讀取背景 Manifest 快取
    bg_hashes = {}
    if os.path.exists(bg_manifest_path):
        with open(bg_manifest_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line_str = line.strip()
                parts = line_str.split(",")
                if parts and len(parts) >= 3:
                    # 儲存 bg_id -> hash 的對照 (路徑格式為 a/bg_bg_500030.unity3d)
                    path = parts[0]
                    # 提取數字
                    m_bg = re.search(r'bg_(\d+)', path)
                    if m_bg:
                        bg_hashes[m_bg.group(1)] = parts[2]

    # 4. 讀取角色/CG Manifest 快取
    still_hashes = {}
    if os.path.exists(unit_manifest_path):
        with open(unit_manifest_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line_str = line.strip()
                parts = line_str.split(",")
                if parts and len(parts) >= 3:
                    # 儲存 still_id -> hash (路徑格式為 a/still_2000001.unity3d)
                    path = parts[0]
                    m_still = re.search(r'still_(\d+)', path)
                    if m_still:
                        still_hashes[m_still.group(1)] = parts[2]

    # 5. 下載並導出背景
    # Scenario still previews live in storydata2_assetmanifest rather than
    # unit2_assetmanifest.  Include both sources so movie/CG IDs are not
    # mistakenly reported as missing.
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 3:
                    m_still = re.search(r'storydata_still_(\d+)', parts[0])
                    if m_still:
                        still_hashes[m_still.group(1)] = parts[2]

    for bg_id in sorted(list(bg_ids)):
        bg_hash = bg_hashes.get(bg_id) or bg_hashes.get(f"bg_{bg_id}")
        if not bg_hash:
            # 嘗試直接字串搜尋模糊比對
            for k, val in bg_hashes.items():
                if bg_id in k:
                    bg_hash = val
                    break
        
        if not bg_hash:
            print(f"  ⚠️ 無法在 Manifest 中定位背景 {bg_id} 的 Hash，跳過")
            results["bg_images"].append({"bg_id": bg_id, "status": "not_found"})
            continue
            
        url_bg_bundle = f"{SONET_CDN}/pool/AssetBundles/{bg_hash[:2]}/{bg_hash}"
        dest_bundle = os.path.join(bg_dir, f"temp_bg_{bg_id}.unity3d")
        
        try:
            time.sleep(0.3)
            # 下載
            req_bg = urllib.request.Request(url_bg_bundle, headers=SONET_HEADER)
            with urllib.request.urlopen(req_bg, timeout=20) as res_bg:
                with open(dest_bundle, "wb") as f_b:
                    f_b.write(res_bg.read())
                    
            # 解碼
            env_bg = UnityPy.load(dest_bundle)
            img_extracted = False
            for obj in env_bg.objects:
                if obj.type.name in ["Texture2D", "Sprite"]:
                    data_obj = obj.read()
                    dest_file = os.path.join(bg_dir, f"bg_{bg_id}.webp")
                    data_obj.image.save(dest_file, format="WEBP", lossy=True, quality=85)
                    print(f"  ✅ 成功下載並還原實體背景圖: bg_{bg_id}.webp")
                    results["bg_images"].append({"bg_id": bg_id, "status": "ok", "dest": dest_file})
                    img_extracted = True
                    break
            
            # 手動釋放進程
            del env_bg
            if os.path.exists(dest_bundle):
                try: os.remove(dest_bundle)
                except: pass
                
            if not img_extracted:
                print(f"  ⚠️ 背景 Bundle {bg_id} 中未找到圖片資源")
                results["bg_images"].append({"bg_id": bg_id, "status": "no_texture"})
        except Exception as e:
            print(f"  ❌ 下載背景 {bg_id} 失敗: {e}")
            results["bg_images"].append({"bg_id": bg_id, "status": "error", "error": str(e)})

    # 6. 下載並導出 CG 插畫 (Still)
    for still_id in sorted(list(still_ids)):
        # 提取 ID 數字部分
        still_num = "".join(filter(str.isdigit, still_id))
        still_hash = still_hashes.get(still_num)
        
        if not still_hash:
            # 模糊比對
            for k, val in still_hashes.items():
                if still_num in k:
                    still_hash = val
                    break
                    
        if not still_hash:
            print(f"  ⚠️ 無法在 Manifest 中定位 CG {still_id} 的 Hash，跳過")
            results["still_images"].append({"still_id": still_id, "status": "not_found"})
            continue
            
        url_still_bundle = f"{SONET_CDN}/pool/AssetBundles/{still_hash[:2]}/{still_hash}"
        dest_bundle = os.path.join(still_dir, f"temp_still_{still_num}.unity3d")
        
        try:
            time.sleep(0.3)
            # 下載
            req_still = urllib.request.Request(url_still_bundle, headers=SONET_HEADER)
            with urllib.request.urlopen(req_still, timeout=20) as res_still:
                with open(dest_bundle, "wb") as f_s:
                    f_s.write(res_still.read())
                    
            # 解碼
            env_still = UnityPy.load(dest_bundle)
            img_extracted = False
            for obj in env_still.objects:
                if obj.type.name in ["Texture2D", "Sprite"]:
                    data_obj = obj.read()
                    dest_file = os.path.join(still_dir, f"{still_num}.webp")
                    data_obj.image.save(dest_file, format="WEBP", lossy=True, quality=85)
                    print(f"  ✅ 成功下載並還原實體 CG 插畫: {still_num}.webp")
                    results["still_images"].append({"still_id": still_id, "status": "ok", "dest": dest_file})
                    img_extracted = True
                    break
            
            # 手動釋放進程
            del env_still
            if os.path.exists(dest_bundle):
                try: os.remove(dest_bundle)
                except: pass
                
            if not img_extracted:
                print(f"  ⚠️ CG Bundle {still_id} 中未找到圖片資源")
                results["still_images"].append({"still_id": still_id, "status": "no_texture"})
        except Exception as e:
            print(f"  ❌ 下載 CG {still_id} 失敗: {e}")
            results["still_images"].append({"still_id": still_id, "status": "error", "error": str(e)})
            
    # ──────────────── 7. 自動更新縮圖快取 (story_thumbnails.json) ────────────────
    try:
        thumbnails_path = os.path.join(DASHBOARD_DIR, "data", "story_thumbnails.json")
        # 取得提取出的劇照或背景
        final_still = None
        final_bg = None
        
        # still_ids 裡面可能含有 "still_10050024" 等
        if still_ids:
            # 取得純數字部分
            # Prefer a successfully extracted image.  A movie command can
            # reference an ID with no matching still bundle (for example a
            # pure video ending), which must never become the card thumbnail.
            for s_id in sorted(still_ids):
                num = "".join(filter(str.isdigit, s_id))
                if num and os.path.exists(os.path.join(still_dir, f"{num}.webp")):
                    final_still = num
                    break
        if bg_ids:
            for b_id in bg_ids:
                num = "".join(filter(str.isdigit, str(b_id)))
                if num:
                    final_bg = num
                    break
                    
        existing_thumbs = {}
        if os.path.exists(thumbnails_path):
            try:
                with open(thumbnails_path, 'r', encoding='utf-8') as tf:
                    existing_thumbs = json.load(tf)
            except Exception:
                pass
                
        # 寫入縮圖快取 (若 still 存在則優先 still，不然使用 bg)
        sid_str = str(story_id)
        existing_thumbs[sid_str] = {
            "still_id": str(final_still) if final_still else None,
            "bg_id": str(final_bg) if final_bg else None
        }
        
        os.makedirs(os.path.dirname(thumbnails_path), exist_ok=True)
        with open(thumbnails_path, 'w', encoding='utf-8') as tf:
            json.dump(existing_thumbs, tf, ensure_ascii=False, indent=4)
        print(f"  📝 [Thumbnail] 已自動更新卡片縮圖快取: {sid_str} -> still_id={final_still}, bg_id={final_bg}")
    except Exception as e:
        print(f"  ⚠️ [Thumbnail] 更新卡片縮圖快取失敗: {e}")

    _write_output(args.output, results)
    print(f"\n✅ 實體圖片素材下載完成！報告已寫入 {args.output}")


def cmd_sync_episode(args):
    """一鍵同步特定話數的所有資源（對白 JSON、語音、背景、劇情 CG）。"""
    story_id = args.story_id
    print(f"\n⚡ 開始一鍵完整同步話數 story_id={story_id} 的所有資源...")

    # ──────────────── 1. 下載並解密對白 JSON ────────────────
    ver = _get_sonet_ver()
    manifest_url = f"{SONET_CDN}/Resources/{ver}/Jpn/AssetBundles/Android/manifest/storydata2_assetmanifest"
    h = None
    try:
        manifest_data = _http_get(manifest_url, WEB_HEADER)
        for line in manifest_data.decode('utf-8').splitlines():
            parts = line.strip().split(",")
            if len(parts) >= 3 and f"storydata_{story_id}.unity3d" in parts[0]:
                h = parts[2]
                break
    except Exception as e:
        print(f"  ❌ 載入 Manifest 失敗: {e}", file=sys.stderr)
        sys.exit(1)

    if not h:
        print(f"  ❌ 錯誤：無法在 Manifest 中找到 story_id={story_id} 的 Hash，請確認該話是否實裝。")
        sys.exit(1)

    url_bundle = f"{SONET_CDN}/pool/AssetBundles/{h[:2]}/{h}"
    print(f"  [Step 1] 下載解密對白 JSON (Hash: {h[:8]})...")
    
    dialogues = []
    try:
        bundle_data = _http_get(url_bundle, WEB_HEADER)
        dialogues = _parse_bundle_dialogues(bundle_data)
        os.makedirs(STORY_DIR, exist_ok=True)
        out_path = os.path.join(STORY_DIR, f"{story_id}.json")
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(dialogues, f, ensure_ascii=False, indent=2)
        print(f"    ✅ 對白解密成功: {len(dialogues)} 句對白 -> story/{story_id}.json")
        
        # ── 自動分析並更新 story_thumbnails.json ──
        thumbnails_path = os.path.join(DASHBOARD_DIR, "data", "story_thumbnails.json")
        still_id = None
        bg_id = None
        for d in dialogues:
            # 在對白中尋找 still_id (CG) 或 bg_id (背景)
            # JSON 欄位中可能包含 still 或 background 屬性
            if "still" in d and d["still"] and not still_id:
                still_id = d["still"]
            if "bg" in d and d["bg"] and not bg_id:
                bg_id = d["bg"]
                
        # 如果沒找到，看看是不是 type=still 或者是 background
        # (有些 bundle 是 command 結構)
        if not still_id or not bg_id:
            for d in dialogues:
                if d.get("type") == "still" and not still_id:
                    still_id = d.get("still") or d.get("still_id")
                if d.get("type") == "background" and not bg_id:
                    bg_id = d.get("background") or d.get("bg_id")
                    
        # 讀取並更新縮圖快取
        existing_thumbs = {}
        if os.path.exists(thumbnails_path):
            try:
                with open(thumbnails_path, 'r', encoding='utf-8') as tf:
                    existing_thumbs = json.load(tf)
            except Exception:
                pass
                
        # 寫入目前話數的縮圖關聯
        sid_str = str(story_id)
        existing_thumbs[sid_str] = {
            "still_id": str(still_id) if still_id else None,
            "bg_id": str(bg_id) if bg_id else None
        }
        
        # 回寫
        os.makedirs(os.path.dirname(thumbnails_path), exist_ok=True)
        with open(thumbnails_path, 'w', encoding='utf-8') as tf:
            json.dump(existing_thumbs, tf, ensure_ascii=False, indent=4)
        print(f"    📝 自動更新縮圖快取 (story_thumbnails.json) 成功! (still_id={still_id}, bg_id={bg_id})")
        
    except Exception as e:
        print(f"  ❌ 對白解密或更新縮圖失敗: {e}", file=sys.stderr)
        sys.exit(1)

    # ──────────────── 2. 自動下載語音封包並解碼轉檔 ────────────────
    print("  [Step 2] 同步下載語音封包 (ACB/AWB) 並轉檔...")
    voice_ids = set()
    for d in dialogues:
        voice_id = d.get("voice")
        if voice_id:
            voice_ids.add(voice_id)

    if voice_ids:
        print(f"    發現 {len(voice_ids)} 個語音項目。開始呼叫下載與轉檔管線...")
        
        # 1. 呼叫 download_voices_tw.py 下載特定 story_id 封包
        # 參數帶入 --group {story_id}，例如 2216002
        import subprocess
        print(f"    📥 正在下載語音封包 vo_{story_id}...")
        voice_dl_script = os.path.join(BASE_DIR, "tools", "maintenance", "download_voices_tw.py")
        cmd_dl = [sys.executable, voice_dl_script, "--group", str(story_id)]
        subprocess.run(cmd_dl, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 2. 呼叫 convert_voices.py 解碼剛下載的封包
        # 參數帶入 --prefix v_t_vo_adv_{story_id}，例如 v_t_vo_adv_2216002
        print(f"    🎵 正在解碼與轉換語音至 story_vo/...")
        cmd_cv = [sys.executable, "tools/convert_voices.py", "--prefix", f"v_t_vo_adv_{story_id}"]
        subprocess.run(cmd_cv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        print("    ✅ 語音下載與轉檔處理完成。")
    else:
        print("    ℹ️ 此話無語音")

    # ──────────────── 3. 自動分析背景圖與 CG 並下載 ────────────────
    print("  [Step 3] 分析並下載劇照 CG 與背景圖...")
    class ImageArgs:
        def __init__(self, sid, out):
            self.story_id = sid
            self.output = out
    try:
        cmd_fetch_story_images(ImageArgs(story_id, "tools/temp_image_sync.json"))
        if os.path.exists("tools/temp_image_sync.json"):
            try: os.remove("tools/temp_image_sync.json")
            except: pass
    except Exception as e:
        print(f"    ⚠️ 圖片下載出現部分錯誤 (非致命): {e}")

    print(f"\n🎉 話數 story_id={story_id} 一鍵同步完成！對白、語音與多媒體圖片皆已齊備。")


# ─────────────────────────── CLI 入口 ───────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="PCRD 台版資料抓取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # update-db
    p_db = sub.add_parser("update-db", help="更新台版明文資料庫")
    p_db.add_argument("--output", default="tools/db_update_report.json", help="輸出報告路徑")

    # fetch-stories
    p_stories = sub.add_parser("fetch-stories", help="下載並解密角色個人劇情 JSON")
    p_stories.add_argument("--unit-id", type=int, required=True, help="角色 unit_id")
    p_stories.add_argument("--output", default="tools/story_fetch_report.json", help="輸出報告路徑")

    # fetch-assets
    p_assets = sub.add_parser("fetch-assets", help="下載立繪與頭像素材")
    p_assets.add_argument("--unit-id", type=int, required=True, help="角色 unit_id")
    p_assets.add_argument("--output", default="tools/asset_fetch_report.json", help="輸出報告路徑")

    # report
    p_report = sub.add_parser("report", help="產出驗證報告")
    p_report.add_argument("--unit-id", type=int, required=True, help="角色 unit_id")
    p_report.add_argument("--output", default="tools/fetch_report.md", help="輸出 Markdown 報告路徑")

    # scan-cdn
    p_scan = sub.add_parser("scan-cdn", help="探測 So-net CDN 是否有新版本或預上架素材")
    p_scan.add_argument(
        "--probe-ids",
        help="額外探測的 unit_id 清單（逗號分隔），例如 138401,138501。留空則自動從已知最大 ID 向後推算"
    )
    p_scan.add_argument(
        "--download",
        action="store_true",
        default=True,
        help="偵測到素材時自動下載到 versions/（預設開啟）"
    )
    p_scan.add_argument("--output", default="tools/scan_cdn_report.md", help="輸出偵測報告路徑")

    # fetch-story-voices
    p_sv = sub.add_parser("fetch-story-voices", help="下載並整合指定劇情話數的音檔素材")
    p_sv.add_argument("--story-id", type=int, required=True, help="主線劇情故事 story_id (例如 2001001)")
    p_sv.add_argument("--output", default="tools/voice_fetch_report.json", help="輸出報告路徑")

    # fetch-story-images
    p_si = sub.add_parser("fetch-story-images", help="下載指定劇情話數的 CG 與背景圖片")
    p_si.add_argument("--story-id", type=int, required=True, help="主線劇情故事 story_id (例如 2001001)")
    p_si.add_argument("--output", default="tools/image_fetch_report.json", help="輸出報告路徑")

    # sync-episode
    p_sync = sub.add_parser("sync-episode", help="一鍵完整同步特定話數的所有資源（JSON、語音、背景、CG）")
    p_sync.add_argument("--story-id", type=int, required=True, help="劇情 story_id")

    args = parser.parse_args()
    dispatch = {
        "update-db": cmd_update_db,
        "fetch-stories": cmd_fetch_stories,
        "fetch-assets": cmd_fetch_assets,
        "report": cmd_report,
        "scan-cdn": cmd_scan_cdn,
        "fetch-story-voices": cmd_fetch_story_voices,
        "fetch-story-images": cmd_fetch_story_images,
        "sync-episode": cmd_sync_episode,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
