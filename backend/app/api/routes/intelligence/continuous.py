"""Tenant-facing API for continuous website intelligence."""
from __future__ import annotations
from typing import Any, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.identity.authorizer import UserIdentity
from app.identity.deps import get_current_user
from app.continuous_intelligence import (
    PILLARS, _month, entitlement_for_org, execute_continuous_run, store,
)

router = APIRouter(prefix="/continuous-intelligence", tags=["Continuous Website Intelligence"])


class WebsiteProfileRequest(BaseModel):
    website_url: str
    niche: str = Field(default="", max_length=300)
    business_model: str = Field(default="", max_length=300)
    target_audience: str = Field(default="", max_length=2000)
    audience_pain_points: List[str] = Field(default_factory=list, max_length=50)
    target_markets: List[str] = Field(default_factory=list, max_length=30)
    languages: List[str] = Field(default_factory=lambda: ["en"], max_length=20)
    competitors: List[str] = Field(default_factory=list, max_length=30)
    goals: List[str] = Field(default_factory=list, max_length=30)
    max_pages: int = Field(default=10, ge=1, le=500)
    schedule_enabled: bool = True


class ScheduleRequest(BaseModel):
    enabled: bool


def _eligible_or_403(org_id: str):
    entitlement = entitlement_for_org(org_id)
    if not entitlement["eligible"]:
        raise HTTPException(status_code=403, detail=entitlement["reason"])
    return entitlement


@router.get("/entitlement")
def get_entitlement(user: UserIdentity = Depends(get_current_user)):
    return entitlement_for_org(user.org_id)


@router.post("/profiles")
def save_profile(payload: WebsiteProfileRequest, user: UserIdentity = Depends(get_current_user)):
    entitlement = _eligible_or_403(user.org_id)
    data = payload.model_dump()
    data["target_markets"] = [x.strip() for x in data["target_markets"] if x.strip()]
    data["languages"] = [x.strip() for x in data["languages"] if x.strip()]
    data["competitors"] = [x.strip() for x in data["competitors"] if x.strip()]
    data["audience_pain_points"] = [x.strip() for x in data["audience_pain_points"] if x.strip()]
    data["goals"] = [x.strip() for x in data["goals"] if x.strip()]
    try:
        return {
            "profile": store.upsert_profile(user.org_id, data, min(payload.max_pages, entitlement["max_pages"])),
            "entitlement": entitlement,
            "schedule": "MONTHLY" if payload.schedule_enabled else "PAUSED",
            "pillars": PILLARS,
            "note": "Trend metrics are reported only when supported by a connected, attributable data source.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/profiles")
def list_profiles(user: UserIdentity = Depends(get_current_user)):
    return {"profiles": store.list_profiles(user.org_id), "entitlement": entitlement_for_org(user.org_id)}


@router.get("/profiles/{profile_id}")
def get_profile(profile_id: str, user: UserIdentity = Depends(get_current_user)):
    profile = store.get_profile(user.org_id, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Website profile not found")
    return profile


@router.patch("/profiles/{profile_id}/schedule")
def set_schedule(profile_id: str, payload: ScheduleRequest, user: UserIdentity = Depends(get_current_user)):
    if payload.enabled:
        _eligible_or_403(user.org_id)
    profile = store.update_schedule(user.org_id, profile_id, payload.enabled)
    if not profile:
        raise HTTPException(status_code=404, detail="Website profile not found")
    return {"profile": profile, "schedule": "MONTHLY" if profile["schedule_enabled"] else "PAUSED"}


@router.post("/profiles/{profile_id}/run")
def run_now(profile_id: str, background_tasks: BackgroundTasks, user: UserIdentity = Depends(get_current_user)):
    entitlement = _eligible_or_403(user.org_id)
    profile = store.get_profile(user.org_id, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Website profile not found")
    profile["max_pages"] = min(profile["max_pages"], entitlement["max_pages"])
    run_id = store.create_run(profile, "manual", _month())
    if not run_id:
        raise HTTPException(status_code=409, detail="A run could not be created.")
    background_tasks.add_task(execute_continuous_run, profile, run_id, "manual")
    return {"run_id": run_id, "status": "QUEUED", "pillars": PILLARS, "message": "Monthly intelligence audit queued."}


@router.get("/runs")
def list_runs(limit: int = Query(20, ge=1, le=100), user: UserIdentity = Depends(get_current_user)):
    return {"runs": store.list_runs(user.org_id, limit=limit)}


@router.get("/runs/{run_id}")
def get_run(run_id: str, user: UserIdentity = Depends(get_current_user)):
    run = next((r for r in store.list_runs(user.org_id, limit=100) if r["run_id"] == run_id), None)
    if not run:
        raise HTTPException(status_code=404, detail="Continuous intelligence run not found")
    return run
