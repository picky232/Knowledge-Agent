import hashlib
import os
import re

from domains.record.repositories.i_index_writer import IIndexWriter

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _slugify(source: str, project: str) -> str:
    base = re.sub(r"[^\w\-가-힣]+", "-", project.strip()).strip("-").lower()
    base = base[:60] if base else "untitled"
    digest = hashlib.sha1(f"{source}:{project}".encode()).hexdigest()[:8]
    return f"{base}-{digest}"


class MarkdownIndexWriter(IIndexWriter):
    """요약을 주제별 md 파일로 저장하고, 전체를 훑는 루트 인덱스(INDEX.md)를 관리한다.
    Claude 자신의 MEMORY.md + 개별 파일 구조를 그대로 본떴다 — 매번 원문 전체를
    읽는 대신 인덱스부터 훑고 필요한 주제만 드릴다운하기 위함."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def read_topic_updated_at(self, source: str, project: str):
        path = self._topic_path(source, project)
        if not os.path.exists(path):
            return None
        frontmatter = self._read_frontmatter(path)
        return frontmatter.get("updated_at")

    def read_topic_summary(self, source: str, project: str) -> str:
        path = self._topic_path(source, project)
        if not os.path.exists(path):
            return ""
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        return FRONTMATTER_RE.sub("", text, count=1).strip()

    def write_topic(self, source: str, project: str, summary: str, chunk_count: int, updated_at: str) -> str:
        path = self._topic_path(source, project)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        frontmatter = (
            "---\n"
            f"source: {source}\n"
            f"project: {project}\n"
            f"chunk_count: {chunk_count}\n"
            f"updated_at: {updated_at}\n"
            "---\n\n"
        )
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(frontmatter + summary.strip() + "\n")
        return path

    def write_root_index(self, entries: list) -> str:
        by_source = {}
        for e in entries:
            by_source.setdefault(e["source"], []).append(e)

        lines = ["# 지식 인덱스", "", f"자동 생성됨 — 총 {len(entries)}개 주제", ""]
        for source in sorted(by_source):
            lines.append(f"## {source}")
            topics = sorted(by_source[source], key=lambda x: x["updated_at"] or "", reverse=True)
            for e in topics:
                rel_path = os.path.relpath(self._topic_path(e["source"], e["project"]), self.base_dir)
                hook = (e["summary"].splitlines()[0][:80] if e["summary"] else "").strip()
                date = (e["updated_at"] or "")[:10]
                lines.append(f"- [{e['project']}]({rel_path}) — {e['chunk_count']}건, {date} — {hook}")
            lines.append("")

        path = os.path.join(self.base_dir, "INDEX.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        return path

    def _read_frontmatter(self, path: str) -> dict:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        m = FRONTMATTER_RE.match(text)
        if not m:
            return {}
        result = {}
        for line in m.group(1).splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                result[key.strip()] = value.strip()
        return result

    def _topic_path(self, source: str, project: str) -> str:
        slug = _slugify(source, project)
        return os.path.join(self.base_dir, source, f"{slug}.md")
