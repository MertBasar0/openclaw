# Workspace Capabilities Index

This index lists durable local capabilities that agents should inspect before concluding a task is unsupported. Capability descriptors are guidance only; they do not grant tool access, bypass approvals, or change OpenClaw gateway policy.

## Available Capabilities

### Windows Bridge and Graph Mail

- Descriptor: `capabilities/windows-bridge-graph-mail.md`
- Use for: Windows-side execution, Microsoft Graph auth checks, bounded Graph mail scans, queue-driven Windows helper jobs.
- Safest first check: inspect the bridge queue and recent outbound result files before starting new work.
- Important boundary: do not delete files, mutate mailbox state, start broad scans, or affect OpenClaw gateway operation without explicit user instruction.

### Capability Discovery Smoke Checklist

- Descriptor: `capabilities/smoke-checklist.md`
- Use for: validating that startup instructions, `TOOLS.md`, and descriptors remain aligned.
- Safest first check: read after changing capability docs or when a new session appears to miss local capabilities.

## Default Rule

Before answering "I cannot do this" for a local integration, Windows-only operation, Graph mail task, ACP fallback, or queue-driven job, inspect this index and the relevant descriptor first.
