# -*- coding: utf-8 -*-
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

# 1. 處理 1383001.json
file1 = 'dashboard/story/1383001.json'
if os.path.exists(file1):
    with open(file1, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 尋找 "voice": "vo_adv_1383001_057"
    target_idx = -1
    for idx, item in enumerate(data):
        if item.get('voice') == 'vo_adv_1383001_057':
            target_idx = idx
            break
    
    if target_idx != -1:
        # 檢查是否已經有 still 節點
        has_still = any(item.get('type') == 'still' and item.get('still') == '138300101' for item in data)
        if not has_still:
            data.insert(target_idx, {"type": "still", "still": "138300101"})
            with open(file1, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            print("Successfully patched 1383001.json with still ID 138300101!")
        else:
            print("1383001.json already has still ID.")
    else:
        print("Target voice node not found in 1383001.json")

# 2. 處理 1383004.json
file4 = 'dashboard/story/1383004.json'
if os.path.exists(file4):
    with open(file4, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 尋找 "voice": "vo_adv_1383004_053"
    target_idx = -1
    for idx, item in enumerate(data):
        if item.get('voice') == 'vo_adv_1383004_053':
            target_idx = idx
            break
    
    if target_idx != -1:
        has_still = any(item.get('type') == 'still' and item.get('still') == '138300401' for item in data)
        if not has_still:
            data.insert(target_idx, {"type": "still", "still": "138300401"})
            with open(file4, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            print("Successfully patched 1383004.json with still ID 138300401!")
        else:
            print("1383004.json already has still ID.")
    else:
        print("Target voice node not found in 1383004.json")
