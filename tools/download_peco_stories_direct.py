# -*- coding: utf-8 -*-
import os
import sys
import base64
import urllib.request
from struct import unpack
import UnityPy

sys.stdout.reconfigure(encoding='utf-8')

# UnityPy 設定
UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'
if hasattr(UnityPy, 'environment') and hasattr(UnityPy.environment, 'Environment'):
    UnityPy.environment.Environment.version_engine = '2021.3.20f1'

ver = "00500024"
story_ids = [1383001, 1383002, 1383003, 1383004]
HEADER = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "dashboard", "story")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 1. 劇情解密算法
def deserialize_command(data):
    index = data[0]
    args = []
    if len(data) > 1:
        args = data[1:]
    array = []
    for arg in args:
        array2 = []
        for byte in arg:
            if byte > 127:
                array2.append(255 - byte)
            else:
                array2.append(byte)
        try:
            str_ = base64.b64decode(bytearray(array2))
            # 台版劇情解密後的 bytes 本身即是 utf-8
            array.append(str_.decode('utf-8', errors='ignore'))
        except Exception:
            array.append("")
    return index, array

def deserialize_story_raw(bytes_):
    commands = []
    fs = 0
    raw_commands = []
    i = 2
    while i < len(bytes_):
        args = []
        if fs + 2 > len(bytes_):
            break
        index = int(unpack(">H", bytes_[fs : fs + 2])[0])
        fs += 2
        args.append(index)
        num = i
        while True:
            if fs + 4 > len(bytes_):
                break
            length = int(unpack(">l", bytes_[fs : fs + 4])[0])
            fs += 4
            if length == 0:
                break
            if fs + length > len(bytes_):
                break
            array = bytes_[fs : fs + length]
            fs += length
            args.append(array)
            num += 4 + length
        i = num + 4
        raw_commands.append(args)
        i += 2
    for raw_command in raw_commands:
        if len(raw_command) > 1:
            commands.append(deserialize_command(raw_command))
    return commands

# 2. 獲取遠端 Hash 清單
manifest_url = f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/AssetBundles/Android/manifest/storydata2_assetmanifest"
print(f"🔍 正在載入故事 Manifest 以獲取 Hash: {manifest_url}")
hash_map = {}
try:
    req = urllib.request.Request(manifest_url, headers=HEADER)
    with urllib.request.urlopen(req, timeout=15) as res:
        content = res.read().decode('utf-8')
        for line in content.splitlines():
            parts = line.strip().split(",")
            if len(parts) >= 3:
                path, _, new_hash = parts[0], parts[1], parts[2]
                for sid in story_ids:
                    if f"storydata_{sid}.unity3d" in path:
                        hash_map[sid] = new_hash
except Exception as e:
    print(f"❌ 載入 Manifest 失敗: {e}")
    sys.exit(1)

# 3. 下載並解析各個故事
for story_id in story_ids:
    new_hash = hash_map.get(story_id)
    if not new_hash:
        print(f"⚠️ 未能找到故事 {story_id} 的 Hash")
        continue
        
    url = f"https://img-pc.so-net.tw/dl/pool/AssetBundles/{new_hash[:2]}/{new_hash}"
    print(f"\n📥 下載並還原故事 {story_id} -> {url}")
    
    try:
        req = urllib.request.Request(url, headers=HEADER)
        with urllib.request.urlopen(req, timeout=15) as res:
            bundle_data = res.read()
            
        bundle = UnityPy.load(bundle_data)
        dialogues = []
        
        for obj in bundle.objects:
            if obj.type.name == "TextAsset":
                data = obj.read()
                if hasattr(data, "script") and data.script:
                    script = data.script
                elif hasattr(data, "m_Script") and data.m_Script:
                    script = data.m_Script
                else:
                    continue
                if isinstance(script, str):
                    script = bytes(script, "utf-8", "surrogateescape")
                
                commands = deserialize_story_raw(script)
                
                current_voice = None
                for idx, args in commands:
                    if idx == 12 and len(args) >= 1:
                        current_voice = args[0]
                    elif idx == 6 and len(args) >= 2:
                        speaker = args[0]
                        words = args[1]
                        
                        # 繁中人名微調與主公大人稱呼
                        if speaker in ["コッコロ", "可可蘿"]:
                            speaker = "可可蘿"
                            words = words.replace("主人", "主公大人")
                        elif speaker in ["ペコリーヌ", "佩可"]:
                            speaker = "貪吃佩可"
                        elif speaker in ["キャル", "凱留"]:
                            speaker = "凱留"
                        elif speaker in ["ユウキ", "祐樹", "騎士君"]:
                            speaker = "佑樹"
                            
                        dialogues.append({
                            "name": speaker,
                            "words": words,
                            "voice": current_voice
                        })
                        current_voice = None
                        
        if dialogues:
            import json
            out_file = os.path.join(OUTPUT_DIR, f"{story_id}.json")
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(dialogues, f, ensure_ascii=False, indent=4)
            print(f"  ✅ 成功解析故事 {story_id}，共 {len(dialogues)} 句對話已寫入 {out_file}")
            
    except Exception as e:
        print(f"  ❌ 還原解析故事 {story_id} 失敗: {e}")

print("\n🎉 個人劇情文本下載解析流程完畢！")
