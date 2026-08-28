import urllib.request
import json
import os
import sys
import UnityPy
from PIL import Image

UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'

SONET_CDN = "https://img-pc.so-net.tw/dl"
SONET_HEADER = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'
}
VER = "00600023"

sys.path.insert(0, os.path.join(os.getcwd(), 'tools'))
from pcrd_fetch import _parse_bundle_dialogues, _http_get

DASHBOARD_DIR = "dashboard"
STORY_DIR = os.path.join(DASHBOARD_DIR, "story")
STILL_SCENARIO_DIR = os.path.join(DASHBOARD_DIR, "still", "scenario")
STILL_BG_DIR = os.path.join(DASHBOARD_DIR, "still", "bg")
ICON_DIR = os.path.join(DASHBOARD_DIR, "icon", "unit")
CARD_DIR = os.path.join(DASHBOARD_DIR, "card", "full")

for d in [STORY_DIR, STILL_SCENARIO_DIR, STILL_BG_DIR, ICON_DIR, CARD_DIR]:
    os.makedirs(d, exist_ok=True)

def get_manifest_dict(mname):
    url = f"{SONET_CDN}/Resources/{VER}/Jpn/AssetBundles/Android/manifest/{mname}"
    req = urllib.request.Request(url, headers=SONET_HEADER)
    with urllib.request.urlopen(req, timeout=10) as res:
        data = res.read().decode('utf-8', errors='ignore')
    hashes = {}
    for l in data.splitlines():
        p = l.split(',')
        if len(p) >= 3:
            hashes[p[0]] = p[2].strip()
    return hashes

print("📥 讀取 00600023 Manifests...")
story_hashes = get_manifest_dict("storydata2_assetmanifest")
unit_hashes = get_manifest_dict("unit2_assetmanifest")
bg_hashes = get_manifest_dict("bg2_assetmanifest")

out = []
out.append("=== 《少女與戰車》聯動資源完整下載與解密報告 ===")

all_stills_to_download = set()
all_bgs_to_download = set()

# 1. 解密活動主線 5216001 ~ 5216008
out.append("\n【1. 解密活動劇情對白 JSON】")
for ep in range(1, 9):
    sid = 5216000 + ep
    bname = f"a/storydata_{sid}.unity3d"
    h = story_hashes.get(bname)
    if h:
        url = f"{SONET_CDN}/pool/AssetBundles/{h[:2]}/{h}"
        bdata = _http_get(url, SONET_HEADER)
        dialogues = _parse_bundle_dialogues(bdata)
        dest = os.path.join(STORY_DIR, f"{sid}.json")
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(dialogues, f, ensure_ascii=False, indent=2)
        
        stills = [d.get('still_id') or d.get('still') for d in dialogues if d.get('type') == 'still' and d.get('still') != 'end']
        bgs = [d.get('bg_id') for d in dialogues if d.get('type') == 'background']
        for s in stills:
            if s: all_stills_to_download.add(str(s))
        for b in bgs:
            if b: all_bgs_to_download.add(str(b))
        out.append(f"  ✅ 活動第 {ep} 話 ({sid}.json): {len(dialogues)} 行對白 (含 CG: {stills})")

# 2. 解密 3 位新角色個人好感度劇情 (1392001~1392004, 1393001~1393004, 1394001~1394004)
out.append("\n【2. 解密 3 位新角色個人好感度劇情】")
unit_list = [
    (139201, "美穗"),
    (139301, "真穗"),
    (139401, "艾麗卡")
]
for uid, uname in unit_list:
    for ep in range(1, 5):
        sid = uid * 10 + ep
        bname = f"a/storydata_{sid}.unity3d"
        h = story_hashes.get(bname)
        if h:
            url = f"{SONET_CDN}/pool/AssetBundles/{h[:2]}/{h}"
            bdata = _http_get(url, SONET_HEADER)
            dialogues = _parse_bundle_dialogues(bdata)
            dest = os.path.join(STORY_DIR, f"{sid}.json")
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(dialogues, f, ensure_ascii=False, indent=2)
            
            stills = [d.get('still_id') or d.get('still') for d in dialogues if d.get('type') == 'still' and d.get('still') != 'end']
            bgs = [d.get('bg_id') for d in dialogues if d.get('type') == 'background']
            for s in stills:
                if s: all_stills_to_download.add(str(s))
            for b in bgs:
                if b: all_bgs_to_download.add(str(b))
            out.append(f"  ✅ 【{uname}】第 {ep} 話 ({sid}.json): {len(dialogues)} 行對白 (含 CG: {stills})")

# 3. 下載並導出所有 CG 插畫 WebP
out.append(f"\n【3. 下載並導出 CG 插畫 (共 {len(all_stills_to_download)} 張)】")
for still_id in sorted(list(all_stills_to_download)):
    dest_path = os.path.join(STILL_SCENARIO_DIR, f"{still_id}.webp")
    bname = f"a/storydata_still_{still_id}.unity3d"
    h = story_hashes.get(bname)
    if h:
        url = f"{SONET_CDN}/pool/AssetBundles/{h[:2]}/{h}"
        try:
            bdata = _http_get(url, SONET_HEADER)
            env = UnityPy.load(bdata)
            for obj in env.objects:
                if obj.type.name in ["Texture2D", "Sprite"]:
                    d = obj.read()
                    d.image.save(dest_path, format="WEBP", quality=92)
                    out.append(f"  ✅ 導出 CG: {dest_path} ({os.path.getsize(dest_path)} bytes)")
                    break
        except Exception as e:
            out.append(f"  ❌ CG {still_id} 下載失敗: {e}")

# 4. 下載並導出所有場景背景 WebP
out.append(f"\n【4. 下載並導出背景圖 (共 {len(all_bgs_to_download)} 張)】")
for bg_id in sorted(list(all_bgs_to_download)):
    bg_num = bg_id.zfill(6)
    dest_path = os.path.join(STILL_BG_DIR, f"bg_{bg_num}.webp")
    bname = f"a/bg_bg_{bg_num}.unity3d"
    h = bg_hashes.get(bname)
    if h:
        url = f"{SONET_CDN}/pool/AssetBundles/{h[:2]}/{h}"
        try:
            bdata = _http_get(url, SONET_HEADER)
            env = UnityPy.load(bdata)
            for obj in env.objects:
                if obj.type.name in ["Texture2D", "Sprite"]:
                    d = obj.read()
                    d.image.save(dest_path, format="WEBP", quality=90)
                    out.append(f"  ✅ 導出背景: {dest_path} ({os.path.getsize(dest_path)} bytes)")
                    break
        except Exception as e:
            out.append(f"  ❌ 背景 {bg_id} 下載失敗: {e}")

# 5. 下載 3 位角色的頭像 (139231, 139331, 139431) 與滿星立繪
out.append(f"\n【5. 下載新角色頭像與卡面大圖】")
for uid, uname in unit_list:
    u3 = uid + 30
    # 頭像
    icon_bname = f"a/unit_icon_unit_{u3}.unity3d"
    h_icon = unit_hashes.get(icon_bname)
    if h_icon:
        url = f"{SONET_CDN}/pool/AssetBundles/{h_icon[:2]}/{h_icon}"
        try:
            bdata = _http_get(url, SONET_HEADER)
            env = UnityPy.load(bdata)
            for obj in env.objects:
                if obj.type.name in ["Texture2D", "Sprite"]:
                    d = obj.read()
                    png_path = os.path.join(ICON_DIR, f"{u3}.png")
                    d.image.save(png_path, format="PNG")
                    # 1星版
                    png_path_1 = os.path.join(ICON_DIR, f"{uid + 10}.png")
                    d.image.save(png_path_1, format="PNG")
                    out.append(f"  ✅ 導出頭像: {png_path}")
                    break
        except Exception as e:
            out.append(f"  ❌ 頭像 {u3} 下載失敗: {e}")

    # 卡面立繪
    card_bname = f"a/bg_still_unit_{u3}.unity3d"
    h_card = bg_hashes.get(card_bname)
    if h_card:
        url = f"{SONET_CDN}/pool/AssetBundles/{h_card[:2]}/{h_card}"
        try:
            bdata = _http_get(url, SONET_HEADER)
            env = UnityPy.load(bdata)
            for obj in env.objects:
                if obj.type.name in ["Texture2D", "Sprite"]:
                    d = obj.read()
                    webp_path = os.path.join(CARD_DIR, f"{u3}.webp")
                    d.image.save(webp_path, format="WEBP", quality=90)
                    out.append(f"  ✅ 導出卡面: {webp_path}")
                    break
        except Exception as e:
            out.append(f"  ❌ 卡面 {u3} 下載失敗: {e}")

with open("scratch/garupan_fetch_report.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))

print("All Garupan assets fetched successfully.")
