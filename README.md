# PR189892 integrated macOS validation harness

Prepared only; **not pushed, dispatched, or executed on macOS**. Product sources and installed applications were not modified.

## Inputs required before use

1. Place Robo's complete binary-capable diff **against base `5fe1403b94d74f8a933ca50a778e6c9bfdfd7b78`** at `.proof/189892/CANDIDATE.diff`.
2. Independently verify its SHA-256 and replace `PENDING_EXACT_ROBO_PATCH` in `.proof/189892/candidate.json`. Do not substitute a diff against the old PR head.
3. Reconcile the resulting source against merge candidate `630a701d85ba0b3ce1b82d6dc6a572d0926e5e1f`, tree `d4b1aa7b250ae5a4853ac4be8ba9e0583b8ae6a2`. The runner fails unless the staged whole-tree identity matches. It does not synthesize a different merge commit or claim that checkout HEAD is the candidate commit.
4. Copy only `.github/workflows/issue-189892-native.yml` and `.proof/189892/` onto an isolated `codex/` task branch in the public `MertBasar0/openclaw` fork. Keep inspection material and this README local unless desired. Parent owns authorization/execution; this preparation does not push or dispatch.

The runner hard-pins current candidate/base/tree. If Robo supplies a different candidate, review and update all three assertions plus metadata deliberately before running.

## Execution and isolation

The manual-dispatch workflow checks out its own harness and pinned public upstream separately with `persist-credentials: false`. Job permissions are read-only contents; no repository secrets, token inputs, credential injection, caches, private network targets or self-hosted runner. Test subprocesses explicitly remove common GitHub/npm token variables. GitHub's infrastructure credentials used internally by artifact/checkout actions are not credentials granted to the product test commands.

The disposable GitHub-hosted `macos-26` OS supplies isolation. Current upstream CI uses a custom `xcode-27` label; this fork workflow deliberately does not request that label. Pinned source requires Swift6.3+/Xcode26.4+ and the runner fails preflight if the selected hosted toolchain cannot satisfy it. Such a failure is an environment failure, not a regression result. No toolchain guard override is present.

Dependency preparation matches the pinned upstream macOS lane, including optional dependencies and generated Mermaid resources. Dependencies have frozen resolution; Swift tools are installed by the repository's checksum-verified owner. Native tests use the repository's default-profile launcher and its temporary home/keychain lifecycle. No installed Companion, daily, Nemo, local user Gateway, signing credentials, or production Gateway is involved.

## Proof and limits

- Compile OpenClaw and its native test bundle.
- Run **StatusMenuSummariesTests and SessionDataTests**, including current-main preview/cancellation/cache behavior and the preserved inherited-checkmark regression. Counts must be read from actual results; prior 12-test results are not relabeled as this larger suite.
- Run scoped macOS lint/format, explicit touched test-file formatting and whitespace checks. Static checks continue after a focused-test failure to collect all actionable findings, without converting any failure into success.
- Retain command, output and exit-status files; worker versions; exact patch/tree metadata; final touched source hashes; and unexpected tracked mutation evidence. Build/dependency failure blocks product testing.
- Require no unstaged tracked modifications and unchanged exact staged candidate tree after execution.

This is integrated compile/test proof after conflict resolution, not another UI screenshot campaign or new real-Gateway proof. Existing standalone red/green and visible native evidence remain historical and separately attributed. The conflict repair must be independently reviewed as preserving the production fix and main preview fixtures. No baseline exception or failure waiver is encoded.

## Local preparation review

Completed: Bash syntax, embedded Python syntax, YAML parsing, read-only permission check; manual source audit against the pinned toolchain/dependency/launcher owners and macOS AGENTS instructions. No product code or native tests executed here. Reviewed failure handling: exact patch/hash/tree and path allowlist precede product code; absent metadata fails closed; tests depend on successful build; artifacts upload even after failure; no shell interpolation from dispatch inputs; no write-token exposure or publication logic.

Before dispatch, validate supplied patch hash/tree independently and inspect outgoing patch/log inputs for private information. After completion, inspect actual focused-test names/results (including preview tests), static exits and final source identity before calling validation passed. A green workflow alone is not a substitute for reviewing its receipts.
