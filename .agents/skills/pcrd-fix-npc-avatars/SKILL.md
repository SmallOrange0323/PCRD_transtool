---
name: pcrd-fix-npc-avatars
description: >-
  診斷並修復新 NPC 角色（非可玩角色）在劇情閱讀器中頭像破圖的問題。從 So-net CDN 的 storydata2_assetmanifest 找到對應 AssetBundle，下載後用 UnityPy 解密匯出 PNG，更新 npc_avatars.json 映射，並處理前端 ID 規整化規則以確保頭像正確顯示。使用時機：新主線章節加入了從未出現過的 NPC，或發現特定 NPC 名字顯示文字佔位符而非頭像圖片時。
---

# PCRD NPC 頭像修復 Skill

## Overview

當新章節引入新 NPC 角色（非可玩 unit_id），前端可能因為缺少頭像圖片或 `npc_avatars.json` 映射而顯示文字佔位符（如「芙蕾」「黎薩」等兩字縮寫），而不是官方頭像。

本 Skill 提供完整的診斷 → 下載 → 解密 → 映射更新的標準化修復流程。

> **重要：NPC 頭像的取得方式**
>
> NPC 頭像**不是明文 WebP，也不在 `unit2_assetmanifest` 中**。
> 正確來源是 **`storydata2_assetmanifest`**，以 `storydata_icon_unit_{id}.unity3d` 格式的 AssetBundle 加密儲存於 CDN pool。
> 必須透過 UnityPy 解密後才能取得圖片。
>
> So-net CDN 上的 `Resources/{ver}/Jpn/Unit/Icon/unit_icon_{id}.webp` 路徑對 NPC ID 全部回應 404。
> estertion 日服鏡像同樣不提供這些 NPC 頭像。

## Dependencies

- Python `UnityPy` 套件（解密 AssetBundle）
- 本地 `dashboard/versions/version_history.json`（取得目前版本號）

---

## 前端 NPC 頭像的核心規則（必讀）

### 1. `npc_avatars.json` 映射

`dashboard/data/npc_avatars.json` 儲存 `"中文名稱" -> unit_id` 的映射。前端的 `avatar-service.js` 用此檔案將劇情中出現的說話者名稱轉換為 unit_id，再生成頭像路徑。

若 NPC 名稱未在此映射中，前端找不到 unit_id，直接顯示文字佔位符。

### 2. ID 規整化規則（`avatar-service.js` 的 `getAvatarHtml` 邏輯）

```javascript
const baseId = Math.floor(unitId / 100) * 100;
const mainId = (unitId < 190000) ? (baseId + 31) : unitId;
// 前端載入的實體檔案名：icon/unit/{mainId}.png
```

| unit_id 範圍 | 規則 | 範例 |
|---|---|---|
| `>= 190000`（NPC 專用區間） | 直接使用原始 ID | `195212` → 載入 `195212.png` |
| `< 190000`（小數字 NPC，如幻境龍后） | 轉換為 `(unitId / 100 取整) * 100 + 31` | `107411` → 載入 `107431.png` |

---

## Step 1：從 storydata2_assetmanifest 查詢 Bundle Hash

```python
import urllib.request, json, os

HEADER = {'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'}

# 讀取目前版本號
hist = json.load(open("dashboard/versions/version_history.json", encoding="utf-8"))
ver = hist.get("last_version", "00500030")

# 下載（或讀取快取）storydata2_assetmanifest
manifest_cache = "dashboard/versions/cached_manifests/storydata2_assetmanifest.txt"
if not os.path.exists(manifest_cache):
    url = f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/AssetBundles/Android/manifest/storydata2_assetmanifest"
    req = urllib.request.Request(url, headers=HEADER)
    with urllib.request.urlopen(req, timeout=15) as res:
        data = res.read().decode("utf-8", errors="ignore")
    os.makedirs(os.path.dirname(manifest_cache), exist_ok=True)
    with open(manifest_cache, "w", encoding="utf-8") as f:
        f.write(data)
else:
    data = open(manifest_cache, encoding="utf-8", errors="ignore").read()

# 查詢特定 NPC 的 bundle hash
# Manifest 格式：path,md5_hash,pool_hash,group,size
# pool URL 使用第三欄（16位 hex）
npc_id = 193711  # 以芙蕾雅為例
for line in data.splitlines():
    if f"storydata_icon_unit_{npc_id}.unity3d" in line:
        parts = line.strip().split(",")
        pool_hash = parts[2]
        print(f"找到 {npc_id}: pool_hash={pool_hash}")
        break
```

---

## Step 2：下載並用 UnityPy 解密

```python
import urllib.request, os, UnityPy

HEADER = {'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'}
UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'

ICON_DIR = "dashboard/icon/unit"
os.makedirs(ICON_DIR, exist_ok=True)

def download_and_decrypt_npc_icon(npc_id, pool_hash):
    """從 CDN pool 下載 storydata_icon_unit bundle 並解密出 PNG。"""
    url = f"https://img-pc.so-net.tw/dl/pool/AssetBundles/{pool_hash[:2]}/{pool_hash}"
    print(f"  下載: {url}")
    req = urllib.request.Request(url, headers=HEADER)
    with urllib.request.urlopen(req, timeout=20) as res:
        bundle_data = res.read()
    print(f"  下載完成: {len(bundle_data)} bytes")

    env = UnityPy.load(bundle_data)
    extracted = False
    for obj in env.objects:
        if obj.type.name in ["Texture2D", "Sprite"]:
            d = obj.read()
            dest_png  = os.path.join(ICON_DIR, f"{npc_id}.png")
            dest_webp = os.path.join(ICON_DIR, f"{npc_id}.webp")
            d.image.save(dest_png, format="PNG")
            d.image.save(dest_webp, format="WEBP", quality=90)
            print(f"  ✅ 解密成功: {dest_png} ({os.path.getsize(dest_png)} bytes)")
            extracted = True
            break
    if not extracted:
        print(f"  ❌ Bundle 中未找到 Texture2D/Sprite")
    return extracted

# 執行（pool_hash 從 Step 1 取得）
download_and_decrypt_npc_icon(193711, "bb38fab7cc14923a")
download_and_decrypt_npc_icon(195212, "81fee211fc45a83a")
download_and_decrypt_npc_icon(195611, "5c3f5e1014fb0d20")
```

---

## Step 3：處理 ID 規整化（針對 unit_id < 190000 的 NPC）

```python
import shutil, os

ICON_DIR = "dashboard/icon/unit"

# 幻境龍后 (107411 < 190000)，前端載入的是 107431
def normalize_npc_icon(unit_id):
    if unit_id >= 190000:
        return  # 無需規整化
    base_id = (unit_id // 100) * 100
    norm_id = base_id + 31  # 107431

    for ext in [".png", ".webp"]:
        src = os.path.join(ICON_DIR, f"{unit_id}{ext}")
        dst = os.path.join(ICON_DIR, f"{norm_id}{ext}")
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
            print(f"  ✅ 規整化拷貝: {unit_id}{ext} -> {norm_id}{ext}")

normalize_npc_icon(107411)  # 幻境龍后
```

---

## Step 4：更新 npc_avatars.json

```python
import json

npc_path = "dashboard/data/npc_avatars.json"
npc = json.load(open(npc_path, encoding="utf-8"))

new_mappings = {
    "芙蕾雅": 193711,
    "黎薩": 195212,
    "阿爾莎特": 195611,
    "幻境龍后": 107411,
}

modified = False
for name, uid in new_mappings.items():
    if name not in npc:
        npc[name] = uid
        print(f"  ✅ 新增映射: {name} -> {uid}")
        modified = True

if modified:
    with open(npc_path, "w", encoding="utf-8") as f:
        json.dump(npc, f, ensure_ascii=False, indent=2)
    print("  💾 npc_avatars.json 已更新")
```

---

## Step 5：同步至 dist_story_map

```python
import shutil, os

src_dir = "dashboard/icon/unit"
dst_dir = "dist_story_map/icon/unit"
os.makedirs(dst_dir, exist_ok=True)

# 複製本次修復的相關檔案（原始 ID + 規整化 ID）
files_to_sync = [
    "193711.png", "193711.webp",
    "195212.png", "195212.webp",
    "195611.png", "195611.webp",
    "107411.png", "107411.webp",
    "107431.png", "107431.webp",  # 規整化
]
for fn in files_to_sync:
    src = os.path.join(src_dir, fn)
    dst = os.path.join(dst_dir, fn)
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f"  ✅ 同步至 dist: {fn}")
```

---

## 如何找到未知 NPC 的 pool_hash

若遇到新 NPC，在 storydata2_assetmanifest 中搜尋：

```python
# 從本地快取的 storydata2_assetmanifest.txt 搜尋
manifest_path = "dashboard/versions/cached_manifests/storydata2_assetmanifest.txt"
data = open(manifest_path, encoding="utf-8", errors="ignore").read()

target_id = 196011  # 替換為新 NPC 的 unit_id
found = False
for line in data.splitlines():
    if f"storydata_icon_unit_{target_id}" in line:
        parts = line.strip().split(",")
        print(f"path={parts[0]}, pool_hash={parts[2]}, size={parts[4]}")
        found = True
if not found:
    print(f"{target_id} 尚未在 storydata2_assetmanifest 中找到，可能尚未實裝")
```

若本地快取是舊的（新章節上線後），先重新下載 manifest：

```bash
python tools/pcrd_fetch.py fetch-story-images --story-id {新話 story_id}
# 這個指令會自動更新 storydata2_assetmanifest 快取
```

---

## 完整 Checklist

- [ ] 在 `storydata2_assetmanifest` 中找到 NPC 對應的 `storydata_icon_unit_{id}.unity3d` 條目
- [ ] 從 CDN pool 下載 AssetBundle 並用 UnityPy 解密出 PNG/WebP
- [ ] `dashboard/icon/unit/{unit_id}.png` 存在（解密後輸出）
- [ ] 若 `unit_id < 190000`，`dashboard/icon/unit/{baseId+31}.png` 也存在（規整化拷貝）
- [ ] `npc_avatars.json` 中已有該 NPC 名稱的映射（值為原始 unit_id）
- [ ] `dist_story_map/icon/unit/` 下有以上所有檔案的副本
- [ ] 執行 `pcrd-deploy-website` Skill 推送上線

---

## Common Mistakes

1. **誤以為 NPC 頭像是明文 WebP**：`https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/Unit/Icon/unit_icon_{id}.webp` 對 NPC ID 全部 404，必須走 storydata2_assetmanifest + UnityPy 解密路徑。
2. **在 unit2_assetmanifest 中找不到 NPC 條目**：unit2 manifest 只有可玩角色（unit_id < 190000 的主要角色）。190000 以上的 NPC 以及部分特殊 NPC 存放在 storydata2_assetmanifest。
3. **只下載原始 unit_id 的圖，忘記規整化拷貝**：`unit_id < 190000` 的 NPC 前端會去讀 `baseId+31` 的圖，若只有 `107411.png` 沒有 `107431.png`，依然破圖。
4. **npc_avatars.json 中填入規整化後的 ID**：值應填入原始 `unit_id`（如 `107411`），而非 `107431`。前端自行計算規整化。
5. **storydata2_assetmanifest 快取過舊**：新章節上線後，舊的快取不含新 NPC 的 bundle 條目。需重新下載 manifest 或執行 `fetch-story-images` 更新快取。
6. **dist_story_map 未同步**：只更新了 `dashboard/icon/unit/` 本地目錄，線上網頁不受影響，必須同步至 dist。
