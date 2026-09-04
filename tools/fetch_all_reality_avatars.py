#!/usr/bin/env python3
"""
tools/fetch_all_reality_avatars.py
從台版官方 CDN 全量下載 PCRD 115+ 位角色之現實生活專屬頭像 (storydata_icon_unit_*.unity3d)，
並解碼導出為高品質 WebP 與 PNG 格式至 dashboard/icon/unit/ 與 dist_story_map/icon/unit/。
同時導出全角色現實名稱至頭像 ID 之完整映射 JSON。
"""

import os
import sys
import re
import json
import sqlite3
import urllib.request
from pathlib import Path
from PIL import Image

try:
    import UnityPy
    UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'
except ImportError:
    print("❌ 請先安裝 UnityPy: pip install UnityPy", file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.pcrd_fetch import SONET_CDN, WEB_HEADER

KNOWN_EXACT = {
    104532: ("空花", "遠見 空花"),
    105231: ("莉瑪", "莉瑪"),
    103332: ("真陽", "野戶 真陽"),
    102332: ("綾音", "北條 綾音"),
    102032: ("美美", "茜 美美"),
    101632: ("鈴奈", "美波 鈴奈"),
    103031: ("妮諾", "妮諾・珠貝爾"),
    101332: ("七七香", "丹野 七七香"),
    101431: ("霞", "霧原 霞"),
    104331: ("真琴", "安芸 真琴"),
    105831: ("貪吃佩可", "尤絲蒂亞娜‧F‧阿斯特賴亞"),
    101832: ("伊緒", "支倉 伊緒"),
    101533: ("美里", "愛川 美里"),
    118031: ("克蕾雅", "克蕾雅‧波洋希亞"),
    100531: ("茉莉", "織原 茉莉"),
    100832: ("雪", "虹村 雪"),
    104833: ("美冬", "大泉 美冬"),
    106631: ("祈梨", "一之瀨 祈梨"),
    103232: ("秋乃", "藤堂 秋乃"),
    104632: ("珠希", "宮坂 珠希"),
    102832: ("咲戀", "佐佐木 咲戀"),
    106832: ("拉比林斯達", "模索路 晶"),
    107032: ("似似花", "現士場 黑江"),
    107131: ("克莉絲提娜", "克莉絲提娜・摩根"),
    106931: ("霸瞳皇帝", "千里 真那"),
    106432: ("雪菲", "阿賀斗 紫布菜"),
    126532: ("萊拉耶爾", "祓樹 艾爾"),
}

def load_manifest_icons() -> dict:
    manifest_paths = [
        Path("dashboard/versions/cached_manifests/storydata2_assetmanifest.txt"),
        Path("dashboard/versions/cached_manifests/storydata2_assetmanifest_latest_00500030.txt"),
    ]
    manifest_icons = {}
    for p in manifest_paths:
        if p.exists():
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parts = line.strip().split(",")
                    if len(parts) >= 3:
                        bpath, _, h = parts[0], parts[1], parts[2]
                        m = re.search(r'storydata_icon_unit_(\d+)\.unity3d', bpath)
                        if m:
                            uid = int(m.group(1))
                            manifest_icons[uid] = (bpath, h)
            if manifest_icons:
                break
    return manifest_icons

def build_reality_character_catalog(manifest_icons: dict) -> tuple:
    db_path = Path("dashboard/redive_tw.db")
    if not db_path.exists():
        raise FileNotFoundError(f"找不到資料庫: {db_path}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT unit_name, unit_id, face_type, bg_id FROM actual_unit_background")
    actual_rows = cur.fetchall()

    cur.execute("SELECT unit_id, unit_name FROM unit_profile")
    profile_dict = dict(cur.fetchall())

    cur.execute("SELECT unit_id, unit_name FROM unit_data WHERE unit_id >= 100000 AND unit_id < 200000")
    unit_data_dict = dict(cur.fetchall())

    characters = {}

    for real_name, uid, face_type, bg_id in actual_rows:
        base_id = (uid // 100) * 100
        base_name = profile_dict.get(base_id + 1) or unit_data_dict.get(base_id + 1)
        if not base_name:
            for u, n in unit_data_dict.items():
                if (u // 100) * 100 == base_id:
                    base_name = n.split('（')[0].split('(')[0]
                    break
        if not base_name:
            base_name = real_name.split(' ')[-1]

        if '＆' in base_name or '&' in base_name or '少戰' in base_name:
            continue

        main_name = base_name.split('（')[0].split('(')[0]
        if main_name not in characters:
            characters[main_name] = {
                'main_name': main_name,
                'base_id': base_id,
                'real_names': set(),
                'aliases': set(),
                'chosen_avatar_id': None,
                'bundle_path': None,
                'hash': None
            }
        characters[main_name]['real_names'].add(real_name)
        characters[main_name]['real_names'].add(real_name.replace(' ', ''))
        characters[main_name]['real_names'].add(real_name.replace('・', '‧'))
        characters[main_name]['real_names'].add(real_name.replace('‧', '・'))

    for k_id, (k_c, k_r) in KNOWN_EXACT.items():
        if k_c not in characters:
            b_id = (k_id // 100) * 100
            characters[k_c] = {
                'main_name': k_c,
                'base_id': b_id,
                'real_names': {k_r, k_r.replace(' ', ''), k_r.replace('・', '‧'), k_r.replace('‧', '・')},
                'aliases': set(),
                'chosen_avatar_id': k_id,
                'bundle_path': manifest_icons.get(k_id, (None, None))[0],
                'hash': manifest_icons.get(k_id, (None, None))[1]
            }

    for u, n in unit_data_dict.items():
        pure = n.split('（')[0].split('(')[0]
        if pure in characters:
            characters[pure]['aliases'].add(n)
            characters[pure]['aliases'].add(pure)

    for name, data in characters.items():
        b_id = data['base_id']
        matched_exact = None
        for k_id, (k_c, k_r) in KNOWN_EXACT.items():
            if k_c == name:
                matched_exact = k_id
                break
        if matched_exact and matched_exact in manifest_icons:
            data['chosen_avatar_id'] = matched_exact
            data['bundle_path'] = manifest_icons[matched_exact][0]
            data['hash'] = manifest_icons[matched_exact][1]
            continue

        cands = [i for i in manifest_icons if (i // 100) * 100 == b_id]
        chosen = None
        for tail in [32, 33, 31, 21, 12, 11]:
            target = b_id + tail
            if target in cands:
                chosen = target
                break
        if chosen:
            data['chosen_avatar_id'] = chosen
            data['bundle_path'] = manifest_icons[chosen][0]
            data['hash'] = manifest_icons[chosen][1]

    if '貪吃佩可' in characters:
        characters['貪吃佩可']['aliases'].update(['佩可', '佩可莉姆', '尤絲蒂亞娜', '貪吃佩可'])
    if '凱留' in characters:
        characters['凱留']['aliases'].update(['凱留', '百地希留耶', '希留耶', '凱留（插班生）'])
    if '可可蘿' in characters:
        characters['可可蘿']['aliases'].update(['可可蘿', '棗可蘿', '可可蘿（遊俠）', '可可蘿（公主）'])
    if '拉比林斯達' in characters:
        characters['拉比林斯達']['aliases'].update(['拉比林斯達', '模索路晶', '晶'])
    if '似似花' in characters:
        characters['似似花']['aliases'].update(['似似花', '現士場黑江', '黑江'])
    if '霸瞳皇帝' in characters:
        characters['霸瞳皇帝']['aliases'].update(['霸瞳皇帝', '霸瞳', '千里真那', '真那'])

    conn.close()

    name_to_avatar_id = {}
    avatar_id_to_bundles = {}

    for name, data in characters.items():
        aid = data['chosen_avatar_id']
        if not aid or not data['hash']:
            continue
        avatar_id_to_bundles[aid] = (data['bundle_path'], data['hash'], name)
        name_to_avatar_id[name] = aid
        for rn in data['real_names']:
            name_to_avatar_id[rn] = aid
        for al in data['aliases']:
            name_to_avatar_id[al] = aid

    return name_to_avatar_id, avatar_id_to_bundles, characters

def main():
    print("🔍 載入 storydata2_assetmanifest 快取...")
    manifest_icons = load_manifest_icons()
    if not manifest_icons:
        print("❌ 未找到可用的 storydata2_assetmanifest 快取！", file=sys.stderr)
        sys.exit(1)

    print("📊 比對 redive_tw.db 構建全角色現實生活頭像清單...")
    name_to_id, avatar_bundles, characters = build_reality_character_catalog(manifest_icons)

    print(f"✅ 成功構建 {len(characters)} 位角色之現實檔案，共 {len(avatar_bundles)} 個專屬現實頭像 Bundle！")
    print(f"📝 涵蓋 {len(name_to_id)} 個真實姓名/別名/換裝映射！\n")

    mapping_json_path = Path("dashboard/avatar_reality_mapping.json")
    with open(mapping_json_path, "w", encoding="utf-8") as f:
        json.dump(name_to_id, f, ensure_ascii=False, indent=2)
    print(f"💾 已儲存映射字典至 {mapping_json_path}")

    out_dirs = [
        Path("dashboard/icon/unit"),
        Path("dist_story_map/icon/unit"),
    ]
    for d in out_dirs:
        d.mkdir(parents=True, exist_ok=True)

    total = len(avatar_bundles)
    success = 0
    skipped = 0
    failed = 0

    print(f"🚀 開始下載並解碼 {total} 個角色現實頭像...\n")

    for uid, (bundle_path, h, chara_name) in sorted(avatar_bundles.items()):
        target_webp = out_dirs[0] / f"{uid}.webp"
        target_png = out_dirs[0] / f"{uid}.png"
        dist_webp = out_dirs[1] / f"{uid}.webp"
        dist_png = out_dirs[1] / f"{uid}.png"

        if target_webp.exists() and target_webp.stat().st_size > 0 and dist_webp.exists() and dist_webp.stat().st_size > 0:
            skipped += 1
            success += 1
            continue

        url = f"{SONET_CDN}/pool/AssetBundles/{h[:2]}/{h}"
        print(f"  📥 [{chara_name} ({uid})] {bundle_path} ...")
        try:
            req = urllib.request.Request(url, headers=WEB_HEADER)
            with urllib.request.urlopen(req, timeout=20) as res:
                bundle_data = res.read()

            env = UnityPy.load(bundle_data)
            img = None
            for obj in env.objects:
                if obj.type.name in ("Texture2D", "Sprite"):
                    img = obj.read().image
                    break

            if img is None:
                print(f"    ❌ 未能解碼 Texture2D: {bundle_path}")
                failed += 1
                continue

            if img.mode != "RGBA":
                img = img.convert("RGBA")

            for out_dir in out_dirs:
                w_path = out_dir / f"{uid}.webp"
                p_path = out_dir / f"{uid}.png"
                img.save(w_path, format="WEBP", quality=95)
                img.save(p_path, format="PNG")

            print(f"    ✅ 成功導出 {uid}.webp / {uid}.png ({img.size[0]}x{img.size[1]})")
            success += 1
        except Exception as e:
            print(f"    ❌ 下載失敗: {e}", file=sys.stderr)
            failed += 1

    print(f"\n✨ 下載與解密完成！總計: {total}, 成功/已存在: {success} (已跳過快取: {skipped}), 失敗: {failed}")

if __name__ == '__main__':
    main()
