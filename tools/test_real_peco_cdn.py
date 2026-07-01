# -*- coding: utf-8 -*-
import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在測試台服 So-net 官方資料庫記錄之佩可全系列真實 ID CDN 資源 ===")

peco_real_list = [
    (105801, 105831, "貪吃佩可 (原版)"),
    (107501, 107531, "貪吃佩可（夏日）"),
    (111801, 111831, "貪吃佩可（新年）"),
    (121001, 121031, "貪吃佩可（超載）"),
    (127901, 127931, "貪吃佩可（聖誕節）"),
    (180401, 180431, "貪吃佩可（公主）"),
]

for u1, u3, name in peco_real_list:
    url_1 = f"https://redive.estertion.win/icon/unit/{u1}.webp"
    url_3 = f"https://redive.estertion.win/icon/unit/{u3}.webp"
    card_url = f"https://redive.estertion.win/card/full/{u3}.webp"
    
    st1, st3, card_ok = False, False, False
    try:
        res = urllib.request.urlopen(urllib.request.Request(url_1, headers={'User-Agent': 'Mozilla/5.0'}), timeout=2)
        if res.status == 200: st1 = True
    except: pass

    try:
        res = urllib.request.urlopen(urllib.request.Request(url_3, headers={'User-Agent': 'Mozilla/5.0'}), timeout=2)
        if res.status == 200: st3 = True
    except: pass

    try:
        res = urllib.request.urlopen(urllib.request.Request(card_url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=2)
        if res.status == 200: card_ok = True
    except: pass

    print(f"✅ [CDN 實裝確認] {name:16s} (ID: {u1}) -> 1星頭像: {'✅' if st1 else '❌'} | 3星頭像: {'✅' if st3 else '❌'} | 立繪卡面: {'✅' if card_ok else '❌'}")
