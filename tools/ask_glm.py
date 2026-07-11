#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import json
import urllib.request
import urllib.error

# 設定輸出編碼為 UTF-8，避免 Windows 終端機亂碼
sys.stdout.reconfigure(encoding='utf-8')

NVIDIA_API_KEY = "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"
API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

def ask_glm(prompt: str, system_prompt: str = "你是一個有用的助理，請一律使用繁體中文回答。", stream: bool = True) -> str:
    """
    呼叫 NVIDIA 託管的 z-ai/glm-5.2 模型。
    支援串流 (Stream) 輸出，防範長文本逾時並提供即時輸出體驗。
    """
    payload = {
        "model": "z-ai/glm-5.2",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 2048,
        "stream": stream
    }
    
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers
    )
    
    full_content = []
    
    try:
        # 串流請求
        with urllib.request.urlopen(req, timeout=180) as response:
            if not stream:
                res_data = json.loads(response.read().decode("utf-8"))
                return res_data["choices"][0]["message"]["content"].strip()
            
            # SSE 串流解析
            for line in response:
                line_str = line.decode("utf-8").strip()
                if not line_str:
                    continue
                
                # 移除 Server-Sent Events 前綴 "data: "
                if line_str.startswith("data:"):
                    data_body = line_str[5:].strip()
                    if data_body == "[DONE]":
                        break
                    try:
                        chunk_json = json.loads(data_body)
                        delta = chunk_json["choices"][0]["delta"]
                        if "content" in delta:
                            content_part = delta["content"]
                            full_content.append(content_part)
                            # 如果是 CLI 執行，即時印出打字機效果
                            if __name__ == "__main__":
                                sys.stdout.write(content_part)
                                sys.stdout.flush()
                    except Exception:
                        continue
            
            return "".join(full_content).strip()
            
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_msg)
            return f"❌ API 錯誤 (HTTP {e.code}): {err_json.get('detail', {}).get('message', err_msg)}"
        except:
            return f"❌ API 錯誤 (HTTP {e.code}): {err_msg}"
    except Exception as e:
        return f"❌ 系統錯誤: {str(e)}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("💡 使用方式：python ask_glm.py \"你的問題\"")
        sys.exit(1)
        
    user_prompt = sys.argv[1]
    # 在 cli 執行時，ask_glm 內部會即時向 stdout 寫入字元
    ask_glm(user_prompt, stream=True)
    print() # 最後換行
