# OpenCode MCP 伺服器多電腦安裝與配置指南

本文件提供如何在其他電腦上安裝與配置 `opencode` MCP 伺服器的完整指南。配置完成後，可以讓您的 AI 編輯器（如 Cursor、Cline、Antigravity 等）透過 MCP 協定，將複雜的程式設計與重構工作委派給 `opencode` 執行。

---

## 🚀 架構說明

這套工具是由兩個主要部分組成的：
1. **OpenCode 服務端 (Headless Server)**：透過全域的 `opencode-ai` 提供底層的 AI Agent 執行能力，一般運行於 `http://localhost:4096`。
2. **OpenCode MCP 橋接器 (opencode-mcp)**：一個 Node.js 專案，負責將 IDE 的 MCP 呼叫轉發給運行中的 OpenCode 服務端。

---

## 📋 準備工作與環境需求

在新電腦上，您需要準備以下環境：
- **Node.js**：版本 18 或以上（建議 LTS 版本）。
- **Git**：用於複製專案。
- **AI 供應商的金鑰**（以下擇一即可）：
  - NVIDIA NIM API 金鑰（如果使用 NVIDIA 雲端模型）。
  - 本地運行的 **Ollama**（例如 Gemma 2 等模型，此時需設定 `OPENAI_BASE_URL` 指向本地端點）。

---

## 🛠️ 第一步：安裝與啟動 OpenCode 服務端

1. **安裝 OpenCode 全域命令**：
   在終端機中執行以下命令進行安裝：
   ```bash
   npm install -g opencode-ai
   ```

2. **建立啟動腳本 (`opencode.bat`)**：
   為了方便設定 API 金鑰並啟動服務，建議在您的工作目錄建立一個 `opencode.bat` 批次檔（以 Windows 為例）：
   ```bat
   @echo off
   :: 若使用 NVIDIA NIM 模型，請填入您的 API 金鑰
   set NVIDIA_API_KEY=您的_NVIDIA_API_KEY
   
   :: 若使用本地 Ollama，請將 OpenAI API 端點指向 Ollama
   set OPENAI_BASE_URL=http://127.0.0.1:11434/v1
   set OPENAI_API_KEY=ollama
   
   :: 繞過 PowerShell 執行原則並執行傳入的命令
   powershell -ExecutionPolicy Bypass -Command "opencode %*"
   ```

3. **啟動 OpenCode 伺服器**：
   執行以下命令，在背景啟動服務端並監聽 `4096` 連接埠：
   ```bash
   opencode.bat serve --port 4096
   ```
   *啟動成功後，您會看到提示：`opencode server listening on http://127.0.0.1:4096`*

---

## 🔌 第二步：建置 OpenCode MCP 橋接器

1. **取得橋接器原始碼**：
   將 `temp_repos/opencode-mcp` 資料夾複製到您的新電腦，或直接從倉庫複製：
   ```bash
   git clone https://github.com/Traves-Theberge/opencode-mcp.git
   cd opencode-mcp
   ```

2. **安裝依賴並建置專案**：
   在 `opencode-mcp` 目錄下執行以下命令：
   ```bash
   npm install
   npm run build
   ```
   *這將在 `dist/` 目錄下產生建置產物（包括入口檔案 `dist/index.js`）。*

---

## ⚙️ 第三步：在 IDE 中配置 MCP 伺服器

請依據您使用的編輯器，將設定寫入對應的 MCP 設定檔中。
設定時，請將 `args` 中的路徑改為您新電腦上 `opencode-mcp/dist/index.js` 的**絕對路徑**，將 `OPENCODE_DEFAULT_PROJECT` 改為您的**預設開發專案路徑**。

### 1. Cursor 配置
- **設定檔路徑**：`C:\Users\您的使用者名稱\.cursor\mcp.json`
- **寫入設定**：
  ```json
  {
    "mcpServers": {
      "opencode": {
        "command": "node",
        "args": [
          "C:/path/to/opencode-mcp/dist/index.js"
        ],
        "env": {
          "OPENCODE_SERVER_URL": "http://localhost:4096",
          "OPENCODE_DEFAULT_PROJECT": "C:/path/to/your/project"
        }
      }
    }
  }
  ```

### 2. Cline (VS Code 擴充套件) 配置
- **設定檔路徑**：`C:\Users\您的使用者名稱\AppData\Roaming\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`
- **寫入設定**：
  *(與 Cursor 設定結構相同)*
  ```json
  {
    "mcpServers": {
      "opencode": {
        "command": "node",
        "args": [
          "C:/path/to/opencode-mcp/dist/index.js"
        ],
        "env": {
          "OPENCODE_SERVER_URL": "http://localhost:4096",
          "OPENCODE_DEFAULT_PROJECT": "C:/path/to/your/project"
        }
      }
    }
  }
  ```

### 3. Antigravity 配置
- **設定檔路徑**：`C:\Users\您的使用者名稱\.gemini\antigravity\mcp_config.json`
- **寫入設定**：
  *(配置相同，重啟 Agent 後即會自動載入 `opencode_run` 等工具)*

---

## 💡 注意事項與疑難排解

1. **每次開啟 IDE 前必須先啟動 OpenCode**：
   MCP 橋接器必須依賴於正在運行的 OpenCode 服務端。請務必在工作前執行 `opencode.bat serve --port 4096`。
2. **路徑反斜線問題**：
   在 JSON 設定檔中，路徑的斜線請使用正斜線 `/`（例如 `C:/path/to/...`）或雙反斜線 `\\`，以避免 JSON 解析錯誤。
3. **無權限載入 PowerShell 腳本**：
   若執行 npm 或 opencode 時出現執行原則（ExecutionPolicy）錯誤，請在啟動時加上 `-ExecutionPolicy Bypass`，或使用 `cmd /c` 調用。
