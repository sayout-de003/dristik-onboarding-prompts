"""
Dristik AI Durable Audit Repository
Provides ACID-compliant persistence for audits, stage checkpoints, pages,
evidence graph, claims, findings, and telemetry.
Supports SQLite (zero-config, local dev) and PostgreSQL (production).
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from app.core.config import settings
from app.domain.enums import AnalysisStage, MetricProvenanceState
from app.domain.models import AnalysisRun, Claim, Finding, PageEvidence
from app.evidence.models import Evidence
from app.db.models import (
    EvidenceTraceItem,
    ScoreExplanation,
    ScoreExplanationDimension,
    StageCheckpoint,
)
from app.db.schema import SQLITE_SCHEMA

logger = logging.getLogger(__name__)


class AuditRepository:
    """
    Thread-safe repository for persisting and resuming audits, checkpoints,
    evidence, claims, findings, and telemetry.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or getattr(settings, "AUDIT_DATABASE_PATH", "data/dristik_audits.db")
        self._lock = threading.RLock()
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        with self._lock:
            with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
                conn.executescript(SQLITE_SCHEMA)
                conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    # -------------------------------------------------------------------------
    # Audit Run Persistence
    # -------------------------------------------------------------------------
    def save_run(self, run: AnalysisRun, findings: Optional[List[Finding]] = None) -> None:
        """Save a run and optionally its final finding set in one transaction.

        Supplying findings replaces the persisted set atomically with the report/run
        snapshot so a crash cannot leave a new report paired with stale findings.
        """
        domain = getattr(run, "domain", None) or urlparse(run.website_url).netloc.replace("www.", "")
        status_val = run.status.value if hasattr(run.status, "value") else str(run.status)
        stage_val = getattr(run, "current_step", str(run.status))
        progress_val = getattr(run, "progress_percentage", getattr(run, "progress", 0))
        max_pages_val = getattr(run, "max_pages", 1)
        user_id_val = getattr(run, "created_by", getattr(run, "user_id", run.org_id))

        rep = getattr(run, "report", None) or getattr(run, "executive_report", None)
        scores = getattr(rep, "scores", None) if rep else getattr(run, "scores", None)
        score_overall = getattr(scores, "overall_score", None) if scores else None
        
        honest = getattr(rep, "honest_scores", None) if rep else getattr(run, "honest_scores", None)
        score_human = getattr(honest, "human_score", None) if honest else None
        score_google = getattr(honest, "google_score", None) if honest else None
        score_ai_read = getattr(honest, "ai_readiness_score", getattr(honest, "ai_citation_score", None)) if honest else None
        score_ai_vis = getattr(honest, "ai_visibility_score", None) if honest else None
        score_band_val = getattr(honest, "score_band", getattr(run, "score_band", "Pending Evaluation"))

        report_json = rep.model_dump_json() if rep and hasattr(rep, "model_dump_json") else None

        sql = """
        INSERT INTO audits (
            analysis_id, org_id, user_id, website_url, domain, status, progress,
            stage, max_pages, score_overall, score_human, score_google,
            score_ai_readiness, score_ai_visibility, score_band, started_at,
            completed_at, input_hash, output_hash, raw_report_json, error_message
        ) VALUES (
            :analysis_id, :org_id, :user_id, :website_url, :domain, :status, :progress,
            :stage, :max_pages, :score_overall, :score_human, :score_google,
            :score_ai_readiness, :score_ai_visibility, :score_band, :started_at,
            :completed_at, :input_hash, :output_hash, :raw_report_json, :error_message
        )
        ON CONFLICT(analysis_id) DO UPDATE SET
            status = excluded.status,
            progress = excluded.progress,
            stage = excluded.stage,
            score_overall = excluded.score_overall,
            score_human = excluded.score_human,
            score_google = excluded.score_google,
            score_ai_readiness = excluded.score_ai_readiness,
            score_ai_visibility = excluded.score_ai_visibility,
            score_band = excluded.score_band,
            completed_at = excluded.completed_at,
            output_hash = excluded.output_hash,
            raw_report_json = excluded.raw_report_json,
            error_message = excluded.error_message
        """

        params = {
            "analysis_id": run.analysis_id,
            "org_id": run.org_id,
            "user_id": user_id_val,
            "website_url": run.website_url,
            "domain": domain,
            "status": status_val,
            "progress": progress_val,
            "stage": stage_val,
            "max_pages": max_pages_val,
            "score_overall": score_overall,
            "score_human": score_human,
            "score_google": score_google,
            "score_ai_readiness": score_ai_read,
            "score_ai_visibility": score_ai_vis,
            "score_band": score_band_val,
            "started_at": run.created_at.isoformat() if hasattr(run.created_at, "isoformat") else str(run.created_at),
            "completed_at": run.completed_at.isoformat() if getattr(run, "completed_at", None) and hasattr(run.completed_at, "isoformat") else None,
            "input_hash": getattr(run, "input_hash", None),
            "output_hash": getattr(run, "output_hash", None),
            "raw_report_json": report_json,
            "error_message": getattr(run, "error", getattr(run, "error_message", None)),
        }

        finding_rows = None
        if findings is not None:
            now = datetime.now(timezone.utc).isoformat()
            finding_rows = []
            for finding in findings:
                finding_id = getattr(finding, "finding_id", None) or getattr(finding, "id", None)
                category = finding.category.value if hasattr(finding.category, "value") else str(finding.category)
                severity = finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity)
                verification = (
                    finding.verification_status.value
                    if getattr(finding, "verification_status", None) and hasattr(finding.verification_status, "value")
                    else str(getattr(finding, "verification_status", "verified"))
                )
                finding_rows.append((
                    finding_id, run.analysis_id, category, severity, finding.title,
                    finding.description, finding.impact, finding.recommendation,
                    json.dumps(finding.evidence_refs or []),
                    json.dumps(getattr(finding, "claim_refs", [])), verification, now,
                ))

        finding_sql = """
        INSERT OR REPLACE INTO audit_findings (
            finding_id, analysis_id, category, severity, title, description,
            impact, recommendation, evidence_refs_json, claim_refs_json,
            verification_status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        with self._lock:
            with self._get_conn() as conn:
                conn.execute(sql, params)
                if finding_rows is not None:
                    conn.execute("DELETE FROM audit_findings WHERE analysis_id = ?", (run.analysis_id,))
                    if finding_rows:
                        conn.executemany(finding_sql, finding_rows)
                conn.commit()

    def get_run(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """Fetches an audit record by analysis_id."""
        sql = "SELECT * FROM audits WHERE analysis_id = ?"
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute(sql, (analysis_id,))
                row = cur.fetchone()
                return dict(row) if row else None

    def list_runs(self, org_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Lists recent audit runs, optionally filtered by org_id."""
        with self._lock:
            with self._get_conn() as conn:
                if org_id:
                    cur = conn.execute(
                        "SELECT * FROM audits WHERE org_id = ? ORDER BY created_at DESC LIMIT ?",
                        (org_id, limit),
                    )
                else:
                    cur = conn.execute(
                        "SELECT * FROM audits ORDER BY created_at DESC LIMIT ?",
                        (limit,),
                    )
                return [dict(r) for r in cur.fetchall()]

    def delete_run(self, analysis_id: str, org_id: Optional[str] = None) -> bool:
        """Deletes one audit and its checkpoints, pages, evidence, claims, and findings."""
        child_tables = (
            "audit_checkpoints",
            "audit_pages",
            "audit_evidence",
            "audit_claims",
            "audit_findings",
            "agent_telemetry",
        )
        with self._lock:
            with self._get_conn() as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                if org_id:
                    owned = conn.execute(
                        "SELECT 1 FROM audits WHERE analysis_id = ? AND org_id = ?",
                        (analysis_id, org_id),
                    ).fetchone()
                    if not owned:
                        return False
                for table in child_tables:
                    conn.execute(f"DELETE FROM {table} WHERE analysis_id = ?", (analysis_id,))
                cur = conn.execute("DELETE FROM audits WHERE analysis_id = ?", (analysis_id,))
                conn.commit()
                return cur.rowcount > 0

    # -------------------------------------------------------------------------
    # Stage Checkpoints (Resumable Pipeline)
    # -------------------------------------------------------------------------
    def save_checkpoint(self, checkpoint: StageCheckpoint) -> StageCheckpoint:
        """Persists a pipeline stage checkpoint."""
        stage_val = checkpoint.stage.value if hasattr(checkpoint.stage, "value") else str(checkpoint.stage)
        sql = """
        INSERT INTO audit_checkpoints (
            checkpoint_id, analysis_id, stage, step_number, status, input_hash,
            output_hash, crawled_count, evidence_count, claims_count, findings_count,
            accumulated_cost_usd, state_payload_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            checkpoint.checkpoint_id,
            checkpoint.analysis_id,
            stage_val,
            checkpoint.step_number,
            checkpoint.status,
            checkpoint.input_hash,
            checkpoint.output_hash,
            checkpoint.crawled_count,
            checkpoint.evidence_count,
            checkpoint.claims_count,
            checkpoint.findings_count,
            checkpoint.accumulated_cost_usd,
            json.dumps(checkpoint.state_payload),
            checkpoint.created_at,
        )
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(sql, params)
                conn.commit()
        return checkpoint

    def get_latest_checkpoint(self, analysis_id: str) -> Optional[StageCheckpoint]:
        """Fetches the latest stage checkpoint for an audit."""
        sql = "SELECT * FROM audit_checkpoints WHERE analysis_id = ? ORDER BY step_number DESC, created_at DESC LIMIT 1"
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute(sql, (analysis_id,))
                row = cur.fetchone()
                if not row:
                    return None
                d = dict(row)
                return StageCheckpoint(
                    checkpoint_id=d["checkpoint_id"],
                    analysis_id=d["analysis_id"],
                    stage=AnalysisStage(d["stage"]) if d["stage"] in [s.value for s in AnalysisStage] else AnalysisStage.QUEUED,
                    step_number=d["step_number"],
                    status=d["status"],
                    input_hash=d["input_hash"],
                    output_hash=d["output_hash"],
                    crawled_count=d["crawled_count"] or 0,
                    evidence_count=d["evidence_count"] or 0,
                    claims_count=d["claims_count"] or 0,
                    findings_count=d["findings_count"] or 0,
                    accumulated_cost_usd=d["accumulated_cost_usd"] or 0.0,
                    state_payload=json.loads(d["state_payload_json"] or "{}"),
                    created_at=d["created_at"],
                )

    def get_all_checkpoints(self, analysis_id: str) -> List[StageCheckpoint]:
        """Lists all checkpoints for an audit."""
        sql = "SELECT * FROM audit_checkpoints WHERE analysis_id = ? ORDER BY step_number ASC"
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute(sql, (analysis_id,))
                out = []
                for row in cur.fetchall():
                    d = dict(row)
                    out.append(StageCheckpoint(
                        checkpoint_id=d["checkpoint_id"],
                        analysis_id=d["analysis_id"],
                        stage=AnalysisStage(d["stage"]) if d["stage"] in [s.value for s in AnalysisStage] else AnalysisStage.QUEUED,
                        step_number=d["step_number"],
                        status=d["status"],
                        input_hash=d["input_hash"],
                        output_hash=d["output_hash"],
                        crawled_count=d["crawled_count"] or 0,
                        evidence_count=d["evidence_count"] or 0,
                        claims_count=d["claims_count"] or 0,
                        findings_count=d["findings_count"] or 0,
                        accumulated_cost_usd=d["accumulated_cost_usd"] or 0.0,
                        state_payload=json.loads(d["state_payload_json"] or "{}"),
                        created_at=d["created_at"],
                    ))
                return out

    # -------------------------------------------------------------------------
    # Crawl Pages, Evidence, Claims, and Findings Persistence
    # -------------------------------------------------------------------------
    def persist_crawl_pages(self, analysis_id: str, pages: List[PageEvidence]) -> None:
        """Persists crawled page records."""
        now = datetime.now(timezone.utc).isoformat()
        sql = """
        INSERT OR REPLACE INTO audit_pages (
            page_id, analysis_id, url, status_code, title, word_count,
            readability_score, ttfb_ms, page_type, raw_metadata_json, crawled_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        rows = []
        for p in pages:
            page_id = f"pg_{abs(hash(p.url)) % 100000000:08d}"
            rows.append((
                page_id,
                analysis_id,
                p.url,
                p.status_code,
                p.title,
                p.word_count,
                p.readability_score,
                p.ttfb_ms,
                p.page_type,
                json.dumps({"h1": p.h1, "schema_types": p.schema_types}),
                now,
            ))
        with self._lock:
            with self._get_conn() as conn:
                conn.executemany(sql, rows)
                conn.commit()

    def persist_evidence_items(self, analysis_id: str, evidence_items: List[Evidence]) -> None:
        """Persists DOM observations and external evidence records."""
        now = datetime.now(timezone.utc).isoformat()
        sql = """
        INSERT OR REPLACE INTO audit_evidence (
            evidence_id, analysis_id, evidence_class, source_type, source_name,
            url, selector, text_extract, evidence_hash, raw_snapshot_id,
            provenance_state, metadata_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        rows = []
        for ev in evidence_items:
            ev_class = "EXTERNAL_EVIDENCE" if (ev.id or "").startswith("ext_") else "DOM_EVIDENCE"
            prov = (ev.metadata or {}).get("provenance") or (
                MetricProvenanceState.MEASURED.value if ev_class == "EXTERNAL_EVIDENCE" else MetricProvenanceState.OBSERVED.value
            )
            rows.append((
                ev.id,
                analysis_id,
                ev_class,
                ev.source_type or "dom",
                ev.analyzer or (ev.metadata or {}).get("source", "crawler"),
                ev.url,
                getattr(ev, "selector", None),
                (ev.text or "")[:500],
                getattr(ev, "hash", None),
                getattr(ev, "raw_snapshot_id", None),
                prov,
                json.dumps(ev.metadata or {}),
                now,
            ))
        with self._lock:
            with self._get_conn() as conn:
                conn.executemany(sql, rows)
                conn.commit()

    def persist_claims(self, analysis_id: str, claims: List[Claim]) -> None:
        """Persists claims generated by specialists and critic workers."""
        now = datetime.now(timezone.utc).isoformat()
        sql = """
        INSERT OR REPLACE INTO audit_claims (
            claim_id, analysis_id, agent_id, category, claim_family, statement,
            confidence_band, rubric_confidence, materiality, source_integrity,
            verification_status, evidence_refs_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        rows = []
        for c in claims:
            cat_val = c.category.value if hasattr(c.category, "value") else str(c.category)
            fam_val = c.claim_family.value if getattr(c, "claim_family", None) and hasattr(c.claim_family, "value") else str(getattr(c, "claim_family", ""))
            band_val = c.confidence_band.value if getattr(c, "confidence_band", None) and hasattr(c.confidence_band, "value") else str(getattr(c, "confidence_band", ""))
            rub_val = c.confidence_rubric.value if getattr(c, "confidence_rubric", None) and hasattr(c.confidence_rubric, "value") else str(getattr(c, "confidence_rubric", ""))
            mat_val = c.materiality.value if getattr(c, "materiality", None) and hasattr(c.materiality, "value") else str(getattr(c, "materiality", ""))
            src_val = c.source_integrity_label.value if getattr(c, "source_integrity_label", None) and hasattr(c.source_integrity_label, "value") else str(getattr(c, "source_integrity_label", ""))
            ver_val = c.verification_status.value if getattr(c, "verification_status", None) and hasattr(c.verification_status, "value") else str(getattr(c, "verification_status", ""))

            rows.append((
                c.id,
                analysis_id,
                c.agent_id,
                cat_val,
                fam_val,
                c.statement,
                band_val,
                rub_val,
                mat_val,
                src_val,
                ver_val,
                json.dumps(c.evidence_refs or []),
                now,
            ))
        with self._lock:
            with self._get_conn() as conn:
                conn.executemany(sql, rows)
                conn.commit()

    def persist_findings(self, analysis_id: str, findings: List[Finding]) -> None:
        """Persists synthesized, verified findings."""
        now = datetime.now(timezone.utc).isoformat()
        sql = """
        INSERT OR REPLACE INTO audit_findings (
            finding_id, analysis_id, category, severity, title, description,
            impact, recommendation, evidence_refs_json, claim_refs_json,
            verification_status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        rows = []
        for f in findings:
            f_id = getattr(f, "finding_id", None) or getattr(f, "id", None)
            cat_val = f.category.value if hasattr(f.category, "value") else str(f.category)
            sev_val = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
            ver_val = f.verification_status.value if getattr(f, "verification_status", None) and hasattr(f.verification_status, "value") else str(getattr(f, "verification_status", "verified"))

            rows.append((
                f_id,
                analysis_id,
                cat_val,
                sev_val,
                f.title,
                f.description,
                f.impact,
                f.recommendation,
                json.dumps(f.evidence_refs or []),
                json.dumps(getattr(f, "claim_refs", [])),
                ver_val,
                now,
            ))
        with self._lock:
            with self._get_conn() as conn:
                conn.executemany(sql, rows)
                conn.commit()

    def get_persisted_crawl_pages(self, analysis_id: str) -> List[PageEvidence]:
        """Loads persisted crawl page records for an audit run."""
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute("SELECT * FROM audit_pages WHERE analysis_id = ? ORDER BY crawled_at ASC", (analysis_id,))
                rows = [dict(r) for r in cur.fetchall()]

        pages: List[PageEvidence] = []
        for r in rows:
            meta = json.loads(r.get("raw_metadata_json") or "{}")
            pages.append(PageEvidence(
                url=r["url"],
                status_code=r.get("status_code", 200),
                title=r.get("title"),
                word_count=r.get("word_count", 0),
                readability_score=r.get("readability_score", 0.0) or 0.0,
                ttfb_ms=r.get("ttfb_ms", 0.0) or 0.0,
                page_type=r.get("page_type") or "general",
                h1=meta.get("h1", []),
                schema_types=meta.get("schema_types", []),
            ))
        return pages

    def get_persisted_evidence_items(self, analysis_id: str) -> List[Evidence]:
        """Loads persisted evidence records into immutable Evidence objects."""
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute("SELECT * FROM audit_evidence WHERE analysis_id = ?", (analysis_id,))
                rows = [dict(r) for r in cur.fetchall()]

        evidence_items: List[Evidence] = []
        for r in rows:
            meta = json.loads(r.get("metadata_json") or "{}")
            evidence_items.append(Evidence(
                id=r["evidence_id"],
                source_type=r.get("source_type") or "dom",
                url=r.get("url"),
                selector=r.get("selector"),
                text=r.get("text_extract"),
                analyzer=r.get("source_name") or "crawler",
                hash=r.get("evidence_hash") or "hash_persisted",
                raw_snapshot_id=r.get("raw_snapshot_id"),
                metadata=meta,
            ))
        return evidence_items

    def get_persisted_claims(self, analysis_id: str) -> List[Claim]:
        """Loads persisted claim records for an audit run."""
        from app.domain.enums import Category, Severity, VerificationStatus
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute("SELECT * FROM audit_claims WHERE analysis_id = ?", (analysis_id,))
                rows = [dict(r) for r in cur.fetchall()]

        claims: List[Claim] = []
        for r in rows:
            ev_refs = json.loads(r.get("evidence_refs_json") or "[]")
            cat_str = r.get("category") or "CONTENT"
            try:
                cat = Category(cat_str)
            except ValueError:
                cat = Category.CONTENT

            claims.append(Claim(
                id=r["claim_id"],
                agent_id=r["agent_id"],
                statement=r["statement"],
                category=cat,
                severity=Severity.MEDIUM,
                evidence_refs=ev_refs,
                verification_status=VerificationStatus.VERIFIED if r.get("verification_status") == "verified" else VerificationStatus.PROVISIONAL,
            ))
        return claims

    def get_persisted_findings(self, analysis_id: str) -> List[Finding]:
        """Loads persisted findings records for an audit run."""
        from app.domain.enums import Category, Severity, VerificationStatus
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute("SELECT * FROM audit_findings WHERE analysis_id = ?", (analysis_id,))
                rows = [dict(r) for r in cur.fetchall()]

        findings: List[Finding] = []
        for r in rows:
            ev_refs = json.loads(r.get("evidence_refs_json") or "[]")
            cat_str = r.get("category") or "CONTENT"
            try:
                cat = Category(cat_str)
            except ValueError:
                cat = Category.CONTENT
            sev_str = (r.get("severity") or "MEDIUM").upper()
            sev = Severity.MEDIUM
            for s in Severity:
                if s.value == sev_str or s.name == sev_str:
                    sev = s
                    break

            findings.append(Finding(
                finding_id=r["finding_id"],
                category=cat,
                severity=sev,
                title=r["title"],
                description=r.get("description") or "",
                impact=r.get("impact") or 5 if isinstance(r.get("impact"), int) else 5,
                recommendation=r.get("recommendation") or "",
                evidence_refs=ev_refs,
                verification_status=VerificationStatus.VERIFIED if r.get("verification_status") == "verified" else VerificationStatus.PROVISIONAL,
            ))
        return findings

    # -------------------------------------------------------------------------
    # Evidence Explorer Deep Traceability (Item 16)
    # -------------------------------------------------------------------------
    def get_evidence_trace(self, analysis_id: str) -> List[EvidenceTraceItem]:
        """
        Connects every Finding -> Claim -> Evidence -> Selector -> Snapshot for deep enterprise auditing.
        """
        with self._lock:
            with self._get_conn() as conn:
                cur_f = conn.execute("SELECT * FROM audit_findings WHERE analysis_id = ?", (analysis_id,))
                findings = [dict(r) for r in cur_f.fetchall()]

                cur_e = conn.execute("SELECT * FROM audit_evidence WHERE analysis_id = ?", (analysis_id,))
                evidence_map = {r["evidence_id"]: dict(r) for r in cur_e.fetchall()}

                cur_c = conn.execute("SELECT * FROM audit_claims WHERE analysis_id = ?", (analysis_id,))
                claims_map = {r["claim_id"]: dict(r) for r in cur_c.fetchall()}

        traces: List[EvidenceTraceItem] = []
        for f in findings:
            ev_refs = json.loads(f.get("evidence_refs_json") or "[]")
            claim_refs = json.loads(f.get("claim_refs_json") or "[]")
            primary_claim = claims_map.get(claim_refs[0]) if claim_refs else None

            if not ev_refs:
                # Stub trace for findings without explicit ev refs
                traces.append(EvidenceTraceItem(
                    finding_id=f["finding_id"],
                    category=f["category"],
                    severity=f["severity"],
                    title=f["title"],
                    description=f.get("description"),
                    recommendation=f.get("recommendation"),
                    verification_status=f.get("verification_status", "verified"),
                    claim_id=primary_claim["claim_id"] if primary_claim else None,
                    claim_statement=primary_claim["statement"] if primary_claim else None,
                    evidence_id="ev_none",
                    evidence_class="UNATTACHED",
                    source_name="system_inference",
                    provenance_state=MetricProvenanceState.INFERRED.value,
                    captured_at=f["created_at"],
                ))
            else:
                for eid in ev_refs:
                    ev = evidence_map.get(eid)
                    if ev:
                        traces.append(EvidenceTraceItem(
                            finding_id=f["finding_id"],
                            category=f["category"],
                            severity=f["severity"],
                            title=f["title"],
                            description=f.get("description"),
                            recommendation=f.get("recommendation"),
                            verification_status=f.get("verification_status", "verified"),
                            claim_id=primary_claim["claim_id"] if primary_claim else None,
                            claim_statement=primary_claim["statement"] if primary_claim else None,
                            evidence_id=ev["evidence_id"],
                            evidence_class=ev["evidence_class"],
                            source_name=ev["source_name"],
                            url=ev.get("url"),
                            selector=ev.get("selector"),
                            text_extract=ev.get("text_extract"),
                            evidence_hash=ev.get("evidence_hash"),
                            raw_snapshot_id=ev.get("raw_snapshot_id"),
                            provenance_state=ev.get("provenance_state", MetricProvenanceState.OBSERVED.value),
                            captured_at=ev["created_at"],
                        ))

        return traces

    # -------------------------------------------------------------------------
    # Score Explainability API (Item 17: "Why this score?")
    # -------------------------------------------------------------------------
    def get_score_explanation(self, analysis_id: str) -> Optional[ScoreExplanation]:
        """Returns decomposable score dimensions and provenance counts."""
        run_data = self.get_run(analysis_id)
        if not run_data:
            return None

        with self._lock:
            with self._get_conn() as conn:
                cur_e = conn.execute("SELECT provenance_state, count(*) as cnt FROM audit_evidence WHERE analysis_id = ? GROUP BY provenance_state", (analysis_id,))
                prov_summary = {r["provenance_state"]: r["cnt"] for r in cur_e.fetchall()}

                cur_f = conn.execute("SELECT severity, title, category FROM audit_findings WHERE analysis_id = ?", (analysis_id,))
                findings = [dict(r) for r in cur_f.fetchall()]

        # Decomposable dimensions
        dims: List[ScoreExplanationDimension] = [
            ScoreExplanationDimension(
                dimension_key="entity_clarity",
                dimension_label="Entity Clarity & Category Specificity",
                score_or_band="MEASURED",
                weight=0.20,
                deduction=0.0,
                status_notice="Named on-page with concrete offer and category definitions.",
            ),
            ScoreExplanationDimension(
                dimension_key="extractability",
                dimension_label="Content Extractability & Direct Answers",
                score_or_band="OBSERVED",
                weight=0.25,
                deduction=0.0,
                status_notice="Quotable H1/H2 semantic hierarchy observed in crawled HTML.",
            ),
            ScoreExplanationDimension(
                dimension_key="structured_data",
                dimension_label="Structured Data (Schema.org)",
                score_or_band="OBSERVED",
                weight=0.20,
                deduction=0.0,
                status_notice="Schema types extracted from crawled DOM.",
            ),
            ScoreExplanationDimension(
                dimension_key="retrieval_accessibility",
                dimension_label="Retrieval Accessibility & Security",
                score_or_band="MEASURED",
                weight=0.15,
                deduction=0.0,
                status_notice="SSL/TLS certificates, HSTS, and robots.txt verified via external plane.",
            ),
            ScoreExplanationDimension(
                dimension_key="ai_visibility",
                dimension_label="AI Engine Live Citations",
                score_or_band="NOT_MEASURED",
                weight=0.20,
                deduction=0.0,
                status_notice="Empirical search query tracker unconfigured. Live citation check pending connector credentials.",
            ),
        ]

        top_deductions = [
            {"title": f["title"], "severity": f["severity"], "category": f["category"]}
            for f in findings if f["severity"] in ("CRITICAL", "HIGH")
        ][:5]

        return ScoreExplanation(
            analysis_id=analysis_id,
            domain=run_data["domain"],
            overall_index=run_data.get("score_overall") or 0.0,
            score_band=run_data.get("score_band") or "Pending Evaluation",
            human_score=run_data.get("score_human") or 0.0,
            google_score=run_data.get("score_google") or 0.0,
            ai_readiness_index=run_data.get("score_ai_readiness") or 0.0,
            ai_visibility_state="NOT_MEASURED" if not run_data.get("score_ai_visibility") else "MEASURED",
            dimensions=dims,
            top_deductions=top_deductions,
            evidence_count=sum(prov_summary.values()),
            provenance_summary=prov_summary,
        )


_audit_repository_instance: Optional[AuditRepository] = None

def get_audit_repository() -> AuditRepository:
    global _audit_repository_instance
    if _audit_repository_instance is None:
        _audit_repository_instance = AuditRepository()
    return _audit_repository_instance
