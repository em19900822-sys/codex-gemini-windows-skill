"""Shared local-only helpers. Python 3.11+; no credential output."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

LOOPBACK = {"localhost", "127.0.0.1", "::1"}

def codex_home(value=None):
    return Path(value or os.environ.get("CODEX_HOME") or Path.home() / ".codex").resolve()

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))

def loopback_url(value):
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "http" or parsed.hostname not in LOOPBACK or parsed.username or parsed.password:
        raise ValueError("Only credential-free http loopback URLs are allowed.")
    if parsed.query or parsed.fragment:
        raise ValueError("Do not put credentials or query parameters in the local URL.")
    return value.rstrip("/")

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def local_json(url, timeout=6):
    loopback_url(url)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with opener.open(request, timeout=timeout) as response:
        raw = response.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError("Response exceeds diagnostic limit.")
        return json.loads(raw.decode("utf-8"))

def merge_no_proxy(*values):
    result = []
    seen = set()
    for value in (*values, "localhost,127.0.0.1,::1"):
        for item in (value or "").split(","):
            item = item.strip()
            if item and item.lower() not in seen:
                result.append(item)
                seen.add(item.lower())
    return ",".join(result)

def proxy_flags(value):
    entries = {s.strip().lower() for s in (value or "").split(",")}
    return {name: name in entries or "*" in entries for name in sorted(LOOPBACK)}
