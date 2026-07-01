# -*- coding: utf-8 -*-
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('dashboard/story/1383001.json', 'r', encoding='utf-8') as f:
    dialogue = json.load(f)

print("=== 正在搜尋 1383001.json 中的特殊節點 (插畫、背景、影片) ===")
special_nodes = [item for item in dialogue if 'type' in item or 'stillId' in item or 'bg' in item or 'still' in item]
print(f"找到 {len(special_nodes)} 個特殊節點：")
for idx, node in enumerate(special_nodes[:15]):
    print(f"  [{idx}]", node)
