import sys
import os
import json
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from AppKit import NSWorkspace
from ApplicationServices import (
    AXIsProcessTrusted,
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeValue,
    kAXFocusedWindowAttribute,
    kAXTitleAttribute,
)

from app import config

LOG_PATH = os.path.join(config.BASE_DIR, "data", "window_title.jsonl")
POLL_SECONDS = 5


def get_frontmost_window():
    app_info = NSWorkspace.sharedWorkspace().activeApplication()
    if not app_info:
        return None, None
    pid = app_info["NSApplicationProcessIdentifier"]
    app_name = str(app_info["NSApplicationName"])

    ax_app = AXUIElementCreateApplication(pid)
    err, window = AXUIElementCopyAttributeValue(ax_app, kAXFocusedWindowAttribute, None)
    if err != 0 or window is None:
        return app_name, None

    err, title = AXUIElementCopyAttributeValue(window, kAXTitleAttribute, None)
    if err != 0 or title is None:
        return app_name, None
    return app_name, str(title)


def append_log(app_name: str, title: str):
    entry = {
        "app": app_name,
        "title": title,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    if not AXIsProcessTrusted():
        print(
            "손쉬운 사용(Accessibility) 권한이 없습니다. "
            "시스템 설정 > 개인정보 보호 및 보안 > 손쉬운 사용에서 이 스크립트를 실행하는 "
            "터미널/Python을 추가한 뒤 다시 실행하세요."
        )
        sys.exit(1)

    print(f"윈도우 제목 감시 시작 (poll {POLL_SECONDS}s) — 로그: {LOG_PATH}")
    last_seen = None
    while True:
        app_name, title = get_frontmost_window()
        if app_name and title:
            key = (app_name, title)
            if key != last_seen:
                append_log(app_name, title)
                last_seen = key
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
