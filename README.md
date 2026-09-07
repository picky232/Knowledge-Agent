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
- [x] 창 제목 타임라인(`WindowTitleSource`) — Accessibility API 기반(5초 폴링). **손쉬운 사용 권한 필요 — 아직 승인 안 함**, 승인 전까지는 로그가 안 쌓일 뿐 다른 기능엔 영향 없음(에러 격리)
- [x] 화면 텍스트 기록(`ScreenTextSource`) — 앱 전환 시에만 캡처 → Apple Vision OCR로 텍스트 추출 → **스크린샷 원본 즉시 삭제**, 텍스트만 보관. 비밀번호 관리자·은행 앱은 캡처 자체를 안 하고, OCR 결과에 민감어가 섞이면 그 캡처분을 통째로 버림. **화면 기록 권한 필요 — 아직 승인 안 함**
- [x] 파일 작업 기록(`FileActivitySource`) — FSEvents(watchdog) 기반, 권한 불필요. 홈 아래 작업 폴더를 감시하되 `node_modules`·`.git`·캐시·숨김파일은 제외하고 코드/문서 확장자만 기록, 같은 파일 5분 디바운스
- [x] 대화기록 6000자 잘림 문제 수정 — 세션 전체를 앞부분만 자르지 않고 **날짜별로 문서를 분리**해 각각 넉넉한 한도(2만자)를 둠. 이 프로젝트를 만든 세션처럼 며칠에 걸친 긴 세션도 날짜별로 다 보존됨(48청크→154청크로 증가)

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
    appfocus/               NSWorkspace 앱 전환 로그 → 날짜별 타임라인
    windowtitle/            Accessibility API 창 제목 로그 → 날짜별 타임라인
    fileactivity/           FSEvents 파일 작업 로그 → 날짜별 기록(노이즈 필터 포함)
    screentext/             화면 OCR 텍스트 로그 → 날짜별 기록(캡처 정책 필터 포함)
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
kb measure 30                        # 응답시간·정확도 측정 (생성속도 12 tok/s 미만이면 측정 거부)
kb measure 30 --accuracy-only        # 느린 환경에서 정확도(거부율)만 측정
kb compare qwen3:8b qwen3:4b 30      # 같은 질문으로 두 모델 비교
kb index                             # 주제 요약 인덱스(INDEX.md) 열기
kb web                               # 브라우저에서 채팅 화면 (http://127.0.0.1:8420)
kb gui                               # 네이티브 창으로 채팅 화면 (pywebview)
kb watch-focus                       # 앱 전환 감시 (foreground, Ctrl-C 종료)
kb watch-files                       # 파일 작업 감시 (foreground, Ctrl-C 종료)
kb watch-screen                      # 화면 텍스트 감시 (화면 기록 권한 필요)
```

venv 활성화나 `src/` 경로 이동 없이 `kb` 명령 하나로 다 됨(`bin/kb`가 내부적으로 처리). Ollama 앱은 메뉴바에서 실행 중이어야 함(Spotlight로 "Ollama" 검색해서 실행, 터미널 불필요).

**앱 사용 타임라인 상시 감시** (로그인할 때마다 자동 실행, 이미 설치·실행됨):
```bash
cp scripts/com.knowledgeagent.appfocus.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.knowledgeagent.appfocus.plist
```
중지: `launchctl unload ~/Library/LaunchAgents/com.knowledgeagent.appfocus.plist`

**파일 작업 상시 감시** (권한 불필요, 이미 설치·실행됨):
```bash
cp scripts/com.knowledgeagent.fileactivity.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.knowledgeagent.fileactivity.plist
```
같은 파일은 5분에 한 번만 기록하므로 저장 한 번에 로그가 수십 줄씩 쌓이지 않음.

**화면 텍스트 상시 감시** (화면 기록 권한 먼저 필요):
1. `kb watch-screen` 한 번 실행 — 권한 없으면 안내 메시지 뜨고 종료
2. 시스템 설정 > 개인정보 보호 및 보안 > 화면 및 시스템 오디오 기록에서 터미널 앱 추가
3. 승인 후 상시 실행하려면:
```bash
cp scripts/com.knowledgeagent.screentext.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.knowledgeagent.screentext.plist
```

설계상 안전장치(Windows Recall이 반복해서 보안 문제를 겪은 지점을 피하려는 것):
- 상시 녹화가 아니라 **앱 전환 시에만** 캡처하고, 같은 앱은 3분 내 재캡처 안 함
- 캡처 → OCR → **이미지 파일 즉시 삭제**, 저장되는 건 텍스트뿐
- 비밀번호 관리자·키체인·은행 앱은 캡처 자체를 건너뜀(`capture_policy.py`)
- OCR 결과에 `password`/`api key`/`계좌` 같은 민감어가 있으면 그 캡처분 전체를 버림

**창 제목 상시 감시** (손쉬운 사용 권한 먼저 필요):
1. `kb watch-window` 한 번 실행 — 권한 없으면 안내 메시지 뜨고 종료
2. 시스템 설정 > 개인정보 보호 및 보안 > 손쉬운 사용에서 터미널 앱(또는 python3) 추가
3. 승인 후 상시 실행하려면:
```bash
cp scripts/com.knowledgeagent.windowtitle.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.knowledgeagent.windowtitle.plist
```

원본 명령어를 직접 쓰려면(디버깅 등):
```bash
source .venv/bin/activate
cd src && python3 app/ask.py "질문 내용"
```

## 벤치마크 결과 (2026-09-05, 100문항)

| 지표 | 최초(9/4) | 검색 개선 후 | 속도 개선 후 |
|---|---|---|---|
| 성공 / 실패 | 100 / 0 | 100 / 0 | 100 / 0 |
| 출처 없이 답한 케이스 | 0건 | 0건 | 0건 |
| 평균 응답시간 | 19.9s | 27.9s | **13.0s** |
| 최대 응답시간 | 85.7s | 82.0s | **31.4s** |
| "자료에 없음" 정직 응답 | 43/100 | 26/100 | 24/100 |

중간에 응답시간이 늘어난 건 인덱싱 데이터가 863→1328청크로 늘고 검색 후보군을 20→50으로 넓힌 대가.
이후 아래 "응답시간 최적화"로 성공률·출처 품질을 그대로 둔 채 절반 이하로 줄임.

## 응답시간 최적화 (2026-09-05)

단계별로 실측해보니 임베딩 0.59s / 벡터검색 0.21s / **LLM 생성 51.9s** — 검색 구조는 병목이 아니었음.
LLM 호출 자체를 파보니 같은 요청이 상황에 따라 8.9s ~ 51.9s로 편차가 컸고, 원인은 **모델 스와핑**이었음:
질의 한 번에 임베딩 모델(nomic-embed-text)과 답변 모델(qwen3:8b)을 번갈아 호출하는데,
Ollama 기본 keep_alive가 짧아 서로를 메모리에서 밀어내며 매 요청마다 4.5초 로드 비용이 붙고 있었음.

**해결**: 모든 Ollama 호출에 `keep_alive: 30m` 명시 → 두 모델(합 6.3GB, 16GB 중) 동시 상주해 스와핑 제거.

시도했다가 기각한 방법들(전부 실측 후 판단):
- 컨텍스트 축소(청크당 700→300자): 15.8→13.8s, 효과 미미
- 검색 청크 수 축소(5→3개): 8.6s로 빨라지지만 답변 못 하는 케이스가 0→2건 발생 — 성공률을 깎는 트레이드오프라 기각
- 더 작은 모델(qwen3:4b): **오히려 52~79s로 훨씬 느리고** 자료없음 3/6로 악화(답변이 장황해짐). 삭제함
  - (2026-09-07 재검토) 이 판단은 근거가 약하다. 표본이 6문항뿐이고, 4B가 8B보다 느리다는 결과 자체가
    모델 성능이 아니라 스와핑/저전력 오염의 징후다(당시는 `keep_alive` 수정 전). 위 "측정 환경" 항목의
    두 요인을 통제한 뒤 `kb compare qwen3:8b qwen3:4b`로 다시 재는 중.

발견한 결함: 답변 중 드물게 다른 문자(키릴 등)가 섞이는 현상 1건 확인 — 8B 모델 자체 한계, 코드 결함 아님.

## 검색 정확도 (2026-09-07, 같은 30문항 3회)

`build_questions`가 seed를 고정하므로 세 번 모두 완전히 같은 질문이다.

| | 기준선 | 문서 앞부분 제공 | 제목매칭 3건 수정 |
|---|---|---|---|
| 답변 거부 | 7 / 30 | 4 / 30 | **2 / 30** |
| 입력 토큰 평균 | 767 | 789 | 816 |
| 출력 토큰 평균 | 43.6 | 47.2 | 43.8 |

남은 2건(`피키`, `파일구조`)은 인덱스에 제목만 있고 본문이 없는 문서라 "기록에 없습니다"가 맞는 답이다.

고친 결함 네 가지. 전부 실측으로 원인을 짚었다.

1. **제목으로 찾은 문서가 중간 토막으로 전달됨** (`services/head_recall.py`)
   제목이 맞는 문서를 찾아놓고 그 안에서 다시 유사도로 조각을 골라 한가운데를 집었다.
   `"티맥스 7주차 뭐로 구현했어?"`에 `"잘못된 입력입니다 다시 시도해주세요')..."`,
   `"db.sql명령어 뭐로 구현했어?"`에 `"mber_2504;"`(단어 중간에서 시작)가 전달돼
   모델이 제목을 보고도 답을 못 했다. 첫 조각은 각각 `"import random"`,
   `"-- create -- insert -- select *"`로 시작해 무엇을 만든 문서인지 바로 드러난다.

2. **질문어가 키워드로 쓰여 정답을 밀어냄** (`services/keyword_boost.py`)
   단계별로 찍어보니 `"웹디자인에서 무슨 작업했어?"`는 dedup까지 노션 `웹디자인`이 1위였는데,
   마지막 boost가 `무슨`을 키워드로 써서 `"진 그레이가 피터에게 무슨 짓을 했을까? - YouTube"`에
   1위를 내줬다. `title_recall`이 이미 가진 질문어 목록을 boost에서도 빼도록 했다.

3. **조사 제거 가드가 두 음절 명사를 막음** (`services/title_recall.py`)
   `자료에서`의 조사를 못 떼 `취업 지원 증빙 자료`를, `22에서`를 못 떼 `7/22`를 놓쳤다.
   가드 자체는 필요하다 — `의`가 조사 목록에 있어 `회의`가 `회`가 된다. 어간 최소 길이만 2로 분리.

4. **와일드카드로 넓게 훑은 뒤 유사도로 자르면 정확한 제목이 탈락** (`services/title_recall.py`)
   `7 22`는 `%7%22%`로 10개 제목에 걸리는데, 짧은 제목은 `nomic-embed-text`에서 점수가 낮아
   정작 `7/22`가 먼저 잘려나갔다. 후보를 넓게 받아 구가 제목을 덮는 비율로 세운 뒤 자른다.

측정 도구 자체의 결함도 하나 있었다. 거부 판정이 답변 전체에서 문구를 찾는 방식이라,
모델이 정확히 요약한 뒤 프롬프트 지시문을 그대로 덧붙인 답변이 거부로 집계됐다.
프롬프트가 첫 문장에 결론을 쓰라고 지시하므로 첫 문장만 보도록 고쳤다.

## 측정 환경 (2026-09-07) — 응답시간을 재기 전에 반드시 확인할 것

이 프로젝트에서 응답시간 숫자를 네 번 버렸다. 790s·4,017s(다른 작업 동시 실행), 평균 23.9s(스왑 8.7GB),
평균 187.79s(같은 원인). 매번 숫자를 먼저 적고 원인은 나중에 찾았다. 원인은 코드가 아니라 측정 환경이었다.

**확인된 두 가지 환경 요인:**

1. **저전력 모드 + 배터리 구동** — `pmset -g | grep lowpowermode`가 `1`이고 전원이 배터리면
   M2 Air는 GPU를 강하게 제한한다. 같은 코드가 **17 tok/s → 3.4 tok/s로 5배 느려진다.**
   측정 전에 충전기를 연결하고 저전력 모드를 끌 것(설정 > 배터리, 또는 `sudo pmset -a lowpowermode 0`).

2. **모델이 통합 메모리를 wired로 점유** — 모델을 내렸다 올리며 실측한 결과
   `wired 8,039M → 2,379M`, 즉 **qwen3:8b + nomic이 5,660MB를 붙잡는다.**
   16GB 머신에서 사용자 앱이 9GB를 쓰면 한도를 넘겨 스왑으로 밀린다.
   `top -l 1 -n 0 | grep PhysMem`의 wired 값으로 확인할 수 있다.
   `vm_stat`의 free 페이지 수는 macOS가 비활성 페이지를 회수하므로 실제 성능과 잘 맞지 않는다.

**그래서 `kb measure`는 먼저 생성 속도를 재고 12 tok/s 미만이면 측정을 거부한다.**
거부율과 입출력 토큰 수는 생성 속도와 무관하므로 `--accuracy-only`로 느린 환경에서도 정확도는 잴 수 있다.
`data/latency_report.jsonl`에 질문마다 시간과 함께 토큰 수·tok/s를 남겨, 나쁜 숫자가 스스로를 식별하게 했다.

## 인덱스 백업

`data/records.db`가 정리 작업 중 0바이트로 비는 사고가 있었다(원본 소스는 전부 무사, 재인덱싱으로 복구).
`scripts/backup_index.sh`가 `run_sync.sh`에서 인덱싱 직전에 자동 실행돼 `data/backups/`에 최근 5벌을 남긴다.
`sqlite3 .backup`을 쓰므로 다른 프로세스가 쓰는 중이어도 일관된 사본이 만들어진다.

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

- [x] `AppFocusSource` — macOS `NSWorkspace` 알림 기반 앱 전환 로그, 권한 불필요
- [x] `WindowTitleSource` — Accessibility API, 코드는 완성(승인 대기)
- [x] 대화기록 6000자 잘림 → 날짜별 문서 분리로 해결
- [~] `dateparser`가 "지난주"/"최근" 같은 주 단위 이상 상대 날짜는 못 잡는 한계 — 보류(narrow edge case, 필요성 낮음)
- [~] 한글-영문 제목 불일치(예: "정글미팅" → "Jungle Meeting" 매칭 안 됨) — 확인해보니 순수 임베딩 유사도로도 210위 밖이라 후보군 확장으론 해결 안 됨, 음역/발음매칭 엔진 필요. 공수 대비 효과 낮아 보류
- [ ] Accessibility 권한 승인 — 시스템 설정에서 직접 해야 함, `WindowTitleSource` 활성화의 전제조건
- [x] 파일 작업 감시(`FileActivitySource`) — 권한 불필요, LaunchAgent로 상시 실행 중
- [x] 화면 캡처 OCR(`ScreenTextSource`) — 구현 완료, 화면 기록 권한 승인만 남음
- [ ] 권한 승인 2건(손쉬운 사용 / 화면 기록) — 시스템 설정에서 직접 해야 함. 승인 전까지 해당 소스만 비어있고 나머지는 정상

리서치 배경과 상세 설계는 기획서 아티팩트 참고: [OS 활동 기억 에이전트 — 2단계 설계](https://claude.ai/code/artifact/1cd32129-746f-4dbf-b874-09541f969a1a)
