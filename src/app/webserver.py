import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn

HOST = "127.0.0.1"
PORT = 8420


def main():
    uvicorn.run("presentation.web.app:app", host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
