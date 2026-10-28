"""
Tests for Phase P1: Durable Audit Persistence, Resumable Stage Checkpoints,
Evidence Explorer, and Score Explainability.
"""
import os
import tempfile
from datetime import datetime, timezone
import pytest
from app.persistence.repository import AuditRepository
from app.persistence.models import StageCheckpoint
from app.domain.enums import AnalysisStage, Category, Severity, MetricProvenanceState
from app.domain.models import AnalysisRun, Claim, Finding, PageEvidence
from app.evidence.models import Evidence


@pytest.fixture
def temp_repo():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = f.name
    repo = AuditRepository(db_path=temp_path)
    yield repo
    if os.path.exists(temp_path):
        os.remove(temp_path)


def test_audit_run_persistence(temp_repo):
    now = datetime.now(timezone.utc).isoformat()
    run = AnalysisRun(
        analysis_id="run_durable_01",
        org_id="org_enterprise",
        website_url="https://linear.app",
        status=AnalysisStage.QUEUED,
        progress_percentage=10,
        current_step="Crawling pages",
        created_at=now,
        updated_at=now,
    )
    temp_repo.save_run(run)

    retrieved = temp_repo.get_run("run_durable_01")
    assert retrieved is not None
    assert retrieved["analysis_id"] == "run_durable_01"
    assert retrieved["domain"] == "linear.app"
    assert retrieved["status"] == "queued"
    assert retrieved["progress"] == 10

    # Update run status
    run.status = AnalysisStage.COMPLETED
    run.progress_percentage = 100
    temp_repo.save_run(run)

    updated = temp_repo.get_run("run_durable_01")
    assert updated["status"] == "completed"
    assert updated["progress"] == 100


def test_stage_checkpoints_and_resumption(temp_repo):
    now = datetime.now(timezone.utc).isoformat()
    analysis_id = "run_chk_test"
    run = AnalysisRun(
        analysis_id=analysis_id,
        org_id="org_test",
        website_url="https://linear.app",
        status=AnalysisStage.INGESTING,
        created_at=now,
        updated_at=now,
    )
    temp_repo.save_run(run)

    # Checkpoint 1: Ingesting
    chk1 = StageCheckpoint(
        analysis_id=analysis_id,
        stage=AnalysisStage.INGESTING,
        step_number=1,
        status="COMPLETED",
        crawled_count=5,
        evidence_count=42,
    )
    temp_repo.save_checkpoint(chk1)

    # Checkpoint 2: Specialist Execution
    chk2 = StageCheckpoint(
        analysis_id=analysis_id,
        stage=AnalysisStage.SPECIALIST_EXECUTION,
        step_number=2,
        status="COMPLETED",
        claims_count=35,
    )
    temp_repo.save_checkpoint(chk2)

    latest = temp_repo.get_latest_checkpoint(analysis_id)
    assert latest is not None
    assert latest.step_number == 2
    assert latest.stage == AnalysisStage.SPECIALIST_EXECUTION
    assert latest.claims_count == 35

    all_chks = temp_repo.get_all_checkpoints(analysis_id)
    assert len(all_chks) == 2


def test_evidence_explorer_traceability(temp_repo):
    now = datetime.now(timezone.utc).isoformat()
    analysis_id = "run_trace_test"
    run = AnalysisRun(
        analysis_id=analysis_id,
        org_id="org_test",
        website_url="https://linear.app",
        status=AnalysisStage.COMPLETED,
        created_at=now,
        updated_at=now,
    )
    temp_repo.save_run(run)

    # Persist evidence
    ev = Evidence(
        id="ev_001",
        source_type="html_dom",
        analyzer="h1_extractor",
        hash="sha_12345",
        url="https://linear.app/",
        text="Issue tracking built for speed",
        value={"h1": "Issue tracking built for speed"},
        selector="h1.hero-title",
        raw_snapshot_id="snap_12345",
    )
    temp_repo.persist_evidence_items(analysis_id, [ev])

    # Persist claim
    claim = Claim(
        id="claim_001",
        agent_id="seo.onpage.v3",
        category=Category.ON_PAGE_SEO,
        statement="H1 clearly targets speed and issue tracking.",
        evidence_refs=["ev_001"],
    )
    temp_repo.persist_claims(analysis_id, [claim])

    # Persist finding
    finding = Finding(
        finding_id="find_001",
        id="find_001",
        category=Category.ON_PAGE_SEO,
        severity=Severity.INFO,
        title="Hero H1 Tag Optimized",
        description="Clear value proposition in H1",
        impact=5,
        recommendation="Maintain current copy",
        evidence_refs=["ev_001"],
        claim_refs=["claim_001"],
    )
    temp_repo.persist_findings(analysis_id, [finding])

    traces = temp_repo.get_evidence_trace(analysis_id)
    assert len(traces) == 1
    t = traces[0]
    assert t.finding_id == "find_001"
    assert t.claim_id == "claim_001"
    assert t.evidence_id == "ev_001"
    assert t.selector == "h1.hero-title"
    assert t.raw_snapshot_id == "snap_12345"


def test_score_explainability_breakdown(temp_repo):
    now = datetime.now(timezone.utc).isoformat()
    analysis_id = "run_explain_test"
    run = AnalysisRun(
        analysis_id=analysis_id,
        org_id="org_test",
        website_url="https://linear.app",
        status=AnalysisStage.COMPLETED,
        created_at=now,
        updated_at=now,
    )
    temp_repo.save_run(run)

    ev = Evidence(
        id="ev_001",
        source_type="html_dom",
        analyzer="test_analyzer",
        hash="sha_ev001",
        url="https://linear.app/",
        text="Test evidence",
    )
    temp_repo.persist_evidence_items(analysis_id, [ev])

    explanation = temp_repo.get_score_explanation(analysis_id)
    assert explanation is not None
    assert explanation.domain == "linear.app"
    assert len(explanation.dimensions) >= 4
    dim_keys = [d.dimension_key for d in explanation.dimensions]
    assert "entity_clarity" in dim_keys
    assert "extractability" in dim_keys
    assert "ai_visibility" in dim_keys



def test_final_run_and_findings_are_saved_as_one_replacement_set(temp_repo):
    now = datetime.now(timezone.utc).isoformat()
    analysis_id = "run_atomic_final"
    run = AnalysisRun(
        analysis_id=analysis_id,
        org_id="org_atomic",
        website_url="https://example.com",
        status=AnalysisStage.EXECUTIVE_SYNTHESIS,
        created_at=now,
        updated_at=now,
    )
    old_finding = Finding(
        finding_id="find_old",
        id="find_old",
        category=Category.ON_PAGE_SEO,
        severity=Severity.INFO,
        title="Stale finding",
        description="Must not survive final report replacement",
        impact=1,
        recommendation="None",
        evidence_refs=[],
    )
    final_finding = Finding(
        finding_id="find_final",
        id="find_final",
        category=Category.ON_PAGE_SEO,
        severity=Severity.MEDIUM,
        title="Final finding",
        description="Validated final finding",
        impact=5,
        recommendation="Fix with evidence",
        evidence_refs=["ev_final"],
    )
    temp_repo.save_run(run)
    temp_repo.persist_findings(analysis_id, [old_finding])

    temp_repo.save_run(run, findings=[final_finding])

    stored = temp_repo.get_persisted_findings(analysis_id)
    assert [item.finding_id for item in stored] == ["find_final"]
    assert temp_repo.get_run(analysis_id)["status"] == "executive_synthesis"
