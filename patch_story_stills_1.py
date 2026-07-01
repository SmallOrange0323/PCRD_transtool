# -*- coding: utf-8 -*-
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

file1 = 'dashboard/story/1383001.json'
if os.path.exists(file1):
    with open(file1, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 檢查是否已經有 still 節點
    has_still = any(item.get('type') == 'still' and item.get('still') == '138300101' for item in data)
    if not has_still:
        # 直接追加在陣列最尾部，作為完結插圖
        data.append({"type": "still", "still": "138300101"})
        with open(file1, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print("Successfully appended 138300101 still to 1383001.json tail!")
    else:
        print("1383001.json already has still ID.")
