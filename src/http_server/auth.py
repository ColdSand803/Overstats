"""Access control for the local HTTP service.

The service holds upstream credentials and runs upstream requests on behalf of
callers, so every route except the health check requires a shared secret once
one is configured. Two schemes are accepted for the same secret:

* ``Authorization: Bearer <secret>`` for API clients;
* HTTP Basic with any username for browsers, so the control panel and its
  static assets can be protected with the browser's own credential prompt.

When no secret is configured the service behaves exactly as before.
"""
from __future__ import annotations

import base64
import hmac
import json
import os
from typing import Any, Mapping, Optional

ACCESS_SECRET_ENV = "OVERSTATS_ACCESS_SECRET"
ACCESS_SECRET_KEY = "ACCESS_SECRET"
MAX_SECRET_CHARS = 512
MAX_AUTHORIZATION_CHARS = 2048
PUBLIC_PATHS = frozenset({"/healthz"})


def resolve_access_secret(json_cfg: Mapping[str, Any]) -> str:
    """Read the access secret: environment first, then the JSON config."""
    raw = os.getenv(ACCESS_SECRET_ENV)
    if raw is None:
        raw = os.getenv(ACCESS_SECRET_KEY)
    if raw is None:
        raw = json_cfg.get(ACCESS_SECRET_KEY)
        if raw is None:
            for key, value in json_cfg.items():
                if str(key).lower() == ACCESS_SECRET_KEY.lower():
                    raw = value
                    break
    secret = "" if raw is None else str(raw).strip()
    if len(secret) > MAX_SECRET_CHARS:
        raise ValueError(f"{ACCESS_SECRET_ENV} must be at most {MAX_SECRET_CHARS} characters.")
    return secret


def _presented_secret(authorization: Optional[str]) -> Optional[str]:
    """Extract the secret from a Bearer or Basic header; None when unusable."""
    header = str(authorization or "")
    if not header.strip() or len(header) > MAX_AUTHORIZATION_CHARS:
        return None
    scheme, separator, value = header.strip().partition(" ")
    if not separator or not value.strip():
        return None
    if scheme.lower() == "bearer":
        return value.strip()
    if scheme.lower() != "basic":
        return None
    try:
        decoded = base64.b64decode(value.strip(), validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    # The username is ignored: the password is the shared secret.
    return decoded.split(":", 1)[1] if ":" in decoded else None


def is_authorized(authorization: Optional[str], secret: str) -> bool:
    """Whether the header carries the configured secret. Empty secret allows all."""
    expected = str(secret or "")
    if not expected:
        return True
    presented = _presented_secret(authorization)
    if presented is None:
        return False
    return hmac.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))


def unauthorized_body() -> bytes:
    """401 payload in the service's standard error shape."""
    return json.dumps(
        {
            "ok": False,
            "error": "unauthorized",
            "message": "This service requires an access secret.",
            "hint": "Send Authorization: Bearer <secret>, or sign in when the browser asks.",
        },
        ensure_ascii=False,
    ).encode("utf-8")
