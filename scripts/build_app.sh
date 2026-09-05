#!/bin/bash
# Finder에서 더블클릭으로 실행할 수 있는 "Knowledge Agent.app"을 만든다.
# osacompile로 만드는 이유: 셸 스크립트만 담은 수제 .app 번들은 macOS
# LaunchServices가 실행을 거부(-1712)하는 경우가 있어, 정식 앱으로 취급되는
# AppleScript 애플릿을 껍데기로 쓰고 실제 실행은 launch_gui.sh에 맡긴다.
set -euo pipefail

PROJECT_DIR="/Users/jiho0215/knowledge-agent"
APP_PATH="$HOME/Applications/Knowledge Agent.app"
SCRIPT_SOURCE="$(mktemp -t ka_launcher).applescript"

cat > "$SCRIPT_SOURCE" <<APPLESCRIPT
on run
	set launchScript to "$PROJECT_DIR/scripts/launch_gui.sh"
	try
		do shell script "nohup " & quoted form of launchScript & " > /dev/null 2>&1 &"
	on error errMsg
		display dialog "실행에 실패했습니다:" & return & errMsg buttons {"확인"} default button 1 with title "Knowledge Agent" with icon caution
	end try
end run
APPLESCRIPT

mkdir -p "$HOME/Applications"
rm -rf "$APP_PATH"
osacompile -o "$APP_PATH" "$SCRIPT_SOURCE"
rm -f "$SCRIPT_SOURCE"

chmod +x "$PROJECT_DIR/scripts/launch_gui.sh"

echo "생성됨: $APP_PATH"
echo "Finder에서 더블클릭하거나, Dock으로 끌어다 놓고 쓰면 됩니다."
