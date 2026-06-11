# -*- coding: utf-8 -*-
import urllib.request
import urllib.error
import sys

sys.stdout.reconfigure(encoding='utf-8')

HEADER = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'
}

def check_url(url):
    req = urllib.request.Request(url, headers=HEADER)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"[SUCCESS] {url} -> 200")
            return True
    except urllib.error.HTTPError as e:
        print(f"[HTTP ERROR] {url} -> {e.code}")
    except Exception as e:
        print(f"[ERROR] {url} -> {e}")
    return False

def main():
    ver = "00510006"
    url = f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/AssetBundles/Android/manifest/masterdata2_assetmanifest"
    check_url(url)

if __name__ == '__main__':
    main()
