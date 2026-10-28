"""
Tests for Dristik Adaptive Audit Book Generator.
Verifies report-family auto-detection, publication manifest generation,
TOC pagination logic, and publication-quality HTML rendering with Zero-Fake evidence governance.
"""
import pytest
from app.domain.models import (
    ExecutiveReport,
    BusinessProfile,
    OverallScoreResult,
    ThreeWayComparison,
    Finding,
)
from app.reports.adaptive_audit_book import (
    detect_report_family,
    build_publication_manifest,
    compute_toc_pagination,
    render_adaptive_audit_book_html,
)


def _build_test_report(
    policy_pack: str = "",
    categories: list[str] | None = None,
    overall_score: float | None = 82.5,
) -> ExecutiveReport:
    cats = categories or ["TECHNICAL_SEO", "GEO", "AI_SEARCH", "UX_CONVERSION"]
    findings = [
        Finding(
            finding_id=f"f_{idx:02d}",
            category=cat,
            severity="HIGH" if idx == 0 else "MEDIUM",
            title=f"Sample defect in {cat}",
            description=f"Empirical description for {cat} defect.",
            evidence_id=f"ev_{idx:03d}",
            recommendation=f"Remediate {cat} defect according to acceptance criteria.",
        )
        for idx, cat in enumerate(cats)
    ]
    return ExecutiveReport(
        report_id="rep_book_test_001",
        analysis_id="analysis_book_001",
        website_url="https://acme-analytics.io",
        domain="acme-analytics.io",
        generated_at="2026-10-12T14:30:00Z",
        policy_pack=policy_pack,
        business_profile=BusinessProfile(business_name="Acme Analytics"),
        scores=OverallScoreResult(
            overall_score=overall_score,
            overall_grade="A-" if overall_score and overall_score >= 80 else "B",
            grade="A-" if overall_score and overall_score >= 80 else "B",
            health_label="STRONG" if overall_score and overall_score >= 80 else "FAIR",
            seo_score=85,
            geo_score=78,
            aeo_score=80,
            cro_score=86,
        ),
        story_summary="Acme Analytics demonstrates robust crawl architecture with opportunities in citation attribution.",
        primary_strategic_opportunity="Publish schema.org Organization and SoftwareApplication entities.",
        consultant_advice_what_to_ignore="Disregard non-indexed development staging subdomains.",
        three_way_comparison=ThreeWayComparison(
            human_visitor_perspective="Clear value proposition on desktop viewport.",
            search_engine_perspective="Clean 200 OK responses with zero redirect loops.",
            ai_answer_engine_perspective="Concise factual extracts verified across test queries.",
        ),
        findings=findings,
    )


class TestReportFamilyDetection:
    def test_detects_complete_when_multi_discipline(self):
        rep = _build_test_report(categories=["TECHNICAL_SEO", "GEO", "AI_SEARCH", "UX_CONVERSION"])
        family = detect_report_family(rep)
        assert family == "COMPLETE"

    def test_detects_seo_from_policy_pack(self):
        rep = _build_test_report(policy_pack="seo_only", categories=["TECHNICAL_SEO"])
        family = detect_report_family(rep)
        assert family == "SEO"

    def test_detects_geo_from_policy_pack(self):
        rep = _build_test_report(policy_pack="geo_only", categories=["GEO"])
        family = detect_report_family(rep)
        assert family == "GEO"

    def test_detects_aeo_from_policy_pack(self):
        rep = _build_test_report(policy_pack="aeo_only", categories=["AI_SEARCH"])
        family = detect_report_family(rep)
        assert family == "AEO"

    def test_detects_cro_from_policy_pack(self):
        rep = _build_test_report(policy_pack="cro_only", categories=["UX_CONVERSION"])
        family = detect_report_family(rep)
        assert family == "CRO"

    def test_detects_competitor_from_policy_pack(self):
        rep = _build_test_report(policy_pack="competitor_analysis", categories=["COMPETITIVE"])
        family = detect_report_family(rep)
        assert family == "COMPETITOR"

    def test_detects_hybrid_when_two_disciplines(self):
        rep = _build_test_report(policy_pack="custom", categories=["GEO", "AI_SEARCH"])
        rep.scores.category_scores = {"GEO": 80, "AEO": 85}
        family = detect_report_family(rep)
        assert family in ("HYBRID", "COMPLETE")

    def test_manual_override_takes_precedence(self):
        rep = _build_test_report(categories=["TECHNICAL_SEO", "GEO", "AI_SEARCH", "UX_CONVERSION"])
        assert detect_report_family(rep, requested_type="CRO") == "CRO"
        assert detect_report_family(rep, requested_type="SEO") == "SEO"
        assert detect_report_family(rep, requested_type="COMPETITORS") == "COMPETITOR"
        assert detect_report_family(rep, requested_type="CUSTOM") == "CUSTOM"


class TestPublicationManifest:
    def test_builds_manifest_with_brand_and_chapters(self):
        rep = _build_test_report()
        manifest = build_publication_manifest(rep, "COMPLETE")

        assert manifest["family"] == "COMPLETE"
        assert manifest["domain"] == "acme-analytics.io"
        assert manifest["brand_name"] == "Acme Analytics"
        assert "Complete Website Intelligence Audit" in manifest["title"]
        assert len(manifest["chapters"]) >= 7

        chapter_ids = [ch["id"] for ch in manifest["chapters"]]
        assert "ch_brief" in chapter_ids
        assert "ch_seo" in chapter_ids
        assert "ch_geo" in chapter_ids
        assert "ch_aeo" in chapter_ids
        assert "ch_roadmap" in chapter_ids
        assert "ch_appendix" in chapter_ids

    def test_manifest_respects_custom_overrides(self):
        rep = _build_test_report()
        manifest = build_publication_manifest(
            rep,
            "SEO",
            title_override="Custom Enterprise SEO Audit 2026",
            subtitle_override="Confidential Engineering Assessment",
            classification_override="STRICTLY CONFIDENTIAL",
        )
        assert manifest["title"] == "Custom Enterprise SEO Audit 2026"
        assert manifest["subtitle"] == "Confidential Engineering Assessment"
        assert manifest["classification"] == "STRICTLY CONFIDENTIAL"

    def test_seo_manifest_contains_page_by_page_chapter(self):
        rep = _build_test_report(policy_pack="seo_only", categories=["TECHNICAL_SEO"])
        manifest = build_publication_manifest(rep, "SEO")
        chapter_ids = [ch["id"] for ch in manifest["chapters"]]
        assert "ch_seo" in chapter_ids
        assert "ch_page_by_page" in chapter_ids
        # GEO and AEO chapters omitted for SEO-only audit
        assert "ch_geo" not in chapter_ids
        assert "ch_aeo" not in chapter_ids


class TestPaginationComputation:
    def test_compute_toc_pagination_sequence(self):
        rep = _build_test_report()
        manifest = build_publication_manifest(rep, "COMPLETE")
        pagination = compute_toc_pagination(manifest)

        assert pagination["ch_brief"] == 1  # Arabic numbering starts at 1 for executive brief
        assert pagination["ch_seo"] > pagination["ch_brief"]
        assert pagination["closing_page"] > pagination["ch_appendix"]


class TestAdaptiveAuditBookHtmlRendering:
    def test_renders_valid_html_with_editorial_tokens(self):
        rep = _build_test_report()
        rendered_html = render_adaptive_audit_book_html(rep)

        assert "<!DOCTYPE html>" in rendered_html
        assert "<html" in rendered_html
        assert "</html>" in rendered_html
        assert "@page" in rendered_html
        assert "size: A4" in rendered_html

    def test_renders_dedicated_cover_page_without_visible_page_number(self):
        rep = _build_test_report()
        rendered_html = render_adaptive_audit_book_html(rep)

        assert "cover-page" in rendered_html
        assert "acme-analytics.io" in rendered_html
        assert "Acme Analytics" in rendered_html
        assert "WEBSITE INTELLIGENCE / DIGITAL AUDIT SERIES" in rendered_html
        assert "CONFIDENTIAL" in rendered_html

    def test_renders_formal_front_matter_with_evidence_conventions(self):
        rep = _build_test_report()
        rendered_html = render_adaptive_audit_book_html(rep)

        assert "DOCUMENT SPECIFICATION" in rendered_html
        assert "EVIDENCE CONVENTIONS &amp; TAXONOMY" in rendered_html
        assert "OBSERVED" in rendered_html
        assert "MEASURED" in rendered_html
        assert "DERIVED" in rendered_html
        assert "RECOMMENDED" in rendered_html
        assert "UNMEASURED" in rendered_html
        assert "SHA-256" in rendered_html

    def test_renders_toc_with_leader_dots_and_page_numbers(self):
        rep = _build_test_report()
        rendered_html = render_adaptive_audit_book_html(rep)

        assert "TABLE OF CONTENTS" in rendered_html
        assert "toc-leader" in rendered_html
        assert "Executive Brief" in rendered_html
        assert "Roadmap" in rendered_html

    def test_renders_remediation_roadmap_priorities(self):
        rep = _build_test_report()
        rendered_html = render_adaptive_audit_book_html(rep)

        assert "Evidence Register" in rendered_html or "EVIDENCE REGISTER" in rendered_html
        assert "Remediate" in rendered_html

    def test_renders_zero_fake_closing_seal(self):
        rep = _build_test_report()
        rendered_html = render_adaptive_audit_book_html(rep)

        assert "ZERO-FAKE EVIDENCE ATTESTATION" in rendered_html
        assert "RE-VERIFICATION PROTOCOL" in rendered_html
        assert "acme-analytics.io" in rendered_html
        assert "NOT_ASSESSED" in rendered_html
        assert "AUDIT CERTIFIED" not in rendered_html

    def test_handles_unmeasured_scores_without_defaulting_to_zero(self):
        rep = _build_test_report()
        rep.scores = None
        rendered_html = render_adaptive_audit_book_html(rep)

        assert "—" in rendered_html
        assert "acme-analytics.io" in rendered_html


class TestAuditBookApiRoute:
    def test_get_adaptive_audit_book_html_and_json(self):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.orchestration.orchestrator import orchestrator
        from app.domain.enums import AnalysisStage, UserRole
        from app.domain.models import AnalysisRun
        from app.identity.authorizer import UserIdentity
        from app.identity.deps import get_current_user

        mock_user = UserIdentity(
            user_id="usr_audit_book_test",
            org_id="org_test",
            email="auditor@dristik.ai",
            role=UserRole.ADMIN,
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user

        try:
            analysis_id = "run_adaptive_book_001"
            rep = _build_test_report()
            run = AnalysisRun(
                analysis_id=analysis_id,
                org_id=mock_user.org_id,
                website_url="https://acme-analytics.io",
                status=AnalysisStage.COMPLETED,
                created_at="2026-10-12T14:30:00Z",
                updated_at="2026-10-12T14:30:00Z",
            )
            run.report = rep
            orchestrator.runs[analysis_id] = run

            client = TestClient(app)

            # Test HTML endpoint
            resp_html = client.get(f"/api/v1/reports/{analysis_id}/audit-book?format=html")
            assert resp_html.status_code == 200
            assert "text/html" in resp_html.headers.get("content-type", "")
            assert resp_html.headers.get("x-dristik-report-family") == "COMPLETE"
            assert "<!DOCTYPE html>" in resp_html.text
            assert "acme-analytics.io" in resp_html.text

            # Test JSON endpoint
            resp_json = client.get(f"/api/v1/reports/{analysis_id}/audit-book?format=json")
            assert resp_json.status_code == 200
            data = resp_json.json()
            assert data["family"] == "COMPLETE"
            assert data["manifest"]["domain"] == "acme-analytics.io"
            assert "pagination" in data
            assert data["status"] == "READY"

            # Test with profile override
            resp_seo = client.get(f"/api/v1/reports/{analysis_id}/audit-book?format=json&profile=SEO")
            assert resp_seo.status_code == 200
            data_seo = resp_seo.json()
            assert data_seo["family"] == "SEO"
            assert "Technical SEO" in data_seo["manifest"]["title"]
        finally:
            app.dependency_overrides.clear()


class TestSectionPdfEndpoint:
    def _setup(self):
        from app.main import app
        from app.orchestration.orchestrator import orchestrator
        from app.domain.enums import AnalysisStage, UserRole
        from app.domain.models import AnalysisRun
        from app.identity.authorizer import UserIdentity
        from app.identity.deps import get_current_user

        user = UserIdentity(user_id="usr_pdf", org_id="org_pdf", email="a@b.co", role=UserRole.ADMIN)
        app.dependency_overrides[get_current_user] = lambda: user
        run = AnalysisRun(
            analysis_id="run_pdf_001", org_id=user.org_id, website_url="https://acme-analytics.io",
            status=AnalysisStage.COMPLETED, created_at="2026-10-12T14:30:00Z", updated_at="2026-10-12T14:30:00Z",
        )
        run.report = _build_test_report()
        orchestrator.runs["run_pdf_001"] = run
        return app

    def test_pdf_default_html_opt_in_and_503(self, monkeypatch):
        from fastapi.testclient import TestClient
        from app.crawl.browser import BrowserRenderService

        app = self._setup()
        try:
            client = TestClient(app)
            url = "/api/v1/reports/run_pdf_001/sections/seo/pdf"

            async def fake_ok(html, timeout_ms=60000):
                return b"%PDF-1.7 fake"
            monkeypatch.setattr(BrowserRenderService, "render_pdf", fake_ok)
            r = client.get(url)
            assert r.status_code == 200
            assert r.headers["content-type"] == "application/pdf"
            assert r.content.startswith(b"%PDF")

            r = client.get(url + "?format=html")
            assert r.status_code == 200 and "text/html" in r.headers["content-type"]

            async def fake_none(html, timeout_ms=60000):
                return None
            monkeypatch.setattr(BrowserRenderService, "render_pdf", fake_none)
            # Isolate the failure path from the successful PDF cached above.
            from app.reports.pdf_generator import _SECTION_PDF_CACHE
            _SECTION_PDF_CACHE.clear()
            assert client.get(url).status_code == 503
        finally:
            app.dependency_overrides.clear()
