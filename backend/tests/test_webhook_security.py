"""Unit tests for provider webhook signature and replay-key helpers."""
from __future__ import annotations

import hashlib
import hmac
import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "connectors" / "webhook_security.py"
SPEC = importlib.util.spec_from_file_location("webhook_security_contract_target", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_slack_signature_requires_fresh_timestamp_and_exact_body():
    secret = "test-signing-secret"
    timestamp = "1700000000"
    body = b'{"type":"event_callback","event_id":"Ev123"}'
    base = b"v0:" + timestamp.encode() + b":" + body
    signature = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    assert MODULE.verify_slack_signature(secret, timestamp, signature, body, now=1700000001)
    assert not MODULE.verify_slack_signature(secret, timestamp, signature, body + b" ", now=1700000001)
    assert not MODULE.verify_slack_signature(secret, timestamp, signature, body, now=1700000400)


def test_meta_signature_rejects_tampering():
    secret = "meta-app-secret"
    body = b'{"object":"whatsapp_business_account"}'
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert MODULE.verify_meta_signature(secret, signature, body)
    assert not MODULE.verify_meta_signature(secret, signature, body + b"tampered")


def test_telegram_shared_secret_is_constant_value_match():
    assert MODULE.verify_shared_secret("telegram-secret", "telegram-secret")
    assert not MODULE.verify_shared_secret("telegram-secret", "wrong")
    assert not MODULE.verify_shared_secret("", "telegram-secret")


def test_webhook_event_key_prefers_provider_event_ids_and_falls_back_to_hash():
    assert MODULE.webhook_event_key("telegram", {"update_id": 123}, b"raw") == "123"
    first = MODULE.webhook_event_key("slack", {"type": "event_callback"}, b"raw")
    second = MODULE.webhook_event_key("slack", {"type": "event_callback"}, b"raw")
    assert first == second
    assert len(first) == 64


def test_meta_batch_deduplication_uses_full_delivery_body():
    payload = {"entry": [{"changes": [{"value": {"messages": [{"id": "m1"}, {"id": "m2"}]}}]}]}
    first = MODULE.webhook_event_key("whatsapp_business", payload, b"batch-one")
    second = MODULE.webhook_event_key("whatsapp_business", payload, b"batch-two")
    assert first != second
