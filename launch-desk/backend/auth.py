"""API-key gate for Launch Desk (mirrors AgentOps control-plane auth)."""

from __future__ import annotations

import logging
import os
from typing import Mapping, Optional

logger = logging.getLogger("launchdesk.auth")

_DEMO_WARNING_EMITTED = False


def get_configured_api_key() -> Optional[str]:
    key = os.getenv("AGENTOPS_API_KEY")
    if key is None:
        return None
    key = key.strip()
    return key or None


def require_auth_enabled(bind_host: Optional[str] = None) -> bool:
    if get_configured_api_key():
        return True
    flag = os.getenv("REQUIRE_AUTH", "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    host = (bind_host if bind_host is not None else os.getenv("HOST", "127.0.0.1")).strip().lower()
    return host not in {"127.0.0.1", "localhost", "::1"}


def warn_if_auth_disabled() -> None:
    global _DEMO_WARNING_EMITTED
    if require_auth_enabled() or _DEMO_WARNING_EMITTED:
        return
    _DEMO_WARNING_EMITTED = True
    logger.warning(
        "AGENTOPS_API_KEY is unset and REQUIRE_AUTH is off on a loopback bind; "
        "Launch Desk mutating routes are open for local demo only. "
        "Set AGENTOPS_API_KEY (or REQUIRE_AUTH=1) before any public deployment."
    )


def extract_api_key(headers: Mapping[str, str]) -> Optional[str]:
    auth = headers.get("authorization") or headers.get("Authorization")
    if auth:
        parts = auth.strip().split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
            return parts[1].strip()
    x_key = headers.get("x-api-key") or headers.get("X-API-Key")
    if x_key and str(x_key).strip():
        return str(x_key).strip()
    return None


def authorize_headers(headers: Mapping[str, str], bind_host: Optional[str] = None) -> tuple[bool, Optional[str]]:
    if not require_auth_enabled(bind_host=bind_host):
        warn_if_auth_disabled()
        return True, None
    expected = get_configured_api_key()
    provided = extract_api_key(headers)
    if not expected:
        return False, "authentication required: set AGENTOPS_API_KEY or bind to loopback for local demo"
    if not provided or provided != expected:
        return False, "unauthorized: provide Authorization: Bearer <key> or X-API-Key"
    return True, None
