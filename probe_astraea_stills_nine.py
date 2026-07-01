# -*- coding: utf-8 -*-
import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在探針檢測阿斯特萊亞佩可 (138301) 所有的潛在 9 位數劇情 CG 圖片 ===")

# 阿斯特萊亞佩可 ID 是 138301 (去掉後面 2 位是 1383)
# 9 位數劇照 ID 規律通常是：10[六位ID]01, 10[六位ID]02...
# 亦即 1013830101 或是 101383011, 101383021 ...
# 或者是 138300101, 138300102 ... 等
# 或者是 101383001, 101383002...

candidates = []
for i in range(1, 10):
    candidates.append(f"1013830{i}1")
    candidates.append(f"10138300{i}")
    candidates.append(f"138300{i}01")
    candidates.append(f"138300{i}11")
    candidates.append(f"10138301{i}")

found = []
for cid in candidates:
    url = f"https://redive.estertion.win/card/story/{cid}.webp"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=1.5)
        if res.status == 200:
            print(f"✅ [發現 CG 圖片] ID: {cid} -> {url}")
            found.append(cid)
    except:
        pass

print("\n探針結束，共找到:", found)
