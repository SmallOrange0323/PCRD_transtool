# -*- coding: utf-8 -*-
import os
import sqlite3
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

def download_card(card_id, save_dir):
    url = f"https://redive.estertion.win/card/full/{card_id}.webp"
    save_path = os.path.join(save_dir, f"{card_id}.webp")
    
    # 如果已經下載過，跳過
    if os.path.exists(save_path):
        return card_id, "EXISTS"
        
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read()
            with open(save_path, 'wb') as f:
                f.write(data)
        return card_id, "SUCCESS"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # 404 很正常，因為不是每個角色都有 1★, 6★ 卡面
            return card_id, "404"
        return card_id, f"HTTP_{e.code}"
    except Exception as e:
        return card_id, f"ERROR: {str(e)}"

def main():
    db_path = os.path.join(os.path.dirname(__file__), "..", "redive_tw.db")
    save_dir = os.path.join(os.path.dirname(__file__), "..", "card")
    os.makedirs(save_dir, exist_ok=True)
    
    print(f"[Info] 開始讀取資料庫: {db_path}")
    if not os.path.exists(db_path):
        print(f"[Error] 資料庫不存在: {db_path}")
        return
        
    # 讀取所有的 Group ID
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT (unit_id / 100) FROM unit_data WHERE unit_id < 200000 AND unit_id >= 100000")
    group_ids = [row[0] for row in cur.fetchall() if row[0] is not None]
    conn.close()
    
    print(f"[Info] 成功查詢到 {len(group_ids)} 個角色 Group ID")
    
    # 建立下載任務列表 (1★, 3★, 6★)
    # 備份卡面後綴：11 (1★), 31 (3★), 61 (6★)
    suffixes = ["11", "31", "61"]
    card_ids = []
    for gid in group_ids:
        for suffix in suffixes:
            card_ids.append(f"{gid}{suffix}")
            
    print(f"[Info] 總共規劃下載 {len(card_ids)} 張卡面大圖，啟動多線程下載中...")
    
    success_count = 0
    exists_count = 0
    not_found_count = 0
    error_count = 0
    
    # 限制執行緒數量，避免對目標網站造成太大的負擔
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(download_card, cid, save_dir): cid for cid in card_ids}
        
        for future in as_completed(futures):
            cid = futures[future]
            try:
                card_id, status = future.result()
                if status == "SUCCESS":
                    success_count += 1
                    print(f"[Downloaded] {card_id} 成功下載")
                elif status == "EXISTS":
                    exists_count += 1
                elif status == "404":
                    not_found_count += 1
                else:
                    error_count += 1
                    print(f"[Failed] {card_id} 失敗: {status}")
            except Exception as e:
                error_count += 1
                print(f"[Exception] {cid} 崩潰: {str(e)}")
                
    print("\n=== 下載報告 ===")
    print(f"成功下載: {success_count} 張")
    print(f"本地已存在: {exists_count} 張")
    print(f"CDN無此卡面(404): {not_found_count} 張")
    print(f"失敗數: {error_count} 張")
    print(f"卡面儲存於: {os.path.abspath(save_dir)}")

if __name__ == '__main__':
    main()
