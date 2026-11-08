#!/usr/bin/env bash
# This harness is for a disposable, secretless GitHub-hosted macOS worker only.
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
  tail -n 70 "$evidence/$label.log"
  return "$code"
}
verify_candidate() {
  python3 - "$kit/candidate.json" <<'PY'
import json,subprocess,sys
m=json.load(open(sys.argv[1]))
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
assert git('rev-parse','HEAD')==m['candidate'], 'HEAD changed'
assert git('rev-parse','HEAD^{tree}')==m['tree'], 'Committed tree changed'
assert git('write-tree')==m['tree'], 'Index tree changed'
subprocess.run(['git','diff','--exit-code','HEAD','--'],check=True)
PY
}
case "$phase" in
  prepare)
    python3 - "$kit/candidate.json" "$evidence" <<'PY'
import json,pathlib,subprocess,sys
m=json.load(open(sys.argv[1])); out=pathlib.Path(sys.argv[2])
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
assert git('rev-parse','HEAD')==m['candidate']
assert git('rev-parse','HEAD^{tree}')==m['tree']
assert not git('status','--porcelain','--untracked-files=no')
assert git('show','-s','--format=%P','HEAD')==m['base']
assert sorted(git('diff','--name-only',m['base'],'HEAD').splitlines())==m['paths']
(out/'candidate.json').write_text(json.dumps(m,indent=2)+'\n')
(out/'candidate.diff').write_bytes(subprocess.check_output(['git','diff',m['base'],'HEAD']))
PY
    { sw_vers; xcodebuild -version; swift --version; node --version; } > "$evidence/worker.txt"
    source scripts/lib/swift-toolchain.sh
    require_swift_toolchain
    run tools scripts/install-swift-tools.sh "$RUNNER_TEMP/swift-tools"
    echo "$RUNNER_TEMP/swift-tools" >> "$GITHUB_PATH"
    run corepack corepack enable
    run dependencies pnpm install --frozen-lockfile --prefer-offline --optional --filter '@openclaw/mermaid-renderer...' --filter '@openclaw/gateway-protocol...' --filter 'openclaw...' --config.ignore-scripts=false --config.engine-strict=false --config.enable-pre-post-scripts=true --config.side-effects-cache=true
    run mermaid node scripts/prepare-apple-mermaid.mjs
    ;;
  baseline)
    python3 - "$kit/candidate.json" <<'PY'
import json,pathlib,subprocess,sys
m=json.load(open(sys.argv[1])); p=pathlib.Path(m['productionPath'])
p.write_bytes(subprocess.check_output(['git','show',m['base']+':'+m['productionPath']]))
PY
    run baseline-test-build swift build --package-path apps/macos --build-system native --build-tests
    code=0
    run baseline-regression node scripts/test-macos-native.mts default --package-path apps/macos --build-system native --skip-build --filter 'StatusMenuSummariesTests' || code=$?
    python3 - "$evidence" "$code" <<'PY'
import json,pathlib,re,sys
p=pathlib.Path(sys.argv[1]); code=int(sys.argv[2]); text=(p/'baseline-regression.log').read_text(errors='replace')
assert code == 1, 'Baseline must finish with a test failure, not a crash or setup error'
assert 'session preference checkmarks distinguish inheritance from explicit Off' in text, 'Regression did not execute'
assert 'checked' in text and 'Expectation failed' in text, 'Missing intended checkmark assertion failure'
assert re.search(r'Test run with \d+ tests? (?:in \d+ suites? )?failed after [^\n]+ with 12 issues?\.',text), 'Missing completed 12-issue baseline summary'
issues=[line for line in text.splitlines() if 'recorded an issue' in line]
assert len(issues)==12, 'Unexpected individual assertion count'
assert all('session preference checkmarks distinguish inheritance from explicit Off' in line and re.search(r'checked.*\["off"\].*expected.*\[\]',line) for line in issues), 'Unexpected baseline assertion'
assert sum('reuseMenu → false' in line for line in issues)==6
assert sum('reuseMenu → true' in line for line in issues)==6
failures=re.findall(r'Test [“\"](.+?)[”\"](?: with \d+ test cases?)? failed after ',text)
assert failures and all('session preference checkmarks distinguish inheritance from explicit Off' in name for name in failures), 'An unrelated test failed'
for marker in ['test Gateway retirement is unverified:', 'security delete-keychain failed', 'retained resources after incomplete launch/cleanup:', 'Swift exited 0 without valid test completion', 'unexpected signal', 'uncaught exception']:
    assert marker.lower() not in text.lower(), 'Native launcher or cleanup failed: '+marker
(p/'baseline-verdict.json').write_text(json.dumps({'expectedFailure':True,'exitCode':code,'expectedAssertionIssues':12})+'\n')
PY
    ;;
  candidate)
    python3 - "$kit/candidate.json" <<'PY'
import json,pathlib,subprocess,sys
m=json.load(open(sys.argv[1])); p=pathlib.Path(m['productionPath'])
p.write_bytes(subprocess.check_output(['git','show',m['candidate']+':'+m['productionPath']]))
PY
    verify_candidate
    run candidate-app-build swift build --package-path apps/macos --build-system native --product OpenClaw
    run candidate-test-build swift build --package-path apps/macos --build-system native --build-tests
    run candidate-focused-tests node scripts/test-macos-native.mts default --package-path apps/macos --build-system native --skip-build --filter 'StatusMenuSummariesTests|SessionDataTests'
    ;;
  static)
    code=0
    run lint scripts/lint-swift.sh macos || code=1
    run format scripts/format-swift.sh macos || code=1
    run touched-test-format swiftformat --lint apps/macos/Tests/OpenClawIPCTests/StatusMenuSummariesTests.swift --config config/swiftformat || code=1
    base=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["base"])' "$kit/candidate.json")
    run whitespace git diff --check "$base" HEAD || code=1
    exit "$code"
    ;;
  receipt)
    git -C "$kit/../.." rev-parse HEAD > "$evidence/harness-sha.txt"
    git status --porcelain > "$evidence/final-status.txt"
    git diff --binary > "$evidence/unexpected-tracked-changes.diff"
    shasum -a 256 apps/macos/Sources/OpenClaw/StatusMenuSessions.swift apps/macos/Tests/OpenClawIPCTests/StatusMenuSummariesTests.swift apps/macos/Tests/OpenClawIPCTests/SessionDataTests.swift > "$evidence/tested-files.sha256"
    verify_candidate
    ;;
  *) exit 2 ;;
esac
