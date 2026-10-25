"""Single source of truth for Dristik's third-party integration directory.

A registry entry describes intended operations; it does not imply that an API is
configured, authorized, or live. Runtime state is supplied separately by connector
health checks. Capabilities marked unavailable must never be presented as working.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    label: str
    category: str
    auth_methods: tuple[str, ...]
    operations: tuple[str, ...]
    adapter_key: str | None
    docs_url: str
    notes: str = ""


# Operation names are deliberately granular. An adapter can support read but not write.
PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec("wordpress", "WordPress", "cms", ("application_password", "bridge_token"), ("health", "discover_pages", "read_seo_metadata", "update_seo_metadata", "publish_draft", "verify_deployment", "rollback"), "wordpress", "https://developer.wordpress.org/rest-api/"),
    ProviderSpec("webflow", "Webflow", "cms", ("oauth", "api_token"), ("health", "discover_sites", "discover_collections", "read_seo_metadata", "update_seo_metadata", "publish", "verify_deployment"), "webflow", "https://developers.webflow.com/"),
    ProviderSpec("framer", "Framer", "cms", ("api_token", "oauth"), ("health", "discover_sites", "sync_content", "verify_deployment"), None, "https://www.framer.com/developers/"),
    ProviderSpec("wix", "Wix", "cms", ("oauth", "api_token"), ("health", "discover_site", "read_content", "update_seo_metadata", "publish", "verify_deployment"), None, "https://dev.wix.com/"),
    ProviderSpec("sanity", "Sanity", "cms", ("api_token",), ("health", "discover_datasets", "discover_schema", "read_documents", "mutate_documents", "verify_publish_state", "rollback"), "provider_api", "https://www.sanity.io/docs/http-api"),
    ProviderSpec("shopify", "Shopify", "cms", ("oauth", "admin_api_token"), ("health", "read_products", "read_collections", "read_themes", "read_seo_metadata", "update_seo_metadata", "publish", "verify_deployment", "rollback"), "shopify", "https://shopify.dev/docs/api"),
    ProviderSpec("generic", "Generic Web / Custom Website", "cms", ("none_for_read", "sftp", "ftp", "deployment_api", "github"), ("health", "crawl", "generate_patch_pack", "deploy_when_configured", "verify_live_html", "rollback_when_supported"), "generic", "https://developer.mozilla.org/"),
    ProviderSpec("google_search_console", "Google Search Console", "seo_analytics", ("google_oauth", "service_account"), ("health", "search_queries", "clicks", "impressions", "ctr", "position", "url_inspection_where_available"), "google_search_console", "https://developers.google.com/webmaster-tools"),
    ProviderSpec("google_analytics_4", "Google Analytics 4", "seo_analytics", ("google_oauth", "service_account"), ("health", "organic_sessions", "landing_pages", "events", "conversions", "attribution"), "google_analytics_4", "https://developers.google.com/analytics"),
    ProviderSpec("crux", "Google CrUX", "seo_analytics", ("api_key",), ("health", "field_core_web_vitals", "reporting_period_validation"), "crux", "https://developer.chrome.com/docs/crux/api"),
    ProviderSpec("dataforseo", "DataForSEO", "seo_analytics", ("http_basic",), ("health", "live_serp", "keywords", "rankings", "backlinks", "competitors"), "dataforseo", "https://docs.dataforseo.com/v3/"),
    ProviderSpec("openai_search", "OpenAI / ChatGPT supported APIs", "ai_visibility", ("api_key",), ("health", "model_evaluation", "search_citations_only_when_api_returns_them"), "provider_api", "https://platform.openai.com/docs/"),
    ProviderSpec("perplexity", "Perplexity", "ai_visibility", ("api_key",), ("health", "live_answer_retrieval", "source_urls_when_returned"), "provider_api", "https://docs.perplexity.ai/"),
    ProviderSpec("claude", "Anthropic Claude", "ai_visibility", ("api_key", "oauth_where_available"), ("health", "model_evaluation", "web_search_evidence_only_when_tool_is_enabled"), "provider_api", "https://docs.anthropic.com/"),
    ProviderSpec("gemini", "Google Gemini", "ai_visibility", ("api_key", "google_oauth"), ("health", "model_evaluation", "grounding_sources_only_when_returned"), "provider_api", "https://ai.google.dev/gemini-api/docs"),
    ProviderSpec("github", "GitHub", "developer", ("oauth", "fine_grained_pat"), ("health", "discover_repositories", "branches", "commits", "pull_requests", "ci_checks", "diffs", "rollback_instructions"), "github", "https://docs.github.com/en/rest"),
    ProviderSpec("linkedin", "LinkedIn", "social", ("oauth",), ("health", "publish_when_scoped", "post_analytics_when_granted"), "provider_api", "https://learn.microsoft.com/linkedin/"),
    ProviderSpec("x", "X", "social", ("oauth",), ("health", "publish_posts_threads_when_scoped", "status", "engagement_metrics_when_granted"), "provider_api", "https://developer.x.com/en/docs"),
    ProviderSpec("tiktok", "TikTok", "social", ("oauth",), ("health", "media_upload_when_approved", "publish_when_approved", "publication_status"), "provider_api", "https://developers.tiktok.com/"),
    ProviderSpec("instagram", "Instagram Professional", "social", ("meta_oauth",), ("health", "publish_media_carousel_reels_when_granted", "insights_when_granted"), "provider_api", "https://developers.facebook.com/docs/instagram-platform/"),
    ProviderSpec("whatsapp_business", "WhatsApp Business Platform", "messaging", ("meta_oauth",), ("health", "template_messaging", "delivery_status_webhooks", "approval_actions"), "provider_api", "https://developers.facebook.com/docs/whatsapp/"),
    ProviderSpec("telegram", "Telegram Bot", "messaging", ("bot_token",), ("health", "send_messages", "inline_approval_buttons", "callback_validation", "webhooks"), "provider_api", "https://core.telegram.org/bots/api"),
    ProviderSpec("slack", "Slack", "messaging", ("oauth", "bot_token"), ("health", "block_kit_messages", "signed_interactions", "approval_workflows"), "provider_api", "https://api.slack.com/"),
    ProviderSpec("hubspot", "HubSpot", "crm_revenue", ("oauth", "private_app_token"), ("health", "contacts", "companies", "deals", "pipeline_stages", "revenue_attribution"), "provider_api", "https://developers.hubspot.com/"),
    ProviderSpec("salesforce", "Salesforce", "crm_revenue", ("oauth",), ("health", "accounts", "leads", "opportunities", "campaign_data", "revenue_reporting"), "provider_api", "https://developer.salesforce.com/docs/"),
    ProviderSpec("stripe", "Stripe", "crm_revenue", ("restricted_key", "oauth"), ("health", "customers", "subscriptions", "payments", "revenue_attribution_inputs"), "provider_api", "https://docs.stripe.com/api"),
)

_BY_ID = {provider.id: provider for provider in PROVIDERS}


def get_provider(provider_id: str) -> ProviderSpec | None:
    return _BY_ID.get(str(provider_id).lower())


def list_provider_specs() -> list[ProviderSpec]:
    return list(PROVIDERS)


def registry_payload(adapter_keys: set[str] | None = None) -> list[dict[str, Any]]:
    """Return truthful directory metadata without leaking credentials or claiming connection."""
    keys = adapter_keys or set()
    result = []
    for provider in PROVIDERS:
        adapter_registered = provider.adapter_key is not None or provider.id in keys
        if not adapter_registered:
            registered_operations: list[str] = []
        elif provider.adapter_key == "provider_api":
            registered_operations = ["health", "live_resource_discovery"]
            if provider.id in {"slack", "whatsapp_business", "telegram"}:
                registered_operations.append("webhook_ingress")
        else:
            # Legacy adapters expose the common lifecycle interface, but are not certified
            # until provider contract tests have passed against real/sandbox accounts.
            registered_operations = ["health", "resource_discovery", "preview_patch", "apply_patch", "rollback_patch"]
        operation_status = {
            operation: ("REGISTERED_UNVERIFIED" if operation in registered_operations else "NOT_IMPLEMENTED_OR_NOT_VERIFIED")
            for operation in provider.operations
        }
        for operation in registered_operations:
            operation_status.setdefault(operation, "REGISTERED_UNVERIFIED")
        result.append({
            "id": provider.id,
            "label": provider.label,
            "category": provider.category,
            "auth_methods": list(provider.auth_methods),
            "target_operations": list(provider.operations),
            "operations": registered_operations,
            "verified_operations": [],
            "operation_status": operation_status,
            "adapter_registered": adapter_registered,
            "implementation_status": "adapter_registered_unverified" if adapter_registered else "adapter_required",
            "connection_status": "DISCONNECTED",
            "docs_url": provider.docs_url,
            "notes": provider.notes or None,
        })
    return result
