import urllib.request
import json

def get_truth_version():
    url = "https://wthee.xyz/pcr/api/v1/db/info/v2"
    payload = json.dumps({"regionCode": "tw"}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            if res_data.get("status") == 0 and "data" in res_data:
                return res_data["data"]["truthVersion"]
    except:
        pass
    return "00500012"

def main():
    truth_ver = get_truth_version()
    hash1 = "bbc0bd2b64279c702674d8359efcded0"
    hash2 = "a28a97362dc47373"
    
    urls = [
        # 1. 之前試過的 pool
        f"https://img-pc.so-net.tw/dl/pool/AssetBundles/{hash1[:2]}/{hash1}",
        f"https://img-pc.so-net.tw/dl/pool/AssetBundles/{hash2[:2]}/{hash2}",
        # 2. 帶有 truth_version 的 pool
        f"https://img-pc.so-net.tw/dl/Resources/{truth_ver}/Jpn/AssetBundles/Android/pool/AssetBundles/{hash1[:2]}/{hash1}",
        f"https://img-pc.so-net.tw/dl/Resources/{truth_ver}/Jpn/AssetBundles/Android/pool/AssetBundles/{hash2[:2]}/{hash2}",
        # 3. 直接使用路徑
        f"https://img-pc.so-net.tw/dl/Resources/{truth_ver}/Jpn/AssetBundles/Android/a/masterdata_master.unity3d",
        # 4. 沒有 Resources，直接 dl
        f"https://img-pc.so-net.tw/dl/Jpn/AssetBundles/Android/pool/AssetBundles/{hash1[:2]}/{hash1}",
        f"https://img-pc.so-net.tw/dl/Jpn/AssetBundles/Android/a/masterdata_master.unity3d",
    ]
    
    for url in urls:
        print(f"嘗試: {url}")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Dalvik/2.1.0'}, method='HEAD')
            with urllib.request.urlopen(req, timeout=5) as res:
                print(f"  --> 成功！Status: {res.status}, 大小: {res.getheader('Content-Length')} bytes")
        except Exception as e:
            print(f"  --> 失敗: {e}")

if __name__ == "__main__":
    main()
