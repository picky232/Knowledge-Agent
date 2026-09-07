"""제목으로 찾은 문서는 중간 토막 대신 문서 시작 부분을 보여준다.

제목이 질문에 그대로 들어있으면 문서 전체를 묻는 것이다. 그런데 제목으로 문서를
찾은 뒤 그 안에서 다시 임베딩 유사도로 조각을 고르면 문서 한가운데가 뽑힌다.
실측에서 이렇게 나왔다:

    "티맥스 7주차 뭐로 구현했어?"  → "잘못된 입력입니다 다시 시도해주세요')..."
    "db.sql명령어 뭐로 구현했어?"  → "mber_2504;\n\ncreate table tbl_class_2504("

둘 다 단어 중간에서 시작하는 파편이라 무엇에 관한 문서인지 알 수 없고, 모델은
제목이 프롬프트에 있는데도 "기록에 없습니다"라고 답했다. 같은 문서의 첫 조각은
각각 "import random  def question(answer):"와
"-- create -- insert -- select * 로 입력된 값 확인  create table tbl_teacher_2504("로
시작해서 무엇을 만든 문서인지 바로 드러난다.

뒤이어 dedup_by_title이 (source, title) 기준으로 한 문서당 하나만 남기므로,
앞자리에 첫 조각을 놓으면 중간 토막은 자연히 걸러진다.
"""

import re

from domains.record.services.title_recall import candidate_phrases

# 구두점과 공백을 모두 떼고 비교한다. 질문을 토큰으로 쪼개면 구두점이 사라져
# "db.sql명령어"가 "db sql명령어"가 되는데, 이걸 그대로 맞대보면 제목의 점 때문에
# 어긋난다. title_recall의 SQL은 공백을 와일드카드로 바꿔 이 문제를 피한다.
NON_TOKEN = re.compile(r"[^0-9A-Za-z가-힣]+")


def _normalize(text: str) -> str:
    return NON_TOKEN.sub("", text.lower())


def _matches_phrase(title: str, phrases: list) -> bool:
    normalized = _normalize(title)
    return any(_normalize(phrase) in normalized for phrase in phrases)


def promote_document_heads(vector_repository, question: str, chunks: list) -> list:
    """제목이 질문 속 구와 겹치는 조각을 그 문서의 첫 조각으로 바꾼다.

    이미 첫 조각이거나 첫 조각을 못 찾으면 원래 조각을 그대로 둔다.
    제목이 안 겹치는 조각은 손대지 않는다 — 그쪽은 유사도로 뽑힌 대목 자체가 답이다.
    """
    phrases = candidate_phrases(question)
    if not phrases:
        return chunks

    result = []
    for chunk in chunks:
        if not _matches_phrase(chunk.title, phrases):
            result.append(chunk)
            continue

        head = vector_repository.get_document_head(chunk.source, chunk.document_id)
        result.append(head if head is not None else chunk)
    return result
