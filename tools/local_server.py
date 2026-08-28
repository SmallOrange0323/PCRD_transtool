import http.server
import socketserver
import os
import sys

PORT = 8000
DIRECTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard")

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

    def guess_type(self, path):
        if path.endswith(".wasm"):
            return "application/wasm"
        if path.endswith(".webp"):
            return "image/webp"
        if path.endswith(".m4a"):
            return "audio/mp4"
        if path.endswith(".json"):
            return "application/json; charset=utf-8"
        if path.endswith(".js"):
            return "application/javascript; charset=utf-8"
        return super().guess_type(path)

def run():
    os.chdir(DIRECTORY)
    # 允許地址重用
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), CustomHandler) as httpd:
        print(f"[START] PCRD Local Server started!")
        print(f"[DIR] Directory: {DIRECTORY}")
        print(f"[URL] Local URL: http://localhost:{PORT}/")
        print(f"Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 伺服器已停止。")

if __name__ == '__main__':
    run()
