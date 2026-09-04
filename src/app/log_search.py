import sys
import os
import json
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import config

LOG_PATH = os.path.join(config.BASE_DIR, "data", "websearch.jsonl")


def main():
    if len(sys.argv) < 3:
        print('사용법: python log_search.py "검색어" "URL" ["메모"]')
        sys.exit(1)

    query = sys.argv[1]
    url = sys.argv[2]
    note = sys.argv[3] if len(sys.argv) > 3 else ""

    entry = {
        "id": uuid.uuid4().hex,
        "query": query,
        "url": url,
        "note": note,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"기록됨: {query} ({url})")


if __name__ == "__main__":
    main()
