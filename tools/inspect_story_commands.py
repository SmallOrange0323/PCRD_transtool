# -*- coding: utf-8 -*-
import sqlite3
import os
import sys
import json
import urllib.request
import base64
from struct import unpack
import UnityPy

sys.stdout.reconfigure(encoding='utf-8')
UnityPy.config.FALLBACK_UNITY_VERSION = '2021.3.20f1'

ver = "00500024"
story_id = 1383001
headers = {'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; Pixel 3 XL Build/QQ3A.200805.001)'}

# 複製解密算法
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
    req = urllib.request.Request(url, headers=headers)
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

new_hash = get_hash_for_story(ver, story_id)
if not new_hash:
    print("Hash not found")
    sys.exit(1)

url = f"https://img-pc.so-net.tw/dl/pool/AssetBundles/{new_hash[:2]}/{new_hash}"
req = urllib.request.Request(url, headers=headers)
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
                continue
            if isinstance(script, str):
                script = bytes(script, "utf-8", "surrogateescape")
            
            commands = deserialize_story_raw(script)
            print("--- 故事腳本前 50 個控制命令 ---")
            for idx, (cmd_type, args) in enumerate(commands[:50]):
                # 篩選掉純空字元命令，只保留有實質內容的
                non_empty = [a for a in args if a.strip()]
                if non_empty:
                    print(f"[{idx}] 類型 {cmd_type}: {non_empty}")
except Exception as e:
    print(f"失敗: {e}")
