from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class PushNotifier:
    def __init__(self) -> None:
        state_dir = Path(os.environ.get("WATCH_CEVIZ_STATE_DIR", str(Path.home() / ".openclaw" / "ceviz-state")))
        self.state_path = state_dir / "push-registration.json"
        self.relay_url = os.environ.get(
            "WATCH_CEVIZ_PUSH_RELAY_URL",
            "https://ceviz-push-relay.mertbasar30.workers.dev",
        ).rstrip("/")

    def _load(self) -> dict[str, Any] | None:
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _store(self, payload: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.chmod(0o600)
        tmp.replace(self.state_path)

    def _post(self, path: str, payload: dict[str, Any], grant: str | None = None) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if grant:
            headers["Authorization"] = f"Bearer {grant}"
        request = urllib.request.Request(
            f"{self.relay_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"push relay HTTP {exc.code}: {detail}") from exc

    def register(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._post("/v1/register", {
            "apnsToken": payload.get("apns_token", ""),
            "bundleId": payload.get("bundle_id", ""),
            "installationId": payload.get("installation_id", ""),
            "environment": payload.get("environment", "production"),
        })
        if not response.get("ok"):
            raise RuntimeError(str(response.get("reason") or "push registration failed"))
        self._store({
            "relay_handle": response["relayHandle"],
            "send_grant": response["sendGrant"],
            "registered_at": time.time(),
            "installation_id": payload.get("installation_id", ""),
        })
        return {"ok": True, "registered": True}

    def notify_terminal_job(self, job: dict[str, Any]) -> bool:
        if job.get("status") not in {"completed", "failed"} or job.get("push_notification_sent_at"):
            return False
        registration = self._load()
        if not registration or job.get("created_at", 0) < registration.get("registered_at", 0):
            return False
        summary = str(job.get("watch_summary") or job.get("canned_result") or "Görev tamamlandı.")
        if len(summary) > 180:
            summary = summary[:177].rstrip() + "…"
        result = self._post("/v1/send", {
            "relayHandle": registration["relay_handle"],
            "jobId": job["id"],
            "title": "Ceviz · Görev tamamlandı" if job.get("status") == "completed" else "Ceviz · Görev tamamlanamadı",
            "message": summary,
            "deepLink": f"ceviz://job/{job['id']}",
        }, registration["send_grant"])
        if not result.get("ok"):
            raise RuntimeError(str(result.get("reason") or "APNs delivery failed"))
        job["push_notification_sent_at"] = time.time()
        job["push_notification_apns_id"] = result.get("apnsId") or ""
        logging.info("Push notification sent for %s (apns=%s)", job["id"], result.get("apnsId"))
        return True
