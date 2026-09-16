"""Offline tests. Run: python -m unittest discover -s tests -v"""
import copy
import queue
import time
from collections import deque
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import common
import diagnose
import build_catalog
import probe_app_server as probe

class HelpersTest(unittest.TestCase):
    def setUp(self):
        self.native = {"models": [{"slug": "gpt-fixture", "base_instructions": "NATIVE_ONLY",
            "context_window": 12345, "input_modalities": ["text", "image"],
            "use_responses_lite": True}]}
        self.extra = {"id": "google-antigravity:gemini-fixture", "display_name": "Gemini fixture",
            "default_reasoning_level": "low", "supported_reasoning_levels": [],
            "shell_type": "shell_command", "base_instructions": "OWN_INSTRUCTIONS"}
        self.gateway = {"data": [self.extra]}

    def test_catalog_preserves_native_metadata_and_does_not_mutate_input(self):
        original = copy.deepcopy(self.native)
        merged = build_catalog.merge_catalog(self.native, self.gateway, self.extra["id"])
        self.assertEqual(self.native, original)
        native = merged["models"][0]
        self.assertEqual(native["base_instructions"], "NATIVE_ONLY")
        self.assertEqual(native["input_modalities"], ["text", "image"])
        self.assertEqual(native, original["models"][0])
        self.assertEqual(merged["models"][1]["base_instructions"], "OWN_INSTRUCTIONS")
        self.assertEqual(merged["models"][1]["input_modalities"], ["text"])

    def test_missing_model_is_not_invented(self):
        with self.assertRaises(ValueError):
            build_catalog.merge_catalog(self.native, self.gateway, "not-available")

    def test_multiple_new_models_preserve_every_existing_field(self):
        self.native["catalog_version"] = {"source": "local-fixture"}
        self.native["models"].append({"slug": "google-antigravity:existing", "custom_field": [1, 2]})
        original = copy.deepcopy(self.native)
        additions = [dict(self.extra, id="google-antigravity:new-" + str(i)) for i in range(3)]
        merged = build_catalog.merge_catalog(self.native, {"data": additions}, [m["id"] for m in additions])
        self.assertEqual(merged["models"][:2], original["models"])
        self.assertEqual(merged["catalog_version"], original["catalog_version"])
        self.assertEqual(len(merged["models"]), 5)
        self.assertNotIn("use_responses_lite", merged["models"][1])
        self.assertEqual(self.native, original)

    def test_only_fresh_native_setup_changes_transport_flags(self):
        merged = build_catalog.merge_catalog(self.native, self.gateway, self.extra["id"], initialize_native=True)
        self.assertFalse(merged["models"][0]["use_responses_lite"])
        self.assertTrue(self.native["models"][0]["use_responses_lite"])

    def test_repeated_requests_preserve_existing_entries_without_duplicates(self):
        first = build_catalog.merge_catalog(self.native, self.gateway, self.extra["id"])
        repeated = build_catalog.merge_catalog(first, self.gateway, [self.extra["id"], self.extra["id"]],
            display_names={self.extra["id"]: "Do not rename an existing entry"})
        self.assertEqual(repeated, first)

    def test_cli_adds_multiple_models_and_friendly_names(self):
        second = dict(self.extra, id="google-antigravity:second")
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "base.json"
            target = Path(tmp) / "candidate.json"
            source.write_text(json.dumps(self.native), encoding="utf-8")
            original = source.read_bytes()
            args = ["build_catalog.py", "--base-catalog", str(source), "--output", str(target),
                "--model", self.extra["id"], "--model", second["id"],
                "--display-name", second["id"] + "=Second model"]
            with patch.object(sys, "argv", args), patch("build_catalog.local_json", return_value={"data": [self.extra, second]}), patch("sys.stdout", new_callable=io.StringIO):
                build_catalog.main()
            merged = common.load_json(target)
            self.assertEqual(merged["models"][0], self.native["models"][0])
            self.assertEqual(merged["models"][-1]["display_name"], "Second model")
            self.assertEqual(source.read_bytes(), original)

    def test_missing_batch_model_leaves_no_partial_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "base.json"
            target = Path(tmp) / "candidate.json"
            source.write_text(json.dumps(self.native), encoding="utf-8")
            original = source.read_bytes()
            args = ["build_catalog.py", "--base-catalog", str(source), "--output", str(target),
                "--model", self.extra["id"], "--model", "not-available"]
            with patch.object(sys, "argv", args), patch("build_catalog.local_json", return_value=self.gateway):
                with self.assertRaises(ValueError):
                    build_catalog.main()
            self.assertFalse(target.exists())
            self.assertEqual(source.read_bytes(), original)

    def test_cli_refuses_input_overwrite_even_with_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "base.json"
            source.write_text(json.dumps(self.native), encoding="utf-8")
            original = source.read_bytes()
            args = ["build_catalog.py", "--base-catalog", str(source), "--output", str(source),
                "--model", self.extra["id"], "--replace"]
            with patch.object(sys, "argv", args), patch("sys.stderr", new_callable=io.StringIO):
                with self.assertRaises(SystemExit):
                    build_catalog.main()
            self.assertEqual(source.read_bytes(), original)

    def test_duplicate_ids_and_incomplete_metadata_are_rejected(self):
        self.native["models"].append(copy.deepcopy(self.native["models"][0]))
        with self.assertRaises(ValueError):
            build_catalog.merge_catalog(self.native, self.gateway, self.extra["id"])
        with self.assertRaises(ValueError):
            build_catalog.merge_catalog({"models": [{"slug": "gpt-fixture"}]},
                {"data": [{"id": self.extra["id"]}]}, self.extra["id"])

    def test_nonlocal_urls_and_embedded_credentials_rejected(self):
        for url in ["https://example.com", "http://example.com", "http://name:secret@127.0.0.1",
                    "http://127.0.0.1?key=private"]:
            with self.assertRaises(ValueError):
                common.loopback_url(url)
        self.assertEqual(common.loopback_url("http://[::1]:1234/"), "http://[::1]:1234")
        self.assertIsNone(common.NoRedirect().redirect_request(None, None, 302, None, {}, "https://example.com"))

    def test_proxy_exceptions_are_merged(self):
        result = common.merge_no_proxy("corp.test,LOCALHOST", "corp.test,10.0.0.1")
        self.assertIn("corp.test", result)
        self.assertIn("10.0.0.1", result)
        self.assertEqual(result.lower().split(",").count("localhost"), 1)
        self.assertTrue(all(common.proxy_flags(result).values()))

    def test_permission_error_is_not_reported_as_stopped(self):
        with patch("diagnose.socket.create_connection", side_effect=PermissionError):
            self.assertEqual(diagnose.port_state(1234), "unknown_permission_denied")
        with patch("diagnose.socket.create_connection", side_effect=ConnectionRefusedError(111, "refused")):
            self.assertEqual(diagnose.port_state(1234), "connection_refused")

    def test_credentials_not_returned_by_diagnosis(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.json"
            path.write_text(json.dumps({"proxy": {"enabled": True, "port": 8045,
                "api_key": "PRIVATE_FIXTURE_DO_NOT_PRINT", "allow_lan_access": False}}), encoding="utf-8")
            result = diagnose.read_proxy_config(path)
            self.assertTrue(result["local_key_present"])
            self.assertNotIn("PRIVATE_FIXTURE", json.dumps(result))
            self.assertNotIn("api_key", result)

    def test_rollout_only_reads_first_metadata_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout-fixture.txt"
            path.write_text(json.dumps({"type": "session_meta", "payload": {"model_provider": "openai"}})
                + "\nTHIS IS NOT JSON AND MUST NOT BE READ", encoding="utf-8")
            self.assertEqual(diagnose.read_rollout_provider(path), "openai")

    def test_unicode_path_and_utf8_bom(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Office User 办公"
            path.mkdir()
            source = path / "fixture.json"
            source.write_text(json.dumps({"text": "中文"}, ensure_ascii=False), encoding="utf-8-sig")
            self.assertEqual(common.load_json(source), {"text": "中文"})
            target = path / "catalog.json"
            build_catalog.write_catalog(target, {"models": []})
            with self.assertRaises(FileExistsError):
                build_catalog.write_catalog(target, {"models": ["new"]})
            self.assertEqual(common.load_json(target), {"models": []})

    def test_codex_home_override(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"CODEX_HOME": tmp}):
            self.assertEqual(common.codex_home(), Path(tmp).resolve())

class FakeRpc:
    provider = "local-unified"
    reply = probe.EXPECTED
    def __init__(self, *args):
        self.sent = []
        self.closed = False
        self.events = [
            {"method": "item/completed", "params": {"threadId": "fixture", "item":
                {"type": "agentMessage", "text": self.reply}}},
            {"method": "turn/completed", "params": {"threadId": "fixture", "turn": {"status": "completed"}}}
        ]
    def send(self, method, params, request_id=None):
        self.sent.append(method)
    def response(self, request_id):
        if request_id == 2:
            return {"modelProvider": self.provider, "thread": {"id": "fixture"}}
        return {}
    def next(self, deadline):
        return self.events.pop(0)
    def close(self):
        self.closed = True

class ProtocolTest(unittest.TestCase):
    def setUp(self):
        self.auth_patch = patch("probe_app_server.verify_gateway_auth")
        self.auth_patch.start()
        self.addCleanup(self.auth_patch.stop)

    def test_success_is_not_desktop_ui_claim(self):
        rpc = FakeRpc()
        with patch("probe_app_server.Rpc", return_value=rpc):
            result = probe.run_probe("fake", ".", "gemini-fixture", "local-unified", 10)
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["reply_matches_expected"])
        self.assertFalse(result["desktop_ui_verified"])
        self.assertTrue(rpc.closed)

    def test_wrong_provider_stops_before_generation(self):
        rpc = FakeRpc()
        rpc.provider = "openai"
        with patch("probe_app_server.Rpc", return_value=rpc):
            result = probe.run_probe("fake", ".", "gemini-fixture", "local-unified", 10)
        self.assertEqual(result["status"], "wrong_provider_no_generation_sent")
        self.assertNotIn("turn/start", rpc.sent)
        self.assertTrue(rpc.closed)

    def test_error_text_is_not_counted_as_success(self):
        rpc = FakeRpc()
        rpc.events[0]["params"]["item"]["text"] = "This model is no longer available."
        with patch("probe_app_server.Rpc", return_value=rpc):
            result = probe.run_probe("fake", ".", "gemini-fixture", "local-unified", 10)
        self.assertFalse(result["reply_matches_expected"])

    def test_notifications_before_rpc_response_are_preserved(self):
        rpc = probe.Rpc.__new__(probe.Rpc)
        rpc.events = queue.Queue()
        rpc.pending = deque()
        notification = {"method": "turn/completed", "params": {"threadId": "fixture"}}
        rpc.events.put(notification)
        rpc.events.put({"id": 5, "result": {"accepted": True}})
        self.assertEqual(rpc.response(5), {"accepted": True})
        self.assertEqual(rpc.next(time.monotonic() + 1), notification)

    def test_temporary_config_is_passed_to_thread_without_file_write(self):
        rpc = FakeRpc()
        calls = []
        rpc.send = lambda method, params, request_id=None: calls.append((method, params))
        with patch("probe_app_server.Rpc", return_value=rpc):
            probe.run_probe("fake", ".", "gemini-fixture", "local-unified", 10,
                {"model_provider": "local-unified"})
        params = next(p for m, p in calls if m == "thread/start")
        self.assertEqual(params["config"]["model_provider"], "local-unified")
        self.assertTrue(params["ephemeral"])

class BillingGateTest(unittest.TestCase):
    def test_api_key_route_is_blocked_before_generation(self):
        with patch("probe_app_server.local_json", return_value={"openai_upstream": {"kind": "api_key"}}):
            with self.assertRaises(RuntimeError):
                probe.verify_gateway_auth("http://127.0.0.1:51122")

    def test_codex_oauth_route_is_accepted(self):
        with patch("probe_app_server.local_json", return_value={"openai_upstream": {"kind": "codex_oauth"}}):
            probe.verify_gateway_auth("http://127.0.0.1:51122")

if __name__ == "__main__":
    unittest.main()
