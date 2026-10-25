"""Lightweight contract tests for the provider directory without importing app packages."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "connectors" / "platform_registry.py"
SPEC = importlib.util.spec_from_file_location("platform_registry_contract_target", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


EXPECTED_PROVIDER_IDS = {
    "wordpress", "webflow", "framer", "wix", "sanity", "shopify", "generic",
    "google_search_console", "google_analytics_4", "crux", "dataforseo",
    "openai_search", "perplexity", "claude", "gemini", "github",
    "linkedin", "x", "tiktok", "instagram", "whatsapp_business", "telegram",
    "slack", "hubspot", "salesforce", "stripe",
}


def test_directory_contains_all_26_named_targets():
    specs = MODULE.list_provider_specs()
    ids = [spec.id for spec in specs]
    assert len(ids) == 26
    assert set(ids) == EXPECTED_PROVIDER_IDS
    assert len(ids) == len(set(ids))


def test_registry_never_claims_a_connection_without_runtime_state():
    payload = MODULE.registry_payload()
    assert len(payload) == 26
    assert all(item["connection_status"] == "DISCONNECTED" for item in payload)
    assert all(item["implementation_status"] in {"adapter_registered_unverified", "adapter_required"} for item in payload)


def test_registry_distinguishes_provider_api_from_unsupported_capabilities():
    payload = {item["id"]: item for item in MODULE.registry_payload()}
    assert payload["hubspot"]["implementation_status"] == "adapter_registered_unverified"
    assert payload["sanity"]["implementation_status"] == "adapter_registered_unverified"
    assert payload["framer"]["implementation_status"] == "adapter_required"
    assert payload["wix"]["implementation_status"] == "adapter_required"


def test_specs_have_docs_and_health_operation():
    for spec in MODULE.list_provider_specs():
        assert spec.docs_url.startswith("https://")
        assert "health" in spec.operations
        assert spec.auth_methods


def test_registered_api_adapter_does_not_claim_publish_operations_are_verified():
    payload = {item["id"]: item for item in MODULE.registry_payload()}
    for provider_id in ("linkedin", "x", "tiktok", "instagram", "whatsapp_business", "slack", "telegram", "hubspot", "salesforce", "stripe"):
        item = payload[provider_id]
        assert "health" in item["operations"]
        assert item["verified_operations"] == []
        assert "publish" not in item["operations"]
        assert item["operation_status"]


def test_signed_webhook_ingress_is_declared_only_for_implemented_providers():
    payload = {item["id"]: item for item in MODULE.registry_payload()}
    for provider_id in ("slack", "whatsapp_business", "telegram"):
        assert "webhook_ingress" in payload[provider_id]["operations"]
        if "webhooks" in payload[provider_id]["operation_status"]:
            assert payload[provider_id]["operation_status"]["webhooks"] == "NOT_IMPLEMENTED_OR_NOT_VERIFIED"
