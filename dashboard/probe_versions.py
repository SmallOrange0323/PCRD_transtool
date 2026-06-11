# -*- coding: utf-8 -*-
import urllib.request
import urllib.error
import sys

sys.stdout.reconfigure(encoding='utf-8')

HEADER = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'
}

def check_version(ver):
    url = f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/AssetBundles/Android/manifest/storydata2_assetmanifest"
    req = urllib.request.Request(url, headers=HEADER)
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            print(f"[FOUND] Version {ver} has storydata2_assetmanifest (200)")
            return True
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"[HTTP] Version {ver} status {e.code}")
    except Exception as e:
        pass
    return False

def main():
    print("Probing versions in range 00500000 to 00520000...")
    # 嘗試探測 00510000 ~ 00510030
    for i in range(0, 30):
        ver = f"005100{i:02d}"
        check_version(ver)
        
    # 嘗試探測 00500000 ~ 00500030
    for i in range(0, 30):
        ver = f"005000{i:02d}"
        check_version(ver)

if __name__ == '__main__':
    main()
