#!/usr/bin/env bash
set -euo pipefail
[[ ${GITHUB_ACTIONS:-} == true && ${RUNNER_OS:-} == macOS && $(uname -s) == Darwin ]]
[[ ${GITHUB_REPOSITORY:-} == MertBasar0/openclaw ]]
unset GH_TOKEN GITHUB_TOKEN NODE_AUTH_TOKEN NPM_TOKEN
kit=${1:?kit directory required}
out=${2:?evidence directory required}
mkdir -p "$out"
swiftc "$kit/desktop-preflight.swift" -o "$RUNNER_TEMP/desktop-preflight"
"$RUNNER_TEMP/desktop-preflight" > "$out/desktop.json"
cat "$out/desktop.json"
code=0
/usr/sbin/screencapture -x "$out/desktop.png" > "$out/screencapture.log" 2>&1 || code=$?
printf '%s\n' "$code" > "$out/screencapture.exit"
code=0
/usr/bin/osascript -e 'tell application "System Events" to get UI elements enabled' > "$out/system-events.txt" 2>&1 || code=$?
printf '%s\n' "$code" > "$out/system-events.exit"
git -C "$kit/../.." rev-parse HEAD > "$out/harness-sha.txt"
printf 'Permission checks only. No settings, TCC grants, or app state were changed.\n' > "$out/scope.txt"
