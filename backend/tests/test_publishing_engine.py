"""
Comprehensive Unit & Integration Tests for Dristik Professional Publishing Engine.
Verifies:
1. Category-specific dynamic cover page generation with pure vector SVG motifs
2. Hierarchical Table of Contents with section badges, dot leaders, and internal links
3. Accurate multi-pass physical PDF pagination resolution using pypdf
4. Interactive PDF bookmark / outline hierarchy and document metadata injection
5. Automated 10-Point PDF Quality Assurance gate validation
6. Multi-discipline report adaptation (SEO, GEO, AEO, CRO, Competitor, Complete)
"""
import io
import pytest
try:
    import pypdf
except ImportError:
    pypdf = None

from app.domain.models import BusinessProfile, ExecutiveReport, Finding, OverallScoreResult
from app.reports.publishing_engine import (
    ChapterSpec,
    CoverGenerator,
    PartSpec,
    PdfPaginationResolver,
    PdfPostProcessor,
    PdfPublishingPipeline,
    PdfQualityAssurance,
    PublicationDocument,
    PublicationHtmlRenderer,
    PublicationMetadata,
    TableOfContentsGenerator,
    get_publishing_css,
)
from app.reports.adaptive_audit_book import (
    build_adaptive_publication_document,
    detect_report_family,
    render_adaptive_audit_book_html,
    render_adaptive_audit_book_pdf,
)


def _make_dummy_doc(family: str = "SEO") -> PublicationDocument:
    meta = PublicationMetadata(
        family=family,
        title="Technical SEO & Organic Search Audit",
        subtitle="CRAWL INFRASTRUCTURE · INDEXABILITY · CANONICAL ROUTING",
        domain="example-corp.com",
        brand_name="Example Corp",
        audit_date="2026-10-14",
        report_ref="DST-TST-001",
        classification="STRICTLY CONFIDENTIAL // C-SUITE DOSSIER",
        purpose="Independent technical assurance examining crawl architecture and search discoverability.",
        score_display="88.5",
        grade="A-",
        overall_score=88.5,
        pages_crawled=25,
        findings_count=12,
        story_summary="Robust crawl architecture with isolated canonical configuration discrepancies.",
        primary_opportunity="Deploy canonical 301 consolidation rules on catalog endpoints.",
    )

    ch1 = ChapterSpec(
        id="ch_01",
        num="01",
        part_id="part_1",
        part_title="PART I — EXECUTIVE OVERVIEW",
        title="Executive Brief & Diagnostic Synthesis",
        desc="Macro indexability scorecards and Tri-Perspective cognitive analysis.",
        html_content="<p>Executive brief body paragraph with verified metrics.</p>",
        page_number=3,
    )
    ch2 = ChapterSpec(
        id="ch_02",
        num="02",
        part_id="part_2",
        part_title="PART II — AUDIT FINDINGS",
        title="Discoverability & Technical Indexability",
        desc="Crawl latency curves, HTTP response ledger, and robots directives.",
        html_content="<p>Technical discoverability analysis and finding records.</p>",
        page_number=5,
    )
    ch3 = ChapterSpec(
        id="ch_03",
        num="03",
        part_id="part_3",
        part_title="PART III — REMEDIATION ROADMAP",
        title="Prioritized Remediation Roadmap",
        desc="Top action plan with NOW / NEXT / ONGOING milestone sprints.",
        html_content="<p>90-day remediation schedule and ownership matrix.</p>",
        page_number=8,
    )

    part1 = PartSpec(id="part_1", num="I", title="EXECUTIVE OVERVIEW", chapters=[ch1])
    part2 = PartSpec(id="part_2", num="II", title="AUDIT FINDINGS", chapters=[ch2])
    part3 = PartSpec(id="part_3", num="III", title="REMEDIATION ROADMAP", chapters=[ch3])

    return PublicationDocument(
        metadata=meta,
        parts=[part1, part2, part3],
        front_matter_html="<div class='front-matter'>Scope & Protocol Details</div>",
        back_matter_html="<div class='back-matter'>Zero-Fake Closing Seal</div>",
        toc_pages=1,
        starting_body_page=3,
    )


class TestCoverGenerator:
    """Verifies Section 2 requirements for dedicated, publication-grade cover pages."""

    @pytest.mark.parametrize("family", ["SEO", "GEO", "AEO", "CRO", "COMPETITOR", "COMPLETE"])
    def test_renders_cover_for_all_families_with_motifs(self, family):
        doc = _make_dummy_doc(family=family)
        html_out = CoverGenerator.render_cover_html(doc)

        assert "book-cover" in html_out
        assert "cover-page" in html_out
        assert "DRISTIK // PUBLICATION" in html_out
        assert "example-corp.com" in html_out
        assert "Example Corp" in html_out
        assert "STRICTLY CONFIDENTIAL" in html_out
        assert "ZERO-FAKE EVIDENCE POLICY" in html_out
        assert "ZERO-FAKE AST CERTIFIED" not in html_out
        assert "PAGE 1 (COVER) // UNNUMBERED" in html_out

        # Verify category motif SVG is present
        assert "<svg" in html_out
        assert "cover-motif-svg" in html_out

    def test_cover_palette_and_eyebrow_customization(self):
        doc_geo = _make_dummy_doc(family="GEO")
        html_geo = CoverGenerator.render_cover_html(doc_geo)
        assert "GENERATIVE ENGINE OPTIMIZATION" in html_geo

        doc_cro = _make_dummy_doc(family="CRO")
        html_cro = CoverGenerator.render_cover_html(doc_cro)
        assert "CONVERSION RATE OPTIMIZATION" in html_cro

        doc_aeo = _make_dummy_doc(family="AEO")
        html_aeo = CoverGenerator.render_cover_html(doc_aeo)
        assert "ANSWER ENGINE OPTIMIZATION" in html_aeo


class TestTableOfContentsGenerator:
    """Verifies Section 3 requirements for hierarchical Table of Contents."""

    def test_renders_hierarchical_toc_with_dot_leaders_and_links(self):
        doc = _make_dummy_doc()
        resolved = {"ch_01": 3, "ch_02": 6, "ch_03": 11}
        html_out = TableOfContentsGenerator.render_toc_html(doc, resolved_pages=resolved)

        assert "Table of Contents" in html_out
        assert "table-of-contents" in html_out
        assert "toc-dots" in html_out
        assert "toc-leader" in html_out

        # Clickable anchor links
        assert 'href="#ch_01"' in html_out
        assert 'href="#ch_02"' in html_out
        assert 'href="#ch_03"' in html_out

        # Page numbers
        assert "p. 3" in html_out
        assert "p. 6" in html_out
        assert "p. 11" in html_out

        # Parts
        assert "EXECUTIVE OVERVIEW" in html_out
        assert "AUDIT FINDINGS" in html_out
        assert "REMEDIATION ROADMAP" in html_out


@pytest.mark.skipif(pypdf is None, reason="pypdf not installed in test environment")
class TestPdfPaginationResolver:
    """Verifies Section 4 requirements for accurate physical page detection with pypdf."""

    def test_detects_physical_pages_from_real_pdf_stream(self):
        # Create a synthetic 5-page PDF with text markers
        writer = pypdf.PdfWriter()

        # Page 0: Cover
        p0 = writer.add_blank_page(width=595.28, height=841.89)
        # Page 1: TOC
        p1 = writer.add_blank_page(width=595.28, height=841.89)
        # Page 2: ch_01
        p2 = writer.add_blank_page(width=595.28, height=841.89)
        # Page 3: ch_01 continuation
        p3 = writer.add_blank_page(width=595.28, height=841.89)
        # Page 4: ch_02
        p4 = writer.add_blank_page(width=595.28, height=841.89)

        buf = io.BytesIO()
        writer.write(buf)
        pdf_bytes = buf.getvalue()

        chapters = [
            ChapterSpec(id="ch_01", num="01", part_id="p1", part_title="", title="Executive Brief", desc="", html_content=""),
            ChapterSpec(id="ch_02", num="02", part_id="p1", part_title="", title="Technical Indexability", desc="", html_content=""),
        ]

        # In blank synthetic PDF, fallback monotonic mapping applies
        res = PdfPaginationResolver.resolve_physical_pages(pdf_bytes, chapters, starting_body_page=3)
        assert res["ch_01"] >= 3
        assert res["ch_02"] > res["ch_01"]


@pytest.mark.skipif(pypdf is None, reason="pypdf not installed in test environment")
class TestPdfPostProcessor:
    """Verifies PDF interactive bookmarks and document metadata injection."""

    def test_injects_hierarchical_bookmarks_and_metadata(self):
        writer = pypdf.PdfWriter()
        for _ in range(6):
            writer.add_blank_page(width=595.28, height=841.89)
        buf = io.BytesIO()
        writer.write(buf)
        raw_pdf = buf.getvalue()

        doc = _make_dummy_doc()
        resolved = {"ch_01": 3, "ch_02": 4, "ch_03": 5}

        enhanced_pdf = PdfPostProcessor.process(raw_pdf, doc, resolved)
        assert len(enhanced_pdf) > len(raw_pdf)

        reader = pypdf.PdfReader(io.BytesIO(enhanced_pdf))
        assert len(reader.pages) == 6
        assert reader.metadata is not None
        assert "Technical SEO" in reader.metadata.title
        assert "Dristik" in reader.metadata.author
        assert len(reader.outline) >= 2


@pytest.mark.skipif(pypdf is None, reason="pypdf not installed in test environment")
class TestPdfQualityAssurance:
    """Verifies Section 13 requirements for automated PDF QA gate."""

    def test_validates_healthy_pdf(self):
        writer = pypdf.PdfWriter()
        for _ in range(5):
            writer.add_blank_page(width=595.28, height=841.89)
        writer.add_metadata({"/Title": "Dristik SEO Audit", "/Author": "Dristik AI"})
        buf = io.BytesIO()
        writer.write(buf)
        pdf_bytes = buf.getvalue()

        doc = _make_dummy_doc()
        resolved = {"ch_01": 3, "ch_02": 4, "ch_03": 5}

        report = PdfQualityAssurance.validate(pdf_bytes, doc, resolved)
        assert report.is_valid is True
        assert "check_pdf_opens_successfully" in report.passed_checks
        assert "check_page_count_threshold" in report.passed_checks
        assert "check_toc_page_numbers_accurate" in report.passed_checks
        assert len(report.failed_checks) == 0

    def test_fails_on_empty_or_corrupt_pdf(self):
        doc = _make_dummy_doc()
        report = PdfQualityAssurance.validate(b"corrupt invalid data", doc, {})
        assert report.is_valid is False
        assert len(report.failed_checks) > 0


@pytest.mark.skipif(pypdf is None, reason="pypdf not installed in test environment")
class TestMasterPublishingPipeline:
    """Verifies the two-pass physical layout orchestration."""

    @pytest.mark.asyncio
    async def test_pipeline_executes_two_pass_flow_with_mock_renderer(self):
        doc = _make_dummy_doc()

        # Mock renderer generating a valid 10-page PDF
        async def mock_render(html_str: str) -> bytes:
            writer = pypdf.PdfWriter()
            for _ in range(10):
                writer.add_blank_page(width=595.28, height=841.89)
            writer.add_metadata({"/Title": "Mock Audit", "/Author": "Dristik"})
            buf = io.BytesIO()
            writer.write(buf)
            return buf.getvalue()

        pdf_bytes, qa = await PdfPublishingPipeline.render_publication_pdf(doc, render_fn=mock_render)
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 200
        assert qa.is_valid is True


class TestAdaptiveAuditBookIntegration:
    """Verifies publication document construction from real ExecutiveReport models."""

    def test_builds_complete_document_with_all_chapters(self):
        from app.domain.models import ThreeWayComparison
        findings = [
            Finding(
                finding_id="F-SEO-01",
                category="TECHNICAL_SEO",
                severity="CRITICAL",
                title="Missing Canonical Directives",
                description="Self-referential canonical tags absent on 15 category pages.",
                recommendation="Inject canonical link elements in HTML head.",
            ),
            Finding(
                finding_id="F-GEO-02",
                category="GEO",
                severity="HIGH",
                title="Ambiguous Product Entities",
                description="Product definitions lack JSON-LD Schema.org attribution.",
                recommendation="Deploy Product schema with ItemAvailability node.",
            ),
            Finding(
                finding_id="F-AEO-03",
                category="AI_SEARCH",
                severity="MEDIUM",
                title="Unstructured Answer Passages",
                description="Product questions lack direct 50-word answer passages.",
                recommendation="Add structured FAQ and definition blocks.",
            ),
        ]
        rep = ExecutiveReport(
            report_id="rep_test_full",
            analysis_id="analysis_full_001",
            website_url="https://enterprise-scale.io",
            domain="enterprise-scale.io",
            generated_at="2026-10-14T10:00:00Z",
            story_summary="Enterprise Scale audit synthesis under deterministic evidence governance.",
            primary_strategic_opportunity="Consolidate canonical routing directives across catalog endpoints.",
            consultant_advice_what_to_ignore="Ignore development staging URLs.",
            three_way_comparison=ThreeWayComparison(
                human_visitor_perspective="Clear value proposition on desktop viewport.",
                search_engine_perspective="Clean 200 OK responses with zero redirect loops.",
                ai_answer_engine_perspective="Concise factual extracts verified across test queries.",
            ),
            business_profile=BusinessProfile(business_name="Enterprise Scale"),
            scores=OverallScoreResult(overall_score=85.0, overall_grade="A", grade="A", health_label="STRONG"),
            findings=findings,
        )

        doc = build_adaptive_publication_document(rep)
        assert doc.metadata.family == "COMPLETE"
        assert len(doc.parts) >= 3

        # Verify all chapter IDs exist
        chapter_ids = [ch.id for part in doc.parts for ch in part.chapters]
        assert "ch_brief" in chapter_ids
        assert "ch_seo" in chapter_ids
        assert "ch_geo" in chapter_ids
        assert "ch_roadmap" in chapter_ids
        assert "ch_appendix" in chapter_ids

        # Render HTML
        html_out = PublicationHtmlRenderer.render(doc)
        assert "enterprise-scale.io" in html_out
        assert "Missing Canonical Directives" in html_out
        assert "Ambiguous Product Entities" in html_out
        assert "screen-toolbar" in html_out
        assert "Table of Contents" in html_out

    def test_print_html_report_renders_with_commercial_evaluations(self):
        from app.seo.reporting.seo_report_generator import seo_report_generator
        from app.domain.models import CommercialQueryEvaluation, OverallScoreResult, ThreeWayComparison, BusinessProfile

        comm_evals = [
            CommercialQueryEvaluation(
                question_key="identity",
                question_title="Identity & Value Prop",
                buyer_query="What does Enterprise Scale do?",
                before_score=8,
                before_answer="Enterprise Scale builds high performance apps.",
                before_evidence_status="VERIFIED",
            ),
            CommercialQueryEvaluation(
                question_key="pricing",
                question_title="Pricing & Commercial Terms",
                buyer_query="How much does Enterprise Scale cost?",
                before_score=2,
                before_answer="",
                before_evidence_status="MISSING",
            ),
        ]

        rep = ExecutiveReport(
            report_id="rep_test_print",
            analysis_id="run_test_print",
            domain="enterprise-scale.io",
            url="https://enterprise-scale.io",
            website_url="https://enterprise-scale.io",
            generated_at="2026-10-14T10:00:00Z",
            story_summary="Test audit narrative with commercial queries.",
            primary_strategic_opportunity="Optimize commercial queries.",
            consultant_advice_what_to_ignore="Ignore dev urls.",
            three_way_comparison=ThreeWayComparison(
                human_visitor_perspective="Clear value.",
                search_engine_perspective="Clean 200.",
                ai_answer_engine_perspective="Extractable.",
            ),
            business_profile=BusinessProfile(business_name="Enterprise Scale"),
            scores=OverallScoreResult(overall_score=78.0, overall_grade="B", grade="B", health_label="MODERATE"),
            commercial_evaluations=comm_evals,
            findings=[],
        )

        print_html = seo_report_generator.render_print_html_report(rep)
        assert "<!DOCTYPE html>" in print_html
        assert "enterprise-scale.io" in print_html
        assert "Buyer Journey Intent Mapping" in print_html
        assert "What does Enterprise Scale do?" in print_html
        assert "ALIGNED" in print_html
        assert "MISALIGNED" in print_html
        assert "80/100" in print_html
        assert "20/100" in print_html

