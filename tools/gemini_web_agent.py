import sys
import json
import asyncio
import os
from gemini_webapi import GeminiClient

# 由使用者提供或環境變數注入的 Cookie
PSID = os.getenv("GEMINI_PSID", "g.a000AwlopfDejykG3F2in7HwIMJlfDkPnXyh7mYJwk8adKCb5yDcinpwUMBeok-anRLDMDWT9AACgYKAYYSARUSFQHGX2MiE79Fb1ShEXchnINDDSdYYRoVAUF8yKpVVYjp_UHJ8fB_x49WUcKv0076")
PSIDTS = os.getenv("GEMINI_PSIDTS", "sidts-CjEBPWEu2QiKtrmTtvc-QyVQH0nosnC5aD5PFHE-1591hc_br_wBAbgoBHMtP2goUw5UEAA")

async def main():
    # 讀取輸入 (支援從 stdin 讀取 JSON 或從命令列參數讀取)
    prompt = ""
    try:
        if not sys.stdin.isatty():
            raw_input = sys.stdin.read()
            if raw_input:
                try:
                    data = json.loads(raw_input)
                    prompt = data.get("prompt", "") or data.get("message", "")
                except Exception:
                    prompt = raw_input.strip()
    except Exception:
        pass

    if not prompt and len(sys.argv) > 1:
        prompt = sys.argv[1]

    if not prompt:
        prompt = "你好，請簡短自我介紹。"

    client = GeminiClient(secure_1psid=PSID, secure_1psidts=PSIDTS)

    try:
        await client.init()
        response = await client.generate_content(prompt)
        print(response.text)
    except Exception as e:
        sys.stderr.write(f"ERROR: 執行失敗 - {str(e)}\n")
        sys.exit(1)
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
