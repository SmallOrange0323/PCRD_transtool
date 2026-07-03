# -*- coding: utf-8 -*-
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在搜尋專案中所有的 redive_tw.db ===")
for root, dirs, files in os.walk('.'):
    for f in files:
        if f == 'redive_tw.db':
            full_path = os.path.join(root, f)
            size = os.path.getsize(full_path)
            print(f"找到: {full_path} | 大小: {size} bytes")
