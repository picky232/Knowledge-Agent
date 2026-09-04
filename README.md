# knowledge-agent

대화 기록(Claude Code), GitHub, Notion에 흩어진 개인 작업 기록을 로컬 LLM(qwen3:8b, Ollama)으로 인덱싱해 자연어로 물어보면 출처와 함께 답해주는 개인용 RAG 에이전트.

## 현재 상태: 안정화 완료 (베타)

- [x] GitHub 커넥터 (레포/README/최근 커밋)
- [x] Claude Code 대화 로그 커넥터 (`~/.claude/projects`)
- [x] Notion 커넥터 (페이지네이션 적용 — 50건 제한 없음, 공유된 페이지 전체 수집)
- [x] 웹서칭 커넥터 — `log_search.py`로 수동 기록 → 인덱싱 대상
- [x] sqlite 기반 벡터 저장소 (numpy 코사인 유사도, sqlite-vec 확장 미사용)
- [x] CLI 질의 (`ask.py`) / 수동 동기화 (`sync.py`)
- [x] 소스별 에러 격리 — 한 소스 실패해도 나머지 정상 진행, 실패 건수 리포트
- [x] cron 자동 동기화 (매일 09:00, `scripts/run_sync.sh` + crontab, 로그 `logs/sync.log`)
- [x] 중단 후 이어서 생성 — `ask_resumable.py` (Ollama 스트리밍 + 토큰 단위 상태 영속화, thinking/answer 단계 모두 재개 가능)
- [x] 웹서칭 소스 — `log_search.py`로 수동 기록 → 인덱싱 대상
- [x] 100문항 벤치마크 완료 (아래 결과 참고)
- [x] 브라우저 히스토리 자동수집 — Chrome(전 프로필) 완료, Safari는 코드 완성됐으나 macOS 전체 디스크 접근 권한 필요(아래 참고)
- [x] 하이브리드 검색(키워드 겹침 부스트) — 짧은 텍스트(브라우저 히스토리 제목 등)가 임베딩 코사인 점수에서 불리한 문제 보완

## 구조 (DDD 4계층)

```
src/
  domains/record/       비즈니스 로직 — 외부 의존성 없음
    entities/            SourceDocument, DocumentChunk, AnswerResult
    repositories/        IDocumentSource, IEmbeddingService, IVectorRepository, IAnswerGenerator
    services/            chunker
    useCases/            IndexDocumentsUseCase, AskQuestionUseCase
  infrastructure/        인터페이스 구현체
    github/               gh CLI 기반
    notion/               Notion API
    conversationlog/      ~/.claude/projects 파싱
    websearch/             log_search.py로 남긴 로컬 기록(data/websearch.jsonl) 파싱
    ollama/               임베딩(nomic-embed-text) / 답변 생성(qwen3:8b, 스트리밍 지원)
    vectorstore/          sqlite 저장 + 코사인 유사도 검색
    resume/                중단된 생성 상태 파일 저장(data/partial_answers/)
    browserhistory/         Chrome/Safari 히스토리 DB 직접 파싱(임시 복사 후 읽음, WAL 포함)
  presentation/cli/       답변/통계 포맷팅
  app/                    container(공통 조립) / config / sync.py / ask.py / ask_resumable.py / log_search.py / run_benchmark.py
```

## 실행

```bash
source .venv/bin/activate
python src/app/sync.py              # 소스 수집 + 인덱싱
python src/app/ask.py "질문 내용"    # 질의
python src/app/ask_resumable.py "질문 내용"    # 질의 (중단돼도 같은 질문으로 재실행하면 이어서 생성)
python src/app/log_search.py "검색어" "URL" "메모"   # 웹서칭 기록 남기기
python src/app/run_benchmark.py 100  # 인덱싱된 데이터 기반 자동 질문 100개 생성 후 일괄 테스트
```

## 벤치마크 결과 (2026-09-04, 100문항)

| 지표 | 값 |
|---|---|
| 성공 / 실패 | 100 / 0 |
| 출처 없이 답한 케이스 | 0건 |
| 평균 응답시간 | 19.9s (4.5s ~ 85.7s) |
| "자료에 없음" 정직 응답 | 43/100 (자동 생성 질문이 얕은 내용도 물어본 영향) |

발견한 결함: 답변 중 드물게 다른 문자(키릴 등)가 섞이는 현상 1건 확인 — 8B 모델 자체 한계, 코드 결함 아님.

## 브라우저 히스토리

- Chrome: 모든 프로필 자동 스캔, 최근 30일 기본. Chrome 실행 중이라 DB가 잠겨있어도 임시 디렉토리에 복사(WAL/SHM 포함) 후 읽어서 문제없음.
- Safari: 코드는 동일하게 구현했지만 `History.db`가 macOS TCC로 보호돼 있어 **전체 디스크 접근 권한**이 있어야 읽힘. 시스템 설정 > 개인정보 보호 및 보안 > 전체 디스크 접근 권한에서 스크립트를 실행하는 터미널 앱을 추가하면 됨. 안 해도 GitHub/Notion/대화기록/Chrome은 정상 동작(에러 격리).
- 검색 품질 이슈 발견 및 수정: 구글 검색 결과 URL은 트래킹 파라미터가 수백 자 붙어 임베딩 노이즈가 됨 → 인덱싱 시 도메인만 남기도록 수정. 그래도 `nomic-embed-text`가 제목처럼 짧은 텍스트에 코사인 점수를 구조적으로 낮게 주는 경향이 있어(긴 노션 문서가 항상 유리), 후보군을 top_k보다 넓게(20개) 뽑은 뒤 질문 키워드가 제목에 그대로 있으면 우선순위를 올리는 하이브리드 재정렬(`domains/record/services/keyword_boost.py`)을 추가함.

## 알려진 제약 (베타)

- **sqlite-vec 확장 미사용**: 이 환경 파이썬은 `sqlite3.enable_load_extension`을 지원하지 않아 확장 로드 불가. 대신 순수 sqlite 저장 + numpy 브루트포스 코사인 유사도로 대체. 개인 규모 데이터에선 성능 문제 없음.
- **8B 모델 답변 품질**: 가끔 다른 언어 단어가 섞여 나올 수 있음(소형 모델 한계). 필요시 더 큰 모델로 교체 가능.
- **웹서칭 기록**: `log_search.py`로 남긴 것만 인덱싱됨. 브라우저 히스토리 자동수집은 미구현.

## 다음 단계

1. 브라우저 히스토리 자동수집 착수 여부 결정
2. "자료에 없음" 응답 비율 낮추려면 소스 커버리지(Notion 페이지 공유 범위 등) 확대 검토
