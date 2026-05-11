# Security Notes

This repository is intended to be private, but it should still be safe if reviewed by someone else.

Do not commit:

- API keys
- OAuth tokens
- gateway tokens
- SSH private keys
- real `.env` files
- OpenClaw credential directories
- logs
- caches
- `node_modules`
- local runtime dependency folders

Before pushing, run:

```bash
./scripts/audit-secrets.sh
git status --short
```

If the audit reports a match, inspect the file before pushing. Some matches may be false positives in documentation, but real credentials must be removed.

