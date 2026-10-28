"""HTTP mount point.

Route modules live under ``app.api.routes``, grouped by product area.
Engines that still own a small router are imported here so ``main`` stays
an application factory.
"""
from fastapi import FastAPI

from app.api.routes.audits.analyses import router as analyses_router
from app.api.routes.audits.deep_crawls import router as deep_crawls_router
from app.api.routes.audits.public_grader import router as public_grader_router
from app.api.routes.audits.recurring import router as recurring_audits_router
from app.api.routes.audits.stream import router as stream_router
from app.api.routes.identity.auth import router as auth_router
from app.api.routes.identity.orgs import router as orgs_router
from app.api.routes.platform.commercial import router as commercial_router
from app.api.routes.platform.contact import router as contact_router
from app.api.routes.platform.meta import router as meta_router
from app.api.routes.platform.payments import router as payments_router
from app.api.routes.platform.system import router as system_router
from app.api.routes.platform.workspaces import router as workspaces_router
from app.geo.api.routes import router as geo_pipeline_router
from app.geo.api.analytics import router as geo_analytics_router
from app.api.routes.intelligence.keywords import router as keywords_router
from app.api.routes.intelligence.continuous import router as continuous_intelligence_router
from app.api.routes.intelligence.outcomes import router as outcomes_router
from app.api.routes.intelligence.radar import router as radar_router
from app.api.routes.intelligence.strategic import router as intelligence_router
from app.api.routes.integrations.connectors import router as connectors_router
from app.api.routes.integrations.universal_connect import router as universal_connect_router
from app.api.routes.integrations.ai_onboarding import router as ai_onboarding_router
from app.api.routes.integrations.provider_adapters import router as provider_adapters_router
from app.api.routes.integrations.external_authority import router as external_authority_router
from app.api.routes.integrations.google import router as integrations_router
from app.api.routes.integrations.performance_data import router as performance_data_router
from app.api.routes.remediation.patches import router as remediation_router
from app.aeo.router import router as aeo_reports_router
from app.core.security.enterprise_audit_logger import router as audit_logs_router
from app.intelligence.citations.live import router as live_ai_citation_router
from app.remediation.sync_engine import router as developer_sync_router
from app.reports.pdf_generator import router as reports_router
from app.tenancy.white_label import router as white_label_router

# Mounted at both /api/v1 and /api.
# The in-memory SCIM and SAML configure routes stay unmounted until they
# verify a real identity provider and a SCIM bearer token.
_PREFIXED_ROUTERS = (
    analyses_router,
    deep_crawls_router,
    public_grader_router,
    recurring_audits_router,
    stream_router,
    commercial_router,
    payments_router,
    auth_router,
    orgs_router,
    contact_router,
    system_router,
    radar_router,
    connectors_router,
    universal_connect_router,
    ai_onboarding_router,
    provider_adapters_router,
    external_authority_router,
    remediation_router,
    intelligence_router,
    outcomes_router,
    geo_pipeline_router,
    geo_analytics_router,
    keywords_router,
    continuous_intelligence_router,
    meta_router,
    integrations_router,
    performance_data_router,
    workspaces_router,
    live_ai_citation_router,
    developer_sync_router,
    reports_router,
    aeo_reports_router,
    audit_logs_router,
    white_label_router,
)


def mount_http(app: FastAPI) -> None:
    for prefix in ("/api/v1", "/api"):
        for router in _PREFIXED_ROUTERS:
            app.include_router(router, prefix=prefix)
    # Also mount universal_connect_router at root so /mcp and /connect are directly accessible
    app.include_router(universal_connect_router)
