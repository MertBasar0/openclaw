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
        self.user_agent = os.environ.get(
            "WATCH_CEVIZ_PUSH_USER_AGENT",
            "CevizBackend/1.0",
        ).strip() or "CevizBackend/1.0"

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
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
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
            cf_ray = exc.headers.get("cf-ray", "") if exc.headers else ""
            suffix = f" (cf-ray={cf_ray})" if cf_ray else ""
            raise RuntimeError(f"push relay {path} HTTP {exc.code}: {detail}{suffix}") from exc

    @staticmethod
    def _devices(registration: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
        if not registration:
            return {}
        devices = registration.get("devices")
        if isinstance(devices, dict):
            return {str(key): value for key, value in devices.items() if isinstance(value, dict)}
        if registration.get("relay_handle") and registration.get("send_grant"):
            return {
                "com.mertbasar.cevizwatch": {
                    "relay_handle": registration["relay_handle"],
                    "send_grant": registration["send_grant"],
                    "registered_at": registration.get("registered_at", 0),
                }
            }
        return {}

    def register(self, payload: dict[str, Any]) -> dict[str, Any]:
        previous = self._load()
        installation_id = str(payload.get("installation_id", ""))
        bundle_id = str(payload.get("bundle_id", "")).strip()
        response = self._post("/v1/register", {
            "apnsToken": payload.get("apns_token", ""),
            "bundleId": bundle_id,
            "installationId": installation_id,
            "environment": payload.get("environment", "production"),
        })
        if not response.get("ok"):
            raise RuntimeError(str(response.get("reason") or "push registration failed"))

        now = time.time()
        same_installation = bool(previous and previous.get("installation_id") == installation_id)
        first_registered_at = now
        devices: dict[str, dict[str, Any]] = {}
        if same_installation:
            first_registered_at = previous.get("first_registered_at", previous.get("registered_at", now))
            devices = self._devices(previous)
        devices[bundle_id] = {
            "relay_handle": response["relayHandle"],
            "send_grant": response["sendGrant"],
            "registered_at": now,
        }
        self._store({
            "devices": devices,
            "registered_at": now,
            "first_registered_at": first_registered_at,
            "installation_id": installation_id,
        })
        return {"ok": True, "registered": True, "device_count": len(devices)}

    def notify_terminal_job(self, job: dict[str, Any]) -> bool:
        if job.get("status") not in {"completed", "failed"} or job.get("push_notification_sent_at"):
            return False
        registration = self._load()
        eligible_since = registration.get("first_registered_at", registration.get("registered_at", 0)) if registration else 0
        devices = self._devices(registration)
        if not registration or not devices or job.get("created_at", 0) < eligible_since:
            return False

        summary = str(job.get("watch_summary") or job.get("canned_result") or "G\u00f6rev tamamland\u0131.")
        if len(summary) > 180:
            summary = summary[:177].rstrip() + "\u2026"
        base_payload = {
            "jobId": job["id"],
            "title": "Ceviz \u00b7 G\u00f6rev tamamland\u0131" if job.get("status") == "completed" else "Ceviz \u00b7 G\u00f6rev tamamlanamad\u0131",
            "message": summary,
            "deepLink": f"ceviz://job/{job['id']}",
            "status": job.get("status", ""),
            "watchSummary": summary,
            "requiresPhoneHandoff": bool(job.get("requires_phone_handoff")),
        }

        apns_ids: list[str] = []
        errors: list[str] = []
        for bundle_id, device in devices.items():
            payload = dict(base_payload)
            payload["relayHandle"] = device["relay_handle"]
            try:
                result = self._post("/v1/send", payload, device["send_grant"])
            except Exception as exc:
                logging.warning("Push notification failed for %s: %s", bundle_id, exc)
                errors.append(f"{bundle_id}: {exc}")
                continue
            if result.get("ok"):
                apns_ids.append(result.get("apnsId") or "")
            else:
                errors.append(f"{bundle_id}: {result.get('reason') or 'APNs delivery failed'}")

        if not apns_ids:
            raise RuntimeError("; ".join(errors) or "APNs delivery failed")
        job["push_notification_sent_at"] = time.time()
        job["push_notification_apns_id"] = ",".join(value for value in apns_ids if value)
        logging.info("Push notification sent for %s to %d device(s)", job["id"], len(apns_ids))
        return True
