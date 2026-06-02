# -*- coding: utf-8 -*-
"""
小胡桃 (aikurumi.cn) API 嗅探器 - 深度 Nginx /api/ 與 BaseUrl 重點定位版
"""

import urllib.request
import re
import ssl

def sniff():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    js_url = "https://aikurumi.cn/main.2a718014f38ed066.js"
    print(f"[INFO] 正在抓取邏輯 JS 檔案: {js_url}")
    
    req = urllib.request.Request(js_url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=12) as response:
            js_content = response.read().decode('utf-8', errors='ignore')
            print(f"[INFO] 成功抓取！開始定位 BaseUrl 與 HttpInterceptor 拼接邏輯...")
            
            # 1. 搜尋包含了 "/pcr/" 或 "charaList" 被呼叫的更完整程式碼
            target = "charaList"
            matches = re.finditer(target, js_content)
            print(f"\n[RESULT] 尋找 '{target}' 的完整使用上下文:")
            for m in matches:
                start = max(0, m.start() - 100)
                end = min(len(js_content), m.end() + 100)
                snippet = js_content[start:end].replace("\n", " ").strip()
                print(f"  * ... {snippet} ...")

            # 2. 尋找與 "/api"、"baseUrl"、"intercept"、"http" 等變數定義相關的程式碼
            # 看看有沒有像是 "baseUrl" 或是環境變數的定義
            base_url_matches = re.finditer(r'baseUrl|apiRoot|apiHost', js_content, re.IGNORECASE)
            print("\n[RESULT] 尋找與 'baseUrl' 相關的上下文:")
            count = 0
            for m in base_url_matches:
                start = max(0, m.start() - 60)
                end = min(len(js_content), m.end() + 60)
                snippet = js_content[start:end].replace("\n", " ").strip()
                print(f"  * ... {snippet} ...")
                count += 1
                if count >= 10:
                    break

            # 3. 搜尋 Angular 的 HTTP 攔截器 (HttpInterceptor) 常用模式
            # 攔截器常用 clone({ url: ... }) 的方式來拼接網域或字首
            intercept_matches = re.finditer(r'clone\(\{', js_content)
            print("\n[RESULT] 尋找 HttpInterceptor clone 複製請求的上下文:")
            count = 0
            for m in intercept_matches:
                start = max(0, m.start() - 80)
                end = min(len(js_content), m.end() + 80)
                snippet = js_content[start:end].replace("\n", " ").strip()
                print(f"  * ... {snippet} ...")
                count += 1
                if count >= 10:
                    break

    except Exception as e:
        print(f"[ERROR] 抓取 JS 失敗: {e}")

if __name__ == "__main__":
    sniff()
