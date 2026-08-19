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

        self.assertEqual(result, {"ok": True, "registered": True, "device_count": 1})
        stored = json.loads(self.notifier.state_path.read_text(encoding="utf-8"))
        device = stored["devices"]["com.mertbasar.cevizwatch"]
        self.assertEqual(device["relay_handle"], "relay-handle")
        self.assertEqual(device["send_grant"], "send-grant")
        self.assertEqual(stored["installation_id"], "installation-1")

    def test_reregister_same_installation_preserves_first_registration(self) -> None:
        self.notifier._store({
            "relay_handle": "old-handle",
            "send_grant": "old-grant",
            "registered_at": 10,
            "installation_id": "installation-1",
        })
        response = {
            "ok": True,
            "relayHandle": "new-handle",
            "sendGrant": "new-grant",
        }
        with mock.patch.object(self.notifier, "_post", return_value=response), mock.patch(
            "push_notifier.time.time", return_value=30
        ):
            self.notifier.register({
                "apns_token": "new-device-token",
                "bundle_id": "com.mertbasar.cevizwatch",
                "installation_id": "installation-1",
                "environment": "production",
            })

        stored = json.loads(self.notifier.state_path.read_text(encoding="utf-8"))
        self.assertEqual(stored["registered_at"], 30)
        self.assertEqual(stored["first_registered_at"], 10)

    def test_new_installation_resets_first_registration(self) -> None:
        self.notifier._store({
            "relay_handle": "old-handle",
            "send_grant": "old-grant",
            "registered_at": 10,
            "first_registered_at": 5,
            "installation_id": "installation-1",
        })
        response = {"ok": True, "relayHandle": "new-handle", "sendGrant": "new-grant"}
        with mock.patch.object(self.notifier, "_post", return_value=response), mock.patch(
            "push_notifier.time.time", return_value=30
        ):
            self.notifier.register({
                "apns_token": "new-device-token",
                "bundle_id": "com.mertbasar.cevizwatch",
                "installation_id": "installation-2",
                "environment": "production",
            })

        stored = json.loads(self.notifier.state_path.read_text(encoding="utf-8"))
        self.assertEqual(stored["first_registered_at"], 30)

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
        payload = post.call_args.args[1]
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["watchSummary"], "Görev tamamlandı.")
        self.assertFalse(payload["requiresPhoneHandoff"])
        self.assertEqual(job["push_notification_apns_id"], "apns-1")
        self.assertIn("push_notification_sent_at", job)


    def test_terminal_notification_targets_iphone_and_watch(self) -> None:
        self.notifier._store({
            "devices": {
                "com.mertbasar.cevizwatch": {
                    "relay_handle": "phone-handle",
                    "send_grant": "phone-grant",
                    "registered_at": 10,
                },
                "com.mertbasar.cevizwatch.watchkitapp": {
                    "relay_handle": "watch-handle",
                    "send_grant": "watch-grant",
                    "registered_at": 11,
                },
            },
            "registered_at": 11,
            "first_registered_at": 10,
            "installation_id": "installation-1",
        })
        job = {
            "id": "job-dual",
            "status": "completed",
            "created_at": 20,
            "watch_summary": "Result ready.",
        }
        with mock.patch.object(
            self.notifier,
            "_post",
            side_effect=[
                {"ok": True, "apnsId": "phone-apns"},
                {"ok": True, "apnsId": "watch-apns"},
            ],
        ) as post:
            self.assertTrue(self.notifier.notify_terminal_job(job))

        self.assertEqual(post.call_count, 2)
        handles = {call.args[1]["relayHandle"] for call in post.call_args_list}
        self.assertEqual(handles, {"phone-handle", "watch-handle"})
        self.assertEqual(job["push_notification_apns_id"], "phone-apns,watch-apns")


if __name__ == "__main__":
    unittest.main()
