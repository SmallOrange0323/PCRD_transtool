# -*- coding: utf-8 -*-
"""
PCRD 即時 AI 翻譯系統 - 專有名詞 Wiki 爬蟲模組
"""

import os
import json
import re
import sys
import urllib.request
import urllib.error

# 確保可以正確導入同目錄下的 config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config

# ==============================================================================
# 本地備用核心名詞字典 (Fallback Glossary)
# 當網路斷線、Wiki 變更或抓取失敗時，此字典可確保系統仍有最完整的 PCRD 專有名詞對照。
# ==============================================================================
DEFAULT_GLOSSARY = {
    # == 美食殿堂 ==
    "ペコリーヌ": "佩可莉姆",
    "コッコロ": "可可蘿",
    "キャル": "凱留",
    "シェフィ": "雪菲",

    # == 破曉之星 ==
    "ユイ": "優衣",
    "レイ": "怜",
    "ヒヨリ": "日和",

    # == 拉比林斯 ==
    "ラビリスタ": "拉比林斯達",
    "シズル": "靜流",
    "リノ": "璃乃",

    # == 卡爾米納 (慈樂之音) ==
    "ノゾミ": "望",
    "チカ": "千歌",
    "ツムギ": "紡希",

    # == 咲戀救濟院 ==
    "サレン": "咲戀",
    "スズメ": "鈴莓",
    "アヤネ": "綾音",
    "クルミ": "胡桃",

    # == 自衛團 (動物苑) ==
    "マホ": "真步",
    "マコト": "真琴",
    "カオリ": "香織",
    "カスミ": "霞",

    # == 森林守護者 ==
    "ミサト": "美里",
    "ハツネ": "初音",
    "アオイ": "碧",

    # == 惡魔偽王國軍 ==
    "イリヤ": "伊莉亞",
    "ヨリ": "依里",
    "アカリ": "茜里",
    "ミヤコ": "宮子",
    "シノブ": "忍",

    # == 墨丘利財團 ==
    "アキノ": "秋乃",
    "ミフユ": "美冬",
    "ユカリ": "優花梨",
    "タマキ": "珠希",

    # == 暮光流星群 ==
    "ルカ": "流夏",
    "エリコ": "惠理子",
    "アンナ": "杏奈",
    "ナナカ": "七香",
    "ミツキ": "深月",

    # == 小小甜心 ==
    "ミミ": "美美",
    "みそぎ": "未奏希",
    "ミソギ": "未奏希",
    "キョウカ": "鏡華",

    # == 王宮騎士團 ==
    "ジュン": "純",
    "トモ": "智",
    "マツリ": "茉莉",
    "クリスティーナ": "克莉絲提娜",

    # == 牧場 ==
    "マヒル": "真陽",
    "リマ": "莉瑪",
    "シオリ": "汐里",
    "リン": "鈴",

    # == 聖德蕾莎女學院 (好朋友社) ==
    "ユニ": "優妮",
    "クロエ": "克蘿依",
    "チエル": "琪愛兒",

    # == 露森特學院 ==
    "イオ": "伊緒",
    "スズナ": "鈴奈",
    "ミサキ": "美咲",

    # == 主要配角與反派 ==
    "ネネカ": "似似花",
    "ムイミ": "矛依未",
    "ホマレ": "帆稀",
    "ランファ": "蘭法",
    "カイザーインサイト": "霸瞳皇帝",
    "アゾールド": "阿佐爾德",
    "ゼーン": "讚恩",
    "カリザ": "卡莉莎",
    "ミロク": "彌勒",
    "オクトー": "尾狗刀",
    "ノウェム": "諾維姆",
    "アユミ": "步未",
    
    # == 常見世界觀與名詞 ==
    "ランドソル": "蘭德索爾",
    "アストライア": "阿斯特賴亞",
    "アストルム": "阿斯特魯姆",
    "ミネルヴァ": "米奈娃",
    "ソルオーブ": "太陽之珠",
    "ギルド": "公會",
    "プリンセスナイト": "公主騎士",
    "シャドウ": "暗影",
    "レイジ・レギオン": "憤怒軍團",
    
    # == 公會名 ==
    "美食殿": "美食殿堂",
    "トゥインクルウィッシュ": "破曉之星",
    "ラビリンス": "拉比林斯",
    "カルミナ": "慈樂之音",
    "サレンディア救護院": "咲戀救濟院",
    "自警団": "自衛團",
    "カオン": "動物苑",
    "フォレスティエ": "森林守護者",
    "悪魔偽王国軍": "惡魔偽王國軍",
    "ディアボロス": "惡魔偽王國軍",
    "メルクリウス財団": "墨丘利財團",
    "トワイライトキャラバン": "暮光流星群",
    "リトルリリカル": "小小甜心",
    "王宮騎士団": "王宮騎士團",
    "エリザベスパーク": "牧場",
    "なかよし部": "好朋友社",
    "ルーセント学院": "露森特學院",
    "ヴァイスフリューゲル": "白翼蘭德索爾分部"
}

def clean_name(name: str) -> str:
    """
    清理名稱中的 HTML 標記與多餘空白字元。
    """
    if not name:
        return ""
    name = re.sub(r'<[^>]+>', '', name)  # 移除 HTML 標記
    name = name.strip()
    return name

def scrape_wikipedia_characters() -> dict:
    """
    使用 urllib.request 爬取中文維基百科的 PCRD 角色列表。
    採用台灣繁體 (zh-tw) 變體，確保取得符合台灣官方譯名的繁體中文。
    回傳字典：{ "日文原名": "繁中譯名" }
    """
    # 使用台灣繁體變體的維基百科 URL，確保取得「佩可莉姆」而非簡體字
    url = "https://zh.wikipedia.org/zh-tw/%E8%B6%85%E7%95%B0%E5%9F%9F%E5%85%AC%E4%B8%BB%E9%80%A3%E7%B5%90_Re:Dive%E8%A7%92%E8%89%B2%E5%88%97%E8%A1%A8"
    
    # 維基百科會阻擋預設的 Python User-Agent，需偽裝為一般瀏覽器
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    scraped_data = {}
    
    print(f"[DEBUG] 正在連接維基百科爬取角色名冊... URL: {url}")
    req = urllib.request.Request(url, headers=headers)
    
    try:
        # 設定 6 秒超時，防止網路卡住影響遊戲啟動速度
        with urllib.request.urlopen(req, timeout=6) as response:
            html_content = response.read().decode('utf-8')
            print("[DEBUG] 成功取得維基百科 HTML 內容，開始解析...")
            
            # 使用 BeautifulSoup 嘗試更精細的解析
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # 遍歷所有的清單項目 (li)
                for li in soup.find_all('li'):
                    # 維基百科的日文原名通常包裹在 <span lang="ja"> 中
                    ja_span = li.find('span', lang=lambda l: l and l.startswith('ja'))
                    if ja_span:
                        ja_name = clean_name(ja_span.text)
                        
                        # 尋找日文前的 <b> 標籤，通常是中文譯名
                        b_tag = li.find('b')
                        if b_tag:
                            zh_name = clean_name(b_tag.text)
                            
                            # 進行基本的欄位清洗與合理性校驗
                            # 確保日文是片假名或平假名，中文含有漢字且不跟日文相同
                            if ja_name and zh_name and ja_name != zh_name:
                                # 排除括號等雜質
                                zh_name = re.sub(r'[\uff08\(\uff09\)].*', '', zh_name).strip()
                                ja_name = re.sub(r'[\uff08\(\uff09\)].*', '', ja_name).strip()
                                if zh_name and ja_name:
                                    scraped_data[ja_name] = zh_name
            
            except ImportError:
                print("[DEBUG] 本地未安裝 beautifulsoup4，自動切換至正則表達式解析...")
                # 正則表達式設計：
                # 匹配：<b>中文譯名</b>（<span lang="ja"...>日文原名</span>，聲：...）
                # 或者是有 <a> 連結的 <b><a...>中文譯名</a></b>
                pattern = r'<b>(?:<a[^>]*>)?([^<]+)(?:</a>)?</b>[\uff08\(\s]*<span\s+lang="ja"[^>]*>([^<]+)</span>'
                matches = re.findall(pattern, html_content)
                for zh_raw, ja_raw in matches:
                    zh_name = clean_name(zh_raw)
                    ja_name = clean_name(ja_raw)
                    # 清洗括號
                    zh_name = re.sub(r'[\uff08\(\uff09\)].*', '', zh_name).strip()
                    ja_name = re.sub(r'[\uff08\(\uff09\)].*', '', ja_name).strip()
                    if zh_name and ja_name and zh_name != ja_name:
                        scraped_data[ja_name] = zh_name

            print(f"[INFO] 網頁解析完畢，共解析出 {len(scraped_data)} 筆角色對照。")
            
    except urllib.error.URLError as e:
        print(f"[WARNING] 無法連接維基百科 (原因: {e})。將啟動本地備用機制。")
    except Exception as e:
        print(f"[WARNING] 爬取過程中發生未知錯誤 ({e})。將啟動本地備用機制。")
        
    return scraped_data

def load_or_create_glossary(force_update: bool = False) -> dict:
    """
    載入專有名詞對照表。
    - 如果 glossary.json 存在且不強制更新，直接載入。
    - 如果不存在或 force_update=True，則執行網頁爬蟲，並將爬取到的名詞與本地預設名詞合併，寫入 glossary.json。
    """
    glossary_path = config.GLOSSARY_FILE
    
    # 如果檔案存在且不強制更新，直接讀取
    if os.path.exists(glossary_path) and not force_update:
        try:
            with open(glossary_path, "r", encoding="utf-8") as f:
                glossary = json.load(f)
                print(f"[INFO] 成功從檔案載入名詞對照表，共 {len(glossary)} 筆。路徑: {glossary_path}")
                return glossary
        except Exception as e:
            print(f"[WARNING] 讀取 glossary.json 失敗 ({e})，重新生成對照表。")
            
    # 進行爬取
    scraped = scrape_wikipedia_characters()
    
    # 將本地預設與爬取到的合併
    # 以爬取到的為優先，若網頁抓到新的譯名，可動態更新；網頁沒有的，則使用本地極其完整的預設名冊補全
    merged_glossary = DEFAULT_GLOSSARY.copy()
    
    # 進行資料合併
    new_adds = 0
    for ja, zh in scraped.items():
        if ja not in merged_glossary or merged_glossary[ja] != zh:
            merged_glossary[ja] = zh
            new_adds += 1
            
    print(f"[INFO] 合併完成。本地核心字典: {len(DEFAULT_GLOSSARY)} 筆，網頁新增/覆蓋: {new_adds} 筆，最終總計: {len(merged_glossary)} 筆。")
    
    # 寫入 json 檔案
    try:
        # 確保父目錄存在
        os.makedirs(os.path.dirname(os.path.abspath(glossary_path)), exist_ok=True)
        with open(glossary_path, "w", encoding="utf-8") as f:
            json.dump(merged_glossary, f, ensure_ascii=False, indent=4)
        print(f"[INFO] 專有名詞對照表已儲存至：{glossary_path}")
    except Exception as e:
        print(f"[ERROR] 儲存 glossary.json 失敗 ({e})。將在記憶體中繼續執行。")
        
    return merged_glossary

if __name__ == "__main__":
    print("=== PCRD Wiki 爬蟲測試與初始化 ===")
    # 強制執行爬蟲，重新生成對照表
    load_or_create_glossary(force_update=True)
