"""Shared proxy selection for repository downloads and Git subprocesses."""
import os
import shutil
import socket
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path


def git_executable():
    found = shutil.which("git")
    if found and os.name == "nt":
        root = Path(found).parent.parent
        for relative in ("ucrt64/bin/git.exe", "mingw64/bin/git.exe"):
            native = root / relative
            if native.is_file():
                return str(native)
    return found or "git"


def validate_proxy(value):
    value = str(value or "auto").strip()
    if value.lower() in ("auto", "direct"):
        return value.lower()
    parsed = urllib.parse.urlsplit(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("代理端口不正确") from exc
    if parsed.scheme not in ("http", "https") or not parsed.hostname or not port or parsed.path not in ("", "/"):
        raise ValueError("代理请填 auto、direct 或完整 HTTP 代理地址，例如 http://127.0.0.1:7897")
    return value


def resolve_proxy(value="auto"):
    value = validate_proxy(value)
    if value == "direct":
        return ""
    if value != "auto":
        return value
    # urllib also reads the Windows Internet Settings proxy; Git does not.
    proxies = urllib.request.getproxies()
    for key in ("https", "http", "all"):
        candidate = proxies.get(key)
        if candidate:
            if "://" not in candidate:
                candidate = "http://" + candidate
            try:
                return validate_proxy(candidate)
            except ValueError:
                pass
    if shutil.which("git"):
        try:
            result = subprocess.run(["git", "config", "--get-urlmatch", "http.proxy", "https://github.com"],
                                    capture_output=True, text=True, timeout=3)
            if result.returncode == 0 and result.stdout.strip():
                return validate_proxy(result.stdout.strip())
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
    # Same local mixed-port proxy as push_to_github.ps1; use it only when listening.
    try:
        with socket.create_connection(("127.0.0.1", 7897), timeout=.2):
            return "http://127.0.0.1:7897"
    except OSError:
        return ""


def proxy_environment(value="auto", base=None):
    env = dict(os.environ if base is None else base)
    proxy = resolve_proxy(value)
    for key in tuple(env):
        if key.lower() in ("http_proxy", "https_proxy", "all_proxy"):
            del env[key]
    if proxy:
        env.update(HTTP_PROXY=proxy, HTTPS_PROXY=proxy)
    env["BLING_NETWORK_PROXY"] = proxy or "direct"
    return env


def proxy_label(proxy):
    if not proxy or proxy == "direct":
        return "直连"
    parsed = urllib.parse.urlsplit(proxy)
    return f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"


def urlopen(request, timeout):
    selected = os.environ.get("BLING_NETWORK_PROXY")
    if selected is None:
        return urllib.request.urlopen(request, timeout=timeout)
    proxy = resolve_proxy(selected)
    handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})
    return urllib.request.build_opener(handler).open(request, timeout=timeout)
