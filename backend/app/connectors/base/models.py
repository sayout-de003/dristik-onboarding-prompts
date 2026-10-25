"""
Dristik AI Connector Base Models & Data Contracts
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.domain.enums import ConnectorType, ConnectorHealthStatus

class ConnectorCredentials(BaseModel):
    provider: ConnectorType
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    webhook_secret: Optional[str] = None
    account_id: Optional[str] = None
    project_id: Optional[str] = None
    username: Optional[str] = None
    app_password: Optional[str] = None
    github_token: Optional[str] = None
    repository: Optional[str] = None
    branch: Optional[str] = "main"
    scopes: List[str] = Field(default_factory=list)

class ConnectorHealth(BaseModel):
    provider: ConnectorType
    status: ConnectorHealthStatus
    latency_ms: float = 0.0
    authenticated: bool
    version: Optional[str] = None
    permissions_granted: List[str] = Field(default_factory=list)
    permissions_missing: List[str] = Field(default_factory=list)
    message: str = "Healthy"

class PatchApplicationResult(BaseModel):
    success: bool
    patch_id: str
    provider: ConnectorType
    applied_at: str
    target_resource: str
    diff_summary: Optional[Dict[str, Any]] = None
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    message: str
    rollback_supported: bool = True

class RollbackResult(BaseModel):
    success: bool
    patch_id: str
    rolled_back_at: str
    message: str
