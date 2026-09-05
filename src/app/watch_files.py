import sys
import os
import json
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app import config
from infrastructure.fileactivity.file_filter import is_tracked

LOG_PATH = os.path.join(config.BASE_DIR, "data", "file_activity.jsonl")
DEBOUNCE_SECONDS = 300
HOME = os.path.expanduser("~")

# 홈 전체가 아니라 실제 작업이 일어나는 위치만 감시 — Library 등 시스템 경로는 제외
WATCH_DIRS = [
    HOME,
    os.path.join(HOME, "Desktop"),
    os.path.join(HOME, "Documents"),
]


class WorkFileHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_logged = {}

    def on_modified(self, event):
        self._record(event, "modified")

    def on_created(self, event):
        self._record(event, "created")

    def _record(self, event, action: str):
        if event.is_directory:
            return
        path = event.src_path
        if not is_tracked(path):
            return

        now = time.time()
        if now - self.last_logged.get(path, 0) < DEBOUNCE_SECONDS:
            return
        self.last_logged[path] = now

        entry = {
            "path": path.replace(HOME, "~"),
            "project": self._project_of(path),
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _project_of(self, path: str) -> str:
        relative = os.path.relpath(path, HOME)
        top = relative.split(os.sep)[0]
        return top if top != ".." else "기타"


def main():
    handler = WorkFileHandler()
    observer = Observer()
    watched = []
    for directory in WATCH_DIRS:
        if os.path.isdir(directory):
            recursive = directory != HOME  # 홈 최상위는 하위 폴더가 개별 감시됨
            observer.schedule(handler, directory, recursive=recursive)
            watched.append(directory)

    for entry in sorted(os.listdir(HOME)):
        full = os.path.join(HOME, entry)
        if not os.path.isdir(full) or entry.startswith(".") or entry == "Library":
            continue
        if full in watched:
            continue
        observer.schedule(handler, full, recursive=True)
        watched.append(full)

    observer.start()
    print(f"파일 활동 감시 시작 ({len(watched)}개 폴더) — 로그: {LOG_PATH}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
