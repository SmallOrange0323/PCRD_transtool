# -*- coding: utf-8 -*-
import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8')

chara_id = 138301
u3 = chara_id + 30
headers = {'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'}

print(f"開始在台版 CDN 探測包含佩可 (ID: {chara_id}) 美術資源的 TruthVersion...")

# 檢測 00500015 到 00500060 之間的所有可能版本
found_versions = []

for v_num in range(15, 60):
    ver = f"0050{v_num:04d}"
    # 測試 3星頭像
    url = f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/Unit/Icon/unit_icon_{u3}.webp"
    try:
        req = urllib.request.Request(url, headers=headers, method='HEAD')
        with urllib.request.urlopen(req, timeout=3) as res:
            if res.status == 200:
                print(f"🔥 [找到實裝版本] TruthVersion: {ver} 含有 3星頭像資源！")
                found_versions.append(ver)
    except Exception:
        pass

if found_versions:
    print(f"\n探測結束！共找到 {len(found_versions)} 個可用資源版本。最新可用版本為: {found_versions[-1]}")
else:
    print("\n❌ 未能在該版本區間內找到佩可的頭像資源，可能是 CDN 的檔案命名或路徑在新角色上有別的規則。")
