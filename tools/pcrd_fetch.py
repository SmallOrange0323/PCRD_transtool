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
import sqlite3
import sys
import time
import urllib.request
from struct import unpack

sys.stdout.reconfigure(encoding='utf-8')

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
    """從本地 DB 取得最新資源版本號。"""
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
    return "00500024"


def _get_story_ids_from_db(unit_id):
    """從 DB 查詢角色個人劇情的 story_id 清單。"""
    if not os.path.exists(DB_PATH):
        return []
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        # chara_story_status 存放每話劇情
        cur.execute(
            "SELECT story_id FROM chara_story_status WHERE unit_id = ? ORDER BY story_id",
            (unit_id,)
        )
        rows = cur.fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        # Fallback：用規則推算 (unit_id * 10 + 1~4)
        return [unit_id * 10 + i for i in range(1, 5)]


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
                if idx == 12 and args:
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
    u1 = unit_id
    u3 = unit_id + 30
    ver = _get_sonet_ver()

    print(f"🎨 開始下載 unit_id={unit_id} 的美術素材（ver={ver}）...")
    os.makedirs(ICON_DIR, exist_ok=True)
    os.makedirs(CARD_DIR, exist_ok=True)

    assets = [
        {
            "url": f"{SONET_CDN}/Resources/{ver}/Jpn/Unit/Icon/unit_icon_{u1}.webp",
            "dest": os.path.join(ICON_DIR, f"unit_icon_{u1}.webp"),
            "desc": "1星頭像"
        },
        {
            "url": f"{SONET_CDN}/Resources/{ver}/Jpn/Unit/Icon/unit_icon_{u3}.webp",
            "dest": os.path.join(ICON_DIR, f"unit_icon_{u3}.webp"),
            "desc": "3星頭像"
        },
        {
            "url": f"{SONET_CDN}/Resources/{ver}/Jpn/Card/Full/card_full_{u3}.webp",
            "dest": os.path.join(CARD_DIR, f"card_full_{u3}.webp"),
            "desc": "3星立繪大圖"
        },
    ]

    results = {"unit_id": unit_id, "assets": []}
    for item in assets:
        time.sleep(0.3)
        try:
            data = _http_get(item["url"], SONET_HEADER, timeout=10)
            with open(item["dest"], 'wb') as f:
                f.write(data)
            results["assets"].append({"desc": item["desc"], "status": "ok", "dest": item["dest"]})
            print(f"  ✅ {item['desc']} → {os.path.basename(item['dest'])}")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                results["assets"].append({"desc": item["desc"], "status": "not_found_on_cdn"})
                print(f"  ⚠️ {item['desc']} CDN 尚未上線 (404)，跳過")
            else:
                results["assets"].append({"desc": item["desc"], "status": "error", "error": str(e)})
                print(f"  ❌ {item['desc']} 下載失敗: {e}", file=sys.stderr)
        except Exception as e:
            results["assets"].append({"desc": item["desc"], "status": "error", "error": str(e)})
            print(f"  ❌ {item['desc']} 下載失敗: {e}", file=sys.stderr)

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

    if not is_first_run:
        for line in added_lines:
            m = re.search(r'storydata_(\d{7})\.unity3d', line)
            if not m:
                continue
            story_id = int(m.group(1))
            first_digit = story_id // 1000000   # 取百萬位

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

    args = parser.parse_args()
    dispatch = {
        "update-db": cmd_update_db,
        "fetch-stories": cmd_fetch_stories,
        "fetch-assets": cmd_fetch_assets,
        "report": cmd_report,
        "scan-cdn": cmd_scan_cdn,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
