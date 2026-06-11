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
    
    # 嘗試下載主 manifest 檔
    url = f"https://img-pc.so-net.tw/dl/Resources/{truth_ver}/Jpn/AssetBundles/Android/manifest/manifest"
    print(f"下載主 manifest: {url}")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Dalvik/2.1.0'})
        with urllib.request.urlopen(req, timeout=10) as res:
            content = res.read()
            print(f"下載成功！大小: {len(content)} bytes")
            lines = content.decode('utf-8', errors='ignore').splitlines()
            print("前 20 行內容:")
            for l in lines[:20]:
                print("  ", l)
                
            # 搜尋有沒有包含 db 的行
            found_db = [l for l in lines if "db" in l.lower()]
            print(f"\n找到 {len(found_db)} 筆包含 db 的行：")
            for f in found_db:
                print("  ", f)
    except Exception as e:
        print(f"下載失敗: {e}")

if __name__ == "__main__":
    main()
