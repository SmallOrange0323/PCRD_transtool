# -*- coding: utf-8 -*-
import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在探測 So-net 台服 CDN 目前實裝的最高 Manifest 版本號 ===")

# 我們從 00500020 開始一直往後探測到 00500050
headers = {'User-Agent': 'Dalvik/2.1.0'}

highest_ver = "00500025"
found_versions = []

for v_num in range(20, 60):
    ver_str = f"005000{v_num}"
    url = f"https://img-pc.so-net.tw/dl/Resources/{ver_str}/Jpn/Sound/manifest/soundmanifest"
    try:
        req = urllib.request.Request(url, headers=headers, method='HEAD')
        with urllib.request.urlopen(req, timeout=2) as res:
            if res.status == 200:
                print(f"✅ 發現版本號存在: {ver_str}")
                found_versions.append(ver_str)
                highest_ver = ver_str
    except Exception as e:
        pass

print(f"\n探測結束！最高版本號為: {highest_ver}")
print("所有找到的版本:", found_versions)
