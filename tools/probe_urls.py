# -*- coding: utf-8 -*-
import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8')

urls = [
    'https://smallorange0323.github.io/PCRD_transtool/story_map.html',
    'https://smallorange0323.github.io/PCRD_transtool/dashboard/characters.js',
    'https://smallorange0323.github.io/PCRD_transtool/characters.js'
]

print("🔍 開始探測 GitHub Pages 線上路由狀態...")
for url in urls:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as res:
            print(f"  🟢 [200 OK] {url}")
    except urllib.error.HTTPError as e:
        print(f"  🔴 [{e.code} {e.reason}] {url}")
    except Exception as e:
        print(f"  ⚠️ [ERROR: {e}] {url}")
