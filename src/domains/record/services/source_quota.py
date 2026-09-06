"""후보군에서 특정 소스가 자리를 독점하지 못하게 상한을 둔다.

브라우저 방문기록은 한 건이 "제목 + 도메인"뿐이라 내용이 거의 없는데,
건수가 압도적으로 많아 후보 50개 중 38개까지 차지하는 경우가 관측됐다.
그러면 정작 본문이 있는 노션·GitHub 문서가 밀려나 답변 품질이 떨어진다.
"""

# 내용이 얕아 다수가 뽑혀도 답변에 크게 기여하지 못하는 소스의 상한
# 최종 top_k가 5라서, 상한이 그보다 크면 한 소스가 답변 근거를 다 채울 수 있다.
# 방문기록만으로 답해야 하는 질문("오늘 뭐 봤어")도 있으므로 0으로 막지는 않는다.
SHALLOW_SOURCE_LIMITS = {
    "browser_history": 3,
    "app_focus": 2,
    "window_title": 2,
    "file_activity": 2,
}


def apply_source_quota(chunks: list) -> list:
    """유사도 순서는 유지한 채, 얕은 소스가 상한을 넘으면 뒤로 미룬다.
    잘라내지 않고 뒤로 보내므로 다른 소스가 부족하면 여전히 쓰인다."""
    kept, overflow = [], []
    counts = {}

    for chunk in chunks:
        limit = SHALLOW_SOURCE_LIMITS.get(chunk.source)
        if limit is None:
            kept.append(chunk)
            continue

        used = counts.get(chunk.source, 0)
        if used < limit:
            counts[chunk.source] = used + 1
            kept.append(chunk)
        else:
            overflow.append(chunk)

    return kept + overflow
