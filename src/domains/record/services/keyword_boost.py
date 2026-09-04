import re

TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣]{2,}")


def _tokenize(text: str) -> set:
    return set(TOKEN_PATTERN.findall(text.lower()))


def dedup_by_title(chunks: list) -> list:
    """(source, title)이 같은 청크는 순위가 가장 높은 것 하나만 남긴다.
    같은 문서/페이지가 여러 청크로 top_k를 잠식하는 것을 방지."""
    seen, result = set(), []
    for chunk in chunks:
        key = (chunk.source, chunk.title)
        if key in seen:
            continue
        seen.add(key)
        result.append(chunk)
    return result


def boost_by_keyword_overlap(question: str, chunks: list, top_k: int) -> list:
    """벡터 유사도 순위(입력 순서)는 유지하되, 질문 키워드가 제목에 그대로
    등장하는 청크를 앞으로 당겨준다. 짧은 텍스트(제목류)에 대한
    임베딩 코사인 점수가 구조적으로 낮게 나오는 것을 보완."""
    keywords = _tokenize(question)
    if not keywords:
        return chunks[:top_k]

    matched, unmatched = [], []
    for chunk in chunks:
        title_tokens = _tokenize(chunk.title)
        if keywords & title_tokens:
            matched.append(chunk)
        else:
            unmatched.append(chunk)

    return (matched + unmatched)[:top_k]
