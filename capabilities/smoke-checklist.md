# Capability Discovery Smoke Checklist

Use this checklist after changing workspace capability docs or when validating a new session startup.

## Startup Visibility

- `AGENTS.md` tells the agent to read `capabilities/index.md`.
- `TOOLS.md` points to `capabilities/index.md` and the relevant descriptor instead of duplicating every operational detail.
- `capabilities/index.md` lists each durable local capability.
- Each listed capability has a descriptor file.

## Behavior Checks

- For Windows-only work, inspect the Windows Bridge descriptor before saying the task is unsupported.
- For Microsoft Graph mail work, inspect the Windows Bridge and Graph Mail descriptor before assuming direct mail tools must exist.
- For queue-driven work, inspect queue state before starting new jobs.
- If ACP delegation fails, check whether a local bridge or taskflow capability covers the request.

## Safety Checks

- Do not treat capability docs as permission grants.
- Do not delete files, mutate mailbox state, start broad scans, or affect OpenClaw gateway operation unless Mert explicitly asks.
- For OpenClaw runtime-impacting actions, stop and ask in plain chat even if a normal tool approval prompt appears.
