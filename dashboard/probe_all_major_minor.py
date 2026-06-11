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
    url = f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/AssetBundles/Android/manifest/masterdata2_assetmanifest"
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
    print("Starting deep concurrency probe for TruthVersion in ranges 0051 ~ 0055...")
    
    versions = []
    # 探測 0051, 0052, 0053, 0054, 0055, 0056 的 0000 ~ 0200 minor 版本
    for major in [51, 52, 53, 54, 55, 56]:
        for minor in range(0, 200):
            versions.append(f"00{major}{minor:04d}")
            
    print(f"Total versions to probe: {len(versions)}")
    
    found = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(check_version, ver): ver for ver in versions}
        for future in concurrent.futures.as_completed(futures):
            ver, res = future.result()
            if res:
                print(f"[FOUND] Valid TruthVersion: {ver}")
                found.append(ver)
                
    print(f"\nProbe finished. Found valid versions: {sorted(found)}")

if __name__ == '__main__':
    main()
