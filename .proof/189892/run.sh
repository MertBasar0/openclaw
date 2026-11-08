#!/usr/bin/env bash
# Only run on a fresh GitHub-hosted macOS worker; no local product execution.
set -euo pipefail
phase=${1:?phase required}
source_root=${2:?source directory required}
kit=${3:?kit directory required}
evidence=${4:?evidence directory required}
[[ ${GITHUB_ACTIONS:-} == true && ${RUNNER_OS:-} == macOS && $(uname -s) == Darwin ]]
[[ ${GITHUB_REPOSITORY:-} == MertBasar0/openclaw ]]
unset GH_TOKEN GITHUB_TOKEN NODE_AUTH_TOKEN NPM_TOKEN
mkdir -p "$evidence"
cd "$source_root"
run() {
  local label=$1; shift
  printf '%q ' "$@" > "$evidence/$label.command"
  printf '\n' >> "$evidence/$label.command"
  local code=0
  "$@" > "$evidence/$label.log" 2>&1 || code=$?
  printf '%s\n' "$code" > "$evidence/$label.exit"
  tail -n 100 "$evidence/$label.log"
  return "$code"
}
case "$phase" in
  prepare|prepare-format)
    python3 - "$kit" "$evidence" <<'PY'
import hashlib,json,pathlib,re,subprocess,sys
kit,out=map(pathlib.Path,sys.argv[1:])
m=json.loads((kit/'candidate.json').read_text())
assert m['base']=='5fe1403b94d74f8a933ca50a778e6c9bfdfd7b78'
assert m['candidate']=='5181fce57a82ec8c01ee5842212e49f08a089814'
assert m['tree']=='f753f3f9fc288c4aee9cf871914247a13571fff1'
assert re.fullmatch('[0-9a-f]{64}',m['patchSha256']), 'Provide independently verified patch SHA-256'
p=kit/'CANDIDATE.diff'
assert hashlib.sha256(p.read_bytes()).hexdigest()==m['patchSha256']
def git(*args): return subprocess.check_output(['git',*args],text=True).strip()
assert git('rev-parse','HEAD')==m['base']
assert not git('status','--porcelain','--untracked-files=no')
subprocess.run(['git','apply','--check','--index',str(p)],check=True)
subprocess.run(['git','apply','--index',str(p)],check=True)
assert sorted(git('diff','--cached','--name-only').splitlines())==sorted([
'apps/macos/Sources/OpenClaw/StatusMenuSessions.swift',
'apps/macos/Tests/OpenClawIPCTests/StatusMenuSummariesTests.swift'])
assert git('write-tree')==m['tree'], 'Exact candidate tree mismatch'
(out/'candidate.json').write_text(json.dumps(m,indent=2)+'\n')
(out/'applied.diff').write_bytes(subprocess.check_output(['git','diff','--cached','--binary']))
(out/'tree.txt').write_text(git('write-tree')+'\n')
PY
    { sw_vers; xcodebuild -version; swift --version; node --version; } > "$evidence/worker.txt"
    source scripts/lib/swift-toolchain.sh
    require_swift_toolchain
    run tools scripts/install-swift-tools.sh "$RUNNER_TEMP/swift-tools"
    echo "$RUNNER_TEMP/swift-tools" >> "$GITHUB_PATH"
    if [[ "$phase" == prepare-format ]]; then exit 0; fi
    run corepack corepack enable
    run dependencies pnpm install --frozen-lockfile --prefer-offline --optional --filter '@openclaw/mermaid-renderer...' --filter '@openclaw/gateway-protocol...' --filter 'openclaw...' --config.ignore-scripts=false --config.engine-strict=false --config.enable-pre-post-scripts=true --config.side-effects-cache=true
    run mermaid node scripts/prepare-apple-mermaid.mjs
    ;;
  build)
    run app-build swift build --package-path apps/macos --build-system native --product OpenClaw
    run tests-build swift build --package-path apps/macos --build-system native --build-tests
    ;;
  tests)
    run focused-tests node scripts/test-macos-native.mts default --package-path apps/macos --build-system native --skip-build --filter 'StatusMenuSummariesTests|SessionDataTests'
    ;;
  static)
    code=0
    run lint scripts/lint-swift.sh macos || code=1
    run format scripts/format-swift.sh macos || code=1
    run test-format swiftformat --lint apps/macos/Tests/OpenClawIPCTests/StatusMenuSummariesTests.swift --config config/swiftformat || code=1
    run whitespace git diff --cached --check || code=1
    exit "$code"
    ;;
  receipt)
    git -C "$kit/../.." rev-parse HEAD > "$evidence/harness-sha.txt"
    git status --porcelain > "$evidence/final-status.txt"
    git diff --binary > "$evidence/unexpected-tracked-changes.diff"
    shasum -a 256 apps/macos/Sources/OpenClaw/StatusMenuSessions.swift apps/macos/Tests/OpenClawIPCTests/StatusMenuSummariesTests.swift apps/macos/Tests/OpenClawIPCTests/SessionDataTests.swift > "$evidence/tested-files.sha256"
    git diff --exit-code
    python3 - "$evidence/candidate.json" <<'PY'
import json,subprocess,sys
m=json.load(open(sys.argv[1]))
assert subprocess.check_output(['git','write-tree'],text=True).strip()==m['tree']
PY
    ;;
  *) exit 2 ;;
esac
