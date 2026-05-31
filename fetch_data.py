import requests
import json
import os
import sys

# 強制使用 UTF-8 輸出，避免 Windows 終端機編碼問題
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def fetch_gvg_data(server, clanBattleId):
    url = "https://aikurumi.cn/api/pcr/gvgTask"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://aikurumi.cn/gvg"
    }
    merged_data = []

    print(f"Fetching {server} {clanBattleId}...")
    
    for stage in [1, 2, 3, 4, 5]:
        payload = {
            "server": server,
            "clanBattleId": clanBattleId,
            "stage": stage
        }
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code == 200:
                try:
                    data = response.json()
                    tasks = data if isinstance(data, list) else data.get("data", [])
                    if tasks:
                        merged_data.extend(tasks)
                        print(f"Stage {stage}: Found {len(tasks)} tasks.")
                    else:
                        # 這裡不要印出 data 內容，避免編碼報錯
                        print(f"Stage {stage}: No tasks found.")
                except:
                    print(f"Stage {stage}: JSON parsing failed.")
            else:
                print(f"Stage {stage}: HTTP {response.status_code}")
        except Exception as e:
            print(f"Stage {stage}: Connection error.")

    filename = f"gvg_data_{clanBattleId}_{server}.json"
    output_path = os.path.join("dashboard", filename)
    
    if not os.path.exists("dashboard"):
        os.makedirs("dashboard")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged_data, f, ensure_ascii=False, indent=2)
    
    print(f"\nDONE! Total {len(merged_data)} tasks saved to {output_path}")

if __name__ == "__main__":
    fetch_gvg_data("jp", "202604")
