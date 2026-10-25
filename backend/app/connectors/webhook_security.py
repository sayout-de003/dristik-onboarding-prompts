"""Signature and replay-safe event-key helpers for provider webhooks."""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any


def verify_slack_signature(
    signing_secret: str,
    timestamp: str,
    signature: str,
    raw_body: bytes,
    now: int | None = None,
    max_age_seconds: int = 300,
) -> bool:
    if not signing_secret or not timestamp or not signature:
        return False
    try:
        issued_at = int(timestamp)
    except (TypeError, ValueError):
        return False
    current = int(time.time()) if now is None else int(now)
    if issued_at > current + 60 or current - issued_at > max_age_seconds:
        return False
    base = b"v0:" + timestamp.encode("ascii", errors="ignore") + b":" + raw_body
    expected = "v0=" + hmac.new(signing_secret.encode(), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_meta_signature(app_secret: str, signature: str, raw_body: bytes) -> bool:
    if not app_secret or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_shared_secret(expected_secret: str | None, supplied_secret: str | None) -> bool:
    if not expected_secret or not supplied_secret:
        return False
    return hmac.compare_digest(expected_secret.encode(), supplied_secret.encode())


def webhook_event_key(provider: str, payload: Any, raw_body: bytes) -> str:
    """Prefer provider event identifiers; use a stable body hash when none is available."""
    if provider == "whatsapp_business":
        # A Meta delivery can batch multiple messages/statuses; hash the full delivery
        # rather than deduplicating distinct batches by only their first message ID.
        return hashlib.sha256(provider.encode() + b":" + raw_body).hexdigest()
    if isinstance(payload, dict):
        candidates = [
            payload.get("event_id"),
            payload.get("update_id"),
            payload.get("trigger_id"),
        ]
        event = payload.get("event")
        if isinstance(event, dict):
            candidates.extend([event.get("event_id"), event.get("client_msg_id"), event.get("ts")])
        entry = payload.get("entry")
        if isinstance(entry, list) and entry and isinstance(entry[0], dict):
            changes = entry[0].get("changes")
            if isinstance(changes, list) and changes and isinstance(changes[0], dict):
                value = changes[0].get("value")
                if isinstance(value, dict):
                    messages = value.get("messages") or value.get("statuses") or []
                    if isinstance(messages, list) and messages and isinstance(messages[0], dict):
                        candidates.append(messages[0].get("id"))
        for candidate in candidates:
            if candidate is not None and str(candidate).strip():
                return str(candidate)[:240]
    return hashlib.sha256(provider.encode() + b":" + raw_body).hexdigest()


def body_sha256(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()
