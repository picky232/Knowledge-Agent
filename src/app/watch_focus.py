import sys
import os
import json
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from AppKit import NSWorkspace, NSWorkspaceDidActivateApplicationNotification
from Foundation import NSObject
from PyObjCTools import AppHelper

from app import config

LOG_PATH = os.path.join(config.BASE_DIR, "data", "app_focus.jsonl")


class FocusWatcher(NSObject):
    def appActivated_(self, notification):
        info = notification.userInfo()
        app = info.get("NSWorkspaceApplicationKey") if info else None
        name = app.localizedName() if app else "unknown"
        bundle_id = app.bundleIdentifier() if app else ""

        entry = {
            "app": str(name) if name else "unknown",
            "bundle_id": str(bundle_id) if bundle_id else "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    watcher = FocusWatcher.alloc().init()
    notification_center = NSWorkspace.sharedWorkspace().notificationCenter()
    notification_center.addObserver_selector_name_object_(
        watcher, "appActivated:", NSWorkspaceDidActivateApplicationNotification, None,
    )
    print(f"앱 전환 감시 시작 — 로그: {LOG_PATH}")
    AppHelper.runConsoleEventLoop()


if __name__ == "__main__":
    main()
