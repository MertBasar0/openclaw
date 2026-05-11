# Windows Bridge Bootstrap

Minimal Phase 1 scaffold for Windows-side automation bootstrap.

## Purpose

- keep Windows-specific probes in one place
- separate safe planning from Windows execution
- record verifiable artifacts
- prepare for a later Outlook/Microsoft Graph bridge without building it yet

## Structure

- `scripts/` trusted, narrow Windows-side entrypoints
- `probes/` command notes and lane-specific test guidance
- `artifacts/` verification records produced during bootstrap
- `samples/` example queue payloads and request envelopes

## Request Kinds

- `capability-probe`
- `dotnet-info`
- `outlook-job-signal-scan`
- `graph-auth-status`
- `graph-auth-login`
- `graph-mail-job-signal-scan`
- `sketchup-poc-action`
- `blender-bonsai-action`

## Blender+Bonsai Bridge

Use the existing queue runner from WSL:

```bash
python3 windows-bridge-bootstrap/scripts/run-bridge-request.py \
  blender-bonsai-action \
  --payload-file windows-bridge-bootstrap/samples/blender-bonsai-action.payload.json
```

`blender-bonsai-action` expects `request.payload` in one of two forms:

- Full envelope: a complete `blender-bonsai-request` object.
- Merge fields: an object with `action`, optional `artifacts`, `inputs`, `options`, and `sourceKind`. The handler fills in `kind`, `contractVersion`, `requestId`, and a default `artifacts.responsePath`.
- Any relative artifact paths inside the inner Blender+Bonsai envelope resolve from `blender-bonsai-poc/`.

Safety rules:

- `readOnly: true` is mandatory.
- The PowerShell handler runs `python3` directly when PowerShell itself is running inside WSL.
- When the queue runner is executing in Windows PowerShell, the handler calls the existing PoC script through `wsl.exe python3 ...`.

Normalized output:

- Outer queue result remains under `queue/outbound/<requestId>.result.json`.
- `result.output.response` contains the inner `blender-bonsai-result` envelope from `blender-bonsai-poc/scripts/handle_blender_bonsai_request.py`.
- The inner request/response envelopes are materialized under `blender-bonsai-poc/out/bridge/`.

## Recommended Use

1. Read the probe notes from WSL/sandboxed planning mode.
2. Run Windows-native checks only through the known working escalated lane.
3. Record each concrete verification artifact under `artifacts/`.

## Non-Goals In Phase 1

- no Graph auth flow
- no Outlook automation
- no long-lived helper service yet
- no unattended browser automation
