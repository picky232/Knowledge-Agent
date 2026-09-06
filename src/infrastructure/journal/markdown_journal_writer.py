import os
import re

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


class MarkdownJournalWriter:
    """날짜 하나당 md 파일 하나. 사람이 그냥 열어봐도 읽히는 형태로 둔다."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def path_for(self, day: str) -> str:
        year, month = day[:4], day[5:7]
        return os.path.join(self.base_dir, year, month, f"{day}.md")

    def read_fingerprint(self, day: str):
        path = self.path_for(day)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        match = FRONTMATTER_RE.match(text)
        if not match:
            return None
        for line in match.group(1).splitlines():
            if line.startswith("fingerprint:"):
                return line.split(":", 1)[1].strip()
        return None

    def write(self, day: str, summary: str, detail: str, fingerprint: str) -> str:
        path = self.path_for(day)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        content = (
            "---\n"
            f"date: {day}\n"
            f"fingerprint: {fingerprint}\n"
            "---\n\n"
            f"# {day}\n\n"
            f"{summary.strip()}\n\n"
            f"{detail.strip()}\n"
        )
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path
