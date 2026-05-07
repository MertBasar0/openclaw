# Watch Ceviz Shortcuts MVP

This path keeps the native watchOS app intact, but lets Apple Watch trigger Watch Ceviz through an Apple Shortcut while signing and TestFlight work stays parked.

## Backend Endpoints

- `POST /api/v1/shortcuts/command`
  - Accepts JSON: `{"text":"bugünkü işleri özetle","wait_seconds":25}`
  - Also accepts `text/plain` body.
  - Starts an OpenClaw job and returns a small Shortcut-friendly JSON payload.
  - If `wait_seconds` is present, the backend waits up to that many seconds for a final result before returning.
- `GET /api/v1/shortcuts/jobs/<job_id>`
  - Returns the latest job state for polling from Shortcuts.

Example response:

```json
{
  "status": "running",
  "done": false,
  "job_id": "job-1234abcd",
  "summary": "Transkript alındı: \"bugünkü işleri özetle\". İşleniyor.",
  "shortcut_text": "Transkript alındı: \"bugünkü işleri özetle\". İşleniyor.",
  "poll_url": "/api/v1/shortcuts/jobs/job-1234abcd",
  "report_url": "/api/v1/jobs/job-1234abcd/report"
}
```

## Local Run

```bash
backend/run.sh 8080
```

Use a URL that the iPhone and Apple Watch can reach. On the same Wi-Fi this is usually:

```text
http://<computer-lan-ip>:8080/api/v1/shortcuts/command
```

If the watch is not on the same network, put the backend behind a tunnel such as Tailscale, Cloudflare Tunnel, or ngrok.

## Apple Shortcut

Create a Shortcut named `Ceviz`.

1. Add `Dictate Text`.
2. Add `Get Contents of URL`.
3. Set method to `POST`.
4. Set request body to `JSON`.
5. Add field `text` with the dictated text.
6. Add field `wait_seconds` with number `25`.
7. Set URL to `http://<computer-lan-ip>:8080/api/v1/shortcuts/command`.
8. Add `Get Dictionary Value` for `shortcut_text`.
9. Add `Speak Text` or `Show Result`.

Optional polling:

Use this only when the first response returns `done: false`.

1. Get `poll_url`.
2. Wait 5 seconds.
3. Call `http://<computer-lan-ip>:8080` + `poll_url`.
4. Speak or show `shortcut_text`.
5. Repeat until `done` is true.
