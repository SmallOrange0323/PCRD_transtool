@echo off
set NVIDIA_API_KEY=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
set OPENAI_BASE_URL=http://127.0.0.1:11434/v1
set OPENAI_API_KEY=ollama
powershell -ExecutionPolicy Bypass -Command "opencode %*"
