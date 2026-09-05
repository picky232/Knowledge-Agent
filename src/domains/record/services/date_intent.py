from datetime import timedelta

import dateparser.search


def detect_date_range(question: str, relative_base=None):
    """질문에 "어제"/"오늘" 같은 상대 날짜 표현이 있으면
    그 날짜의 로컬 하루 전체를 (start, end)로 반환. 없으면 None.
    "지난주"/"최근" 같은 넓은 표현은 dateparser가 못 잡아 걸러지지 않음 — 알려진 한계."""
    settings = {"RETURN_AS_TIMEZONE_AWARE": True}
    if relative_base is not None:
        settings["RELATIVE_BASE"] = relative_base

    found = dateparser.search.search_dates(question, languages=["ko", "en"], settings=settings)
    if not found:
        return None

    _, detected = found[0]
    day_start = detected.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    return day_start, day_end
