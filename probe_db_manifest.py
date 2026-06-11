import sys
import urllib.request
import json

sys.stdout.reconfigure(encoding='utf-8')

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
    print(f"TruthVersion: {truth_ver}")
    
    # 嘗試多種可能的資料庫 manifest 檔名
    possible_names = [
        "masterdata_assetmanifest",
        "master_data_assetmanifest",
        "database_assetmanifest",
        "db_assetmanifest",
        "masterdb_assetmanifest",
        "redive_assetmanifest",
        "redivedb_assetmanifest",
        "master_assetmanifest"
    ]
    
    for name in possible_names:
        url = f"https://img-pc.so-net.tw/dl/Resources/{truth_ver}/Jpn/AssetBundles/Android/manifest/{name}"
        print(f"探測: {url}")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Dalvik/2.1.0'}, method='HEAD')
            with urllib.request.urlopen(req, timeout=5) as res:
                print(f"  --> 成功！HTTP Status: {res.status}, 大小: {res.getheader('Content-Length')} bytes")
        except Exception as e:
            print(f"  --> 失敗: {e}")

if __name__ == "__main__":
    main()
