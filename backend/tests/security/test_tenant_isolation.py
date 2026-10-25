"""Organization-scoped access must not leak another tenant's audit or artifacts."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.identity.authorization import UserIdentity
from app.identity.roles import UserRole
from app.identity.tenancy.isolation import require_analysis
import app.identity.access as access


def test_missing_run_is_not_found(monkeypatch):
    owner = UserIdentity(org_id="org_1", email="owner@example.com", role=UserRole.OWNER)
    monkeypatch.setattr(access.orchestrator, "get_run", lambda _analysis_id: None)
    monkeypatch.setattr(access.orchestrator, "runs", {})
    with pytest.raises(HTTPException) as caught:
        require_analysis("run_does_not_exist", owner)
    assert caught.value.status_code == 404


def test_cross_tenant_run_is_hidden_as_not_found(monkeypatch):
    foreign_run = SimpleNamespace(org_id="org_2", report=None)
    owner = UserIdentity(org_id="org_1", email="owner@example.com", role=UserRole.OWNER)
    monkeypatch.setattr(access.orchestrator, "get_run", lambda _analysis_id: foreign_run)
    with pytest.raises(HTTPException) as caught:
        require_analysis("run_owned_by_org_2", owner)
    assert caught.value.status_code == 404


def test_same_tenant_run_is_accessible(monkeypatch):
    owned_run = SimpleNamespace(org_id="org_1", report=None)
    owner = UserIdentity(org_id="org_1", email="owner@example.com", role=UserRole.OWNER)
    monkeypatch.setattr(access.orchestrator, "get_run", lambda _analysis_id: owned_run)
    assert require_analysis("run_owned_by_org_1", owner) is owned_run


def test_inactive_user_cannot_access_even_own_tenant(monkeypatch):
    owned_run = SimpleNamespace(org_id="org_1", report=None)
    owner = UserIdentity(
        org_id="org_1",
        email="owner@example.com",
        role=UserRole.OWNER,
        is_active=False,
    )
    monkeypatch.setattr(access.orchestrator, "get_run", lambda _analysis_id: owned_run)
    with pytest.raises(HTTPException) as caught:
        require_analysis("run_owned_by_org_1", owner)
    assert caught.value.status_code == 403
