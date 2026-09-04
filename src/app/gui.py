import sys
import os
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn
import webview

from presentation.web.app import app as fastapi_app

HOST = "127.0.0.1"
PORT = 8420


def run_server():
    uvicorn.run(fastapi_app, host=HOST, port=PORT, log_level="warning")


def main():
    threading.Thread(target=run_server, daemon=True).start()
    webview.create_window("Knowledge Agent", f"http://{HOST}:{PORT}", width=880, height=680)
    webview.start()


if __name__ == "__main__":
    main()
