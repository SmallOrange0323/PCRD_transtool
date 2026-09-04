#!/usr/bin/env python3
"""
tools/fetch_reality_avatars.py
從台版官方 CDN 下載第 3 部分支現實劇情角色之專屬頭像 (storydata_icon_unit_*.unity3d)，
並解碼導出為無損/高質量 WebP 與 PNG 格式至 dashboard/icon/unit/ 與 dist_story_map/icon/unit/。
"""

import os
import sys
import re
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

REALITY_AVATARS_MANIFEST = {
    104532: ("空花", "a/storydata_icon_unit_104532.unity3d", "現實便服陶醉空花"),
    105231: ("莉瑪", "a/storydata_icon_unit_105231.unity3d", "現實動物園羊駝本體"),
    103332: ("真陽", "a/storydata_icon_unit_103332.unity3d", "現實草帽格子襯衫真陽"),
    102332: ("綾音", "a/storydata_icon_unit_102332.unity3d", "現實便服綾音"),
    102032: ("美美", "a/storydata_icon_unit_102032.unity3d", "現實羽絨便服美美"),
    101632: ("鈴奈", "a/storydata_icon_unit_101632.unity3d", "現實模特便服鈴奈"),
    103031: ("妮諾", "a/storydata_icon_unit_103031.unity3d", "現實高校校服圍巾妮諾"),
    101332: ("七七香", "a/storydata_icon_unit_101332.unity3d", "現實眼鏡宅女便服七七香"),
    101431: ("霞", "a/storydata_icon_unit_101431.unity3d", "現實初中制服小霧"),
    104331: ("真琴", "a/storydata_icon_unit_104331.unity3d", "現實高校校服背書包真琴"),
    105831: ("貪吃佩可", "a/storydata_icon_unit_105831.unity3d", "現實草帽洋裝尤絲蒂亞娜"),
    101832: ("伊緒", "a/storydata_icon_unit_101832.unity3d", "現實女教師套裝伊緒"),
    101533: ("美里", "a/storydata_icon_unit_101533.unity3d", "現實幼兒園老師便服美里"),
    118031: ("克蕾雅", "a/storydata_icon_unit_118031.unity3d", "現實墨鏡條紋西裝克蕾雅"),
    100531: ("茉莉", "a/storydata_icon_unit_100531.unity3d", "現實無袖運動便服茉莉"),
    100832: ("雪", "a/storydata_icon_unit_100832.unity3d", "現實男高校生西裝校服雪"),
    104833: ("美冬", "a/storydata_icon_unit_104833.unity3d", "現實眼鏡休閒便服美冬"),
    106631: ("祈梨", "a/storydata_icon_unit_106631.unity3d", "現實貝雷帽送報便服祈梨"),
    103232: ("秋乃", "a/storydata_icon_unit_103232.unity3d", "現實千金高校制服秋乃"),
    104632: ("珠希", "a/storydata_icon_unit_104632.unity3d", "現實鯛魚燒工作圍裙珠希"),
    102832: ("咲戀", "a/storydata_icon_unit_102832.unity3d", "現實千金高校制服咲戀"),
}

def load_storydata_hash_map() -> dict:
    manifest_paths = [
        Path("dashboard/versions/cached_manifests/storydata2_assetmanifest.txt"),
        Path("dashboard/versions/cached_manifests/storydata2_assetmanifest_latest_00500030.txt"),
    ]
    hash_map = {}
    for p in manifest_paths:
        if p.exists():
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parts = line.strip().split(",")
                    if len(parts) >= 3:
                        bundle_path, _, h = parts[0], parts[1], parts[2]
                        hash_map[bundle_path] = h
            if hash_map:
                break
    return hash_map

def main():
    print("🔍 載入 storydata2_assetmanifest 哈希表...")
    hash_map = load_storydata_hash_map()
    if not hash_map:
        print("❌ 未找到可用的 storydata2_assetmanifest 快取！", file=sys.stderr)
        sys.exit(1)

    out_dirs = [
        Path("dashboard/icon/unit"),
        Path("dist_story_map/icon/unit"),
    ]
    for d in out_dirs:
        d.mkdir(parents=True, exist_ok=True)

    total = len(REALITY_AVATARS_MANIFEST)
    success = 0
    print(f"🚀 開始下載並解密 {total} 個現實分支專屬頭像素材...\n")

    for uid, (chara, bundle_key, desc) in REALITY_AVATARS_MANIFEST.items():
        h = hash_map.get(bundle_key)
        if not h:
            print(f"  ⚠️ 找不到 {bundle_key} 的 Hash，跳過")
            continue

        url = f"{SONET_CDN}/pool/AssetBundles/{h[:2]}/{h}"
        print(f"  📥 [{chara} ({uid})] {desc} ...")
        try:
            req = urllib.request.Request(url, headers=WEB_HEADER)
            with urllib.request.urlopen(req, timeout=15) as res:
                bundle_data = res.read()

            env = UnityPy.load(bundle_data)
            img = None
            for obj in env.objects:
                if obj.type.name in ("Texture2D", "Sprite"):
                    img = obj.read().image
                    break

            if img is None:
                print(f"    ❌ 未能解碼 Texture2D: {bundle_key}")
                continue

            if img.mode != "RGBA":
                img = img.convert("RGBA")

            for out_dir in out_dirs:
                webp_path = out_dir / f"{uid}.webp"
                png_path = out_dir / f"{uid}.png"
                img.save(webp_path, format="WEBP", quality=95)
                img.save(png_path, format="PNG")

            print(f"    ✅ 成功導出 {uid}.webp / {uid}.png ({img.size[0]}x{img.size[1]})")
            success += 1
        except Exception as e:
            print(f"    ❌ 下載失敗: {e}", file=sys.stderr)

    print(f"\n✨ 完成！成功處理 {success}/{total} 個現實角色頭像。")

if __name__ == '__main__':
    main()
