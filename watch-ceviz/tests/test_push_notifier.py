import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from push_notifier import PushNotifier  # noqa: E402


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class PushNotifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.notifier = PushNotifier()
        self.notifier.state_path = Path(self.tmp.name) / "push-registration.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_post_uses_stable_user_agent_and_authorization(self) -> None:
        with mock.patch(
            "push_notifier.urllib.request.urlopen",
            return_value=FakeResponse({"ok": True}),
        ) as urlopen:
            result = self.notifier._post("/v1/send", {"hello": "world"}, "grant-123")

        self.assertTrue(result["ok"])
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), "CevizBackend/1.0")
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertEqual(request.get_header("Authorization"), "Bearer grant-123")

    def test_register_persists_relay_credentials_atomically(self) -> None:
        response = {
            "ok": True,
            "relayHandle": "relay-handle",
            "sendGrant": "send-grant",
        }
        with mock.patch.object(self.notifier, "_post", return_value=response):
            result = self.notifier.register({
                "apns_token": "device-token",
                "bundle_id": "com.mertbasar.cevizwatch",
                "installation_id": "installation-1",
                "environment": "production",
            })

        self.assertEqual(result, {"ok": True, "registered": True})
        stored = json.loads(self.notifier.state_path.read_text(encoding="utf-8"))
        self.assertEqual(stored["relay_handle"], "relay-handle")
        self.assertEqual(stored["send_grant"], "send-grant")
        self.assertEqual(stored["installation_id"], "installation-1")

    def test_terminal_notification_is_idempotent(self) -> None:
        self.notifier._store({
            "relay_handle": "relay-handle",
            "send_grant": "send-grant",
            "registered_at": 10,
            "installation_id": "installation-1",
        })
        job = {
            "id": "job-1",
            "status": "completed",
            "created_at": 20,
            "watch_summary": "Görev tamamlandı.",
        }
        with mock.patch.object(
            self.notifier,
            "_post",
            return_value={"ok": True, "apnsId": "apns-1"},
        ) as post:
            self.assertTrue(self.notifier.notify_terminal_job(job))
            self.assertFalse(self.notifier.notify_terminal_job(job))

        self.assertEqual(post.call_count, 1)
        self.assertEqual(job["push_notification_apns_id"], "apns-1")
        self.assertIn("push_notification_sent_at", job)


if __name__ == "__main__":
    unittest.main()
