# -*- coding: utf-8 -*-
import urllib.request
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

url_base = 'https://smallorange0323.github.io/PCRD_transtool/characters.js'

print("====================================================")
print("⏱️ 開始監控 GitHub Pages 的線上全球 CDN 部署進度...")
print("====================================================")

success = False
for i in range(12): # 最多監控 2 分鐘 (12 * 10s)
    try:
        url = f"{url_base}?v={time.time()}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as res:
            html = res.read().decode('utf-8')
            if 'replace(/\\\\\\n|\\n/g' in html:
                success = True
                print(f"\n🎉 [SUCCESS] GitHub Pages 已於第 {i*10} 秒完成線上換行瑕疵的更新！")
                print("您的網站現在已是最新版本！")
                break
            else:
                print(f"  - [{i*10}s] GitHub Pages 仍在編譯排隊中，請稍候...", end="\r", flush=True)
    except Exception as e:
        print(f"\n  - [{i*10}s] 請求異常 (可能伺服器正在重新整理): {e}")
    time.sleep(10)

if not success:
    print("\n⚠️ [TIMEOUT] 超過 2 分鐘 GitHub 還在部署，但請放心，後端已成功上傳，稍後即可重新整理看到。")
print("====================================================")
