# Work Computer Setup

Use this flow when setting up OpenClaw on a new work computer.

## 1. Clone This Private Repo

```bash
git clone <private-repo-url> openclaw-workstation-bootstrap
cd openclaw-workstation-bootstrap
```

## 2. Install Runtime

Linux/macOS:

```bash
./bootstrap.sh
```

Windows:

```bat
bootstrap.bat
```

This installs:

```text
openclaw@2026.4.26
```

## 3. Fill Local Secrets

Edit:

```text
~/.openclaw/secrets.env
```

Never commit the filled secrets file.

## 4. Review Config

Edit:

```text
~/.openclaw/openclaw.json
```

Important fields:

- `gateway.auth.token`: generate a local token for the machine.
- `auth.profiles.*.email`: replace example email with the work account.
- `channels.whatsapp.enabled`: keep false unless the work machine should use WhatsApp integration.

## 5. Verify

```bash
openclaw --version
openclaw tui --help
openclaw plugins list
```

## 6. Optional Source Development

Clone OpenClaw source separately:

```bash
git clone git@github-openclaw:MertBasar0/openclaw.git openclaw-src
cd openclaw-src
git checkout feat/main-session-durable-delivery-gpt55
```

Keep this source checkout separate from the global runtime.

