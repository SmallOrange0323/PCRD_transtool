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
story_id = 1383001
HEADER = {'User-Agent': 'Mozilla/5.0'}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 獲取 Hash
manifest_url = f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/AssetBundles/Android/manifest/storydata2_assetmanifest"
new_hash = None
try:
    req = urllib.request.Request(manifest_url, headers=HEADER)
    with urllib.request.urlopen(req, timeout=15) as res:
        content = res.read().decode('utf-8')
        for line in content.splitlines():
            parts = line.strip().split(",")
            if len(parts) >= 3:
                path, _, val = parts[0], parts[1], parts[2]
                if f"storydata_{story_id}.unity3d" in path:
                    new_hash = val
                    break
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)

url = f"https://img-pc.so-net.tw/dl/pool/AssetBundles/{new_hash[:2]}/{new_hash}"
req = urllib.request.Request(url, headers=HEADER)
with urllib.request.urlopen(req, timeout=15) as res:
    bundle_data = res.read()
    
bundle = UnityPy.load(bundle_data)
for obj in bundle.objects:
    if obj.type.name == "TextAsset":
        data = obj.read()
        print("Available TextAsset attributes:", dir(data))
        script = None
        if hasattr(data, "script") and data.script:
            script = data.script
        elif hasattr(data, "m_Script") and data.m_Script:
            script = data.m_Script
        if script is None:
            print("❌ Cannot find script attribute.")
            sys.exit(1)
        if isinstance(script, str):
            script = bytes(script, "utf-8", "surrogateescape")
            
        # 我們來看看前幾個位元組
        print(f"原始 Script 前 40 位元組 (hex): {script[:40].hex()}")
        
        # 進行 deserialization 並印出第一個對話指令的解密 bytes
        fs = 0
        i = 2
        while i < len(script):
            args = []
            if fs + 2 > len(script): break
            index = int(unpack(">H", script[fs : fs + 2])[0])
            fs += 2
            args.append(index)
            num = i
            while True:
                if fs + 4 > len(script): break
                length = int(unpack(">l", script[fs : fs + 4])[0])
                fs += 4
                if length == 0: break
                if fs + length > len(script): break
                array = script[fs : fs + length]
                fs += length
                args.append(array)
                num += 4 + length
            i = num + 4
            i += 2
            
            # 如果 index == 6 (對話指令)，我們印出它的原始 Base64 解碼前與解碼後的 bytes
            if index == 6 and len(args) >= 3:
                # args[0] 是 index (6)
                # args[1] 是 speaker
                # args[2] 是 words
                speaker_arg = args[1]
                words_arg = args[2]
                
                # 解密 Base64
                def decrypt_arg(arg):
                    array2 = []
                    for byte in arg:
                        if byte > 127:
                            array2.append(255 - byte)
                        else:
                            array2.append(byte)
                    return base64.b64decode(bytearray(array2))
                    
                speaker_raw = decrypt_arg(speaker_arg)
                words_raw = decrypt_arg(words_arg)
                
                print(f"\n🔍 找到對話指令 (Index == 6):")
                print(f"  - 說話者原始位元組 (hex): {speaker_raw.hex()}")
                print(f"  - 對白原始位元組 (hex): {words_raw.hex()}")
                
                # 測試幾種解碼
                for enc in ['utf-8', 'cp950', 'utf-16', 'big5', 'gbk']:
                    try:
                        print(f"    - [{enc}] 解碼結果: 說話者={speaker_raw.decode(enc)}, 對白={words_raw.decode(enc)}")
                    except Exception as e:
                        print(f"    - [{enc}] 解碼失敗: {e}")
                break
        break
