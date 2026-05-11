# Runtime-Aware Model Switch Plan

Date: 2026-05-11

## Problem

OpenClaw currently treats model selection and agent runtime selection as separate configuration surfaces.

Observed local behavior:

- `openclaw models set <model>` updates `agents.defaults.model.primary`.
- It also ensures the selected model exists in `agents.defaults.models`.
- It does not update `agents.defaults.agentRuntime.id`.
- `/model` and per-session model commands are useful for model selection, but they do not guarantee a runtime-compatible switch.

This creates a confusing path when moving across runtime families, for example:

- Codex runtime with `openai-codex/gpt-5.5`
- Claude CLI runtime with `anthropic/claude-opus-4-7`
- Gemini CLI runtime with `google-gemini-cli/gemini-3.1-pro-preview`

Changing only the model can leave the agent running under the wrong backend runtime.

## Goal

Add a practical command path that switches both:

- the default model
- the compatible agent runtime

The command should validate auth/runtime readiness before making the user think the switch is complete.

## Proposed UX

Preferred new command:

```bash
openclaw models switch <model-or-alias>
```

Optional compatibility flag on the existing command:

```bash
openclaw models set <model-or-alias> --with-runtime
```

Recommended initial implementation should favor the new `models switch` command. It makes the behavior explicit and avoids changing the established meaning of `models set`.

## Expected Behavior

Given:

```bash
openclaw models switch opus
```

The command should:

1. Resolve aliases to a canonical model ref.
2. Infer the best compatible runtime for that model.
3. Check whether the runtime is installed/enabled.
4. Check whether provider auth is usable or expired.
5. Print a dry-run style summary before writing config unless `--yes` is provided.
6. Atomically update config.
7. Tell the user whether gateway restart is required.

Example output shape:

```text
Resolved model: opus -> anthropic/claude-opus-4-7
Runtime: claude-cli
Auth: expired

Next action:
openclaw models auth login --provider anthropic --method cli
```

If auth and runtime are ready:

```text
Resolved model: openai-codex/gpt-5.5
Runtime: codex
Config updates:
- agents.defaults.model.primary
- agents.defaults.models[openai-codex/gpt-5.5]
- agents.defaults.agentRuntime.id

Gateway restart recommended.
```

## Runtime Mapping

Initial runtime inference can be conservative:

| Model/provider pattern | Runtime |
| --- | --- |
| `openai-codex/*` | `codex` |
| `openai/*` when using Codex app-server mode | `codex` |
| `anthropic/*` with Claude CLI auth | `claude-cli` |
| `google-gemini-cli/*` | `gemini-cli` |
| API-only providers | keep existing default runtime unless a provider declares a runtime preference |

Do not silently switch runtime when inference is ambiguous. Ask for `--runtime <id>` or print the candidate list.

## CLI Flags

Suggested flags:

```bash
openclaw models switch <model-or-alias> --runtime <id>
openclaw models switch <model-or-alias> --agent <id>
openclaw models switch <model-or-alias> --dry-run
openclaw models switch <model-or-alias> --yes
openclaw models switch <model-or-alias> --restart-gateway
openclaw models switch <model-or-alias> --no-restart
```

`--agent <id>` should update the selected agent's model/runtime rather than the global defaults.

## Config Writes

Default switch should update:

```json
{
  "agents": {
    "defaults": {
      "agentRuntime": { "id": "<runtime>" },
      "model": { "primary": "<provider/model>" },
      "models": {
        "<provider/model>": {}
      }
    }
  }
}
```

Agent-scoped switch should update the matching `agents.list[]` entry instead.

## Safety Rules

- Do not change runtime on plain `models set` unless the user explicitly passes `--with-runtime`.
- Do not write config if runtime inference is ambiguous.
- Do not write config if provider auth is missing or expired unless `--allow-broken` is passed.
- Do not restart the gateway unless explicitly requested with `--restart-gateway`.
- Always print the before/after model and runtime.

## Implementation Notes

Likely code areas:

- `src/cli/models-cli.ts`
- `src/commands/models/set.ts`
- model alias/ref resolution helpers used by `models set`
- config update helpers around `agents.defaults.model` and `agents.defaults.agentRuntime`
- model status/auth readiness logic used by `openclaw models status`

The existing `models set` implementation confirms the split: it calls the default model update helper and does not mutate `agentRuntime`.

## Tests

Minimum test coverage:

- `models switch openai-codex/gpt-5.5` sets runtime `codex`.
- `models switch anthropic/claude-opus-4-7` sets runtime `claude-cli`.
- `models switch opus` resolves alias and sets the expected model/runtime pair.
- ambiguous provider does not mutate config.
- expired/missing auth blocks config write unless explicitly overridden.
- `models set <model>` keeps current behavior and does not mutate runtime.

## Status

Planned. This should be treated as a CLI/config ergonomics improvement, not as an urgent runtime bug.
