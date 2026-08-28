# -*- coding: utf-8 -*-
"""
[Network Diagnostic / Probe-only]
搜尋台服 00500026 版 soundmanifest 中的冬日角色語音封包。
"""
import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8')

manifest_url = "https://img-pc.so-net.tw/dl/Resources/00500026/Jpn/Sound/manifest/soundmanifest"
headers = {'User-Agent': 'Dalvik/2.1.0'}

print("=== 正在搜尋台服 00500026 版 soundmanifest 中的冬日角色語音封包 ===")

try:
    req = urllib.request.Request(manifest_url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as res:
        content = res.read().decode('utf-8', errors='ignore')
        
    lines = content.splitlines()
    found = []
    for line in lines:
        if '1387' in line or '1388' in line:
            found.append(line.strip())
            
    print(f"找到 {len(found)} 個匹配項：")
    for f in found[:30]:
        print("  ", f)
except Exception as e:
    print("出錯:", e)
