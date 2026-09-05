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
- [x] 주제별 요약 인덱스(`data/index/`) — 원본 청크는 그대로 두고, 프로젝트 단위로 로컬 LLM 요약을 md로 남겨 `INDEX.md`부터 훑을 수 있게 함(Claude 자신의 MEMORY.md 구조를 참고). 내용 안 바뀐 주제는 재요약 안 하고 재사용(증분 빌드)
- [x] `kb` CLI 단축 명령어 — venv/경로 신경 안 쓰고 바로 사용
- [x] 브라우저 채팅 UI(`kb web`) + 네이티브 창(`kb gui`, pywebview) — SSE 스트리밍, 중단 후 이어쓰기 그대로 재사용
- [x] 날짜인지 검색 — "어제"/"오늘" 같은 상대 날짜를 실제 날짜구간으로 해석해 그 안에서만 검색, 날짜 의도가 있으면 대화·방문기록·웹서칭 같은 사건형 소스를 노션 같은 지식형 소스보다 우선
- [x] 앱 사용 타임라인(`AppFocusSource`) — macOS `NSWorkspace` 알림 기반, 권한 불필요. `kb watch-focus`로 상시 감시하거나 LaunchAgent(`scripts/com.knowledgeagent.appfocus.plist`)로 로그인 시 자동 실행

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
    topicindex/             주제별 요약 md 파일 + 루트 INDEX.md 작성(data/index/)
  presentation/
    cli/                    답변/통계 포맷팅
    web/                    FastAPI 서버 + 정적 채팅 UI (SSE 스트리밍, ask_resumable 재사용)
  app/                    container(공통 조립) / config / sync.py / ask.py / ask_resumable.py / log_search.py / run_benchmark.py
```

## 실행

최초 1회, `~/.zshrc`에 `export PATH="$HOME/knowledge-agent/bin:$PATH"` 추가(이미 되어있음) 후 새 터미널에서:

```bash
kb ask "질문 내용"                    # 질의
kb ask-resume "질문 내용"             # 질의 (중단돼도 같은 질문으로 재실행하면 이어서 생성)
kb sync                              # 소스 수집 + 인덱싱 (매일 09:00 cron 자동 실행됨)
kb log "검색어" "URL" "메모"          # 웹서칭 기록 남기기
kb bench 100                         # 인덱싱된 데이터 기반 자동 질문 100개 생성 후 일괄 테스트
kb index                             # 주제 요약 인덱스(INDEX.md) 열기
kb web                               # 브라우저에서 채팅 화면 (http://127.0.0.1:8420)
kb gui                               # 네이티브 창으로 채팅 화면 (pywebview)
kb watch-focus                       # 앱 전환 감시 (foreground, Ctrl-C 종료)
```

venv 활성화나 `src/` 경로 이동 없이 `kb` 명령 하나로 다 됨(`bin/kb`가 내부적으로 처리). Ollama 앱은 메뉴바에서 실행 중이어야 함(Spotlight로 "Ollama" 검색해서 실행, 터미널 불필요).

**앱 사용 타임라인 상시 감시** (로그인할 때마다 자동 실행, 이미 설치·실행됨):
```bash
cp scripts/com.knowledgeagent.appfocus.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.knowledgeagent.appfocus.plist
```
중지: `launchctl unload ~/Library/LaunchAgents/com.knowledgeagent.appfocus.plist`

원본 명령어를 직접 쓰려면(디버깅 등):
```bash
source .venv/bin/activate
cd src && python3 app/ask.py "질문 내용"
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
- 검색 품질 이슈 발견 및 수정: 구글 검색 결과 URL은 트래킹 파라미터가 수백 자 붙어 임베딩 노이즈가 됨 → 인덱싱 시 도메인만 남기도록 수정. 그래도 `nomic-embed-text`가 제목처럼 짧은 텍스트에 코사인 점수를 구조적으로 낮게 주는 경향이 있어(긴 노션 문서가 항상 유리), 후보군을 top_k보다 넓게(50개) 뽑은 뒤 질문 키워드가 제목에 그대로 있으면 우선순위를 올리는 하이브리드 재정렬(`domains/record/services/keyword_boost.py`)을 추가함.
- 추가로 발견한 버그: 같은 페이지를 URL 프래그먼트/쿼리만 다르게 여러 번 방문하면(예: 같은 ChatGPT 대화창을 설정 탭 옮겨 다니며 재방문) 소스 단에서 별개 문서로 취급돼 거의 내용 없는 중복이 top-5를 잠식하고, 진짜 알맹이 있는 자료(예: Notion 실습 노트)가 밀려나는 문제가 있었음("CSAPP 내용 알려줘"가 빈 답변만 준 원인). (title, domain) 기준 인덱싱 단계 중복 제거 + 검색 단계 (source, title) 중복 제거 2중으로 수정.

## 알려진 제약 (베타)

- **sqlite-vec 확장 미사용**: 이 환경 파이썬은 `sqlite3.enable_load_extension`을 지원하지 않아 확장 로드 불가. 대신 순수 sqlite 저장 + numpy 브루트포스 코사인 유사도로 대체. 개인 규모 데이터에선 성능 문제 없음.
- **8B 모델 답변 품질**: 가끔 다른 언어 단어가 섞여 나올 수 있음(소형 모델 한계). 필요시 더 큰 모델로 교체 가능.
- **웹서칭 기록**: `log_search.py`로 남긴 것만 인덱싱됨. 브라우저 히스토리 자동수집은 미구현.

## 주제별 요약 인덱스

`sync.py` 실행 시 인덱싱 이후 자동으로 프로젝트/문서 단위로 묶어 로컬 LLM(qwen3:8b)으로 2~4문장 요약하고
`data/index/{source}/{slug}.md`로 저장, `data/index/INDEX.md`에서 전체 목록을 한눈에 볼 수 있게 함.
같은 내용이면(청크 기준 최신 수정일 동일) 재요약하지 않고 기존 요약 재사용 — 최초 1회(주제 수에 비례, 주제당 15~20초)만 오래 걸리고 이후 증분 동기화는 빠름.
검색(`ask.py`)은 여전히 원본 청크 기반 벡터 검색을 그대로 사용함 — 이 인덱스는 사람이(또는 향후 다른 도구가) 빠르게 훑어보기 위한 보조 레이어.

## 다음 단계 (리서치 기반 v2 기획서 순서)

1. `AppFocusSource` 추가 — macOS `NSWorkspace` 알림 기반 앱 전환 로그, 권한 불필요, 날짜인지 검색이 활용할 "언제 뭐 하고 있었는지" 데이터 확보
2. `WindowTitleSource` 추가 — Accessibility API(권한 1회), 창 제목까지 확보
3. 대화기록 소스가 세션당 앞 6000자로 잘리는 문제 — 긴 세션은 최근 내용이 인덱스에서 아예 빠짐
4. `dateparser`가 "지난주"/"최근" 같은 주 단위 이상 상대 날짜는 못 잡는 한계 — 필요시 별도 규칙 추가
5. 한글-영문 제목 불일치(예: "정글미팅" 질의가 실제 제목 "Jungle Meeting"과 매칭 안 됨) — 키워드 부스트가 언어 간에는 안 통함
6. 화면 캡처(OCR→요약 후 원본 삭제) 소스 — 이벤트 기반으로, 상시캡처는 지양(Windows Recall 사례 참고)

리서치 배경과 상세 설계는 기획서 아티팩트 참고: [OS 활동 기억 에이전트 — 2단계 설계](https://claude.ai/code/artifact/1cd32129-746f-4dbf-b874-09541f969a1a)
