"""Minimal real-model test via Codex's desktop protocol; consumes existing account quota."""
import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
import tomllib
from collections import deque
from pathlib import Path
from common import codex_home, local_json, loopback_url, merge_no_proxy

EXPECTED = "CODEX_BRIDGE_TEST_OK"

class Rpc:
    def __init__(self, codex, cwd):
        env = os.environ.copy()
        env["NO_PROXY"] = merge_no_proxy(env.get("NO_PROXY"))
        self.process = subprocess.Popen([str(codex), "app-server"], cwd=cwd, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8")
        self.events = queue.Queue()
        self.pending = deque()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.process.stdout:
            try:
                self.events.put(json.loads(line))
            except ValueError:
                continue
        self.events.put({"_closed": True})

    def send(self, method, params, request_id=None):
        request = {"method": method, "params": params}
        if request_id is not None:
            request["id"] = request_id
        self.process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def _read_event(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Timed out waiting for the desktop protocol.")
        try:
            event = self.events.get(timeout=remaining)
        except queue.Empty:
            raise TimeoutError("Timed out waiting for the desktop protocol.") from None
        if event.get("_closed"):
            raise RuntimeError("Codex app-server exited before completing the check.")
        return event

    def next(self, deadline):
        if self.pending:
            return self.pending.popleft()
        return self._read_event(deadline)

    def response(self, request_id, timeout=40):
        deadline = time.monotonic() + timeout
        while True:
            event = self._read_event(deadline)
            if event.get("id") == request_id:
                if "error" in event:
                    raise RuntimeError("RPC configuration/protocol error, code=" + str(event["error"].get("code")))
                return event["result"]
            self.pending.append(event)

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

def verify_gateway_auth(gateway):
    status = local_json(loopback_url(gateway) + "/health")
    if status.get("openai_upstream", {}).get("kind") != "codex_oauth":
        raise RuntimeError("Gateway has not confirmed ChatGPT authentication. No model request was sent.")

def run_probe(codex, cwd, model, expected_provider, timeout, overrides=None, gateway="http://127.0.0.1:51122"):
    verify_gateway_auth(gateway)
    rpc = Rpc(codex, cwd)
    result = {"model": model, "test_process_no_proxy_explicit": True,
              "desktop_ui_verified": False, "ephemeral": True}
    try:
        rpc.send("initialize", {"clientInfo": {"name": "codex_gemini_skill_probe", "version": "1.0"},
                               "capabilities": {"experimentalApi": True}}, 1)
        rpc.response(1)
        rpc.send("initialized", {})
        test_config = dict(overrides or {})
        test_config["model_reasoning_effort"] = "low"
        rpc.send("thread/start", {"cwd": str(cwd), "ephemeral": True, "model": model,
            "approvalPolicy": "never", "sandbox": "read-only",
            "config": test_config,
            "developerInstructions": "Connection check only. Do not use tools. Reply exactly " + EXPECTED}, 2)
        thread = rpc.response(2)
        result["provider"] = thread.get("modelProvider")
        if result["provider"] != expected_provider:
            result["status"] = "wrong_provider_no_generation_sent"
            return result
        thread_id = thread["thread"]["id"]
        rpc.send("turn/start", {"threadId": thread_id,
            "input": [{"type": "text", "text": "Reply exactly " + EXPECTED, "text_elements": []}]}, 3)
        rpc.response(3)
        deadline = time.monotonic() + timeout
        replies = []
        while True:
            event = rpc.next(deadline)
            method = event.get("method")
            params = event.get("params", {})
            if params.get("threadId") != thread_id:
                continue
            if method == "item/completed" and params.get("item", {}).get("type") == "agentMessage":
                replies.append(params["item"].get("text", ""))
            if method == "turn/completed":
                result["status"] = params.get("turn", {}).get("status")
                result["reply_matches_expected"] = "\n".join(replies).strip() == EXPECTED
                return result
    finally:
        rpc.close()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", required=True, type=Path)
    parser.add_argument("--cwd", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--expected-provider", default="local-unified")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--test-config", type=Path, help="Optional standalone TOML overrides, used only for the ephemeral test.")
    args = parser.parse_args()
    if not args.codex.is_file() or not args.cwd.is_dir():
        parser.error("Pass an existing Codex executable and working directory from this computer.")
    try:
        if args.test_config:
            overrides = tomllib.loads(args.test_config.read_text(encoding="utf-8-sig"))
            allowed = {"model", "model_provider", "model_catalog_json", "model_providers", "model_reasoning_effort"}
            if set(overrides) - allowed:
                raise ValueError("Test config contains settings outside the model connection scope.")
            connection_config = overrides
        else:
            overrides = None
            connection_config = tomllib.loads((codex_home() / "config.toml").read_text(encoding="utf-8-sig"))
        base_url = connection_config.get("model_providers", {}).get(args.expected_provider, {}).get("base_url", "")
        gateway = loopback_url(base_url).removesuffix("/v1")
        result = run_probe(args.codex, args.cwd, args.model, args.expected_provider, args.timeout, overrides, gateway)
    except Exception as exc:
        print(json.dumps({"status": "check_failed", "error_type": type(exc).__name__,
                          "desktop_ui_verified": False}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "completed" and result.get("reply_matches_expected") else 1

if __name__ == "__main__":
    sys.exit(main())
