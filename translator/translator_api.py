# -*- coding: utf-8 -*-
"""
PCRD 即時 AI 翻譯系統 - Gemini 翻譯 API 模組
實作雙軌制翻譯 (Text-based & Vision-based) 與上下文滑動視窗快取
"""

import os
import json
import re
import sys
import io
import asyncio
import random
from PIL import Image
import google.generativeai as genai

# 確保可以正確導入同目錄下的 config 與 wiki_scraper
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from wiki_scraper import load_or_create_glossary

class GeminiTranslator:
    """
    PCRD 即時 AI 翻譯器，串接 Gemini 2.5 API，具備雙軌翻譯與歷史滑動上下文快取。
    """
    def __init__(self):
        # 1. 載入 API 金鑰與模型設定
        self.api_key = config.GEMINI_API_KEY
        if not self.api_key:
            # 嘗試從系統環境變數獲取 fallback
            self.api_key = os.getenv("GEMINI_API_KEY", "")
            
        if not self.api_key:
            print("[WARNING] 未偵測到 GEMINI_API_KEY，請在 config.py 或系統環境變數中設定。翻譯功能將無法正常運作。")
        else:
            genai.configure(api_key=self.api_key)
            print("[INFO] Gemini API 配置成功。")
            
        self.text_model_name = getattr(config, "GEMINI_TEXT_MODEL", "gemini-2.5-flash")
        self.vision_model_name = getattr(config, "GEMINI_VISION_MODEL", "gemini-2.5-flash")
        
        # 2. 載入或自動生成專有名詞字典 (Glossary)
        print("[DEBUG] 正在初始化專有名詞對照表...")
        self.glossary = load_or_create_glossary()
        
        # 3. 歷史對話快取 (Context History Cache)
        # 格式：[{"speaker": "...", "japanese": "...", "chinese": "..."}, ...]
        self.history = []
        self.history_limit = getattr(config, "CONTEXT_HISTORY_LIMIT", 3)
        
        # 4. 初始化系統指令 (System Instruction)
        self.system_instruction = self._build_system_instruction()
        
        # 5. 初始化 Gemini 模型實例
        self.use_fallback_system_prompt = False
        self._init_models()

    def _init_models(self):
        """
        初始化文字與視覺模型，支援舊版 SDK 的相容性處理。
        """
        if not self.api_key:
            return
            
        # 文字翻譯模型
        try:
            self.text_model = genai.GenerativeModel(
                model_name=self.text_model_name,
                system_instruction=self.system_instruction
            )
            print(f"[INFO] 成功建立文字翻譯模型: {self.text_model_name} (含 System Instruction)")
        except TypeError:
            # 相容舊版 SDK 不支援 system_instruction 參數的情況
            self.use_fallback_system_prompt = True
            self.text_model = genai.GenerativeModel(model_name=self.text_model_name)
            print(f"[INFO] 成功建立文字翻譯模型: {self.text_model_name} (SDK 相容模式)")
            
        # 視覺多模態模型 (Gemini Vision 通常使用相同的 System Instruction 或者在 Prompt 中設定)
        try:
            self.vision_model = genai.GenerativeModel(
                model_name=self.vision_model_name,
                system_instruction=self.system_instruction
            )
            print(f"[INFO] 成功建立視覺翻譯模型: {self.vision_model_name} (含 System Instruction)")
        except TypeError:
            self.vision_model = genai.GenerativeModel(model_name=self.vision_model_name)
            print(f"[INFO] 成功建立視覺翻譯模型: {self.vision_model_name} (SDK 相容模式)")

    def _build_system_instruction(self) -> str:
        """
        建構給 Gemini 的 System Instruction。
        融合 glossary.json 專有名詞對照表，強制約束翻譯名詞，確保翻譯口氣與品質。
        """
        # 格式化對照表為 text
        glossary_parts = []
        for jp, zh in self.glossary.items():
            glossary_parts.append(f"- {jp} -> {zh}")
        glossary_str = "\n".join(glossary_parts)
        
        instruction = f"""你是一位精通手遊《超異域公主連結 Re:Dive》(PCRD) 的專業日翻中翻譯大師。
你的任務是將遊戲中的日文劇情對話與場景文字翻譯成極具沉浸感、口語化且符合角色性格的繁體中文。

【翻譯核心規範】
1. 使用繁體中文（台灣習慣用語，例如使用「公會」、「羈絆」、「佑樹」、「步未」、「破曉之星」、「美食殿堂」等）。
2. 翻譯風格必須極具動漫與美少女遊戲感，語氣要生動，且務必符合角色性格與說話語氣：
   - 可可蘿 (コッコロ)：對主角佑樹極度尊敬，說話溫柔有禮，常使用「主公大人」作為稱呼。
   - 凱留 (キャル)：典型的傲嬌，說話常有口是心非、傲嬌吐槽的語氣。
   - 佩可莉姆 (ペコリーヌ)：總是元氣滿滿，開朗大方，非常喜愛美食，經常提到食物。
   - 其他角色請依其原本人設語氣進行優雅流暢的翻譯。
3. 嚴格遵循下方的【專有名詞日中對照表】。如果日文文本中出現了對照表中的日文詞彙，務必將其替換為指定的中文官方譯名。
4. 輸出格式：請只輸出翻譯後的繁體中文內容，不要包含任何解釋、羅馬字拼音、標籤或額外的引號。

【專有名詞日中對照表】
{glossary_str}
"""
        return instruction

    def _build_text_prompt(self, text: str, speaker: str = None) -> str:
        """
        建構包含歷史上下文的文字翻譯 Prompt。
        """
        prompt_parts = []
        
        # 若為 SDK 相容模式，將 System Instruction 合併在 Prompt 頭部
        if self.use_fallback_system_prompt:
            prompt_parts.append(self.system_instruction)
            prompt_parts.append("========================================\n")
            
        # 插入歷史對話上下文，使翻譯前後連貫
        if self.history:
            prompt_parts.append("【前文對話歷史（供翻譯上下文參考）】")
            for idx, hist in enumerate(self.history):
                hist_speaker = hist.get("speaker", "角色")
                prompt_parts.append(f" 歷史 {idx+1}:")
                prompt_parts.append(f"   說話者: {hist_speaker}")
                prompt_parts.append(f"   日文原句: {hist['japanese']}")
                prompt_parts.append(f"   中文譯文: {hist['chinese']}")
            prompt_parts.append("--------------------------------")
            
        # 放入當前待翻譯句子
        prompt_parts.append("【請翻譯以下當前日文句子】")
        if speaker:
            prompt_parts.append(f"說話者: {speaker}")
        prompt_parts.append(f"日文原句: {text}")
        prompt_parts.append("\n請直接輸出此句的繁體中文翻譯（不要有任何 JSON、標籤或解釋）：")
        
        return "\n".join(prompt_parts)

    def _build_vision_prompt(self) -> str:
        """
        建構包含歷史與名詞對照的 Vision 翻譯 Prompt。
        要求 Gemini 輸出嚴格的 JSON 結構，方便主程式同時更新歷史快取與懸浮視窗。
        """
        glossary_parts = []
        for jp, zh in self.glossary.items():
            glossary_parts.append(f"- {jp} -> {zh}")
        glossary_str = "\n".join(glossary_parts)
        
        # 歷史上下文
        if self.history:
            history_parts = []
            for idx, hist in enumerate(self.history):
                hist_speaker = hist.get("speaker", "未知")
                history_parts.append(f"  歷史 {idx+1}: 說話者: {hist_speaker} | 日文: {hist['japanese']} -> 中文: {hist['chinese']}")
            history_str = "\n".join(history_parts)
        else:
            history_str = "  (無)"
            
        prompt = f"""請分析附圖（PCRD 遊戲對話框截圖），辨識並翻譯其中的日文內容。

【翻譯核心規範】
1. 使用流暢、口語的台灣繁體中文。
2. 語氣需符合美少女遊戲氛圍與角色性格，確保與歷史上下文連貫。
3. 嚴格遵循下方的【專有名詞日中對照表】。

【專有名詞日中對照表】
{glossary_str}

【前文對話歷史（供翻譯上下文參考）】
{history_str}

【任務要求】
請仔細辨識圖片中對話框的文字：
1. 辨識出「說話者」的日文名字（通常在對話框上方，若沒有則留空）。
2. 辨識出「對話框內」的日文原句。
3. 將日文原句翻譯為繁體中文譯文。

【輸出格式規範】
請務必嚴格以 JSON 格式回傳，不要有任何額外的引言、說明或 markdown 標籤，格式如下：
{{
  "speaker": "辨識出的說話者日文名字 (若無則填寫空字串 \"\")",
  "japanese": "辨識出的對話框日文原句全文",
  "chinese": "翻譯後的繁體中文譯文"
}}
"""
        return prompt

    def add_to_history(self, japanese: str, chinese: str, speaker: str = None):
        """
        將翻譯好的對話加入上下文歷史快取 (Context History Cache)。
        採用滑動視窗限制 (CONTEXT_HISTORY_LIMIT)，為 FIFO 隊列。
        """
        hist_item = {
            "speaker": speaker if speaker else "",
            "japanese": japanese.strip(),
            "chinese": chinese.strip()
        }
        
        self.history.append(hist_item)
        
        # 限制長度
        if len(self.history) > self.history_limit:
            self.history.pop(0)
            
        print(f"[DEBUG] 歷史上下文更新成功。目前緩存條數: {len(self.history)}")

    def clear_history(self):
        """
        清空對話歷史（通常在切換章節、回到主畫面或玩家手動重置時呼叫）。
        """
        self.history.clear()
        print("[INFO] 歷史上下文快取已成功清空。")

    def _extract_json(self, text: str) -> dict:
        """
        極度穩健的 JSON 提取與解析器，防範 AI 回傳 Markdown Code Block 或非標準 JSON 格式。
        """
        text = text.strip()
        
        # 1. 尋找 markdown block 中的 json: ```json ... ```
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            # 2. 尋找第一個 { 到最後一個 }
            match_brace = re.search(r'(\{.*\})', text, re.DOTALL)
            if match_brace:
                json_str = match_brace.group(1)
            else:
                json_str = text
                
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"[WARNING] 嚴格解析 JSON 失敗 ({e})，正在嘗試 Regex 提取 Fallback...")
            # 3. 採用 Regex 逐一抓取 key-value 做 Fallback
            fallback_data = {"speaker": "", "japanese": "", "chinese": ""}
            
            zh_match = re.search(r'"chinese"\s*:\s*"([^"]+)"', text)
            if zh_match:
                fallback_data["chinese"] = zh_match.group(1)
            else:
                # 實在找不到，就把整段 text 當作中文翻譯
                fallback_data["chinese"] = text
                
            ja_match = re.search(r'"japanese"\s*:\s*"([^"]+)"', text)
            if ja_match:
                fallback_data["japanese"] = ja_match.group(1)
                
            sp_match = re.search(r'"speaker"\s*:\s*"([^"]+)"', text)
            if sp_match:
                fallback_data["speaker"] = sp_match.group(1)
                
            return fallback_data

    async def _call_gemini_with_retry(self, model, contents, generation_config=None, max_retries=3) -> str:
        """
        處理 Rate Limit (429) 與網路波動的指數退避重試呼叫。
        """
        delay = 1.0  # 初始等待 1 秒
        for attempt in range(max_retries):
            try:
                if generation_config:
                    response = await model.generate_content_async(
                        contents,
                        generation_config=generation_config
                    )
                else:
                    response = await model.generate_content_async(contents)
                return response.text
            except Exception as e:
                err_msg = str(e)
                # 判斷是否為 Rate Limit (ResourceExhausted) 或是暫時性網路錯誤
                is_rate_limit = "429" in err_msg or "ResourceExhausted" in err_msg or "Quota exceeded" in err_msg
                is_temp_err = "503" in err_msg or "ServiceUnavailable" in err_msg or "deadline" in err_msg
                
                if (is_rate_limit or is_temp_err) and attempt < max_retries - 1:
                    # 指數退避 + 隨機抖動 (Jitter)
                    sleep_time = delay * (2 ** attempt) + random.uniform(0.0, 0.5)
                    print(f"[Gemini API] 偵測到限制或網路暫時錯誤 ({e})。正在進行第 {attempt+1} 次重試，將等待 {sleep_time:.2f} 秒...")
                    await asyncio.sleep(sleep_time)
                else:
                    print(f"[Gemini API] 呼叫失敗。原因: {e}")
                    raise e
        return ""

    # ==============================================================================
    # 雙軌翻譯路徑 1：純文本翻譯 (Text-based)
    # ==============================================================================
    async def translate_text(self, text: str, speaker: str = None) -> str:
        """
        純文本翻譯路徑。
        將輸入的日文字串，結合歷史上下文與 Glossary 翻譯為繁中譯文。
        """
        if not self.api_key:
            return f"[未配置 API 金鑰] {text}"
            
        if not text.strip():
            return ""
            
        print(f"[DEBUG] 啟動純文本翻譯路徑... 日文原長: {len(text)} 字")
        prompt = self._build_text_prompt(text, speaker)
        
        try:
            translated_text = await self._call_gemini_with_retry(self.text_model, prompt)
            translated_text = translated_text.strip()
            
            # 將結果記錄到歷史滑動快取中
            self.add_to_history(japanese=text, chinese=translated_text, speaker=speaker)
            
            print("[INFO] 純文本翻譯成功。")
            return translated_text
            
        except Exception as e:
            print(f"[ERROR] 純文本翻譯路徑出錯: {e}")
            # 發生錯誤時回傳原文，確保 UI 不崩潰
            return f"[翻譯失敗] {text}"

    # ==============================================================================
    # 雙軌翻譯路徑 2：多模態 Vision 讀圖翻譯 (Vision-based)
    # ==============================================================================
    async def translate_vision(self, image: Image.Image) -> dict:
        """
        多模態 Vision 讀圖翻譯路徑。
        接收 PIL Image，由 Gemini Vision 自動讀取對話框內容並翻譯。
        回傳字典格式：{"speaker": "...", "japanese": "...", "chinese": "..."}
        """
        if not self.api_key:
            return {"speaker": "", "japanese": "", "chinese": "[未配置 API 金鑰]"}
            
        print("[DEBUG] 啟動多模態 Vision 翻譯路徑... 正在將圖片壓縮為位元流...")
        
        # 1. 將 PIL Image 轉換為 raw bytes 位元流，提升 API 傳遞的穩定性與速度
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()
        
        image_part = {
            'mime_type': 'image/png',
            'data': img_bytes
        }
        
        # 2. 建立 Vision Prompt
        prompt = self._build_vision_prompt()
        
        # 3. 準備 contents
        contents = [image_part, prompt]
        
        # 4. 指定 JSON 輸出的 generation_config
        generation_config = {
            "response_mime_type": "application/json"
        }
        
        try:
            print("[DEBUG] 正在發送 Vision 請求給 Gemini...")
            response_text = await self._call_gemini_with_retry(
                self.vision_model, 
                contents, 
                generation_config=generation_config
            )
            
            # 5. 解析與還原結果
            result = self._extract_json(response_text)
            
            # 6. 加入歷史對話
            ja_text = result.get("japanese", "").strip()
            zh_text = result.get("chinese", "").strip()
            sp_name = result.get("speaker", "").strip()
            
            if zh_text:
                # 只有當翻譯非空時，才將其寫入歷史
                self.add_to_history(japanese=ja_text, chinese=zh_text, speaker=sp_name)
                
            print(f"[INFO] 多模態 Vision 翻譯成功。說話者: {sp_name} | 譯文: {zh_text}")
            return result
            
        except Exception as e:
            print(f"[ERROR] 多模態 Vision 翻譯路徑出錯: {e}")
            return {
                "speaker": "",
                "japanese": "",
                "chinese": f"[多模態翻譯失敗]: {e}"
            }

# ==============================================================================
# 非同步主程式測試區
# ==============================================================================
async def main():
    print("=== PCRD Gemini API 翻譯模組測試 ===")
    translator = GeminiTranslator()
    
    # 測試 1: 文本翻譯
    print("\n--- 測試 1: 純文本翻譯 1 ---")
    test_jp_1 = "あ、主さま！お帰りなさいませ！コッコロは主さまをお待ちしておりました。"
    result_zh_1 = await translator.translate_text(test_jp_1, speaker="コッコロ")
    print(f"原句: {test_jp_1}")
    print(f"譯文: {result_zh_1}")
    
    # 測試 2: 上下文歷史測試 (下一句)
    print("\n--- 測試 2: 純文本翻譯 2 (應帶入上一句的歷史上下文) ---")
    test_jp_2 = "ふふ、今日の晩ご飯はペコリーヌ様が採ってきた魔物の肉を使ったお鍋ですよ！"
    result_zh_2 = await translator.translate_text(test_jp_2, speaker="コッコロ")
    print(f"原句: {test_jp_2}")
    print(f"譯文: {result_zh_2}")
    
    # 測試 3: 專有名詞對照測試 (傲嬌凱留)
    print("\n--- 測試 3: 專有名詞對照測試 (凱留與美食殿堂) ---")
    test_jp_3 = "ちょっと！また変な魔物の肉食べてるの！？美食殿のギルドハウスが台無しよ！"
    result_zh_3 = await translator.translate_text(test_jp_3, speaker="キャル")
    print(f"原句: {test_jp_3}")
    print(f"譯文: {result_zh_3}")
    
    # 測試 4: 傲嬌與霸瞳皇帝專有名詞
    print("\n--- 測試 4: 世界觀與名詞 (蘭德索爾、霸瞳皇帝) ---")
    test_jp_4 = "カイザーインサイトのせいでランドソルは滅茶苦茶になったのに、あんた達はのんきね。"
    result_zh_4 = await translator.translate_text(test_jp_4, speaker="キャル")
    print(f"原句: {test_jp_4}")
    print(f"譯文: {result_zh_4}")

if __name__ == "__main__":
    # 執行非同步測試
    asyncio.run(main())
