# -*- coding: utf-8 -*-
import urllib.request
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://redive.estertion.win/spine/main.min.js?v=250205"
headers = {'User-Agent': 'Mozilla/5.0'}

try:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as res:
        content = res.read().decode('utf-8')
        
    print("正在分析 main.min.js 中加載 Spine 骨架的 URL 拼接邏輯...")
    
    # 搜尋含有 .atlas 或 .skel 的程式碼段落
    lines = content.splitlines()
    for idx, line in enumerate(lines):
        if ".atlas" in line or ".skel" in line or "common" in line:
            # 印出該行前後文
            start = max(0, idx - 2)
            end = min(len(lines), idx + 3)
            print(f"\n--- 匹配行 {idx} 前後文 ---")
            for i in range(start, end):
                print(f"[{i}]: {lines[i]}")
                
except Exception as e:
    print(f"失敗: {e}")
