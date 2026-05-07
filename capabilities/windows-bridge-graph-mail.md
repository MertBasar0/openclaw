# Windows Bridge and Graph Mail

## Purpose

Use this capability when a task needs Windows-side execution or Microsoft Graph mail access from this workspace. It exists so agents do not conclude that a task is impossible just because direct shell, direct mail tools, or ACP delegation are unavailable.

The bridge lets the Linux/WSL side prepare a request while the Windows helper executes Windows-native work.

## Supported Requests

- Check Microsoft Graph authentication status.
- Start Microsoft Graph login when explicitly requested.
- Run bounded Graph mail scans when explicitly requested.
- Inspect prior Graph mail scan outputs and queue state.
- Run Windows-host operations that require PowerShell, browser launch, .NET, or Windows filesystem access.
- Submit queue-driven jobs through the bridge wrapper.

This capability does not by itself authorize:

- Sending mail.
- Mutating mailbox state.
- Deleting queue, archive, or result files.
- Starting broad scans without explicit user instruction.
- Changing OpenClaw gateway runtime state.

## Entry Points

- Bridge root: `/home/mertb/.openclaw/workspace/windows-bridge-bootstrap`
- Request wrapper: `/home/mertb/.openclaw/workspace/windows-bridge-bootstrap/scripts/run-bridge-request.py`
- Queue root: `/home/mertb/.openclaw/workspace/windows-bridge-bootstrap/queue`
- Inbound queue: `/home/mertb/.openclaw/workspace/windows-bridge-bootstrap/queue/inbound`
- Outbound results: `/home/mertb/.openclaw/workspace/windows-bridge-bootstrap/queue/outbound`
- Archived requests: `/home/mertb/.openclaw/workspace/windows-bridge-bootstrap/queue/archive`
- Windows helper runner: `/home/mertb/.openclaw/workspace/windows-bridge-bootstrap/windows-helper/runner.ps1`

Known request kinds include:

- `graph-auth-status`
- `graph-auth-login`
- `graph-mail-job-signal-scan`
- `outlook-job-signal-scan`
- `capability-probe`
- `dotnet-info`
- `sketchup-poc-action`
- `blender-bonsai-action`

Use wrapper help or source as the source of truth when parameters are unclear.

Typical wrapper shape:

```bash
/home/mertb/.openclaw/workspace/windows-bridge-bootstrap/scripts/run-bridge-request.py graph-auth-status --timeout-seconds 90
```

For mail scans, pass bounded parameters such as `--days-back` and `--max-results` only when the wrapper supports them. Inspect generated results under `queue/outbound`.

## Safety Boundaries

- Prefer read-only inspection before starting new work.
- If a request file is in `queue/inbound`, treat it as pending unless a Windows helper process is actively consuming it.
- Do not delete queue files, output files, archived requests, or mail scan results unless Mert explicitly asks.
- Do not send mail, mutate mailbox state, or start a broad mail scan without explicit user instruction.
- Do not restart OpenClaw, run `doctor --fix`, mutate OpenClaw config, or otherwise affect gateway operation without a plain chat prompt and explicit answer.
- If ACP delegation fails, treat that as one route failing; it does not invalidate this bridge capability.

## Verification

Safe read-only queue inspection:

```bash
find /home/mertb/.openclaw/workspace/windows-bridge-bootstrap/queue -maxdepth 3 -type f -printf '%TY-%Tm-%Td %TH:%TM:%TS %s %p\n'
```

Safe read-only process inspection:

```bash
ps -eo pid,ppid,etime,stat,args | rg -i 'graph_mail|graph-mail|mail-job|run-bridge-request|runner\.ps1|pwsh|powershell|msal|microsoft\.graph|me/messages'
```

For existing mail scan output, verify at least:

- `status`
- `pageCount`
- `totalScanned`
- `matchedCount`
- timestamps
- whether the file is stale, shallow, partial, or superseded by a paged output

## Fallback

Before saying a Windows or Microsoft Graph mail task is unsupported:

- Inspect `capabilities/index.md`.
- Inspect this descriptor.
- Check `queue/inbound`, `queue/outbound`, and `queue/archive`.
- Check whether the wrapper supports the needed request kind.
- If the task would require a new broad scan, mailbox mutation, deletion, gateway restart, or config change, ask Mert explicitly in plain chat before acting.

If the bridge exists but the needed request kind is missing, say that the current bridge does not expose that specific request yet and propose a bounded bridge request type or taskflow follow-up.
