# -*- coding: utf-8 -*-
import urllib.request
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在修正路徑並從 Estertion 抓取 若菜(冬日)與栞(冬日) 的個人故事全對白語音 ===")

output_dir = 'dashboard/sound/story_vo'
os.makedirs(output_dir, exist_ok=True)

urls_to_download = []

for prefix in ['1387', '1388']:
    for ch in range(1, 5): # 1 ~ 4 話
        story_id = f"{prefix}00{ch}" # 1387001, 1388001 等
        # 在 estertion 上，語音目錄是按這話的完整 story_id 分類的，例如 1387001 底下！
        # 網址格式: https://prcn-sound.estertion.win/story_vo/1387001/vo_adv_1387001_000.m4a
        group_id = story_id
        
        for voice_idx in range(100): # 預估每話最多 100 句對白
            voice_name = f"vo_adv_{story_id}_{voice_idx:03d}"
            url = f"https://prcn-sound.estertion.win/story_vo/{group_id}/{voice_name}.m4a"
            local_path = os.path.join(output_dir, f"{voice_name}.m4a")
            urls_to_download.append((url, local_path, voice_name))

def download_voice(url, local_path, name):
    if os.path.exists(local_path) and os.path.getsize(local_path) > 1024:
        return None
        
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as res:
            with open(local_path, 'wb') as out_f:
                out_f.write(res.read())
        return name
    except Exception as e:
        return None

print(f"正在啟動多執行緒下載 (共 {len(urls_to_download)} 個可能音軌)...")

success_count = 0
with ThreadPoolExecutor(max_workers=16) as executor:
    futures = {executor.submit(download_voice, item[0], item[1], item[2]): item for item in urls_to_download}
    for future in as_completed(futures):
        res = future.result()
        if res:
            success_count += 1
            if success_count % 10 == 0:
                print(f"  已下載 {success_count} 個語音檔案...")

print(f"\n🎉 語音抓取成功！共下載了 {success_count} 個對白 M4A 檔案到本地！")
