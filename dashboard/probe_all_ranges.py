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
    print("Probing version ranges from 00510000 to 00560000...")
    
    # 探測 00510000 ~ 00560000
    for major in range(51, 57):
        for minor in range(0, 15):
            ver = f"00{major}00{minor:02d}"
            if check_version(ver):
                # 如果在這個大版本中找到了，順便探測後面的 15 個
                for extra in range(15, 30):
                    extra_ver = f"00{major}00{extra:02d}"
                    check_version(extra_ver)
                break # 繼續下一個大版本

if __name__ == '__main__':
    main()
