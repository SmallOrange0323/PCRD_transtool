# -*- coding: utf-8 -*-
import urllib.request
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://redive.estertion.win/spine/main.min.js?v=250205"
headers = {'User-Agent': 'Mozilla/5.0'}

print("正在從 EsterTion 下載 main.min.js...")
try:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as res:
        content = res.read().decode('utf-8')
        
    print(f"下載成功！長度: {len(content)} 字元。")
    
    # 尋找含有 .json 或是 AJAX 載入列表的特徵
    json_files = re.findall(r'[\w\-/]+\.json', content)
    print(f"\n在 JS 中找到的 JSON 檔案關聯:")
    print(json_files)
    
    # 尋找與 skeletonList 或角色清單載入相關的關鍵字
    # 例如：找到 $.get、$.post、fetch 等
    for match in re.finditer(r'(\.getJSON|fetch|\.ajax|\.get)\([^)]+\)', content):
        print(f"\n匹配到 AJAX 請求: {match.group(0)}")
        
except Exception as e:
    print(f"出錯: {e}")
