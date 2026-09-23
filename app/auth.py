"""Shared API-key gate for AgentOps control-plane and Launch Desk."""

from __future__ import annotations

import hmac
import logging
import os
from typing import Mapping, Optional

logger = logging.getLogger("agentops.auth")

_DEMO_WARNING_EMITTED = False


def get_configured_api_key() -> Optional[str]:
    key = os.getenv("AGENTOPS_API_KEY")
    if key is None:
        return None
    key = key.strip()
    return key or None


def require_auth_enabled(bind_host: Optional[str] = None) -> bool:
    """Return True when non-health routes must enforce authentication.

    Fail-closed when:
    - AGENTOPS_API_KEY is set (always require a matching key), or
    - REQUIRE_AUTH is truthy (1/true/yes), or
    - the process is not clearly bound to a loopback address.
    """
    if get_configured_api_key():
        return True
    flag = os.getenv("REQUIRE_AUTH", "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    host = (bind_host if bind_host is not None else os.getenv("HOST", "0.0.0.0")).strip().lower()
    loopback = {"127.0.0.1", "localhost", "::1"}
    return host not in loopback


def warn_if_auth_disabled() -> None:
    global _DEMO_WARNING_EMITTED
    if require_auth_enabled() or _DEMO_WARNING_EMITTED:
        return
    _DEMO_WARNING_EMITTED = True
    logger.warning(
        "AGENTOPS_API_KEY is unset and REQUIRE_AUTH is off on a loopback bind; "
        "mutating/export API routes are open for local demo only. "
        "Set AGENTOPS_API_KEY (or REQUIRE_AUTH=1) before any public deployment."
    )


def extract_api_key(headers: Mapping[str, str]) -> Optional[str]:
    """Accept Authorization: Bearer <key> and/or X-API-Key."""
    # Header maps may be case-insensitive (BaseHTTPRequestHandler) or plain dicts.
    def _get(name: str) -> Optional[str]:
        if hasattr(headers, "get"):
            direct = headers.get(name) or headers.get(name.lower()) or headers.get(name.title())
            if direct:
                return direct
        # Fallback case-insensitive scan
        for key, value in getattr(headers, "items", lambda: [])():
            if str(key).lower() == name.lower():
                return value
        return None

    auth = _get("Authorization")
    if auth:
        parts = auth.strip().split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
            return parts[1].strip()
    x_key = _get("X-API-Key")
    if x_key and x_key.strip():
        return x_key.strip()
    return None


def authorize_request(headers: Mapping[str, str], bind_host: Optional[str] = None) -> tuple[bool, Optional[str]]:
    """Return (ok, error_message). Public callers should only invoke this for gated routes."""
    if not require_auth_enabled(bind_host=bind_host):
        warn_if_auth_disabled()
        return True, None

    expected = get_configured_api_key()
    provided = extract_api_key(headers)
    if not expected:
        return False, "authentication required: set AGENTOPS_API_KEY or bind to loopback for local demo"
    if not provided or not hmac.compare_digest(provided, expected):
        return False, "unauthorized: provide Authorization: Bearer <key> or X-API-Key"
    return True, None
