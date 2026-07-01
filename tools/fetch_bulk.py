import requests
import json
import os
import time

def fetch_bulk():
    url = "https://aikurumi.cn/api/pcr/gvgTask"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    months = ["202512", "202601", "202602", "202603", "202604"]
    stages = [3, 4] # 4階段(丁), 5階段(戊)
    merged = []

    for m in months:
        for s in stages:
            print(f"Fetching {m} Stage {s}...")
            try:
                res = requests.post(url, json={"server": "jp", "clanBattleId": m, "stage": s}, headers=headers, timeout=15)
                if res.status_code == 200:
                    data = res.json()
                    tasks = data if isinstance(data, list) else data.get("data", [])
                    merged.extend(tasks)
                    print(f"  - Success: {len(tasks)} tasks")
                else:
                    print(f"  - Failed: HTTP {res.status_code}")
                time.sleep(1) # 避免請求過快
            except Exception as e:
                print(f"  - Error: {e}")

    output = "dashboard/gvg_data_merged_bulk.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"Done! Saved {len(merged)} tasks to {output}")

if __name__ == "__main__":
    fetch_bulk()
