"""Dristik-issued credentials for external AI/MCP clients.

Re-exports canonical AI connection models and helpers from universal_connect
to maintain backward compatibility and a single source of truth.
"""
from __future__ import annotations

from app.api.routes.integrations.universal_connect import (  # noqa: F401
    AIConnectionCreate,
    AIConnectionValidate,
    create_ai_connection,
    list_ai_connections,
    validate_ai_connection,
    rotate_ai_connection,
    revoke_ai_connection,
    get_ai_connection_activity,
    get_mcp_user,
    _mcp_authorized,
    AI_GRANT_SCOPES,
    router,
)

__all__ = [
    "AIConnectionCreate",
    "AIConnectionValidate",
    "create_ai_connection",
    "list_ai_connections",
    "validate_ai_connection",
    "rotate_ai_connection",
    "revoke_ai_connection",
    "get_ai_connection_activity",
    "get_mcp_user",
    "_mcp_authorized",
    "AI_GRANT_SCOPES",
    "router",
]
