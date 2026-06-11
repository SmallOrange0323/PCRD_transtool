# -*- coding: utf-8 -*-
import json
import urllib.request
import os
import sys
import UnityPy

sys.stdout.reconfigure(encoding='utf-8')
UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'

HEADER = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'
}

# 引用 CyGames 序列化規範反序列化
import base64
from enum import Enum
from struct import unpack

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

def get_hash_for_story(ver, target_id):
    url = f"https://img-pc.so-net.tw/dl/Resources/{ver}/Jpn/AssetBundles/Android/manifest/storydata2_assetmanifest"
    req = urllib.request.Request(url, headers=HEADER)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            lines = response.read().decode('utf-8').splitlines()
            for line in lines:
                parts = line.strip().split(",")
                if len(parts) >= 3:
                    path, _, new_hash = parts[0], parts[1], parts[2]
                    if f"storydata_{target_id}.unity3d" in path:
                        return new_hash
    except Exception as e:
        print("Failed to get manifest:", e)
    return None

def download_and_parse(target_id, new_hash, ver):
    url = f"https://img-pc.so-net.tw/dl/pool/AssetBundles/{new_hash[:2]}/{new_hash}"
    req = urllib.request.Request(url, headers=HEADER)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            bundle_data = response.read()
        bundle = UnityPy.load(bundle_data)
        for obj in bundle.objects:
            if obj.type == obj.type.TextAsset:
                data = obj.read()
                if hasattr(data, "script") and data.script:
                    script = data.script
                elif hasattr(data, "m_Script") and data.m_Script:
                    script = data.m_Script
                else:
                    return None
                if isinstance(script, str):
                    script = bytes(script, "utf-8", "surrogateescape")
                
                commands = deserialize_story_raw(script)
                title = ""
                dialogues = []
                for idx, args in commands:
                    if idx == 0 and len(args) >= 1:
                        title = args[0]
                    elif idx == 6 and len(args) >= 2:
                        dialogues.append(f"{args[0]}: {args[1]}")
                return title, dialogues
    except Exception as e:
        print(f"Error parse {target_id}:", e)
    return None

def main():
    ver = "00500015"
    
    # 測試 Prefix 52x, 60x, 61x 的劇情
    targets = [5210001]
    for tid in targets:
        print(f"\n--- Checking Story {tid} ---")
        new_hash = get_hash_for_story(ver, tid)
        if not new_hash:
            print(f"Hash not found for {tid}")
            continue
        res = download_and_parse(tid, new_hash, ver)
        if res:
            title, diags = res
            print(f"Title: {title}")
            print("First 10 lines of dialogues:")
            for d in diags[:10]:
                print(f"  {d}")
        else:
            print("Failed to download or parse")

if __name__ == '__main__':
    main()
