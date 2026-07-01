# -*- coding: utf-8 -*-
import glob
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在統計分析所有個人劇情 JSON 檔案中是否含有 still (圖片) 標註 ===")

# 個人劇情的 ID 通常是 7 位數，以 1 開頭 (如 1001001.json ~ 1800000.json)
files = glob.glob('dashboard/story/1*.json')
total_files = len(files)

files_with_still = 0
sample_stills = []

for f in files:
    try:
        dialogue = json.load(open(f, encoding='utf-8'))
        has_still = any('still' in item or ('type' in item and item['type'] == 'still') for item in dialogue)
        if has_still:
            files_with_still += 1
            if len(sample_stills) < 5:
                sample_stills.append(f)
    except:
        pass

print(f"\n📊 統計報告：")
print(f"- 共有 {total_files} 個個人劇情 JSON 檔案")
print(f"- 其中含有 still (圖片) 標註的檔案有: {files_with_still} 個")
print(f"- 比例為: {files_with_still / total_files * 100:.2f}%")
print(f"- 含有 still 標註的樣版檔案: {sample_stills}")
