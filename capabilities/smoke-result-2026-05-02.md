# Capability Discovery Smoke Result - 2026-05-02

## Scope

Read-only validation of the local workspace capability discovery docs.

Checked files:

- `AGENTS.md`
- `TOOLS.md`
- `capabilities/index.md`
- `capabilities/windows-bridge-graph-mail.md`
- `capabilities/smoke-checklist.md`

## Result

Status: pass

## Checks

- Pass: `AGENTS.md` instructs session startup to read `capabilities/index.md`.
- Pass: `AGENTS.md` instructs agents to read the specific `capabilities/*.md` descriptor relevant to the task.
- Pass: `AGENTS.md` says new durable local capabilities should be documented in `capabilities/*.md`, added to `capabilities/index.md`, and summarized in `TOOLS.md` only as an access pointer.
- Pass: `TOOLS.md` points to `capabilities/index.md` and `capabilities/windows-bridge-graph-mail.md` instead of duplicating all operational details.
- Pass: `capabilities/index.md` lists the current durable descriptors.
- Pass: every descriptor listed in `capabilities/index.md` exists.
- Pass: Windows and Microsoft Graph mail fallback guidance says to inspect the capability index and descriptor before answering that the task is unsupported.
- Pass: gateway-impacting actions require a plain chat prompt and explicit answer before acting.
- Pass: mailbox mutation, broad scans, and deletion of queue/output files require explicit user instruction.

## Current Capability Files

- `capabilities/index.md`
- `capabilities/smoke-checklist.md`
- `capabilities/windows-bridge-graph-mail.md`

## Notes

This smoke check did not start jobs, inspect live queues, restart OpenClaw, mutate config, or contact external services. It only verified local documentation consistency.
