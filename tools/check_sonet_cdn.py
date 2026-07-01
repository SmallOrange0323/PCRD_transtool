# -*- coding: utf-8 -*-
import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在檢測公主連結佩可 (貪吃佩可 / Pecorine) 全系列換裝角色 CDN 資源 ===")

# 佩可的 unit_id 規律：前兩位與中間為 1001xx
# 100101: 貪吃佩可 (原版)
# 100102: 佩可莉姆（夏日）
# 100103: 佩可莉姆（公主）
# 100104: 佩可莉姆（超載 / Overload）
# 100105: 佩可莉姆（儀式服 / Formal）
# 100106, 100107, 100108 ... 等未來潛在換裝

peco_variants = [
    (100101, "貪吃佩可 (原版)"),
    (100102, "佩可莉姆（夏日）"),
    (100103, "佩可莉姆（公主）"),
    (100104, "佩可莉姆（超載 Overload）"),
    (100105, "佩可莉姆（儀式服 / 其他特殊換裝 100105）"),
    (100106, "佩可莉姆（最新換裝 100106）"),
    (100107, "佩可莉姆（最新換裝 100107）"),
    (100108, "佩可莉姆（最新換裝 100108）"),
]

for uid, name in peco_variants:
    # 測試 3 星頭像 1001xx31.webp 與卡面圖 1001xx31.webp
    icon_url = f"https://redive.estertion.win/icon/unit/{uid}31.webp"
    full_url = f"https://redive.estertion.win/card/full/{uid}31.webp"
    
    icon_status = False
    full_status = False
    
    try:
        req = urllib.request.Request(icon_url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=3)
        if res.status == 200:
            icon_status = True
    except Exception:
        pass

    try:
        req = urllib.request.Request(full_url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=3)
        if res.status == 200:
            full_status = True
    except Exception:
        pass

    if icon_status:
        print(f"✅ [已上架 CDN] ID: {uid} | {name} -> 頭像已可存取 (卡面: {'✅' if full_status else '❌'})")
    else:
        print(f"❌ [未上架 CDN] ID: {uid} | {name} -> 遠端鏡像與 CDN 尚無此 ID 資源")
