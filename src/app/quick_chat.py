"""Option 키를 두 번 눌러 여닫는 빠른 질문 창.

Spotlight처럼 어디서든 불러내고, 닫으면 화면은 비워진다.
나눈 대화는 파일로 남아 다음 인덱싱 때 검색 대상이 된다.
"""

import sys
import os
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import Quartz
import uvicorn
import webview
from ApplicationServices import AXIsProcessTrusted

from presentation.web import app as web_app

HOST = "127.0.0.1"
PORT = 8420
DOUBLE_TAP_SECONDS = 0.4

PERMISSION_HINT = (
    "손쉬운 사용(Accessibility) 권한이 없어 Option 두 번 누르기를 감지할 수 없습니다.\n"
    "시스템 설정 > 개인정보 보호 및 보안 > 손쉬운 사용에서 이 스크립트를 실행하는\n"
    "터미널(또는 Knowledge Agent 앱)을 추가한 뒤 다시 실행하세요.\n"
    "권한 없이도 창은 떠 있으며, 직접 클릭해 사용할 수 있습니다."
)


class HotkeyListener:
    """Option 키를 눌렀다 뗀 것이 짧은 간격으로 두 번 반복되면 콜백을 부른다."""

    def __init__(self, on_double_tap):
        self.on_double_tap = on_double_tap
        self.option_was_down = False
        self.last_release_at = 0.0

    def handle(self, proxy, event_type, event, refcon):
        flags = Quartz.CGEventGetFlags(event)
        option_down = bool(flags & Quartz.kCGEventFlagMaskAlternate)
        other_modifier = bool(flags & (
            Quartz.kCGEventFlagMaskCommand
            | Quartz.kCGEventFlagMaskShift
            | Quartz.kCGEventFlagMaskControl
        ))

        if option_down and not other_modifier:
            self.option_was_down = True
        elif self.option_was_down and not option_down:
            self.option_was_down = False
            now = time.time()
            if now - self.last_release_at < DOUBLE_TAP_SECONDS:
                self.last_release_at = 0.0
                self.on_double_tap()
            else:
                self.last_release_at = now
        return event

    def run(self):
        tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged),
            self.handle,
            None,
        )
        if not tap:
            print("이벤트 탭을 만들지 못했습니다. 권한을 확인하세요.")
            return

        source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        Quartz.CFRunLoopAddSource(
            Quartz.CFRunLoopGetCurrent(), source, Quartz.kCFRunLoopCommonModes
        )
        Quartz.CGEventTapEnable(tap, True)
        Quartz.CFRunLoopRun()


def run_server():
    uvicorn.run(web_app.app, host=HOST, port=PORT, log_level="warning")


def main():
    if not AXIsProcessTrusted():
        print(PERMISSION_HINT)

    threading.Thread(target=run_server, daemon=True).start()

    window = webview.create_window(
        "Knowledge Agent",
        f"http://{HOST}:{PORT}/quick",
        width=720, height=420,
        frameless=True, on_top=True, hidden=True,
    )

    visible = {"state": False}

    def hide():
        if visible["state"]:
            window.hide()
            visible["state"] = False

    def toggle():
        if visible["state"]:
            hide()
        else:
            window.show()
            visible["state"] = True

    web_app.hide_callback["fn"] = hide

    listener = HotkeyListener(on_double_tap=toggle)
    threading.Thread(target=listener.run, daemon=True).start()

    print(f"빠른 질문 창 준비됨 — Option 두 번 눌러 열기 (창 주소 {HOST}:{PORT}/quick)")
    webview.start()


if __name__ == "__main__":
    main()
