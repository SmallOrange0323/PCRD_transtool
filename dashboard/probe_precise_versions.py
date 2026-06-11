# -*- coding: utf-8 -*-
import urllib.request
import urllib.error
import concurrent.futures
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
            return ver, True
    except urllib.error.HTTPError as e:
        pass
    except Exception as e:
        pass
    return ver, False

def main():
    print("Starting concurrent probe for 0050 and 0051 minor versions...")
    
    versions = []
    # 00510000 ~ 00510150
    for i in range(0, 150):
        versions.append(f"0051{i:04d}")
    # 00500000 ~ 00500150
    for i in range(0, 150):
        versions.append(f"0050{i:04d}")
        
    found = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = {executor.submit(check_version, ver): ver for ver in versions}
        for future in concurrent.futures.as_completed(futures):
            ver, res = future.result()
            if res:
                print(f"[FOUND] Version {ver} has storydata2_assetmanifest!")
                found.append(ver)
                
    print(f"\nProbe finished. Found versions: {found}")

if __name__ == '__main__':
    main()
