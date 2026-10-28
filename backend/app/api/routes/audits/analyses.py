"""
Dristik AI Analysis API Routes
Endpoints for triggering audits, polling status, and fetching executive reports.
"""
import asyncio
import json
import math
from urllib.parse import urlparse, quote
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Response, status
from app.core.config import settings
from app.domain.models import (
    AnalysisRequest,
    AnalysisRun,
    ExecutiveReport,
    Finding,
    CommercialQueryEvaluation,
    CompetitorBakeoffResult,
)
from app.identity.access import require_analysis
from app.identity.authorizer import Authorizer, UserIdentity
from app.identity.deps import get_current_user, require_permission
from app.identity.store import get_store
from app.domain.commercial.payments.store import get_payment_store
from app.orchestration.orchestrator import orchestrator
from app.domain.scoring.displayed_score import displayed_composite
from app.remediation.patch_pack import (
    generate_patch_pack_zip,
    generate_notion_block,
    build_patch_pack_files,
    generate_whatsapp_summary,
)

router = APIRouter(prefix="/analyses", tags=["Analyses"])


def _listed_score(report: Any, fallback: Any) -> Any:
    """History badge uses the same composite as the open audit and the PDF cover."""
    shown = displayed_composite(report)
    return fallback if shown is None else shown


def _read_report_path(value: Any, *path: str) -> Any:
    """Read nested report data from Pydantic objects or stored JSON without guessing."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return None
    for key in path:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            value = getattr(value, key, None)
        if value is None:
            return None
    return value


def _listed_cro_score(report: Any) -> Optional[float]:
    """Return only an explicitly stored CRO score; never substitute the site-wide score."""
    candidates = (
        _read_report_path(report, "cro_audit", "overall_cro_score"),
        _read_report_path(report, "scores", "category_scores", "UX_CONVERSION", "score"),
    )
    for value in candidates:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if math.isfinite(float(value)) and 0 <= float(value) <= 100:
            return float(value)
    return None


def _listed_cro_metrics(report: Any) -> List[Dict[str, Any]]:
    """Expose only CRO metric observations actually stored with an audit report."""
    records = _read_report_path(report, "cro_audit", "intelligence", "metrics")
    if not isinstance(records, (list, tuple)):
        return []
    result: List[Dict[str, Any]] = []
    for item in records:
        name = _read_report_path(item, "metric")
        if not isinstance(name, str) or not name.strip():
            continue
        value = _read_report_path(item, "value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            value = None
        status_value = _read_report_path(item, "status")
        result.append({
            "metric": name,
            "formula": _read_report_path(item, "formula") or "",
            "status": status_value if isinstance(status_value, str) and status_value else "UNAVAILABLE",
            "value": float(value) if value is not None else None,
            "display": _read_report_path(item, "display") or "Unavailable",
            "denominator": _read_report_path(item, "denominator"),
            "numerator": _read_report_path(item, "numerator"),
            "window": _read_report_path(item, "window"),
            "note": _read_report_path(item, "note") or "",
        })
    return result

_BAKEOFF_PLANS = {
    "diagnostic_bakeoff",
    "business",
    "growth",
    "enterprise",
    "monitoring-growth",
    "monitoring-agency",
    "monitoring-enterprise",
}


def _require_bakeoff_entitlement(user: Optional[UserIdentity]) -> None:
    """Competitor bake-off is a paid tier. Free scans do not run it."""
    if user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ENTITLEMENT_REQUIRED: Sign in on a bake-off plan to compare a competitor.")
    role = getattr(getattr(user, "role", None), "value", getattr(user, "role", None))
    if role == "system_admin" or getattr(user, "is_system", False):
        return
    org = get_store().get_organization(user.org_id)
    plan = ((dict(org).get("plan") if org else None) or "free_scan").lower()
    if plan not in _BAKEOFF_PLANS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"ENTITLEMENT_REQUIRED: Competitor bake-off is not included in plan '{plan}'. "
                "Upgrade to Competitor Bake-Off, Growth, or Enterprise."
            ),
        )

class ReQueryRequest(BaseModel):
    custom_schema: Optional[str] = None
    custom_faq: Optional[str] = None

class CompetitorBakeoffRequest(BaseModel):
    competitor_url: str = Field(..., description="Competitor website URL or domain")



def _get_org_run(analysis_id: str, user: Optional[UserIdentity] = None) -> AnalysisRun:
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return require_analysis(analysis_id, user)


async def _execute_analysis_with_provider(provider_id: str, org_id: str, *pipeline_args: Any) -> None:
    """Run the canonical pipeline with a task-local selected-provider override."""
    from app.core.inference.model_router import use_provider_override
    with use_provider_override(provider_id, org_id):
        await orchestrator.execute_analysis_pipeline(*pipeline_args)

@router.get("", response_model=List[Dict[str, Any]])
async def list_analyses(
    limit: int = 25,
    user: UserIdentity = Depends(get_current_user),
):
    """
    Lists recent audit summaries for the organization.
    Enables users to revisit previous audits and switch between them.
    """
    if not Authorizer.can_perform(user, "mission:read"):
        raise HTTPException(status_code=403, detail="You do not have permission to view audits.")
    org_id = user.org_id
    repo = orchestrator.repository
    runs = repo.list_runs(org_id=org_id, limit=limit)
    seen_ids = set()
    summaries = []

    for r in orchestrator.runs.values():
        if Authorizer.can_access_org(user, r.org_id):
            seen_ids.add(r.analysis_id)
            summaries.append({
                "analysis_id": r.analysis_id,
                "website_url": r.website_url,
                "domain": getattr(r.report, "domain", None) or urlparse(r.website_url).netloc.replace("www.", ""),
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                "progress": r.progress_percentage,
                "score_overall": _listed_score(
                    r.report,
                    getattr(getattr(r.report, "scores", None), "overall_score", None),
                ),
                "score_band": getattr(r, "score_band", None) or getattr(getattr(r.report, "honest_scores", None), "score_band", None),
                "score_cro": _listed_cro_score(r.report),
                "cro_score_status": "MEASURED" if _listed_cro_score(r.report) is not None else "UNAVAILABLE",
                "cro_metrics": _listed_cro_metrics(r.report),
                "started_at": r.created_at.isoformat() if hasattr(r.created_at, "isoformat") else str(r.created_at),
                "completed_at": r.completed_at.isoformat() if getattr(r, "completed_at", None) and hasattr(r.completed_at, "isoformat") else None,
                "page_count": getattr(r, "max_pages", 1),
            })

    # DB stored runs
    for r in runs:
        aid = r["analysis_id"]
        if aid not in seen_ids:
            seen_ids.add(aid)
            summaries.append({
                "analysis_id": aid,
                "website_url": r["website_url"],
                "domain": r.get("domain") or urlparse(r["website_url"]).netloc.replace("www.", ""),
                "status": r["status"],
                "progress": r["progress"],
                "score_overall": _listed_score(r.get("raw_report_json"), r.get("score_overall")),
                "score_band": r.get("score_band"),
                "score_cro": _listed_cro_score(r.get("raw_report_json")),
                "cro_score_status": "MEASURED" if _listed_cro_score(r.get("raw_report_json")) is not None else "UNAVAILABLE",
                "cro_metrics": _listed_cro_metrics(r.get("raw_report_json")),
                "started_at": r.get("started_at") or r.get("created_at"),
                "completed_at": r.get("completed_at"),
                "page_count": r.get("max_pages", 1),
            })

    return summaries

@router.delete("/{analysis_id}")
async def delete_analysis(
    analysis_id: str,
    user: UserIdentity = Depends(get_current_user),
):
    """Deletes a stored audit owned by the caller's organization."""
    if not Authorizer.can_perform(user, "mission:delete"):
        raise HTTPException(status_code=403, detail="You do not have permission to delete audits.")
    run = require_analysis(analysis_id, user, permission="mission:read")
    removed = orchestrator.repository.delete_run(run.analysis_id, org_id=run.org_id)
    orchestrator.runs.pop(run.analysis_id, None)
    if not removed and run.analysis_id not in orchestrator.runs:
        return {"deleted": run.analysis_id}
    return {"deleted": run.analysis_id}

@router.post("", response_model=AnalysisRun)
async def start_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    user: UserIdentity = Depends(require_permission("mission:create")),
    model_provider_id: Optional[str] = None,
):
    """
    Submits a website URL to start an autonomous audit run.
    """
    raw_url = (request.website_url or "").strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="Website URL is required. Please provide a valid target website URL.")

    url = raw_url
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
        
    parsed = urlparse(url)
    if not parsed.netloc or "." not in parsed.netloc:
        raise HTTPException(status_code=400, detail=f"Invalid website URL '{request.website_url}'. Please provide a valid domain (e.g., https://example.com).")

    if model_provider_id:
        from app.api.routes.integrations import provider_adapters
        with provider_adapters._db() as conn:
            provider_row = conn.execute(
                "SELECT id,status FROM uc_provider_credentials WHERE id=? AND org_id=?",
                (model_provider_id, user.org_id),
            ).fetchone()
        if provider_row is None or provider_row["status"] == "revoked":
            raise HTTPException(status_code=404, detail="Selected model provider is not available in this organization.")
        if provider_row["status"] != "healthy":
            raise HTTPException(status_code=409, detail="Test the selected model provider successfully before using it for an audit.")

    if not settings.has_active_llm_key and not model_provider_id:
        active_prov = settings.get_active_provider()
        raise HTTPException(
            status_code=400,
            detail=(
                f"No LLM API key configured for active provider '{active_prov}'. "
                f"Please set GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY, TOGETHER_API_KEY, or NVIDIA_API_KEY in backend/.env."
            )
        )

    requested_pages = request.max_crawl_pages or 1
    allowed_pages = 1

    # Commercial Entitlement Check:
    # 1. If voucher provided, it MUST be valid, bound to this exact target domain, and have sufficient page capacity
    if request.voucher_code and request.voucher_code.strip():
        store = get_payment_store()
        is_valid, reason, v_pages = store.validate_entitlement(request.voucher_code.strip(), url, requested_pages)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"ENTITLEMENT_VIOLATION: Voucher '{request.voucher_code}' is invalid for this target domain: {reason}"
            )
        allowed_pages = min(requested_pages, v_pages)
    elif requested_pages > 1:
        # 2. Check if organization has an active paid subscription covering multi-page depth
        org = get_store().get_organization(user.org_id)
        org_dict = dict(org) if org else {}
        org_plan = (org_dict.get("plan") or "free_scan").lower()
        tier_limits = {
            "free_scan": 1,
            "starter": 3,
            "professional": 10,
            "diagnostic": 15,
            "business": 35,
            "enterprise": 100,
        }
        plan_max = tier_limits.get(org_plan, 1)
        if plan_max >= requested_pages:
            allowed_pages = requested_pages
        elif plan_max > 1:
            allowed_pages = min(requested_pages, plan_max)
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"ENTITLEMENT_REQUIRED: Auditing {requested_pages} pages requires a verified voucher or paid plan. "
                    f"Your current plan ('{org_plan}') is limited to 1 page. Please provide a valid voucher code or upgrade your plan."
                )
            )

    run = orchestrator.create_run(
        url,
        org_id=user.org_id,
        created_by=user.user_id,
        target_pillars=request.target_pillars,
    )
    max_pages = allowed_pages
    get_store().record_audit(
        analysis_id=run.analysis_id,
        org_id=user.org_id,
        user_id=user.user_id,
        website_url=url,
        status=run.status.value if hasattr(run.status, "value") else str(run.status),
        page_count=max_pages,
    )
    # Launch the same canonical orchestration pipeline. A selected provider is
    # applied only to this background task through a ContextVar, avoiding
    # cross-tenant/provider leakage when audits run concurrently.
    site_type = request.site_type or request.industry
    pipeline_args = (
        run.analysis_id, url, max_pages, site_type,
        request.declared_site_type_notes, request.country,
        request.language, request.target_pillars,
    )
    if model_provider_id:
        background_tasks.add_task(
            _execute_analysis_with_provider, model_provider_id, user.org_id, *pipeline_args
        )
    else:
        background_tasks.add_task(orchestrator.execute_analysis_pipeline, *pipeline_args)
    return run


@router.get("/{analysis_id}", response_model=AnalysisRun)
async def get_analysis_status(analysis_id: str, user: UserIdentity = Depends(get_current_user)):
    return _get_org_run(analysis_id, user)

@router.get("/{analysis_id}/report", response_model=ExecutiveReport)
async def get_analysis_report(analysis_id: str, user: UserIdentity = Depends(get_current_user)):
    run = _get_org_run(analysis_id, user)
    if not run.report:
        raise HTTPException(status_code=400, detail="Report is not ready yet or analysis is still in progress.")
    return run.report


@router.get("/{analysis_id}/manifest")
async def get_analysis_manifest(analysis_id: str, user: UserIdentity = Depends(get_current_user)):
    """Return the sealed run manifest used to reconstruct this audit."""
    from app.crawl.audit.manifest import load_manifest
    run = _get_org_run(analysis_id, user)
    disk = load_manifest(run.analysis_id)
    if not disk:
        raise HTTPException(status_code=404, detail="Run manifest not found.")
    return disk.model_dump()


@router.get("/{analysis_id}/snapshots/{snapshot_id}")
async def get_analysis_snapshot(analysis_id: str, snapshot_id: str, user: UserIdentity = Depends(get_current_user)):
    """Return a raw immutable snapshot (page body or API payload) by content-addressed ID."""
    from app.crawl.audit.snapshots import SnapshotStore
    run = _get_org_run(analysis_id, user)
    store = SnapshotStore(run.analysis_id)
    record = store.get(snapshot_id)
    if not record:
        raise HTTPException(status_code=404, detail="Snapshot not found.")
    if not store.verify(snapshot_id):
        raise HTTPException(status_code=409, detail="Snapshot failed hash verification.")
    return record.model_dump()

@router.get("/{analysis_id}/findings", response_model=list[Finding])
async def get_analysis_findings(analysis_id: str, user: UserIdentity = Depends(get_current_user)):
    run = _get_org_run(analysis_id, user)
    if not run.report:
        raise HTTPException(status_code=404, detail="Findings not found.")
    return run.report.findings

@router.get("/{analysis_id}/twin")
async def get_analysis_digital_twin(analysis_id: str, user: UserIdentity = Depends(get_current_user)):
    run = _get_org_run(analysis_id, user)
    if not run.report:
        raise HTTPException(status_code=404, detail="Analysis report not found.")
    domain = run.report.domain
    twin = orchestrator.digital_twins.get(domain)
    if not twin:
        raise HTTPException(status_code=404, detail="Digital Twin not available for this domain.")
    return twin.model_dump()

@router.get("/{analysis_id}/intent-graph")
async def get_analysis_intent_graph(analysis_id: str, user: UserIdentity = Depends(get_current_user)):
    run = _get_org_run(analysis_id, user)
    if not run.report:
        raise HTTPException(status_code=404, detail="Analysis report not found.")
    paths = orchestrator.intent_graph.construct_intent_paths(
        run.report.business_profile,
        run.report.crawl_manifest.pages if run.report.crawl_manifest else []
    )
    return [p.model_dump() for p in paths]

@router.get("/{analysis_id}/remediation")
async def get_analysis_remediation_plan(analysis_id: str, user: UserIdentity = Depends(get_current_user)):
    run = _get_org_run(analysis_id, user)
    if not run.report:
        raise HTTPException(status_code=404, detail="Analysis report not found.")
    plan = orchestrator.remediation_planner.build_remediation_plan(
        findings=run.report.findings,
        business_profile=run.report.business_profile,
        target_url=run.report.website_url
    )
    return plan.model_dump()

@router.get("/{analysis_id}/timeline")
async def get_analysis_timeline(analysis_id: str, user: UserIdentity = Depends(get_current_user)):
    run = _get_org_run(analysis_id, user)
    if not run.report:
        raise HTTPException(status_code=404, detail="Analysis report not found.")
    domain = run.report.domain
    timeline = orchestrator.timelines.get(domain)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found for this domain.")
    return {
        "domain": domain,
        "total_audits": len(timeline.snapshots),
        "snapshots": [s.model_dump() for s in timeline.snapshots],
        "delta": timeline.compute_delta().model_dump() if timeline.compute_delta() else None
    }

@router.get("/{analysis_id}/patch-pack/zip")
async def download_patch_pack_zip(analysis_id: str, user: UserIdentity = Depends(get_current_user)):
    """Downloads a developer-ready ZIP containing schema.jsonld, metadata.html, faq.html, llms.txt, robots.txt."""
    run = _get_org_run(analysis_id, user)
    if not run.report:
        raise HTTPException(status_code=404, detail="Analysis report not ready yet.")
    
    zip_bytes = generate_patch_pack_zip(
        bp=run.report.business_profile,
        website_url=run.report.website_url,
        commercial_evals=run.report.commercial_evaluations or []
    )
    safe_domain = run.report.domain.replace(".", "_")
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_domain}_dristik_patch_pack.zip"'
        }
    )

@router.get("/{analysis_id}/patch-pack/files")
async def get_patch_pack_files(analysis_id: str, user: UserIdentity = Depends(get_current_user)):
    """Returns individual text contents of the patch pack files for in-browser preview."""
    run = _get_org_run(analysis_id, user)
    if not run.report:
        raise HTTPException(status_code=404, detail="Analysis report not ready yet.")
    
    files = build_patch_pack_files(
        bp=run.report.business_profile,
        website_url=run.report.website_url,
        commercial_evals=run.report.commercial_evaluations or []
    )
    return {
        "domain": run.report.domain,
        "files": files,
        "file_names": list(files.keys())
    }

@router.get("/{analysis_id}/patch-pack/notion")
async def get_patch_pack_notion(analysis_id: str, user: UserIdentity = Depends(get_current_user)):
    """Returns a single clean Markdown block formatted for 1-click copy into Notion or Jira."""
    run = _get_org_run(analysis_id, user)
    if not run.report:
        raise HTTPException(status_code=404, detail="Analysis report not ready yet.")
    
    notion_md = generate_notion_block(
        bp=run.report.business_profile,
        website_url=run.report.website_url,
        commercial_evals=run.report.commercial_evaluations or []
    )
    return {
        "domain": run.report.domain,
        "notion_markdown": notion_md
    }

@router.post("/{analysis_id}/simulate-ai-search")
async def simulate_ai_search(
    analysis_id: str,
    user: UserIdentity = Depends(get_current_user)
):
    """
    Executes or refreshes the 6 Canonical Commercial Inquiries simulation using the active LLM (Claude).
    Uses the crawled page evidence stored in the analysis report.
    """
    run = _get_org_run(analysis_id, user)
    if not run.report:
        raise HTTPException(status_code=404, detail="Analysis report not ready yet.")

    from app.orchestration.cognition.blackboard import CognitiveBlackboard
    blackboard = CognitiveBlackboard(run_id=run.analysis_id, website_url=run.website_url)
    blackboard.business_profile = run.report.business_profile

    # Populate evidence store from crawl manifest
    if run.report.crawl_manifest and run.report.crawl_manifest.pages:
        blackboard.crawl_manifest = run.report.crawl_manifest
        blackboard.pages = run.report.crawl_manifest.pages
        for page in run.report.crawl_manifest.pages:
            if page.title:
                blackboard.evidence_store.add_evidence(source_type="dom", url=page.url, selector="title", text=page.title)
            if page.meta_description:
                blackboard.evidence_store.add_evidence(source_type="dom", url=page.url, selector="meta[name=description]", text=page.meta_description)
            if page.h1:
                for h in page.h1:
                    blackboard.evidence_store.add_evidence(source_type="dom", url=page.url, selector="h1", text=h)
            if page.body_text:
                blackboard.evidence_store.add_evidence(source_type="dom", url=page.url, selector="body", text=page.body_text[:1500])

    sim_res = await orchestrator.team_orchestrator.worker_simulator.execute_task("ai_search_simulation", blackboard)

    if blackboard.commercial_evaluations:
        run.report.commercial_evaluations = blackboard.commercial_evaluations
    if getattr(blackboard, "dynamic_sandbox_evaluations", None):
        run.report.dynamic_sandbox_evaluations = blackboard.dynamic_sandbox_evaluations
    if blackboard.ai_search_evaluations:
        run.report.ai_search_matrix = blackboard.ai_search_evaluations

    return {
        "status": sim_res.get("status", "AVAILABLE"),
        "commercial_evaluations": [c.model_dump() for c in run.report.commercial_evaluations or []],
        "dynamic_sandbox_evaluations": [d.model_dump() for d in getattr(run.report, "dynamic_sandbox_evaluations", []) or []],
        "ai_search_matrix": [m.model_dump() for m in run.report.ai_search_matrix or []]
    }

@router.post("/{analysis_id}/dynamic-sandbox")
async def generate_audit_dynamic_sandbox(
    analysis_id: str,
    user: UserIdentity = Depends(get_current_user)
):
    """
    Synthesizes and evaluates 100 bespoke business questions across 10 strategic facets
    for this specific audit report using its crawled DOM evidence and active LLM.
    """
    from app.seo.business.entity_resolver import UniversalEntityResolver
    from app.geo.dynamic_sandbox import DynamicQuestionSandboxEngine
    from app.domain.models import PageEvidence

    run = _get_org_run(analysis_id, user)
    if not run.report:
        raise HTTPException(status_code=404, detail="Analysis report not ready yet.")

    pages = []
    if run.report.crawl_manifest and run.report.crawl_manifest.pages:
        pages = list(run.report.crawl_manifest.pages)
    elif run.report.page_reports:
        for p in run.report.page_reports:
            p_title = getattr(p, "title", None) or (getattr(p, "seo", None) and getattr(p.seo, "title", None)) or run.report.domain
            p_desc = (getattr(p, "seo", None) and getattr(p.seo, "meta_description", None)) or getattr(p, "meta_description", "")
            p_h1 = getattr(p, "h1", None)
            h1_list = [p_h1] if isinstance(p_h1, str) else (p_h1 or [])
            p_h2 = getattr(p, "h2", None) or []
            p_text = getattr(p, "body_text", None) or run.report.story_summary or ""
            pages.append(PageEvidence(
                url=getattr(p, "url", run.report.website_url),
                title=p_title,
                meta_description=p_desc,
                h1=h1_list,
                h2=p_h2,
                body_text=p_text,
                word_count=getattr(p, "word_count", None) or len(p_text.split()) or 100
            ))
    elif run.report.crawl_manifest and run.report.crawl_manifest.crawled_urls:
        for u in run.report.crawl_manifest.crawled_urls:
            pages.append(PageEvidence(
                url=u,
                title=run.report.domain,
                body_text=run.report.story_summary or "",
                word_count=100
            ))
    else:
        pages.append(PageEvidence(
            url=run.report.website_url,
            title=f"{run.report.domain} Official",
            body_text=run.report.story_summary or "Digital platform offering commercial services.",
            word_count=100
        ))

    resolved_entity = UniversalEntityResolver.resolve_from_evidence(
        website_url=run.report.website_url,
        pages=pages
    )

    model_router = getattr(orchestrator, "model_router", None)
    if not model_router:
        from app.core.inference.model_router import ModelRouter
        model_router = ModelRouter()
    sandbox_engine = DynamicQuestionSandboxEngine(model_router=model_router)
    evaluations = await sandbox_engine.generate_and_evaluate_100_questions(
        pages=pages,
        website_url=run.report.website_url,
        resolved_entity=resolved_entity,
        profile=run.report.business_profile
    )

    # ── KIE Phase 6: Rebuild graph, store summary & 5-dimension scorecard ────
    from app.crawl.knowledge.website_knowledge_graph import WebsiteKnowledgeGraph
    from app.crawl.knowledge.grounded_simulator import AiVisibilityIndexCalculator

    domain = run.report.website_url.split("//")[-1].split("/")[0].replace("www.", "") if run.report.website_url else run.report.domain
    kg = WebsiteKnowledgeGraph(brand=resolved_entity.name, domain=domain)
    try:
        kg.build_from_pages(pages)
        run.report.kie_graph_summary = kg.summary()

        # Build simulations from the evaluations we just produced
        from app.crawl.knowledge.primitives import GroundedAnswerSimulation, KieAnswerRisk
        from app.crawl.knowledge.primitives import ClaimGroundingResult
        sim_list = []
        for ev in evaluations:
            grounding = ev.grounding_ratio or 0.0
            risk = ev.answer_risk or "LOW"
            if isinstance(risk, str):
                try:
                    risk = KieAnswerRisk(risk)
                except Exception:
                    risk = KieAnswerRisk.LOW
            from app.crawl.knowledge.primitives import GroundedAnswerSimulation
            sim_obj = GroundedAnswerSimulation(
                question_id=ev.question_id,
                candidate_answer=ev.crawled_answer or "",
                grounding_ratio=grounding,
                retrieval_evidence_count=ev.retrieval_evidence_count or 0,
                answer_risk=risk,
            )
            sim_list.append(sim_obj)

        dims = AiVisibilityIndexCalculator().compute(kg, sim_list)
        run.report.five_dimension_ai_visibility = dims.model_dump()
    except Exception:
        pass  # Non-fatal; KIE data is enhancement not hard requirement

    run.report.dynamic_sandbox_evaluations = evaluations

    # Persist the updated run to storage so reloads retain generated evaluations
    try:
        orchestrator.repository.save_run(run)
    except Exception:
        pass

    answerable = sum(1 for e in evaluations if e.is_answerable)
    unanswerable = sum(1 for e in evaluations if not e.is_answerable)
    avg_score = round(sum(e.citability_score for e in evaluations) / max(1, len(evaluations)), 1)
    avg_grounding = round(sum((e.grounding_ratio or 0.0) for e in evaluations) / max(1, len(evaluations)), 3)

    return {
        "status": "AVAILABLE",
        "total_questions": len(evaluations),
        "answerable_count": answerable,
        "unanswerable_count": unanswerable,
        "average_citability_score": avg_score,
        "average_grounding_ratio": avg_grounding,
        "kie_graph_summary": run.report.kie_graph_summary,
        "five_dimension_ai_visibility": run.report.five_dimension_ai_visibility,
        "system_execution_log": getattr(sandbox_engine, "system_execution_log", []),
        "evaluations": [e.model_dump() for e in evaluations]
    }

@router.get("/{analysis_id}/ki-graph")
async def get_ki_graph(
    analysis_id: str,
    user: UserIdentity = Depends(get_current_user)
):
    """
    Returns the Knowledge Intelligence Engine (KIE) graph for a completed audit.
    Provides:
      - Knowledge Graph Summary (entity count, claim count, relationship count, contradictions)
      - 5-Dimension AI Visibility Scorecard (knowledge_coverage, retrieval_coverage,
        evidence_quality, answer_grounding, citation_quality)
      - Contradiction list (cross-page knowledge conflicts: ICP, pricing, headcount)

    Cached on report if already computed. Re-builds from page evidence if not.
    """
    from app.crawl.knowledge.website_knowledge_graph import WebsiteKnowledgeGraph
    from app.crawl.knowledge.grounded_simulator import (
        GroundedAnswerSimulator, AiVisibilityIndexCalculator
    )
    from app.crawl.knowledge.primitives import GroundedAnswerSimulation, KieAnswerRisk

    run = _get_org_run(analysis_id, user)
    if not run.report:
        raise HTTPException(status_code=404, detail="Analysis report not ready yet.")

    # Return cached if available and both fields present
    if run.report.kie_graph_summary and run.report.five_dimension_ai_visibility:
        return {
            "status": "CACHED",
            "kie_graph_summary": run.report.kie_graph_summary,
            "five_dimension_ai_visibility": run.report.five_dimension_ai_visibility,
            "contradictions": [],  # not re-derived from cache
        }

    # Rebuild from page evidence
    pages = []
    if run.report.page_reports:
        for p in run.report.page_reports:
            pages.append(PageEvidence(
                url=p.url,
                title=p.title,
                meta_description=p.meta_description,
                h1=[p.h1] if isinstance(p.h1, str) else (p.h1 or []),
                h2=p.h2 or [],
                body_text=p.body_text or "",
                word_count=p.word_count or 0
            ))
    elif run.report.crawl_manifest and run.report.crawl_manifest.crawled_urls:
        for u in run.report.crawl_manifest.crawled_urls:
            pages.append(PageEvidence(
                url=u,
                title=run.report.domain,
                body_text=run.report.story_summary or "",
                word_count=100
            ))
    else:
        pages.append(PageEvidence(
            url=run.report.website_url,
            title=f"{run.report.domain} Official",
            body_text=run.report.story_summary or "Digital platform offering commercial services.",
            word_count=100
        ))

    biz_name = (
        run.report.business_profile.business_name
        if run.report.business_profile else run.report.domain
    )
    domain = run.report.website_url.split("//")[-1].split("/")[0].replace("www.", "") if run.report.website_url else run.report.domain

    kg = WebsiteKnowledgeGraph(brand=biz_name, domain=domain)
    try:
        kg.build_from_pages(pages)
        summary = kg.summary()
        run.report.kie_graph_summary = summary

        # Build simulations from existing sandbox evaluations if available
        sim_list = []
        for ev in (run.report.dynamic_sandbox_evaluations or []):
            risk = ev.answer_risk or "LOW"
            try:
                risk_enum = KieAnswerRisk(risk)
            except Exception:
                risk_enum = KieAnswerRisk.LOW
            sim_list.append(GroundedAnswerSimulation(
                question_id=ev.question_id,
                candidate_answer=ev.crawled_answer or "",
                grounding_ratio=ev.grounding_ratio or 0.0,
                retrieval_evidence_count=ev.retrieval_evidence_count or 0,
                answer_risk=risk_enum,
            ))

        dims = AiVisibilityIndexCalculator().compute(kg, sim_list)
        run.report.five_dimension_ai_visibility = dims.model_dump()

        contradictions = [c.model_dump() for c in kg.contradictions]
    except Exception as exc:
        return {
            "status": "ERROR",
            "message": str(exc),
            "kie_graph_summary": None,
            "five_dimension_ai_visibility": None,
            "contradictions": [],
        }

    return {
        "status": "OK",
        "kie_graph_summary": run.report.kie_graph_summary,
        "five_dimension_ai_visibility": run.report.five_dimension_ai_visibility,
        "contradictions": contradictions,
    }


@router.post("/{analysis_id}/re-query")
async def run_patch_requery(
    analysis_id: str,
    req: ReQueryRequest,
    user: UserIdentity = Depends(get_current_user)
):
    """
    Re-runs the 6 Commercial Buyer Questions after applying the patch (or custom pasted schema/FAQ).
    Executes a real live-model evaluation against the proposed patch context using the active LLM engine.
    Returns updated before -> after citation readiness and genuine model-graded score deltas.
    """
    from app.geo.citations.answer_change import settle_patch_scores
    from app.workers.simulator_worker import CANONICAL_COMMERCIAL_QUESTIONS

    run = _get_org_run(analysis_id, user)
    if not run.report:
        raise HTTPException(status_code=404, detail="Analysis report not ready yet.")
    
    current_evals = run.report.commercial_evaluations or []
    
    # 1. Assemble patch context from request or report code patches
    patch_context_parts = []
    if req.custom_schema and req.custom_schema.strip():
        patch_context_parts.append(f"### CUSTOM SCHEMA.ORG JSON-LD:\n{req.custom_schema.strip()}")
    if req.custom_faq and req.custom_faq.strip():
        patch_context_parts.append(f"### CUSTOM FAQ CONTENT:\n{req.custom_faq.strip()}")
        
    if not patch_context_parts and run.report.code_patches:
        for p in run.report.code_patches:
            if p.after_snippet:
                patch_context_parts.append(f"### PATCH FILE ({p.target_file} - {p.title}):\n{p.after_snippet}")

    if not patch_context_parts and not current_evals:
        return {
            "status": "unavailable",
            "message": "No patch code or commercial inquiries available to verify. Generate code patches or supply custom schema/FAQ.",
            "domain": run.report.domain,
            "commercial_evaluations": [],
            "avg_before_score": None,
            "avg_after_score": None,
            "total_citation_gain_pct": None,
            "is_live": False
        }

    combined_patch_text = "\n\n".join(patch_context_parts) if patch_context_parts else "Standard Schema.org + Semantic FAQ Patch"

    # 2. Invoke live model router to genuinely evaluate the questions against the patch
    biz_name = run.report.business_profile.business_name if run.report.business_profile else run.report.domain
    
    # Format questions to evaluate
    questions_to_eval = []
    source_list = current_evals if current_evals else CANONICAL_COMMERCIAL_QUESTIONS
    for idx, e in enumerate(source_list):
        key = getattr(e, "question_key", None) or (e.get("key") if isinstance(e, dict) else f"q_{idx}")
        title = getattr(e, "question_title", None) or (e.get("title") if isinstance(e, dict) else f"Question {idx+1}")
        query = getattr(e, "buyer_query", None) or (e.get("query") if isinstance(e, dict) else "")
        b_score = getattr(e, "before_score", None) or (e.get("before_score", 3) if isinstance(e, dict) else 3)
        b_ans = getattr(e, "before_answer", None) or (e.get("before_answer", "Cannot determine from raw site.") if isinstance(e, dict) else "Cannot determine from raw site.")
        ev_stat = getattr(e, "before_evidence_status", None) or (e.get("before_evidence_status", "MISSING") if isinstance(e, dict) else "MISSING")
        questions_to_eval.append({
            "key": key,
            "title": title,
            "query": query,
            "before_score": b_score,
            "before_answer": b_ans,
            "before_evidence_status": ev_stat
        })

    eval_prompt = (
        f"You are an objective AI Answer Engine evaluation auditor (evaluating for ChatGPT Search, Perplexity, Claude, Gemini).\n"
        f"Target Domain: {run.report.domain} | Organization: {biz_name}\n\n"
        f"Candidate Patch Code:\n```\n{combined_patch_text[:4000]}\n```\n\n"
        f"Evaluate how an AI answer engine will answer each of the following commercial buyer inquiries "
        f"AFTER this patch code is deployed into the site's DOM / structured metadata.\n"
        f"Questions:\n" + "\n".join([f"- [{q['key']}] '{q['query']}' (Baseline before_score: {q['before_score']})" for q in questions_to_eval])
    )

    schema_desc = (
        "{\n"
        '  "evaluations": [\n'
        '    {\n'
        '      "question_key": "string",\n'
        '      "after_score": 8,\n'
        '      "after_answer": "exact answer synthesized from patch context",\n'
        '      "evidence_snippet": "extracted quote or attribute from patch",\n'
        '      "gap_analysis": "status of any remaining gaps"\n'
        '    }\n'
        '  ]\n'
        "}"
    )

    try:
        model_result = await orchestrator.model_router.generate_structured(
            capability="ai_search_simulation",
            agent_role="Principal Generative Search Retrieval Scientist",
            task_contract=eval_prompt,
            evidence_list=[],
            rubric=(
                "1. STRICT POST-PATCH FIDELITY: after_answer must use only facts present in the candidate patch. "
                "2. If the patch does not add a fact the current answer lacks, repeat the before answer, set after_score equal to before_score, and do not claim a citation gain. "
                "3. Do not raise the score for restating that the fact cannot be determined, or for citing the current meta description or title."
            ),
            output_schema_desc=schema_desc,
            additional_context=f"Domain: {run.report.domain}"
        )

        after_eval_map = {}
        for item in (model_result.get("evaluations") or []):
            if isinstance(item, dict) and "question_key" in item:
                after_eval_map[item["question_key"]] = item

        updated_evals = []
        for q in questions_to_eval:
            k = q["key"]
            after_info = after_eval_map.get(k, {})
            b_sc = int(q["before_score"])
            after_answer = after_info.get("after_answer") or q["before_answer"]
            raw_after = int(after_info.get("after_score")) if after_info.get("after_score") is not None else None
            a_sc, delta, gain = settle_patch_scores(b_sc, raw_after, q["before_answer"], after_answer, None)

            updated_eval = CommercialQueryEvaluation(
                question_key=k,
                question_title=q["title"],
                buyer_query=q["query"],
                before_score=b_sc,
                before_answer=q["before_answer"],
                before_evidence_status=q["before_evidence_status"],
                after_score=a_sc,
                after_answer=after_answer,
                delta=delta,
                patch_citation_gain=gain,
                evidence_snippet=after_info.get("evidence_snippet") or "",
                gap_analysis=after_info.get("gap_analysis") or "Verified via live model re-query."
            )
            updated_evals.append(updated_eval)

        run.report.commercial_evaluations = updated_evals
        
        avg_before = round(sum(e.before_score for e in updated_evals) / max(1, len(updated_evals)), 1)
        avg_after = round(sum(e.after_score for e in updated_evals) / max(1, len(updated_evals)), 1)
        avg_gain = round(((avg_after - avg_before) / max(1.0, avg_before)) * 100, 1)

        creds = settings.get_llm_credentials()
        changed = any((e.delta or 0) > 0 for e in updated_evals)
        return {
            "status": "updated" if changed else "unchanged",
            "message": (
                "The patch states a new fact for at least one question."
                if changed
                else "The patch does not change these answers. Scores were not raised."
            ),
            "domain": run.report.domain,
            "commercial_evaluations": [e.model_dump() for e in updated_evals],
            "avg_before_score": avg_before,
            "avg_after_score": avg_after,
            "total_citation_gain_pct": avg_gain,
            "is_live": True,
            "model_used": creds.get("model_reasoning") or creds.get("model_fast"),
            "provider_used": settings.get_active_provider()
        }

    except Exception as exc:
        return {
            "status": "error",
            "message": f"Live model re-query failed: {str(exc)}",
            "domain": run.report.domain,
            "commercial_evaluations": [e.model_dump() for e in current_evals],
            "avg_before_score": round(sum(e.before_score for e in current_evals) / max(1, len(current_evals)), 1) if current_evals else None,
            "avg_after_score": None,
            "total_citation_gain_pct": None,
            "is_live": False
        }


@router.post("/{analysis_id}/competitor-bakeoff", response_model=CompetitorBakeoffResult)
async def run_competitor_bakeoff(
    analysis_id: str,
    req: CompetitorBakeoffRequest,
    user: UserIdentity = Depends(get_current_user)
):
    """
    Runs the 1-Competitor Bake-off across the 6 Commercial Questions.
    Compares who ChatGPT/Perplexity can answer for: Target vs Rival.
    """
    run = _get_org_run(analysis_id, user)
    if not run.report:
        raise HTTPException(status_code=404, detail="Analysis report not ready yet.")
    _require_bakeoff_entitlement(user)

    bakeoff_result = await orchestrator.bakeoff_engine.execute_bakeoff(
        target_profile=run.report.business_profile,
        target_evals=run.report.commercial_evaluations or [],
        competitor_url=req.competitor_url
    )
    
    run.report.competitor_bakeoff = bakeoff_result
    return bakeoff_result

@router.get("/{analysis_id}/whatsapp-summary")
async def get_whatsapp_summary(analysis_id: str, user: UserIdentity = Depends(get_current_user)):
    """Returns formatted plain text for WhatsApp sharing plus direct wa.me link."""
    run = _get_org_run(analysis_id, user)
    if not run.report:
        raise HTTPException(status_code=404, detail="Analysis report not ready yet.")
    
    summary = run.report.whatsapp_summary or generate_whatsapp_summary(
        domain=run.report.domain,
        honest_scores=run.report.honest_scores or run.report.scores,
        what_to_ignore=run.report.consultant_advice_what_to_ignore,
        top_bottleneck=run.report.primary_strategic_opportunity,
        top_actions=[r.title for r in (run.report.roadmap_7_days or [])[:3]],
        report_url=run.report.website_url
    )
    
    encoded_text = quote(summary)
    return {
        "domain": run.report.domain,
        "summary_text": summary,
        "whatsapp_url": f"https://wa.me/?text={encoded_text}"
    }

@router.get("/{analysis_id}/evidence-graph")
async def get_evidence_graph(analysis_id: str, user: UserIdentity = Depends(get_current_user)):
    """
    Returns the cryptographic Evidence Graph 2.0 structure with SHA-256 hashes,
    DOM selectors, and relational provenance edges.
    """
    run = _get_org_run(analysis_id, user)
    if not run.report or not run.report.evidence_graph:
        raise HTTPException(status_code=404, detail="Evidence Graph not ready yet.")
    return run.report.evidence_graph


@router.get("/{analysis_id}/evidence-explorer")
async def get_evidence_explorer(analysis_id: str, user: UserIdentity = Depends(get_current_user)):
    """
    Enterprise Evidence Explorer: Returns deep end-to-end provenance traces connecting
    every Finding -> Claim -> Evidence Item -> Selector -> Snapshot -> Captured Timestamp.
    """
    _get_org_run(analysis_id, user)
    from app.db.repository import get_audit_repository
    repo = get_audit_repository()
    traces = repo.get_evidence_trace(analysis_id)
    return {
        "analysis_id": analysis_id,
        "total_traces": len(traces),
        "traces": [t.model_dump() for t in traces]
    }


@router.get("/{analysis_id}/score-explanation")
async def get_score_explanation(analysis_id: str, user: UserIdentity = Depends(get_current_user)):
    """
    Score Explainability ('Why this score?'): Decomposes overall index into
    exact contributing dimensions, specific evidence tokens, and deduction reasons.
    """
    _get_org_run(analysis_id, user)
    from app.db.repository import get_audit_repository
    repo = get_audit_repository()
    expl = repo.get_score_explanation(analysis_id)
    if not expl:
        raise HTTPException(status_code=404, detail=f"Score explanation for audit '{analysis_id}' not found.")
    return expl.model_dump()


@router.get("/{analysis_id}/checkpoints")
async def get_analysis_checkpoints(analysis_id: str, user: UserIdentity = Depends(get_current_user)):
    """
    Returns all durable stage checkpoints for the analysis run.
    """
    _get_org_run(analysis_id, user)
    from app.db.repository import get_audit_repository
    repo = get_audit_repository()
    checkpoints = repo.get_all_checkpoints(analysis_id)
    return {
        "analysis_id": analysis_id,
        "checkpoints_count": len(checkpoints),
        "checkpoints": [c.model_dump() for c in checkpoints]
    }


@router.get("/{analysis_id}/graph")
async def get_analysis_graph(analysis_id: str, user: UserIdentity = Depends(get_current_user)):
    """
    Returns the full DAG execution topology, node statuses, dependency prerequisites,
    and recent activity events for the analysis.
    """
    _get_org_run(analysis_id, user)
    return orchestrator.get_pipeline_graph(analysis_id)


@router.post("/{analysis_id}/pause")
async def pause_analysis(analysis_id: str, user: UserIdentity = Depends(require_permission("mission:create"))):
    """
    Cooperatively pauses a running analysis run.
    """
    _get_org_run(analysis_id, user)
    success = orchestrator.pause_analysis_pipeline(analysis_id)
    return {"status": "paused" if success else "failed", "analysis_id": analysis_id}


@router.post("/{analysis_id}/resume")
async def resume_analysis(analysis_id: str, user: UserIdentity = Depends(require_permission("mission:create"))):
    """
    Resumes an interrupted or failed analysis run from its latest stage checkpoint.
    """
    run = _get_org_run(analysis_id, user)
    success = await orchestrator.resume_analysis_pipeline(analysis_id)
    if not success:
        raise HTTPException(status_code=400, detail=f"Analysis '{analysis_id}' could not be resumed.")
    return {"status": "resumed", "analysis_id": analysis_id}


@router.post("/{analysis_id}/nodes/{node_id}/run")
async def run_single_graph_node(analysis_id: str, node_id: str, user: UserIdentity = Depends(require_permission("mission:create"))):
    """
    Executes an individual sub-section or agent node separately, provided its upstream dependencies are met.
    """
    _get_org_run(analysis_id, user)
    res = await orchestrator.run_pipeline_node(analysis_id, node_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", f"Node '{node_id}' could not be executed."))
    return res


@router.post("/{analysis_id}/sections/{section_id}/run")
async def run_pipeline_section_endpoint(analysis_id: str, section_id: str, user: UserIdentity = Depends(require_permission("mission:create"))):
    """
    Executes all DAG nodes belonging to an entire phase / section sequentially.
    """
    _get_org_run(analysis_id, user)
    res = await orchestrator.run_pipeline_section(analysis_id, section_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", f"Section '{section_id}' execution failed."))
    return res


@router.post("/{analysis_id}/pillars/{pillar_key}/run")
async def run_pipeline_pillar_endpoint(analysis_id: str, pillar_key: str, user: UserIdentity = Depends(require_permission("mission:create"))):
    """
    Executes all DAG nodes belonging to a specific pillar (SEO, GEO, AEO, CRO) on demand.
    """
    _get_org_run(analysis_id, user)
    from app.orchestration.pipeline_dag import PILLAR_TO_SECTION
    section_id = PILLAR_TO_SECTION.get(pillar_key.lower())
    if not section_id:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid pillar '{pillar_key}'. Valid pillars are: {', '.join(PILLAR_TO_SECTION.keys())}"
        )
    res = await orchestrator.run_pipeline_section(analysis_id, section_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", f"Pillar '{pillar_key}' execution failed."))
    return res


@router.get("/{analysis_id}/agent-workforce")
async def get_agent_workforce_state(analysis_id: str, user: UserIdentity = Depends(get_current_user)):
    """
    Returns live execution status, claims produced, and observations across all 50 specialist agents.
    """
    run = _get_org_run(analysis_id, user)
    blackboard = orchestrator.blackboards.get(analysis_id)
    agent_results = (blackboard.blackboard_state.get("agent_results") if blackboard else {}) or {}
    
    from app.orchestration.runtime.registry import SPECIALIST_AGENTS_V3
    workforce = []
    for agent_id, defn in SPECIALIST_AGENTS_V3.items():
        res = agent_results.get(agent_id) or {}
        workforce.append({
            "agent_id": agent_id,
            "agent_name": defn.agent_name,
            "domain": defn.domain,
            "description": defn.description,
            "status": res.get("status") or ("completed" if run.status == "completed" else "pending"),
            "mode": res.get("mode") or ("DETERMINISTIC" if "deterministic" in defn.allowed_models else "HYBRID"),
            "claims_count": len(res.get("claims") or []),
            "claims": res.get("claims") or [],
            "observations": res.get("observations") or {},
            "unavailable_reason": res.get("unavailable_reason"),
        })
    return {
        "analysis_id": analysis_id,
        "total_agents": len(SPECIALIST_AGENTS_V3),
        "agents": workforce,
    }


@router.get("/{analysis_id}/visual_intelligence")
async def get_visual_intelligence(analysis_id: str, user: UserIdentity = Depends(get_current_user)):
    """
    Returns the AI-adaptive visual intelligence payload (tailored charts, graphs, and spotlight numbers).
    If not yet generated, dynamically evaluates the report context and synthesizes it on-the-fly.
    """
    run = _get_org_run(analysis_id, user)
    if not run.report:
        raise HTTPException(status_code=400, detail="Audit report is still processing or unavailable.")

    if run.report.visual_intelligence:
        return run.report.visual_intelligence

    from app.core.monitoring.visual_intelligence import visual_intelligence_engine
    visual_intel = visual_intelligence_engine.synthesize_visual_intelligence(
        domain=run.report.domain,
        business_profile=run.report.business_profile,
        scores=run.report.scores,
        honest_scores=run.report.honest_scores,
        manifest=run.report.crawl_manifest,
        findings=run.report.findings,
        ai_search_matrix=run.report.ai_search_matrix,
        commercial_evaluations=run.report.commercial_evaluations,
        geo_readiness=run.report.geo_readiness,
        competitor_bakeoff=run.report.competitor_bakeoff,
    )
    run.report.visual_intelligence = visual_intel
    return visual_intel



