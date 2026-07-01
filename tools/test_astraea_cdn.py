# -*- coding: utf-8 -*-
import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在探針檢測最新角色『佩可莉姆（阿斯特萊亞）/ ペコリーヌ（アストライア）』(ID: 138301 / 138331) CDN 資源 ===")

u1 = 138301
u3 = 138331

url_1 = f"https://redive.estertion.win/icon/unit/{u1}.webp"
url_3 = f"https://redive.estertion.win/icon/unit/{u3}.webp"
card_url = f"https://redive.estertion.win/card/full/{u3}.webp"

st1, st3, card_ok = False, False, False
try:
    res = urllib.request.urlopen(urllib.request.Request(url_1, headers={'User-Agent': 'Mozilla/5.0'}), timeout=3)
    if res.status == 200: st1 = True
except: pass

try:
    res = urllib.request.urlopen(urllib.request.Request(url_3, headers={'User-Agent': 'Mozilla/5.0'}), timeout=3)
    if res.status == 200: st3 = True
except: pass

try:
    res = urllib.request.urlopen(urllib.request.Request(card_url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=3)
    if res.status == 200: card_ok = True
except: pass

print(f"結果：")
print(f"- 1星頭像 ({url_1}): {'✅ 已上架' if st1 else '❌ 未上架'}")
print(f"- 3星頭像 ({url_3}): {'✅ 已上架' if st3 else '❌ 未上架'}")
print(f"- 全圖立繪卡面 ({card_url}): {'✅ 已上架' if card_ok else '❌ 未上架'}")
