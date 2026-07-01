# -*- coding: utf-8 -*-
import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== 正在強效探針搜尋 So-net 台服 CDN 上的『佩可莉姆（阿斯特萊亞）』(ID: 138301/138331) 劇情與技能數據 ===")

headers = {'User-Agent': 'Mozilla/5.0'}

def check_url(url, desc):
    try:
        req = urllib.request.Request(url, headers=headers)
        res = urllib.request.urlopen(req, timeout=2.5)
        if res.status == 200:
            print(f"✅ [台服 CDN 已實裝] {desc} -> 可正常存取！({url})")
            return True
    except Exception:
        pass
    print(f"❌ [台服 CDN 尚未實裝/404] {desc}")
    return False

# 1. 檢測個人劇情聲音檔 (測試多種可能的故事 ID 格式)
print("\n--- 1. 個人劇情聲音檔 (Story Voice) 測試 ---")
check_url("https://redive.estertion.win/sound/story_vo/vo_adv_1138301_000.m4a", "個人劇情 Episode 1 首句語音 (ID: 1138301)")
check_url("https://redive.estertion.win/sound/story_vo/vo_adv_138301_000.m4a", "個人劇情 Episode 1 首句語音 (ID: 138301)")
check_url("https://redive.estertion.win/sound/story_vo/vo_adv_1064008_000.m4a", "對照組: 已知雪菲個人劇情語音")

# 2. 檢測戰鬥/技能聲音檔 (Battle / Skill Voice)
print("\n--- 2. 角色戰鬥與技能語音 (Battle/Skill Voice) 測試 ---")
check_url("https://redive.estertion.win/sound/unit_battle_voice/vo_btl_138301_ub.m4a", "必殺技 UB 語音 (vo_btl_138301_ub)")
check_url("https://redive.estertion.win/sound/unit_battle_voice/vo_btl_138301_skill_1.m4a", "技能 1 語音 (vo_btl_138301_skill_1)")

# 3. 檢測角色動態 Spine 戰鬥骨架圖
print("\n--- 3. 角色戰鬥 Spine 骨架資源測試 ---")
check_url("https://redive.estertion.win/spine/unit/138331/138331.atlas", "3星戰鬥 Spine Atlas 骨架檔 (138331)")
