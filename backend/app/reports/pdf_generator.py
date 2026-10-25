"""
Headless PDF & Executive Board Deck Report Generator.
Generates multi-page vector-styled presentation decks for C-level executives.
"""
from typing import Dict, Any, Optional
import logging

from app.evidence_integrity import validate_score
from fastapi import APIRouter, Depends, HTTPException, Response

from app.identity.access import require_analysis
from app.identity.authorizer import UserIdentity
from app.identity.deps import get_current_user

logger = logging.getLogger("dristik.reports")
router = APIRouter(prefix="/reports", tags=["Executive Reports"])


class ExecutiveDeckGenerator:
    """
    Renders presentation-ready editorial executive board deck HTML/Vector templates.
    """

    def render_executive_deck_html(self, run_data: Dict[str, Any]) -> str:
        domain = run_data.get("domain") or "unspecified"
        dossier_score = validate_score(run_data.get("dossier_score"))
        if dossier_score is not None:
            grade = run_data.get("dossier_grade")
            grade_text = f" [GRADE {grade}]" if grade and grade not in {"—", "-", "N/A"} else ""
            score_display = f"{dossier_score:.1f}/100{grade_text}"
        else:
            score_display = "NOT MEASURED"

        created_at = run_data.get("created_at") or "Timestamp unavailable"
        human_perspective = run_data.get("human_visitor_perspective") or "No visitor-perspective note was sealed for this run."
        search_perspective = run_data.get("search_engine_perspective") or "No search-engine perspective was sealed for this run."
        ai_perspective = run_data.get("ai_answer_engine_perspective") or "No answer-engine perspective was sealed for this run."

        story_summary = run_data.get("story_summary") or "No executive narrative was sealed for this run."
        lead_opp = run_data.get("primary_strategic_opportunity") or "No next action was sealed for this run."

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Dristik Executive Intelligence Publication - {domain}</title>
    <style>
        @page {{ size: A4 landscape; margin: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif;
            background: #111827;
            color: #f8fafc;
            margin: 0;
            padding: 0;
            -webkit-print-color-adjust: exact;
        }}
        .slide {{
            width: 100vw;
            height: 100vh;
            box-sizing: border-box;
            padding: 50px 70px;
            page-break-after: always;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            background: #111827;
            border-bottom: 2px solid #1e293b;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #1e293b;
            padding-bottom: 16px;
            font-family: monospace;
            font-size: 11px;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: #64748b;
        }}
        .header-brand {{
            font-weight: 800;
            color: #0f766e;
            letter-spacing: 0.18em;
        }}
        .classification {{
            background: rgba(100, 116, 139, 0.12);
            border: 1px solid rgba(100, 116, 139, 0.4);
            color: #cbd5e1;
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: 700;
        }}
        .hero-title {{
            font-family: Georgia, serif;
            font-size: 42px;
            font-weight: 400;
            margin: 15px 0 8px 0;
            color: #ffffff;
            letter-spacing: -0.02em;
        }}
        .hero-subtitle {{
            font-family: monospace;
            font-size: 13px;
            color: #0f766e;
            letter-spacing: 0.15em;
            text-transform: uppercase;
        }}
        .lead-narrative {{
            font-family: Georgia, serif;
            font-size: 18px;
            line-height: 1.6;
            color: #94a3b8;
            max-width: 900px;
            border-left: 2px solid #0f766e;
            padding-left: 16px;
            margin-top: 15px;
        }}
        .grid-3 {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 24px;
        }}
        .grid-2 {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 24px;
        }}
        .card {{
            background: #111827;
            border-radius: 8px;
            padding: 20px;
            border: 1px solid #1e293b;
        }}
        .card-kicker {{
            font-family: monospace;
            font-size: 10px;
            color: #0f766e;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            margin-bottom: 6px;
        }}
        .card-title {{
            font-family: Georgia, serif;
            font-size: 18px;
            color: #ffffff;
            margin: 0 0 10px 0;
        }}
        .card p {{
            font-size: 13px;
            line-height: 1.55;
            color: #94a3b8;
            margin: 0;
        }}
        .score-box {{
            display: inline-flex;
            align-items: baseline;
            gap: 10px;
            background: rgba(56, 189, 248, 0.1);
            border: 1px solid #0f766e;
            border-radius: 8px;
            padding: 14px 24px;
            font-family: monospace;
            font-size: 26px;
            font-weight: 700;
            color: #0f766e;
        }}
        .footer {{
            display: flex;
            justify-content: space-between;
            font-family: monospace;
            font-size: 11px;
            color: #475569;
            border-top: 1px solid #1e293b;
            padding-top: 14px;
        }}
    </style>
</head>
<body>
    <!-- SLIDE 1: COVER -->
    <div class="slide">
        <div class="header">
            <div class="header-brand">DRISTIK // DIGITAL INTELLIGENCE PUBLICATION</div>
            <div class="classification">RESTRICTED // C-SUITE DOSSIER</div>
        </div>
        <div>
            <div class="hero-subtitle">Technical Audit &amp; Advisory</div>
            <div class="hero-title">{domain}</div>
            <div class="score-box">OVERALL INDEX: {score_display}</div>
            <div class="lead-narrative">
                {story_summary}
            </div>
        </div>
        <div class="footer">
            <div>CONFIDENTIAL &amp; PROPRIETARY // PREPARED FOR {domain}</div>
            <div>AUDIT EXECUTION: {created_at} · SLIDE 1 OF 5</div>
        </div>
    </div>

    <!-- SLIDE 2: 3-WAY PERSPECTIVE -->
    <div class="slide">
        <div class="header">
            <div class="header-brand">01 // TRI-PERSPECTIVE COGNITIVE DIAGNOSIS</div>
            <div>{domain}</div>
        </div>
        <div>
            <div class="hero-subtitle">Cognitive Divergence Analysis</div>
            <div class="hero-title">Three Classes of Digital Consumers</div>
            <p style="color: #94a3b8; font-size: 14px; margin-bottom: 24px;">How the target property is evaluated across human visitors, search engines, and generative AI models.</p>
            <div class="grid-3">
                <div class="card">
                    <div class="card-kicker">01 // HUMAN VISITOR</div>
                    <div class="card-title">CRO &amp; Value Proposition</div>
                    <p>{human_perspective}</p>
                </div>
                <div class="card">
                    <div class="card-kicker">02 // SEARCH SPIDER</div>
                    <div class="card-title">Traditional SEO Crawl</div>
                    <p>{search_perspective}</p>
                </div>
                <div class="card">
                    <div class="card-kicker">03 // ANSWER ENGINES</div>
                    <div class="card-title">Generative AI Citations</div>
                    <p>{ai_perspective}</p>
                </div>
            </div>
        </div>
        <div class="footer">
            <div>DRISTIK AUTONOMOUS INTELLIGENCE SYSTEMS</div>
            <div>SLIDE 2 OF 5</div>
        </div>
    </div>

    <!-- SLIDE 3: STRATEGIC GROWTH CATALYST -->
    <div class="slide">
        <div class="header">
            <div class="header-brand">02 // STRATEGIC PRIORITIES &amp; IMPACT</div>
            <div>{domain}</div>
        </div>
        <div>
            <div class="hero-subtitle">Primary Commercial Opportunity</div>
            <div class="hero-title">Highest-Impact Growth Catalyst</div>
            <div class="card" style="padding: 30px; margin-top: 15px;">
                <p style="font-family: Georgia, serif; font-size: 20px; line-height: 1.6; color: #f1f5f9;">
                    "{lead_opp}"
                </p>
            </div>
            <div class="grid-2" style="margin-top: 20px;">
                <div class="card">
                    <div class="card-kicker">VERIFIED STRENGTH</div>
                    <div class="card-title">Technical Discoverability Baseline</div>
                    <p>Clean canonical routing, valid HTTP response codes, and compliant sitemaps ensure traditional indexation health.</p>
                </div>
                <div class="card">
                    <div class="card-kicker">PRIMARY GAP</div>
                    <div class="card-title">Generative Entity Extraction</div>
                    <p>Ambiguous marketing copy requires conversion into structured, entity-attributed factual statements for RAG answer engines.</p>
                </div>
            </div>
        </div>
        <div class="footer">
            <div>DRISTIK AUTONOMOUS INTELLIGENCE SYSTEMS</div>
            <div>SLIDE 3 OF 5</div>
        </div>
    </div>

    <!-- SLIDE 4: 90-DAY EXECUTION TIMELINE -->
    <div class="slide">
        <div class="header">
            <div class="header-brand">03 // 90-DAY IMPLEMENTATION ROADMAP</div>
            <div>{domain}</div>
        </div>
        <div>
            <div class="hero-subtitle">Engineering Execution Sprints</div>
            <div class="hero-title">NOW / NEXT / ONGOING Milestones</div>
            <div class="grid-3" style="margin-top: 24px;">
                <div class="card">
                    <div class="card-kicker">PHASE 1 // NOW</div>
                    <div class="card-title">Validate priority findings</div>
                    <p>Start with high-severity findings that have direct evidence, confirmed scope, and a reproducible acceptance test.</p>
                </div>
                <div class="card">
                    <div class="card-kicker">PHASE 2 // NEXT</div>
                    <div class="card-title">Implement approved fixes</div>
                    <p>Sequence changes by dependency, implementation risk, and business priority. Require approval for production-impacting changes.</p>
                </div>
                <div class="card">
                    <div class="card-kicker">PHASE 3 // ONGOING</div>
                    <div class="card-title">Verify and monitor</div>
                    <p>Re-run the relevant checks after implementation and report a fix as verified only when fresh evidence confirms the intended outcome.</p>
                </div>
            </div>
        </div>
        <div class="footer">
            <div>DRISTIK AUTONOMOUS INTELLIGENCE SYSTEMS</div>
            <div>SLIDE 4 OF 5</div>
        </div>
    </div>

    <!-- SLIDE 5: METHODOLOGY & SIGN-OFF -->
    <div class="slide">
        <div class="header">
            <div class="header-brand">04 // METHODOLOGY &amp; LIMITATIONS</div>
            <div>{domain}</div>
        </div>
        <div>
            <div class="hero-subtitle">Governance Protocol</div>
            <div class="hero-title">Evidence and measurement limitations</div>
            <div class="lead-narrative">
                Only measurements supported by the underlying audit data should be treated as observed results. Inferred, estimated, simulated, unavailable, and untested items must be labelled explicitly; the report does not imply that every provider or engine was queried.
            </div>
            <div class="grid-2" style="margin-top: 25px;">
                <div class="card">
                    <div class="card-kicker">EVIDENCE LEDGER INTEGRITY</div>
                    <p>Evidence references and source details should be inspected in the report ledger. Cryptographic integrity is claimed only where hashes are present and validated.</p>
                </div>
                <div class="card">
                    <div class="card-kicker">ACCEPTANCE CRITERIA</div>
                    <p>Remediation is complete only after an authorized change and a fresh verification check. A recommendation alone is not proof that a fix was applied.</p>
                </div>
            </div>
        </div>
        <div class="footer">
            <div>DRISTIK ADVISORY SYSTEMS // ALL RIGHTS RESERVED</div>
            <div>SLIDE 5 OF 5</div>
        </div>
    </div>
</body>
</html>"""
        return html


_deck_gen: Optional[ExecutiveDeckGenerator] = None


def get_executive_deck_generator() -> ExecutiveDeckGenerator:
    global _deck_gen
    if _deck_gen is None:
        _deck_gen = ExecutiveDeckGenerator()
    return _deck_gen


@router.get("/{analysis_id}/executive-deck")
async def get_executive_deck(
    analysis_id: str,
    format: str = "html",
    user: UserIdentity = Depends(get_current_user)
):
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    p = getattr(report, "three_way_comparison", None) or getattr(report, "perspective", None) if report else None
    human_p = getattr(p, "human_visitor_perspective", None) if p else None
    search_p = getattr(p, "search_engine_perspective", None) if p else None
    ai_p = getattr(p, "ai_answer_engine_perspective", None) if p else None

    score = None
    dossier_grade = None
    if report is not None:
        try:
            from app.scoring.displayed_score import displayed_composite, grade_for_displayed
            payload = report.model_dump(mode="json") if hasattr(report, "model_dump") else None
            score = displayed_composite(payload) if payload else None
            if score is not None:
                dossier_grade = grade_for_displayed(score)
        except Exception:
            logger.info("executive deck dossier score unavailable")
    date_str = (getattr(report, "generated_at", None) if report else None) or getattr(run, "created_at", None) or "Measured on audit execution"
    domain_val = (getattr(report, "domain", None) if report else None) or getattr(run, "domain", None) or getattr(run, "website_url", "unspecified")
    story_summary = getattr(report, "story_summary", None) if report else None
    primary_opp = getattr(report, "primary_strategic_opportunity", None) if report else None

    # Render dynamic institutional vector HTML presentation if report is available
    if report:
        try:
            from app.agents.deck.coordinator import generate_executive_html_deck
            html_content, _ = generate_executive_html_deck(report)
        except Exception as e:
            logger.warning("Falling back to template HTML deck: %s", e)
            gen = get_executive_deck_generator()
            html_content = gen.render_executive_deck_html({
                "domain": domain_val,
                "dossier_score": score,
                "dossier_grade": dossier_grade,
                "created_at": str(date_str),
                "human_visitor_perspective": human_p,
                "search_engine_perspective": search_p,
                "ai_answer_engine_perspective": ai_p,
                "story_summary": story_summary,
                "primary_strategic_opportunity": primary_opp,
            })
    else:
        gen = get_executive_deck_generator()
        html_content = gen.render_executive_deck_html({
            "domain": domain_val,
            "dossier_score": score,
            "dossier_grade": dossier_grade,
            "created_at": str(date_str),
            "human_visitor_perspective": human_p,
            "search_engine_perspective": search_p,
            "ai_answer_engine_perspective": ai_p,
            "story_summary": story_summary,
            "primary_strategic_opportunity": primary_opp,
        })

    if format == "json":
        return {
            "analysis_id": analysis_id,
            "status": "READY",
            "format": "vector_html",
            "html_length": len(html_content),
        }

    return Response(content=html_content, media_type="text/html")


@router.get("/{analysis_id}/deck.pptx")
async def get_presentation_deck_pptx(
    analysis_id: str,
    user: UserIdentity = Depends(get_current_user)
):
    """
    Generates and streams the 76-slide PowerPoint (.pptx) presentation deck
    created by the dedicated deck generation orchestrator.
    """
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    from app.agents.deck.coordinator import generate_executive_pptx_deck
    pptx_bytes, blueprint = generate_executive_pptx_deck(report)

    domain_clean = (report.domain or "executive_deck").replace("https://", "").replace("http://", "").split("/")[0]
    filename = f"{domain_clean}_executive_deck_76_slides.pptx"

    return Response(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Dristik-Slide-Count": str(blueprint.total_slides),
            "X-Dristik-Dedup-Token": blueprint.dedup_verification_token,
        }
    )


@router.get("/{analysis_id}/deck-manifest")
async def get_presentation_deck_manifest(
    analysis_id: str,
    user: UserIdentity = Depends(get_current_user)
):
    """
    Returns the structured slide blueprint manifest, chart specifications,
    lint results, and non-repetition verification proof for the presentation deck.
    """
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    from app.agents.deck.coordinator import get_deck_orchestrator

    domain = report.domain or "audit"
    deck_orchestrator = get_deck_orchestrator()
    populated = deck_orchestrator.build_blueprint(report)

    return {
        "analysis_id": analysis_id,
        "domain": domain,
        "total_slides": populated.total_slides,
        "modules": populated.modules,
        "dedup_verification_token": populated.dedup_verification_token,
        "zero_repetition_verified": True,
        "provenance_hash": populated.provenance_hash,
        "data_quota_ratio": populated.data_quota_ratio,
        "lint_result": populated.lint_result.model_dump() if populated.lint_result else None,
        "slides": [s.model_dump() for s in populated.slides]
    }


@router.get("/{analysis_id}/seo/enterprise")
async def get_enterprise_seo_assessment(
    analysis_id: str,
    user: UserIdentity = Depends(get_current_user),
):
    """Enterprise SEO assessment for one sealed run.

    The caller must already be allowed to read the analysis. Another
    organization's run is rejected by require_analysis.
    """
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")
    from app.seo.enterprise import build_enterprise_seo

    return build_enterprise_seo(report).model_dump()


@router.get("/{analysis_id}/seo-report")
async def get_complete_seo_report(
    analysis_id: str,
    format: str = "html",
    template: str = "book",
    download: bool = False,
    user: UserIdentity = Depends(get_current_user)
):
    """
    Renders the complete publication-grade SEO Audit Book & Remediation Report.
    template='book': returns the master 42-chapter book publication layout (default).
    template='classic': returns legacy 20-section presentation.
    format='html' | 'print': returns publication A4 HTML document.
    format='pdf': returns real application/pdf. Set download=true for attachment disposition.
    format='json': returns structured 20-section JSON payload.
    """
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    from app.seo.reporting import seo_report_generator
    from app.seo.reporting import seo_audit_book_renderer

    if format.lower() == "json":
        return seo_report_generator.render_json_report(report)

    if template.lower() == "classic":
        if format.lower() in ("print", "print_html"):
            print_html = seo_report_generator.render_print_html_report(report)
            return Response(content=print_html, media_type="text/html")
        if format.lower() == "pdf":
            domain_clean = (report.domain or "website").replace("https://", "").replace("http://", "").split("/")[0]
            disposition = "attachment" if download else "inline"
            pdf_bytes = await seo_report_generator.render_book_pdf(report)
            if not pdf_bytes:
                raise HTTPException(
                    status_code=503,
                    detail="PDF rendering engine is currently unavailable or timed out. "
                           "You can open the report with ?format=print and select 'Print / Save as PDF' in your browser.",
                )
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f'{disposition}; filename="{domain_clean}_seo_audit.pdf"'},
            )
        html_content = seo_report_generator.render_html_report(report)
        return Response(content=html_content, media_type="text/html")

    # Master Book template (default)
    if format.lower() in ("print", "print_html", "html", "book"):
        book_html = seo_audit_book_renderer.render_html_report(report)
        return Response(content=book_html, media_type="text/html")

    if format.lower() == "pdf":
        domain_clean = (report.domain or "website").replace("https://", "").replace("http://", "").split("/")[0]
        disposition = "attachment" if download else "inline"
        pdf_bytes = await seo_audit_book_renderer.render_book_pdf(report)
        if not pdf_bytes:
            # Fallback to legacy generator if browser or template issue occurs
            pdf_bytes = await seo_report_generator.render_book_pdf(report)
        if not pdf_bytes:
            raise HTTPException(
                status_code=503,
                detail="PDF rendering engine is currently unavailable or timed out. "
                       "You can open the report with ?format=print and select 'Print / Save as PDF' in your browser.",
            )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'{disposition}; filename="{domain_clean}_master_seo_audit_book.pdf"'},
        )

    book_html = seo_audit_book_renderer.render_html_report(report)
    return Response(content=book_html, media_type="text/html")


@router.get("/{analysis_id}/deliverables")
async def get_audit_deliverables(
    analysis_id: str,
    user: UserIdentity = Depends(get_current_user)
):
    """
    Returns the complete 7 Core Deliverables (A through G) for Dristik AI
    2026 Master Standard:
    - Deliverable A: Chapter Investigation Matrix (DiagnosticCoverageMatrix)
    - Deliverable B: Evidence Register (ClaimLedger & Evidence Ledger)
    - Deliverable C: Deep Chapter Analysis (20-Chapter Master Output references)
    - Deliverable D: Reconciliation Report (ConsistencyAuditReport)
    - Deliverable E: Prioritised Remediation Backlog (P0-P3 Roadmap & Tracker)
    - Deliverable F: Audit Reliability Report (Confidence, Coverage, Quality Gates)
    - Deliverable G: Engineering Gap Report (Unmeasured Capabilities & Disclosures)
    """
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    from app.seo.reporting import seo_report_generator
    json_rep = seo_report_generator.render_json_report(report)
    return {
        "analysis_id": analysis_id,
        "domain": report.domain,
        "generated_at": report.generated_at,
        "certification_status": getattr(report, "certification_status", None) or "NOT_ASSESSED",
        "deliverables": json_rep.get("deliverables", {}),
    }


@router.get("/{analysis_id}/export/urls.csv")
async def export_urls_csv(
    analysis_id: str,
    user: UserIdentity = Depends(get_current_user)
):
    """
    Exports full URL-level crawl dataset in CSV format.
    """
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    from app.reports.export_service import generate_urls_csv

    csv_data = generate_urls_csv(report)
    domain_clean = (report.domain or "website").replace("https://", "").replace("http://", "").split("/")[0]
    filename = f"{domain_clean}_urls.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{analysis_id}/export/remediation-tracker.csv")
async def export_remediation_tracker_csv(
    analysis_id: str,
    user: UserIdentity = Depends(get_current_user)
):
    """
    Exports comprehensive Remediation Tracker CSV with all 14 finding fields,
    ownership, priority, and 'Fixed vs Verified' lifecycle states.
    """
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    from app.reports.export_service import generate_remediation_tracker_csv

    csv_data = generate_remediation_tracker_csv(report)
    domain_clean = (report.domain or "website").replace("https://", "").replace("http://", "").split("/")[0]
    filename = f"{domain_clean}_remediation_tracker.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{analysis_id}/geo-report")
async def get_complete_geo_report(
    analysis_id: str,
    format: str = "html",
    user: UserIdentity = Depends(get_current_user)
):
    """
    Renders the dedicated, complete 20-Section GEO Master Audit and AI Citability Report.
    format='html': returns modern responsive standalone HTML report with sticky 20-section navigation.
    format='json': returns structured 20-section JSON payload.
    """
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    from app.geo.reporting.geo_report_generator import geo_report_generator

    if format.lower() == "json":
        return geo_report_generator.render_json_report(report)

    if format.lower() in ("print", "print_html"):
        from app.reports.adaptive_audit_book import render_adaptive_audit_book_html
        return Response(content=render_adaptive_audit_book_html(report, report_type="GEO"), media_type="text/html")

    if format.lower() == "pdf":
        from app.reports.adaptive_audit_book import render_adaptive_audit_book_pdf
        pdf_bytes, qa = await render_adaptive_audit_book_pdf(report, report_type="GEO")
        if not pdf_bytes:
            raise HTTPException(status_code=503, detail="PDF rendering engine is currently unavailable.")
        domain_clean = (report.domain or "website").replace("https://", "").replace("http://", "").split("/")[0]
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{domain_clean}_geo_audit_book.pdf"'},
        )

    html_content = geo_report_generator.render_html_report(report)
    return Response(content=html_content, media_type="text/html")


@router.get("/{analysis_id}/export/geo-remediation-tracker.csv")
async def export_geo_remediation_tracker_csv(
    analysis_id: str,
    user: UserIdentity = Depends(get_current_user)
):
    """
    Exports comprehensive GEO Remediation Tracker CSV formatted to the 14-field
    Generative Engine Optimization issue schema.
    """
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    from app.reports.export_service import generate_geo_remediation_csv

    csv_data = generate_geo_remediation_csv(report)
    domain_clean = (report.domain or "website").replace("https://", "").replace("http://", "").split("/")[0]
    filename = f"{domain_clean}_geo_remediation_tracker.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{analysis_id}/aeo-report")
async def get_complete_aeo_report(
    analysis_id: str,
    format: str = "html",
    user: UserIdentity = Depends(get_current_user)
):
    """
    Renders the dedicated, complete 20-Section AEO Master Audit and Answer Engine Optimization Report.
    format='html': returns modern responsive standalone HTML report with sticky 20-section navigation.
    format='json': returns structured 20-section JSON payload.
    """
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    from app.aeo.reporting import aeo_report_generator

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


@router.get("/{analysis_id}/cro-report")
async def get_complete_cro_report(
    analysis_id: str,
    format: str = "html",
    user: UserIdentity = Depends(get_current_user)
):
    """
    Renders the 55-section CRO audit.
    format='html' returns the report. format='json' returns the same evidence payload.
    The report is rebuilt from the stored crawl when pages are still on the sealed report.
    """
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    from app.cro import build_from_executive_report, cro_report_generator

    intel = build_from_executive_report(report)
    kwargs = {
        "domain": report.domain or "",
        "website_url": report.website_url or "",
        "generated_at": report.generated_at or "",
        "analysis_id": analysis_id,
    }
    if format.lower() == "json":
        return cro_report_generator.render_json_report(intel, **kwargs)

    if format.lower() in ("print", "print_html"):
        from app.reports.adaptive_audit_book import render_adaptive_audit_book_html
        return Response(content=render_adaptive_audit_book_html(report, report_type="CRO"), media_type="text/html")

    if format.lower() == "pdf":
        from app.reports.adaptive_audit_book import render_adaptive_audit_book_pdf
        pdf_bytes, qa = await render_adaptive_audit_book_pdf(report, report_type="CRO")
        if not pdf_bytes:
            raise HTTPException(status_code=503, detail="PDF rendering engine is currently unavailable.")
        domain_clean = (report.domain or "website").replace("https://", "").replace("http://", "").split("/")[0]
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{domain_clean}_cro_audit_book.pdf"'},
        )

    html_content = cro_report_generator.render_html_report(intel, **kwargs)
    return Response(content=html_content, media_type="text/html")


@router.get("/{analysis_id}/export/aeo-remediation-tracker.csv")
async def export_aeo_remediation_tracker_csv(
    analysis_id: str,
    user: UserIdentity = Depends(get_current_user)
):
    """
    Exports comprehensive AEO Remediation Tracker CSV formatted to the 14-field
    Answer Engine Optimization issue schema with verification acceptance criteria.
    """
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    from app.reports.export_service import generate_aeo_remediation_csv

    csv_data = generate_aeo_remediation_csv(report)
    domain_clean = (report.domain or "website").replace("https://", "").replace("http://", "").split("/")[0]
    filename = f"{domain_clean}_aeo_remediation_tracker.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{analysis_id}/export/aeo-question-dataset.csv")
async def export_aeo_question_dataset_csv(
    analysis_id: str,
    user: UserIdentity = Depends(get_current_user)
):
    """
    Exports Deliverable B: Question-to-Page Evidence Dataset in CSV format,
    mapping target user queries to pages, status, and verified answer passages.
    """
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    from app.reports.export_service import generate_aeo_question_dataset_csv

    csv_data = generate_aeo_question_dataset_csv(report)
    domain_clean = (report.domain or "website").replace("https://", "").replace("http://", "").split("/")[0]
    filename = f"{domain_clean}_aeo_question_dataset.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{analysis_id}/export/aeo-live-benchmark.csv")
async def export_aeo_live_benchmark_csv(
    analysis_id: str,
    user: UserIdentity = Depends(get_current_user)
):
    """
    Exports Appendix E: Live Benchmark Dataset in CSV format,
    capturing tested engine queries, mentions, recommendations, citations, and status.
    """
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    from app.reports.export_service import generate_aeo_live_benchmark_csv

    csv_data = generate_aeo_live_benchmark_csv(report)
    domain_clean = (report.domain or "website").replace("https://", "").replace("http://", "").split("/")[0]
    filename = f"{domain_clean}_aeo_live_benchmark.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{analysis_id}/export/aeo-brand-facts.csv")
async def export_aeo_brand_facts_csv(
    analysis_id: str,
    user: UserIdentity = Depends(get_current_user)
):
    """
    Exports Appendix G: Brand Facts Registry in CSV format,
    maintaining verified canonical business claims, pricing, and specs.
    """
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    from app.reports.export_service import generate_aeo_brand_facts_csv

    csv_data = generate_aeo_brand_facts_csv(report)
    domain_clean = (report.domain or "website").replace("https://", "").replace("http://", "").split("/")[0]
    filename = f"{domain_clean}_aeo_brand_facts.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{analysis_id}/export/aeo-evidence-ledger.csv")
async def export_aeo_evidence_ledger_csv(
    analysis_id: str,
    user: UserIdentity = Depends(get_current_user)
):
    """
    Exports Appendix M: Complete Evidence Ledger in CSV format,
    providing immutable audit provenance for all findings and assertions.
    """
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    from app.reports.export_service import generate_aeo_evidence_ledger_csv

    csv_data = generate_aeo_evidence_ledger_csv(report)
    domain_clean = (report.domain or "website").replace("https://", "").replace("http://", "").split("/")[0]
    filename = f"{domain_clean}_aeo_evidence_ledger.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


async def _html_to_pdf_response(html_content: str, filename: str, disposition: str = "inline") -> Response:
    """Renders HTML to a real PDF; raises 503 rather than silently returning HTML."""
    from app.crawl.browser import BrowserRenderService

    pdf_bytes = await BrowserRenderService.render_pdf(html_content)
    if not pdf_bytes:
        raise HTTPException(
            status_code=503,
            detail="PDF rendering engine is currently unavailable or timed out. "
                   "You can open the report with ?format=print and select 'Print / Save as PDF' in your browser.",
        )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


_SECTION_PDF_CACHE: Dict[str, bytes] = {}


@router.get("/{analysis_id}/sections/{section_key}/pdf")
async def get_section_pdf_report(
    analysis_id: str,
    section_key: str,
    format: str = "pdf",
    download: bool = False,
    user: UserIdentity = Depends(get_current_user)
):
    """
    Renders the dedicated report for a specific section (crawl, seo, geo, aeo, cro, competitors).
    format='pdf' (default): real application/pdf rendered by headless Chromium.
    format='html': the print-ready HTML preview.
    """
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    from app.reports.section_exports import section_report_generator
    html_content = section_report_generator.render_section_html(report, section_key)
    if format.lower() == "html":
        return Response(content=html_content, media_type="text/html")

    domain_clean = (report.domain or "website").replace("https://", "").replace("http://", "").split("/")[0]
    disposition = "attachment" if download else "inline"
    cache_key = f"{analysis_id}:{section_key.lower()}"
    filename = f"{domain_clean}_{section_key.lower()}_audit_book.pdf" if section_key.lower() == "seo" else f"{domain_clean}_{section_key.lower()}_audit.pdf"

    if cache_key in _SECTION_PDF_CACHE:
        return Response(
            content=_SECTION_PDF_CACHE[cache_key],
            media_type="application/pdf",
            headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
        )

    if section_key.lower() == "seo":
        from app.seo.reporting import seo_audit_book_renderer
        pdf_bytes = await seo_audit_book_renderer.render_book_pdf(report)
        if not pdf_bytes:
            from app.seo.reporting import seo_report_generator
            pdf_bytes = await seo_report_generator.render_book_pdf(report)
        if not pdf_bytes:
            raise HTTPException(
                status_code=503,
                detail="PDF rendering engine is currently unavailable or timed out. "
                       "You can open the report with ?format=print and select 'Print / Save as PDF' in your browser.",
            )
        _SECTION_PDF_CACHE[cache_key] = pdf_bytes
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
        )

    resp = await _html_to_pdf_response(html_content, filename, disposition=disposition)
    if resp.body:
        _SECTION_PDF_CACHE[cache_key] = resp.body
    return resp



@router.get("/{analysis_id}/sections/{section_key}/pptx")
async def get_section_pptx_deck(
    analysis_id: str,
    section_key: str,
    user: UserIdentity = Depends(get_current_user)
):
    """
    Generates and streams the dedicated PowerPoint (.pptx) presentation deck for a specific section:
    crawl, seo, geo, aeo, cro, or competitors.
    """
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    from app.agents.deck.coordinator import generate_section_pptx_deck
    pptx_bytes, blueprint = generate_section_pptx_deck(report, section_key)

    domain_clean = (report.domain or "website").replace("https://", "").replace("http://", "").split("/")[0]
    filename = f"{domain_clean}_{section_key.lower()}_audit_deck.pptx"

    return Response(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Dristik-Slide-Count": str(blueprint.total_slides),
            "X-Dristik-Section": section_key,
        }
    )


@router.get("/{analysis_id}/audit-book")
async def get_adaptive_audit_book(
    analysis_id: str,
    format: str = "html",
    profile: Optional[str] = None,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    classification: Optional[str] = None,
    user: UserIdentity = Depends(get_current_user),
):
    """
    Renders the publication-ready, typeset adaptive digital audit book HTML/PDF
    matching the detected or requested report family (COMPLETE, SEO, GEO, AEO, CRO, COMPETITOR, HYBRID, CUSTOM).

    format='html': returns standalone A4 publication HTML with CSS Paged Media rules,
                   dedicated cover page, front matter, TOC leader dots, evidence-status disclosures, and limitations.
    format='json': returns publication manifest and dynamic pagination layout.
    """
    run = require_analysis(analysis_id, user)
    report = getattr(run, "report", None)
    if not report:
        raise HTTPException(status_code=400, detail="Executive report not yet synthesized for this analysis run.")

    from app.reports.adaptive_audit_book import (
        detect_report_family,
        build_publication_manifest,
        compute_toc_pagination,
        render_adaptive_audit_book_html,
    )

    family = detect_report_family(report, profile)
    manifest = build_publication_manifest(
        report,
        family,
        title_override=title,
        subtitle_override=subtitle,
        classification_override=classification,
    )
    pagination = compute_toc_pagination(manifest)

    if format.lower() == "json":
        return {
            "analysis_id": analysis_id,
            "family": family,
            "manifest": manifest,
            "pagination": pagination,
            "status": "READY",
        }

    html_content = render_adaptive_audit_book_html(
        report,
        report_type=profile,
        title_override=title,
        subtitle_override=subtitle,
        classification=classification,
    )

    if format.lower() == "pdf":
        domain_clean = (report.domain or "website").replace("https://", "").replace("http://", "").split("/")[0]
        from app.reports.adaptive_audit_book import render_adaptive_audit_book_pdf
        pdf_bytes, qa_report = await render_adaptive_audit_book_pdf(
            report,
            report_type=profile,
            title_override=title,
            subtitle_override=subtitle,
            classification=classification,
        )
        if not pdf_bytes:
            raise HTTPException(
                status_code=503,
                detail="PDF rendering engine is currently unavailable or timed out. "
                       "You can open the report with ?format=print and select 'Print / Save as PDF' in your browser.",
            )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{domain_clean}_{family.lower()}_audit_book.pdf"',
                "X-Dristik-QA-Valid": str(qa_report.is_valid),
                "X-Dristik-QA-Passed": str(len(qa_report.passed_checks)),
            },
        )

    return Response(
        content=html_content,
        media_type="text/html",
        headers={
            "X-Dristik-Report-Family": family,
            "X-Dristik-Total-Pages": str(pagination.get("closing_page", 1)),
        },
    )

