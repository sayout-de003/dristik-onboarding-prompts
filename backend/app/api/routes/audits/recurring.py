"""Tenant-scoped recurring audit schedule API with plan-entitlement checks."""
from __future__ import annotations

from urllib.parse import urlsplit
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.identity.authorizer import UserIdentity
from app.identity.deps import get_current_user, require_permission
from app.identity.store import get_store
from app.monitoring.recurring_audits import get_recurring_audit_store

router = APIRouter(prefix="/recurring-audits", tags=["Recurring Audits"])

_PLAN_PAGE_LIMITS = {
    "starter": 3,
    "professional": 10,
    "diagnostic": 15,
    "business": 35,
    "enterprise": 100,
    "monitoring-growth": 35,
    "monitoring-agency": 100,
    "monitoring-enterprise": 100,
}


class RecurringAuditCreate(BaseModel):
    website_url: str = Field(min_length=8, max_length=2048)
    cadence_days: int = Field(default=30, ge=7, le=30)
    max_pages: int = Field(default=10, ge=1, le=100)
    target_pillars: list[str] = Field(default_factory=lambda: ["seo"])
    site_type: Optional[str] = Field(default=None, max_length=120)
    country: Optional[str] = Field(default="Global", max_length=80)
    language: Optional[str] = Field(default="en", max_length=24)


def _org_dict(org) -> dict:
    if org is None:
        return {}
    try:
        return dict(org)
    except (TypeError, ValueError):
        return {}


def _plan_limit(user: UserIdentity) -> int:
    org = _org_dict(get_store().get_organization(user.org_id))
    plan = str(org.get("plan") or "free_scan").lower()
    if plan not in _PLAN_PAGE_LIMITS:
        raise HTTPException(
            status_code=403,
            detail="RECURRING_AUDIT_ENTITLEMENT_REQUIRED: Recurring audits require an active paid monitoring plan.",
        )
    for key in ("subscription_status", "billing_status", "subscription_state"):
        state = str(org.get(key) or "").lower()
        if state and state not in {"active", "trialing", "trial"}:
            raise HTTPException(
                status_code=403,
                detail=f"SUBSCRIPTION_NOT_ACTIVE: recurring audits are paused for subscription state '{state}'.",
            )
    return _PLAN_PAGE_LIMITS[plan]


@router.post("", status_code=201)
async def create_recurring_audit(
    payload: RecurringAuditCreate,
    user: UserIdentity = Depends(require_permission("mission:create")),
):
    limit = _plan_limit(user)
    parts = urlsplit(payload.website_url.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise HTTPException(status_code=422, detail="website_url must be a valid public HTTP(S) website URL.")
    pillars = sorted({str(p).strip().lower() for p in payload.target_pillars if str(p).strip()})
    allowed_pillars = {"seo", "geo", "aeo", "cro"}
    if not pillars or not set(pillars).issubset(allowed_pillars):
        raise HTTPException(status_code=422, detail="target_pillars must contain one or more of seo, geo, aeo, cro.")
    if payload.max_pages > limit:
        raise HTTPException(
            status_code=403,
            detail=f"PLAN_PAGE_LIMIT: this plan supports at most {limit} pages per recurring audit.",
        )
    return get_recurring_audit_store().create(
        org_id=user.org_id,
        created_by=user.user_id,
        website_url=payload.website_url.strip(),
        cadence_days=payload.cadence_days,
        max_pages=payload.max_pages,
        target_pillars=pillars,
        site_type=payload.site_type,
        country=payload.country,
        language=payload.language,
    )


@router.get("")
async def list_recurring_audits(
    limit: int = 100,
    user: UserIdentity = Depends(get_current_user),
):
    return {"schedules": get_recurring_audit_store().list_for_org(user.org_id, limit=limit)}


@router.delete("/{schedule_id}", status_code=204)
async def cancel_recurring_audit(
    schedule_id: str,
    user: UserIdentity = Depends(require_permission("mission:create")),
):
    if not get_recurring_audit_store().cancel(schedule_id, user.org_id):
        raise HTTPException(status_code=404, detail="Recurring audit schedule not found.")
    return Response(status_code=204)
