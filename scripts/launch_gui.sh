#!/bin/bash
# "Knowledge Agent.app"(AppleScript 런처)이 호출하는 실제 실행 스크립트.
# 터미널 없이 쓰는 경로라, 실패하면 조용히 죽지 않고 대화상자로 알린다.

DIR="/Users/jiho0215/knowledge-agent"
LOG="$DIR/logs/app.log"
mkdir -p "$DIR/logs"

# Finder가 이 번들을 Rosetta(x86_64)로 띄우면 arm64로 설치된 venv 패키지를
# 못 읽는다. 파이썬만 네이티브 아키텍처로 돌리면 되므로, 프로세스를 exec으로
# 갈아치우지 않고(그러면 LaunchServices가 앱이 죽은 것으로 본다) 실행할 때만 지정한다.
PY="$DIR/.venv/bin/python3"
if [ "$(uname -m)" != "arm64" ] && /usr/bin/arch -arm64 /usr/bin/true 2>/dev/null; then
    PY_RUNNER=(/usr/bin/arch -arm64 "$PY")
else
    PY_RUNNER=("$PY")
fi

fail() {
    osascript -e "display dialog \"$1\" buttons {\"확인\"} default button 1 with title \"Knowledge Agent\" with icon caution" >/dev/null 2>&1
    exit 1
}

if [ ! -x "$DIR/.venv/bin/python3" ]; then
    fail "설치가 완료되지 않았습니다. 터미널에서 다음을 실행하세요:\n\ncd ~/knowledge-agent\npython3 -m venv .venv\nsource .venv/bin/activate\npip install -r requirements.txt"
fi

# Ollama가 떠 있지 않으면 먼저 띄운다 (모델 응답에 필요)
if ! curl -s --max-time 3 http://localhost:11434/api/version >/dev/null 2>&1; then
    open -a Ollama 2>/dev/null
    for _ in $(seq 1 20); do
        sleep 1
        curl -s --max-time 3 http://localhost:11434/api/version >/dev/null 2>&1 && break
    done
    if ! curl -s --max-time 3 http://localhost:11434/api/version >/dev/null 2>&1; then
        fail "Ollama를 시작하지 못했습니다. Ollama 앱이 설치되어 있는지 확인하세요."
    fi
fi

cd "$DIR/src" || fail "프로젝트 폴더를 찾을 수 없습니다: $DIR/src"

echo "=== $(date '+%Y-%m-%d %H:%M:%S') 실행 ($(uname -m)) ===" >> "$LOG"
if ! "${PY_RUNNER[@]}" app/gui.py >> "$LOG" 2>&1; then
    fail "실행 중 오류가 발생했습니다. 자세한 내용: $LOG"
fi
