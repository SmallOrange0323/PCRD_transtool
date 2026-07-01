# -*- coding: utf-8 -*-
import urllib.request
import sys
import json
import os

sys.stdout.reconfigure(encoding='utf-8')

ver = "00500024"
headers = {'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'}

url = f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/AssetBundles/Android/manifest/manifest"

print(f"正在嘗試從台服 CDN 下載主 Manifest: {url}")
try:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as res:
        content = res.read().decode('utf-8', errors='ignore')
        
    print(f"下載成功！共 {len(content.splitlines())} 行。")
    
    # 1. 搜尋包含 .awb 或 .acb 的行
    print("\n正在檢索語音包 (.awb / .acb) 行...")
    awb_lines = []
    peco_lines = []
    
    for line in content.splitlines():
        if ".awb" in line or ".acb" in line:
            awb_lines.append(line)
            if "138301" in line or "1383001" in line or "31383" in line:
                peco_lines.append(line)
        elif "138301" in line or "1383001" in line or "31383" in line:
            # 其他含有佩可 ID 的行
            peco_lines.append(line)
            
    print(f"總共找到 {len(awb_lines)} 筆語音包資料。")
    print(f"找到 {len(peco_lines)} 筆佩可 (138301 / 31383) 關聯資料。")
    
    if peco_lines:
        print("\n--- 佩可關聯資料展示 ---")
        for line in peco_lines:
            print(line)
    else:
        # 如果沒找到，展示前 15 筆音檔
        print("\n--- 語音包前 15 筆展示 ---")
        for line in awb_lines[:15]:
            print(line)

except Exception as e:
    print(f"失敗: {e}")
