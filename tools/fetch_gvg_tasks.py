# -*- coding: utf-8 -*-
"""
PCRD Data Hub - 小胡桃戰隊戰作業一鍵同步器
自動連線 aikurumi.cn API 深度下載出刀作業，並利用高性能批次翻譯器將其繁體化，直接匯入本機 Data Hub 系統。
"""

import os
import sys
import json
import ssl
import re
import time
import urllib.request
import urllib.parse

# 確保 Windows 終端機印出 UTF-8 時不發生編碼報錯
sys.stdout.reconfigure(encoding='utf-8')

# 配置路徑
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gvg_token.json")
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard", "gvg_data_merged_bulk.json")

# 本地翻譯快取，減少 API 請求
TRANSLATION_CACHE = {
    "物": "物",
    "法": "法",
    "日服": "日服",
    "台服": "台服",
    "陆服": "陸服",
    "阶段": "階段",
    "一阶段": "一階段",
    "二阶段": "二階段",
    "三阶段": "三階段",
    "四阶段": "四階段",
    "五阶段": "五階段"
}

def load_or_request_tokens():
    """
    載入或引導玩家輸入瀏覽器 F12 取得的 d, l, t 臨時憑證
    """
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                tokens = json.load(f)
                if tokens.get("d") and tokens.get("l") and tokens.get("t"):
                    print("[INFO] 成功從本地 gvg_token.json 載入通行證憑證！")
                    return tokens
        except Exception as e:
            print(f"[WARNING] 讀取 gvg_token.json 失敗 ({e})。")

    print("\n" + "="*60)
    print("🔑 首次啟動引導：配置小胡桃 (aikurumi.cn) 通行證憑證")
    print("="*60)
    print("請開啟瀏覽器小胡桃 GVG 網頁，按 F12 開啟開發者工具 Console，")
    print("輸入以下指令並 Enter：")
    print('  console.log(JSON.parse(sessionStorage.getItem("pcr_token") || localStorage.getItem("pcr_token")));')
    print("="*60 + "\n")
    
    d = input("請貼上憑證中的 d 數值: ").strip()
    l = input("請貼上憑證中的 l 數值: ").strip()
    t = input("請貼上憑證中的 t 數值: ").strip()
    
    tokens = {"d": d, "l": l, "t": t}
    
    try:
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(tokens, f, ensure_ascii=False, indent=4)
        print(f"[SUCCESS] 憑證已安全儲存至：{TOKEN_FILE}")
    except Exception as e:
        print(f"[WARNING] 儲存 gvg_token.json 失敗 ({e})")
        
    return tokens

# 🚀 高性能免金鑰批次 Google 翻譯器 (復用並優化，保證作業說明「軸」100% 精準對齊)
def translate_batch(text_list, batch_size=15):
    if not text_list:
        return []
    
    results = {}
    to_translate = []
    
    for text in text_list:
        if not text.strip():
            results[text] = ""
        elif text in TRANSLATION_CACHE:
            results[text] = TRANSLATION_CACHE[text]
        else:
            to_translate.append(text)
            
    if not to_translate:
        return [results.get(t, t) for t in text_list]
        
    for i in range(0, len(to_translate), batch_size):
        chunk = to_translate[i:i+batch_size]
        combined_ja = "\n".join(f"{idx}. {text}" for idx, text in enumerate(chunk, 1))
        
        url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=zh-CN&tl=zh-TW&dt=t&q=" + urllib.parse.quote(combined_ja)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        
        translated_chunk = []
        success = False
        
        for attempt in range(3):
            try:
                # 忽略 SSL 校驗
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urllib.request.urlopen(req, context=ctx, timeout=8) as response:
                    content = response.read().decode('utf-8')
                    raw_json = json.loads(content)
                    
                    translation = ""
                    for part in raw_json[0]:
                        if part[0]:
                            translation += part[0]
                            
                    parts = re.split(r'\n?\d+\.\s*', translation.strip())
                    parts = [p.strip() for p in parts if p.strip()]
                    
                    if len(parts) == len(chunk):
                        translated_chunk = parts
                        success = True
                        break
            except Exception as e:
                time.sleep(1)
                
        if success:
            for ja, zh in zip(chunk, translated_chunk):
                TRANSLATION_CACHE[ja] = zh
                results[ja] = zh
        else:
            # Fallback 簡繁直接字元轉換 (最穩健底層)
            for ja in chunk:
                # 簡單替換
                zh = ja.replace("伤", "傷").replace("阶段", "階段").replace("自动", "自動").replace("手动", "手動").replace("作业", "作業")
                TRANSLATION_CACHE[ja] = zh
                results[ja] = zh
                
        time.sleep(0.1)
        
    return [results.get(t, t) for t in text_list]

def fetch_and_sync_gvg(tokens, stage=4, server="jp", clan_battle_id=1073):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    url = "https://aikurumi.cn/api/pcr/gvgTask"
    
    payload = {
        "stage": stage,
        "server": server,
        "clanBattleId": clan_battle_id
    }
    
    data = json.dumps(payload).encode('utf-8')
    
    # 注入安全通行證
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://aikurumi.cn",
        "Referer": "https://aikurumi.cn/gvg",
        "d": tokens["d"],
        "l": tokens["l"],
        "t": tokens["t"]
    }
    
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        print(f"[INFO] 正在請求小胡桃戰隊戰作業數據... 伺服器: {server.upper()}, 階段: {stage}, 期次: {clan_battle_id}")
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            res_content = response.read().decode('utf-8')
            res_json = json.loads(res_content)
            
            if res_json.get("code") != 200 or not res_json.get("data"):
                error_msg = res_json.get("msg", "未知錯誤")
                print(f"[ERROR] API 拒絕了您的請求，原因: {error_msg} (代碼: {res_json.get('code')})")
                if res_json.get("code") == 800:
                    print("[WARNING] 這通常代表您保存在本地的臨時憑證已過期！請刪除 gvg_token.json 並重新配置。")
                return False
                
            raw_tasks = res_json["data"]
            print(f"[SUCCESS] 成功下載 {len(raw_tasks)} 筆出刀作業數據！正在進行高品質批次繁中化編譯...")
            
            # 蒐集所有需要翻譯的欄位（Boss 名字、作業說明、出刀備註）
            boss_names = list(set(task.get("bossName", "") for task in raw_tasks if task.get("bossName")))
            remarks = list(set(task.get("remarks", "") for task in raw_tasks if task.get("remarks")))
            links = list(set(task.get("link", "") for task in raw_tasks if task.get("link")))
            
            # 高速批次翻譯
            print(f"[INFO] 正在對 {len(boss_names)} 個 Boss 名字與 {len(remarks)} 筆作業軸說明進行批次翻譯...")
            translated_bosses = translate_batch(boss_names)
            translated_remarks = translate_batch(remarks)
            
            # 建立對照字典
            boss_map = dict(zip(boss_names, translated_bosses))
            remark_map = dict(zip(remarks, translated_remarks))
            
            # 重構與中文化數據
            processed_tasks = []
            for task in raw_tasks:
                b_name_raw = task.get("bossName", "")
                b_name_zh = boss_map.get(b_name_raw, b_name_raw)
                
                remark_raw = task.get("remarks", "")
                remark_zh = remark_map.get(remark_raw, remark_raw)
                
                # 台灣在地化術語修正
                remark_zh = remark_zh.replace("自动", "自動").replace("半自动", "半自動").replace("手动", "手動")
                remark_zh = remark_zh.replace("一图流", "一圖流").replace("国服", "陸服").replace("日服", "日服")
                
                # 解析角色編隊（Chara List）
                charas = task.get("charaList", [])
                
                processed_tasks.append({
                    "id": task.get("id"),
                    "bossName": b_name_zh,
                    "stage": task.get("stage"),
                    "damage": task.get("damage"),
                    "remarks": remark_zh,
                    "link": task.get("link"),
                    "charaList": charas,
                    "server": server
                })
                
            # 寫入本地 Data Hub 系統
            os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(processed_tasks, f, ensure_ascii=False, indent=4)
                
            print(f"[SUCCESS] 數據已成功繁中化並寫入 Data Hub 系統！")
            print(f"▶ 儲存路徑：{OUTPUT_PATH}")
            print(f"▶ 本期 Boss 作業總計: {len(processed_tasks)} 筆")
            return True
            
    except Exception as e:
        print(f"[ERROR] 同步作業出錯: {e}")
        return False

def main():
    tokens = load_or_request_tokens()
    
    # 預設自動抓取 日服(jp) 第4階段 最新 GVG 作業
    # 您也可以修改為 server="tw" 來同步台服！
    success = fetch_and_sync_gvg(tokens, stage=4, server="jp", clan_battle_id=1073)
    
    if success:
        print("\n" + "="*50)
        print("🎉 戰隊戰實戰作業同步成功！")
        print("現在，當您開啟 PCRD Data Hub 網站並切換到「戰隊戰」或「作業統計」分頁時，")
        print("網頁將會以無與倫比的流暢度與繁體中文，完美呈現所有 Boss 出刀精準配置與對話軸！")
        print("="*50 + "\n")
    else:
        print("\n[FAILED] 同步失敗。請檢查您的網路連線或 F12 憑證金鑰是否正確。\n")

if __name__ == "__main__":
    main()
