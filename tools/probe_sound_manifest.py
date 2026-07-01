# -*- coding: utf-8 -*-
import urllib.request
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')

ver = "00500024"
headers = {'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'}

# 測試幾種可能的 So-net 語音 Manifest 網址
manifest_urls = [
    f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/Sound/manifest/soundmanifest2",
    f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/Sound/manifest/sound2_assetmanifest",
    f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/AssetBundles/Android/manifest/sound2_assetmanifest",
    f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/AssetBundles/Android/manifest/soundmanifest2"
]

print("正在探測台服 CDN 語音 Manifest 網址...")

found_url = None
for url in manifest_urls:
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as res:
            if res.status == 200:
                print(f"✅ 找到語音 Manifest: {url}")
                found_url = url
                # 印出前 5 行內容
                content = res.read().decode('utf-8', errors='ignore')
                print("--- 前 5 行內容 ---")
                for line in content.splitlines()[:5]:
                    print(line)
                print("-------------------")
                break
    except Exception as e:
        print(f"❌ 嘗試失敗 {url}: {e}")

if found_url:
    # 搜尋是否有佩可(138301/1383001)關聯的語音檔案 (例如 vo_adv_1383001, v_1383001 等)
    try:
        req = urllib.request.Request(found_url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as res:
            content = res.read().decode('utf-8', errors='ignore')
            
            print("\n正在搜尋佩可相關音軌...")
            matches = []
            for line in content.splitlines():
                if "1383001" in line or "138301" in line:
                    matches.append(line)
            
            if matches:
                print(f"🎯 找到 {len(matches)} 筆佩可關聯音軌！")
                for m in matches[:10]:
                    print(m)
            else:
                print("❌ 未在語音 Manifest 中找到佩可關聯音軌。")
    except Exception as e:
        print(f"搜尋出錯: {e}")
