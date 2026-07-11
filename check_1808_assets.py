# -*- coding: utf-8 -*-
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在檢測 1808001 (禊＆美美＆鏡華) 本地對白與語音存在狀態 ===")

for i in range(1, 5):
    p = f"dashboard/story/180800{i}.json"
    print(f"  - 故事 JSON {p} 是否存在: {os.path.exists(p)}")
    
# 檢測語音
sound_dir = 'dashboard/sound/story_vo'
if os.path.exists(sound_dir):
    files = [f for f in os.listdir(sound_dir) if '180800' in f]
    print(f"  - 本地語音檔案數量: {len(files)} 個")
