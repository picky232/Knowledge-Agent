import sys
import os
import json
import subprocess
import tempfile
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from AppKit import NSWorkspace

from app import config
from infrastructure.screentext.capture_policy import contains_sensitive_text, is_app_blocked

LOG_PATH = os.path.join(config.BASE_DIR, "data", "screen_text.jsonl")
POLL_SECONDS = 10
MIN_CAPTURE_INTERVAL = 180  # 같은 앱을 계속 쓰는 동안 반복 캡처 방지
MIN_CONFIDENCE = 0.5
MAX_TEXT_CHARS = 2000


def screen_available() -> bool:
    """Screen Recording 권한이 있는지 실제 캡처를 시도해서 확인."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        path = tmp.name
    try:
        result = subprocess.run(
            ["screencapture", "-x", "-t", "png", path],
            capture_output=True, timeout=15,
        )
        return result.returncode == 0 and os.path.getsize(path) > 0
    except Exception:
        return False
    finally:
        if os.path.exists(path):
            os.remove(path)


def capture_and_ocr() -> str:
    """화면을 캡처해 텍스트만 추출하고, 이미지 파일은 항상 즉시 삭제한다."""
    from ocrmac import ocrmac

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        image_path = tmp.name
    try:
        result = subprocess.run(
            ["screencapture", "-x", "-t", "png", image_path],
            capture_output=True, timeout=20,
        )
        if result.returncode != 0:
            return ""

        annotations = ocrmac.OCR(
            image_path, language_preference=["ko-KR", "en-US"]
        ).recognize()
        lines = [text for text, confidence, _ in annotations if confidence >= MIN_CONFIDENCE]
        return "\n".join(lines)[:MAX_TEXT_CHARS]
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


def append_log(app_name: str, text: str):
    entry = {
        "app": app_name,
        "text": text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    if not screen_available():
        print(
            "화면 기록(Screen Recording) 권한이 없습니다. "
            "시스템 설정 > 개인정보 보호 및 보안 > 화면 및 시스템 오디오 기록에서 "
            "이 스크립트를 실행하는 터미널/Python을 추가한 뒤 다시 실행하세요."
        )
        sys.exit(1)

    print(f"화면 텍스트 감시 시작 (앱 전환 시에만 캡처) — 로그: {LOG_PATH}")
    last_app = None
    last_capture_at = {}

    while True:
        app_info = NSWorkspace.sharedWorkspace().activeApplication()
        if app_info:
            app_name = str(app_info.get("NSApplicationName", ""))
            bundle_id = str(app_info.get("NSApplicationBundleIdentifier", ""))

            switched = app_name != last_app
            cooled = time.time() - last_capture_at.get(app_name, 0) > MIN_CAPTURE_INTERVAL

            if switched and cooled and not is_app_blocked(app_name, bundle_id):
                text = capture_and_ocr()
                if text and not contains_sensitive_text(text):
                    append_log(app_name, text)
                    last_capture_at[app_name] = time.time()
            last_app = app_name

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
