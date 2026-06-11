# -*- coding: utf-8 -*-
import json
import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8')

HEADER = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'
}

def get_truth_version():
    url = "https://wthee.xyz/pcr/api/v1/db/info/v2"
    payload = json.dumps({"regionCode": "tw"}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            if res_data.get("status") == 0 and "data" in res_data:
                return res_data["data"]["truthVersion"]
    except Exception as e:
        print("wthee failed:", e)
    return "00500012"

def main():
    ver = get_truth_version()
    print("Truth Version:", ver)
    
    url = f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/AssetBundles/Android/manifest/storydata2_assetmanifest"
    req = urllib.request.Request(url, headers=HEADER)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            lines = response.read().decode('utf-8').splitlines()
    except Exception as e:
        print("Failed to download manifest:", e)
        return

    print(f"Total entries in manifest: {len(lines)}")
    
    # 提取所有的 storydata_XXXXXXX
    story_ids = []
    for line in lines:
        parts = line.split(",")
        if len(parts) > 0:
            path = parts[0]
            # 格式通常是 a/storydata_XXXXXXX.unity3d
            if "storydata_" in path:
                try:
                    # 取得 XXXXXXX 部分
                    id_str = path.split("storydata_")[1].split(".")[0]
                    story_ids.append(int(id_str))
                except Exception:
                    pass
                    
    story_ids = sorted(list(set(story_ids)))
    print(f"Total unique story IDs in manifest: {len(story_ids)}")
    
    # 按前綴分群統計
    groups = {}
    for sid in story_ids:
        prefix = sid // 100000
        groups[prefix] = groups.get(prefix, 0) + 1
        
    print("\nStory ID Distribution in Manifest:")
    for prefix in sorted(groups.keys()):
        count = groups[prefix]
        min_id = min([sid for sid in story_ids if sid // 100000 == prefix])
        max_id = max([sid for sid in story_ids if sid // 100000 == prefix])
        print(f"  Prefix {prefix}x (ID {prefix*100000}~{(prefix+1)*100000-1}): Count={count}, Min={min_id}, Max={max_id}")

    # 特別看一下 50xxxxx (活動) 之後的區間，有沒有 51xxxxx, 52xxxxx, 8xxxxxx 或是 9xxxxxx
    print("\nRecent Story IDs in Manifest (Prefix 5x / 9x / others):")
    recent_sids = [sid for sid in story_ids if sid >= 5000000]
    # 列出各個大前綴的最新幾個
    for p in [50, 51, 52, 70, 90]:
        matching = [sid for sid in story_ids if sid // 100000 == p]
        if matching:
            print(f"  Prefix {p}x latest 10: {matching[-10:]}")

if __name__ == '__main__':
    main()
