"""날짜별 활동 일지 생성.

기록이 늘어날수록 "어제 뭐 했지" 같은 질문이 어려워진다 — 그날 것 수천 건이
후보 자리를 두고 경쟁하기 때문. 날짜마다 활동을 한 편으로 정리해두면
그 한 편만 찾으면 되므로 경쟁 자체가 사라진다.
"""

from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Asia/Seoul")

SOURCE_LABELS = {
    "browser_history": "방문한 페이지",
    "conversation": "AI와 나눈 대화",
    "app_focus": "사용한 앱",
    "window_title": "열어본 창",
    "file_activity": "작업한 파일",
    "screen_text": "화면에 있던 내용",
    "websearch": "검색 기록",
    "notion": "노션 문서",
    "github": "GitHub 활동",
}

MAX_ITEMS_PER_SOURCE = 25
MAX_SUMMARY_INPUT = 4000


class BuildDailyJournalUseCase:
    def __init__(self, vector_repository, summarizer, journal_writer, max_days: int = 30):
        self.vector_repository = vector_repository
        self.summarizer = summarizer
        self.journal_writer = journal_writer
        self.max_days = max_days

    def run(self) -> dict:
        by_day = self._group_by_day()
        written, reused = 0, 0

        for day, sections in sorted(by_day.items(), reverse=True)[: self.max_days]:
            fingerprint = str(sum(len(v) for v in sections.values()))
            if self.journal_writer.read_fingerprint(day) == fingerprint:
                reused += 1
                continue

            raw = self._render_sections(sections)
            summary = self.summarizer.summarize(f"{day} 활동", raw[:MAX_SUMMARY_INPUT])
            self.journal_writer.write(day, summary, raw, fingerprint)
            written += 1

        return {"days": len(by_day), "written": written, "reused": reused}

    def _group_by_day(self) -> dict:
        by_day = defaultdict(lambda: defaultdict(list))
        for source, title, updated_at in self.vector_repository.list_activity():
            if not updated_at:
                continue
            try:
                ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            day = ts.astimezone(LOCAL_TZ).date().isoformat()
            entries = by_day[day][source]
            if title not in entries:
                entries.append(title)
        return by_day

    def _render_sections(self, sections: dict) -> str:
        parts = []
        for source, titles in sections.items():
            label = SOURCE_LABELS.get(source, source)
            shown = titles[:MAX_ITEMS_PER_SOURCE]
            more = len(titles) - len(shown)
            lines = [f"- {t}" for t in shown]
            if more > 0:
                lines.append(f"- (외 {more}건)")
            parts.append(f"## {label}\n" + "\n".join(lines))
        return "\n\n".join(parts)
