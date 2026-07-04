# -*- coding: utf-8 -*-
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在檢測冬日角色語音在本地 (GitHub 準備區) 的收錄狀態 ===")

# 若菜(冬日) story_id 1387001 ~ 1387004 -> 語音檔 vo_adv_1387001_xxx.m4a
# 栞(冬日) story_id 1388001 ~ 1388004 -> 語音檔 vo_adv_1388001_xxx.m4a

sound_dir = 'dashboard/sound/story_vo'

if not os.path.exists(sound_dir):
    print("❌ 找不到本地語音資料夾")
    sys.exit(0)

# 搜尋是否有檔名包含 1387001 或 1388001 的語音檔案
all_files = os.listdir(sound_dir)

wakana_voices = [f for f in all_files if '138700' in f]
shiori_voices = [f for f in all_files if '138800' in f]

print(f"- 若菜（冬日）[138700] 本地語音檔案數量: {len(wakana_voices)} 個")
if len(wakana_voices) > 0:
    print(f"  樣本: {wakana_voices[:5]}")
    
print(f"- 栞（冬日）[138800] 本地語音檔案數量: {len(shiori_voices)} 個")
if len(shiori_voices) > 0:
    print(f"  樣本: {shiori_voices[:5]}")
