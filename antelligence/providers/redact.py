"""One scrubber for every piece of text that is stored (sqlite, cells, ledgers, archives) or printed.

Removes: URL userinfo, path and query (``scheme://host[:port]`` is kept); Bearer / Authorization values; ``sk-`` style
and 64-hex tokens; and any secret value passed in or registered with :func:`register_secret` (RPC URL, pod secret,
Nous key). Servers may echo what they were sent, so response bodies go through this too.
"""

from __future__ import annotations

import re
import threading
from typing import Iterable, Set

_URL = re.compile(r"(https?://)(?:[^/\s'\"<>@]*@)?([^/\s'\"<>?#]+)[^\s'\"<>)\]]*", re.IGNORECASE)
_BEARER = re.compile(r"(?i)\b(?:authorization:?\s*)?bearer\s+['\"]?[^\s'\",;)]+|\b(?:authorization:?|api[_-]?key[=:])\s*['\"]?(?!bearer\b)[^\s'\",;)]+")
_URLPATH = re.compile(r"(?i)\b(url:?\s*)/\S+")
_TOKENS = re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}|\b(?:0x)?[0-9a-fA-F]{64}\b")
_lock = threading.Lock()
_registered: Set[str] = set()


def register_secret(*values: str) -> None:
    with _lock:
        _registered.update(v for v in values if v and len(v) >= 6)


def register_url(url: str) -> None:
    """Register an endpoint URL and its secret-bearing parts (userinfo, path, query), which libraries echo on their own."""
    from urllib.parse import urlsplit

    register_secret(url)
    parts = urlsplit(url)
    register_secret(parts.password or "", parts.path.strip("/"), parts.query)
    for seg in parts.path.split("/") + parts.query.replace("&", "=").split("="):
        if len(seg) >= 12:
            register_secret(seg)


_LONG_TOKEN = re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-.]+|[A-Za-z0-9+/_\-]{32,}={0,2}")
ERROR_BODY_CHARS = 500
_KEYNAME = r"[\w.-]*(?:api[_-]?key|key|token|secret|password|passwd|authorization)"
_KV_JSON = re.compile(r'(?i)("' + _KEYNAME + r'"\s*:\s*)(?:"(?:[^"\\]|\\.)*"|[^\s,}\]]+)')
_KV_FORM = re.compile(r"(?i)(?<![\w.-])(" + _KEYNAME + r"=)[^&\s\"'<>;,]*")
_KV_HEADER = re.compile(r"(?i)(?<![\w.-])(" + _KEYNAME + r":[ \t]*)[^\r\n\"',}]*")


def redact_body(text: object, extra_secrets: Iterable[str] = (), limit: int = ERROR_BODY_CHARS) -> str:
    """A failed provider reply body made safe to store: scrubbed like everything else, then values of secret-named keys (``api_key``, ``token``, ``access_token``, ``secret``, ``password``, ``authorization``
    in JSON, ``k=v`` and ``k: v`` forms), bearer tokens, ``sk-`` keys,
    JWTs and any long base64-like run become ``[redacted]``, then cut to ``limit`` characters. Redaction runs on the
    whole text first so a key straddling the cut cannot survive as a fragment."""
    out = str(text)                        # secret-named keys first: scrub() would half-eat "Authorization: Basic x"
    out = _KV_JSON.sub(lambda m: m.group(1) + '"[redacted]"', out)
    out = _KV_FORM.sub(lambda m: m.group(1) + "[redacted]", out)
    out = _KV_HEADER.sub(lambda m: m.group(1) + "[redacted]", out)
    out = scrub(out, extra_secrets)
    out = _LONG_TOKEN.sub("***", out)
    return out.replace("***", "[redacted]")[:limit]


def scrub(text: object, extra_secrets: Iterable[str] = ()) -> str:
    out = str(text)
    with _lock:
        secrets = sorted(_registered | {s for s in extra_secrets if s}, key=len, reverse=True)
    for s in secrets:                      # exact values first, before URL stripping rewrites the context
        out = out.replace(s, "***")
        if len(s) >= 8:                    # also a secret broken across lines or spaces
            out = re.sub(r"\s*".join(re.escape(c) for c in s), "***", out)
    out = _URL.sub(lambda m: m.group(1) + m.group(2), out)
    out = _BEARER.sub("Bearer ***", out)
    out = _URLPATH.sub(lambda m: m.group(1) + "<path>", out)
    return _TOKENS.sub("***", out)
