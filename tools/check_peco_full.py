# -*- coding: utf-8 -*-
import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在檢測公主連結佩可 (貪吃佩可 / Pecorine) 官方全換裝資源 ===")

# 探針列表：含全系列佩可 known ID
peco_ids = [
    (100101, 100131, "貪吃佩可 (原版)"),
    (105901, 105931, "佩可莉姆（夏日）"),
    (118501, 118531, "佩可莉姆（公主）"),
    (123701, 123731, "佩可莉姆（超載 Overload）"),
    (129201, 129231, "佩可莉姆（新年）"),
]

# 擴充搜尋 120000~140000 區間可能的新佩可角色
for base_id in [1001, 1059, 1185, 1237, 1292, 1313, 1314, 1330, 1340, 1350]:
    pass

results = []

for u1, u3, name in peco_ids:
    url_1 = f"https://redive.estertion.win/icon/unit/{u1}.webp"
    url_3 = f"https://redive.estertion.win/icon/unit/{u3}.webp"
    
    st1 = False
    st3 = False
    try:
        res = urllib.request.urlopen(urllib.request.Request(url_1, headers={'User-Agent': 'Mozilla/5.0'}), timeout=3)
        if res.status == 200: st1 = True
    except: pass

    try:
        res = urllib.request.urlopen(urllib.request.Request(url_3, headers={'User-Agent': 'Mozilla/5.0'}), timeout=3)
        if res.status == 200: st3 = True
    except: pass

    results.append((name, u1, st1, st3))

for name, u1, st1, st3 in results:
    status_str = "✅ 已上架 CDN (完整)" if (st1 and st3) else ("⚠️ 部分上架" if (st1 or st3) else "❌ 未上架")
    print(f"{status_str} | {name} (ID: {u1}) -> 1星頭像: {'✅' if st1 else '❌'} | 3星頭像: {'✅' if st3 else '❌'}")
