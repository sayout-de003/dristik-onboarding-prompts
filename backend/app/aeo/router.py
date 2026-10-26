"""
Dristik Modular Monolith: AEO HTTP API Router.

Endpoints for:
1. Complete 55-Section AEO Master Audit Report (HTML & JSON).
2. 5 Certified AEO CSV Export Deliverables (Remediation, Questions, Benchmarks, Facts, Evidence).
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response

from app.identity.access import require_analysis
from app.identity.authorizer import UserIdentity
from app.identity.deps import get_current_user
from app.aeo.scoring import AeoMetricsCalculator
from app.aeo.analytics_history import aeo_analytics_history_store
from app.aeo.reporting import (
    aeo_report_generator,
    generate_aeo_remediation_csv,
    generate_aeo_question_dataset_csv,
    generate_aeo_live_benchmark_csv,
    generate_aeo_brand_facts_csv,
    generate_aeo_evidence_ledger_csv,
)

router = APIRouter(prefix="/reports", tags=["AEO Intelligence"])


@router.get("/{analysis_id}/aeo-report")
async def get_complete_aeo_report(
    analysis_id: str,
    format: str = "html",
    user: UserIdentity = Depends(get_current_user),
):
    """
    Renders the dedicated, complete 55-Section AEO Master Audit Report.
    format='html': modern responsive standalone HTML report.
    format='json': structured 55-section JSON payload.
    format='print' / 'pdf': printable adaptive book.
    """
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    if format.lower() == "json":
        return aeo_report_generator.render_json_report(report)

    if format.lower() in ("print", "print_html"):
        from app.reports.adaptive_audit_book import render_adaptive_audit_book_html
        return Response(content=render_adaptive_audit_book_html(report, report_type="AEO"), media_type="text/html")

    if format.lower() == "pdf":
        from app.reports.adaptive_audit_book import render_adaptive_audit_book_pdf
        pdf_bytes, qa = await render_adaptive_audit_book_pdf(report, report_type="AEO")
        if not pdf_bytes:
            raise HTTPException(status_code=503, detail="PDF rendering engine is currently unavailable.")
        domain_clean = (report.domain or "website").replace("https://", "").replace("http://", "").split("/")[0]
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{domain_clean}_aeo_audit_book.pdf"'},
        )

    html_content = aeo_report_generator.render_html_report(report)
    return Response(content=html_content, media_type="text/html")


@router.get("/{analysis_id}/aeo-analytics")
async def get_aeo_analytics(analysis_id: str, user: UserIdentity = Depends(get_current_user)):
    """Return evidence-state-aware AEO metrics for the selected analysis."""
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="AEO analytics are unavailable until the analysis report has been synthesized.")
    scorecard = AeoMetricsCalculator.calculate(report)
    payload = scorecard.to_dict()
    payload["analysis_id"] = analysis_id
    payload["domain"] = getattr(report, "domain", None)
    payload["measurement_policy"] = {
        "version": "aeo-four-pillars-v1",
        "missing_values": "remain null with an explicit evidence state",
        "unified_total_score": None,
        "unified_total_score_reason": "Content readiness, technical eligibility, observed answer visibility and business outcomes are independent measurements and must not be conflated.",
    }
    return payload


@router.get("/{analysis_id}/aeo-analytics/history")
async def get_aeo_analytics_history(
    analysis_id: str,
    limit: int = 100,
    user: UserIdentity = Depends(get_current_user),
):
    """Return historical AEO pillar scorecards for completed audits of the same domain."""
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="AEO analytics history requires a synthesized report.")
    domain = getattr(report, "domain", None) or getattr(run, "website_url", None)
    history = aeo_analytics_history_store.get_domain_history(domain or "", limit=limit)
    return {
        "analysis_id": analysis_id,
        "domain": domain,
        "total_snapshots": len(history),
        "history": history,
        "policy": "Only completed audits with persisted scorecards are included; historical data is not backfilled from estimates.",
    }


@router.get("/{analysis_id}/export/aeo-remediation-tracker.csv")
async def export_aeo_remediation_tracker_csv(
    analysis_id: str,
    user: UserIdentity = Depends(get_current_user),
):
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    csv_data = generate_aeo_remediation_csv(report)
    domain_clean = (report.domain or "website").replace("https://", "").replace("http://", "").split("/")[0]
    filename = f"{domain_clean}_aeo_remediation_tracker.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{analysis_id}/export/aeo-question-dataset.csv")
async def export_aeo_question_dataset_csv(
    analysis_id: str,
    user: UserIdentity = Depends(get_current_user),
):
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    csv_data = generate_aeo_question_dataset_csv(report)
    domain_clean = (report.domain or "website").replace("https://", "").replace("http://", "").split("/")[0]
    filename = f"{domain_clean}_aeo_question_dataset.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{analysis_id}/export/aeo-live-benchmark.csv")
async def export_aeo_live_benchmark_csv(
    analysis_id: str,
    user: UserIdentity = Depends(get_current_user),
):
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    csv_data = generate_aeo_live_benchmark_csv(report)
    domain_clean = (report.domain or "website").replace("https://", "").replace("http://", "").split("/")[0]
    filename = f"{domain_clean}_aeo_live_benchmark.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{analysis_id}/export/aeo-brand-facts.csv")
async def export_aeo_brand_facts_csv(
    analysis_id: str,
    user: UserIdentity = Depends(get_current_user),
):
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    csv_data = generate_aeo_brand_facts_csv(report)
    domain_clean = (report.domain or "website").replace("https://", "").replace("http://", "").split("/")[0]
    filename = f"{domain_clean}_aeo_brand_facts.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{analysis_id}/export/aeo-evidence-ledger.csv")
async def export_aeo_evidence_ledger_csv(
    analysis_id: str,
    user: UserIdentity = Depends(get_current_user),
):
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    csv_data = generate_aeo_evidence_ledger_csv(report)
    domain_clean = (report.domain or "website").replace("https://", "").replace("http://", "").split("/")[0]
    filename = f"{domain_clean}_aeo_evidence_ledger.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
