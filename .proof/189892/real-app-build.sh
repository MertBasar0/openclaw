#!/usr/bin/env bash
set -euo pipefail
[[ ${GITHUB_ACTIONS:-} == true && ${RUNNER_OS:-} == macOS && $(uname -s) == Darwin ]]
[[ ${GITHUB_REPOSITORY:-} == MertBasar0/openclaw ]]
unset GH_TOKEN GITHUB_TOKEN NODE_AUTH_TOKEN NPM_TOKEN
phase=${1:?}; source_root=${2:?}; kit=${3:?}; out=${4:?}
mkdir -p "$out"
cd "$source_root"
run() {
  local label=$1; shift
  local code=0
  "$@" > "$out/$label.log" 2>&1 || code=$?
  printf '%s\n' "$code" > "$out/$label.exit"
  tail -n 45 "$out/$label.log"
  return "$code"
}
if [[ $phase == prepare ]]; then
  python3 - "$kit/candidate.json" <<'PY'
import json,subprocess,sys
m=json.load(open(sys.argv[1]))
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
assert git('rev-parse','HEAD')==m['candidate']
assert git('rev-parse','HEAD^{tree}')==m['tree']
assert git('show','-s','--format=%P','HEAD')==m['base']
assert not git('status','--porcelain','--untracked-files=no')
PY
  { sw_vers; xcodebuild -version; swift --version; node --version; } > "$out/toolchain.txt"
  run driver swiftc -framework AppKit -framework ApplicationServices "$kit/RealAppMenuDriver.swift" -o "$RUNNER_TEMP/real-menu-driver"
  source scripts/lib/swift-toolchain.sh
  require_swift_toolchain
  run corepack corepack enable
  run dependencies pnpm install --frozen-lockfile --prefer-offline
  # Restored root artifacts alone omit workspace-package outputs required at runtime.
  run gateway-runtime node --import ./scripts/tsx.mjs scripts/build-all.mts qaRuntime
  run mermaid node scripts/prepare-apple-mermaid.mjs
  run mac-cli swift build --package-path apps/macos --build-system native --product openclaw-mac
else
  python3 - "$kit/candidate.json" "$phase" <<'PY'
import json,pathlib,subprocess,sys
m=json.load(open(sys.argv[1])); ref=m['base'] if sys.argv[2]=='baseline' else m['candidate']
pathlib.Path(m['productionPath']).write_bytes(subprocess.check_output(['git','show',ref+':'+m['productionPath']]))
PY
  run "$phase-build" swift build --package-path apps/macos --build-system native --product OpenClaw
  if [[ $phase == candidate ]]; then git diff --exit-code HEAD --; fi
fi
