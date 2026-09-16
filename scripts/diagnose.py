"""Read-only status report. No credentials, conversation bodies or model calls."""
import argparse
import errno
import json
import os
import socket
import sys
import tomllib
import urllib.error
from pathlib import Path
from common import codex_home, load_json, local_json, proxy_flags

def read_proxy_config(path):
    if not path.exists():
        return {"present": False}
    proxy = load_json(path).get("proxy", {})
    return {"present": True, "enabled": proxy.get("enabled"),
            "port": proxy.get("port"), "allow_lan_access": proxy.get("allow_lan_access"),
            "local_key_present": bool(proxy.get("api_key"))}

def read_rollout_provider(path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        line = stream.readline(8 * 1024 * 1024 + 1)
    if len(line) > 8 * 1024 * 1024:
        raise ValueError("Metadata exceeds diagnostic limit.")
    item = json.loads(line)
    if item.get("type") != "session_meta":
        raise ValueError("First record is not session metadata.")
    return item.get("payload", {}).get("model_provider")

def port_state(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return "accepting_connections"
    except PermissionError:
        return "unknown_permission_denied"
    except ConnectionRefusedError:
        return "connection_refused"
    except (socket.timeout, TimeoutError):
        return "unknown_timeout"
    except OSError as exc:
        if getattr(exc, "winerror", None) in (5, 10013) or exc.errno in (errno.EACCES, errno.EPERM):
            return "unknown_permission_denied"
        if getattr(exc, "winerror", None) == 10061 or exc.errno == errno.ECONNREFUSED:
            return "connection_refused"
        return "unknown_os_error"

def health(port):
    try:
        data = local_json(f"http://127.0.0.1:{port}/health", timeout=3)
        return {"reachable": True, "status": data.get("status", data.get("ok")),
                "version": data.get("version", data.get("package_version")),
                "openai_auth_kind": data.get("openai_upstream", {}).get("kind")}
    except urllib.error.HTTPError as exc:
        return {"reachable": True, "http_status": exc.code}
    except Exception as exc:
        return {"reachable": False, "error_type": type(exc).__name__}

def user_no_proxy():
    if os.name != "nt":
        return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            return winreg.QueryValueEx(key, "NO_PROXY")[0]
    except FileNotFoundError:
        return None

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home")
    parser.add_argument("--proxy-config", type=Path)
    parser.add_argument("--gateway-port", type=int, default=51122)
    parser.add_argument("--rollout", type=Path)
    parser.add_argument("--offline", action="store_true", help="Skip sockets and health requests.")
    args = parser.parse_args()
    root = codex_home(args.codex_home)
    report = {"codex_home": str(root), "model_generation_performed": False}
    path = root / "config.toml"
    try:
        config = tomllib.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
        provider = config.get("model_provider", "openai")
        selected = config.get("model_providers", {}).get(provider, {})
        # Do not print arbitrary URLs: they may contain access tokens.
        from urllib.parse import urlsplit
        url = urlsplit(selected.get("base_url", ""))
        report["configuration"] = {"present": path.exists(), "model": config.get("model"),
            "provider": provider, "endpoint_host": url.hostname, "endpoint_port": url.port,
            "custom_catalog_present": bool(config.get("model_catalog_json")),
            "websockets": selected.get("supports_websockets")}
    except Exception as exc:
        report["configuration"] = {"error_type": type(exc).__name__}
    proxy_path = args.proxy_config or Path.home() / ".antigravity_tools" / "gui_config.json"
    try:
        report["antigravity"] = read_proxy_config(proxy_path)
    except Exception as exc:
        report["antigravity"] = {"error_type": type(exc).__name__}
    report["no_proxy_process"] = proxy_flags(os.environ.get("NO_PROXY"))
    try:
        report["no_proxy_user"] = proxy_flags(user_no_proxy())
    except PermissionError:
        report["no_proxy_user"] = {"state": "unknown_permission_denied"}
    report["explicit_openai_api_config_present"] = any(p.exists() for p in {
        root / "antigravity-openai.json", Path.home() / ".codex" / "antigravity-openai.json"})
    if args.rollout:
        try:
            report["existing_thread_provider"] = read_rollout_provider(args.rollout)
        except Exception as exc:
            report["existing_thread_error_type"] = type(exc).__name__
    if not args.offline:
        proxy_port = report.get("antigravity", {}).get("port", 8045)
        ports = [args.gateway_port]
        if isinstance(proxy_port, int) and 0 < proxy_port < 65536:
            ports.append(proxy_port)
        report["services"] = {str(p): {"tcp": port_state(p), "health": health(p)} for p in set(ports)}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
