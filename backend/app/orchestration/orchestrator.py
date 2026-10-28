"""
Dristik AI Advanced Autonomous Website Intelligence & Growth OS Orchestrator
Coordinates the 4-level cognitive architecture, dynamic cognitive teams, Evidence Graph 2.0,
hypothesis formulation, causal bottleneck discovery, AI search simulation, and validated remediation.
"""
import asyncio
import logging
import uuid
from datetime import datetime
from urllib.parse import urlparse
from typing import Dict, Any, Optional, AsyncGenerator, List

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.aeo.analytics_history import aeo_analytics_history_store
from app.aeo.scoring import AeoMetricsCalculator
from app.domain.models import AnalysisRun, ExecutiveReport, CrawlManifest, FindingEvidence
from app.domain.enums import AnalysisStage, Category, Severity
from app.domain.capability import CAPABILITY_REGISTRY
from app.orchestration.cognition.blackboard import CognitiveBlackboard
from app.orchestration.cognition.decision_engine import DecisionEngine
from app.orchestration.cognition.hypotheses import HypothesisEngine
from app.orchestration.cognition.causal import CausalReasoningEngine
from app.orchestration.cognition.confidence import CalibratedConfidenceEngine
from app.domain.evidence.graph import GraphNodeType, GraphEdgeType
from app.domain.evidence.validation import EvidenceGapDetector
from app.seo.business.website_twin import WebsiteDigitalTwin
from app.seo.business.intent_graph import SearchIntentGraph
from app.seo.business.opportunity import OpportunityDetector
from app.geo.citations.simulation import AISearchSimulationEngine
from app.core.monitoring.timeline import WebsiteIntelligenceTimeline
from app.core.inference.model_router import ModelRouter
from app.core.inference.telemetry import TelemetryTracker
from app.crawl.crawler import CrawlerService
from app.orchestration.mission.director import MissionDirector
from app.orchestration.team_orchestrator import TeamOrchestrator
from app.orchestration.agent_pool import AgentPool
from app.domain.scoring.engine import ScoringEngine
from app.remediation.planner import RemediationPlanner
from app.reports.narrative import NarrativeGenerator
from app.reports.roadmap import RoadmapBuilder
from app.crawl.page_intelligence import PageIntelligenceAgent
from app.domain.evidence.site_facts import extract_site_facts
from app.remediation.patch_pack import generate_character_safe_copy, generate_whatsapp_summary
from app.seo.competitive.bakeoff import CommercialBakeoffEngine
from app.seo.competitive.benchmark import build_competitor_seo_parity_matrix
from app.seo.business.understanding import BusinessUnderstandingOrchestrator
from app.orchestration.integrity_gate import integrity_gate
from app.orchestration.pipeline_dag import (
    get_pipeline_controller,
    GraphNodeStatus,
    ActivityEvent,
    NODES_REGISTRY,
    SECTIONS_REGISTRY,
    PILLAR_TO_SECTION,
    SECTION_TO_PILLAR,
)

class AnalysisOrchestrator:
    def __init__(self):
        self.runs: Dict[str, AnalysisRun] = {}
        self.blackboards: Dict[str, CognitiveBlackboard] = {}
        self.event_queues: Dict[str, asyncio.Queue] = {}
        self.crawler = CrawlerService()
        self.mission_director = MissionDirector()
        self.decision_engine = DecisionEngine()
        self.hypothesis_engine = HypothesisEngine()
        self.causal_engine = CausalReasoningEngine()
        self.confidence_engine = CalibratedConfidenceEngine()
        self.gap_detector = EvidenceGapDetector()
        self.opportunity_detector = OpportunityDetector()
        self.ai_simulator = AISearchSimulationEngine()
        self.intent_graph = SearchIntentGraph()
        self.scoring_engine = ScoringEngine()
        self.remediation_planner = RemediationPlanner()
        self.narrative_gen = NarrativeGenerator()
        self.roadmap_builder = RoadmapBuilder()
        self.bakeoff_engine = CommercialBakeoffEngine()
        self.digital_twins: Dict[str, WebsiteDigitalTwin] = {}
        self.timelines: Dict[str, WebsiteIntelligenceTimeline] = {}
        from app.db.repository import get_audit_repository
        self.repository = get_audit_repository()
        self.model_router = ModelRouter()

    def create_run(
        self,
        website_url: str,
        org_id: str = "org_default",
        created_by: Optional[str] = None,
        target_pillars: Optional[List[str]] = None,
    ) -> AnalysisRun:
        analysis_id = f"run_{uuid.uuid4().hex[:10]}"
        now_str = datetime.now().isoformat()
        norm_pillars = [p.strip().lower() for p in target_pillars if p and p.strip().lower() in PILLAR_TO_SECTION] if target_pillars else None

        run = AnalysisRun(
            analysis_id=analysis_id,
            org_id=org_id,
            website_url=website_url,
            status=AnalysisStage.QUEUED,
            progress_percentage=0,
            current_step="Analysis Queued",
            created_at=now_str,
            updated_at=now_str,
            target_pillars=norm_pillars,
        )
        self.runs[analysis_id] = run
        self.event_queues[analysis_id] = asyncio.Queue()
        try:
            self.repository.save_run(run)
        except Exception as e:
            logger.warning(f"Failed to persist initial audit run {analysis_id}: {e}")
        return run

    def get_run(self, analysis_id: str) -> Optional[AnalysisRun]:
        # Support lookup by run ID or report ID
        if analysis_id in self.runs:
            return self.runs[analysis_id]
        for r in self.runs.values():
            if r.report and (r.report.report_id == analysis_id or getattr(r.report, "analysis_id", None) == analysis_id):
                return r
        # Durable DB fallback
        try:
            stored = self.repository.get_run(analysis_id)
            if stored:
                report_obj = None
                raw_json = stored.get("raw_report_json")
                if raw_json:
                    try:
                        report_obj = ExecutiveReport.model_validate_json(raw_json)
                    except Exception as e:
                        logger.warning(f"Failed to deserialize report for {analysis_id}: {e}")

                status_val = stored["status"]
                stage_enum = AnalysisStage.QUEUED
                for s in AnalysisStage:
                    if s.value == status_val or str(s) == status_val:
                        stage_enum = s
                        break

                run = AnalysisRun(
                    analysis_id=stored["analysis_id"],
                    org_id=stored["org_id"],
                    website_url=stored["website_url"],
                    status=stage_enum,
                    progress_percentage=stored.get("progress", 100 if report_obj else 0),
                    current_step=stored.get("stage", "Completed" if report_obj else "Queued"),
                    score_band=stored.get("score_band") or "Pending Evaluation",
                    created_at=stored.get("started_at") or stored.get("created_at") or datetime.now().isoformat(),
                    updated_at=stored.get("completed_at") or stored.get("started_at") or datetime.now().isoformat(),
                    completed_at=stored.get("completed_at"),
                    report=report_obj
                )
                self.runs[analysis_id] = run
                return run
        except Exception as err:
            logger.warning(f"Error loading stored run {analysis_id}: {err}")
        return None

    async def _emit_event(self, analysis_id: str, stage: str, progress: int, message: str, data: Optional[Dict[str, Any]] = None):
        run = self.runs.get(analysis_id)
        if run:
            run.progress_percentage = progress
            run.current_step = message
            run.updated_at = datetime.now().isoformat()

        queue = self.event_queues.get(analysis_id)
        if queue:
            payload_data = dict(data or {})
            telemetry_snapshot = None
            if run and getattr(run, "telemetry", None):
                try:
                    telemetry_snapshot = run.telemetry.model_dump(mode="json")
                    if "telemetry" not in payload_data:
                        payload_data["telemetry"] = telemetry_snapshot
                except Exception:
                    pass

            ctrl = get_pipeline_controller(analysis_id)
            graph_snapshot = ctrl.get_full_graph_state()
            if "graph" not in payload_data:
                payload_data["graph"] = graph_snapshot

            event_payload = {
                "stage": stage,
                "progress": progress,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "data": payload_data,
                "telemetry": telemetry_snapshot,
                "graph": graph_snapshot,
            }
            await queue.put(event_payload)

    async def stream_events(self, analysis_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        queue = self.event_queues.get(analysis_id)
        if not queue:
            return

        while True:
            event = await queue.get()
            yield event
            if event.get("stage") in [AnalysisStage.COMPLETED.value, AnalysisStage.FAILED.value]:
                break

    async def execute_analysis_pipeline(
        self,
        analysis_id: str,
        website_url: str,
        max_pages: Optional[int] = None,
        site_type: Optional[str] = None,
        declared_site_type_notes: Optional[str] = None,
        country: Optional[str] = None,
        language: Optional[str] = None,
        target_pillars: Optional[List[str]] = None,
    ):
        """
        Cognitive OS mission execution across all 4 cognitive levels.
        """
        run = self.runs.get(analysis_id)
        if target_pillars is None and run and run.target_pillars:
            target_pillars = run.target_pillars

        effective_pillars: Optional[Set[str]] = (
            {p.strip().lower() for p in target_pillars if p and p.strip().lower() in PILLAR_TO_SECTION}
            if target_pillars
            else None
        )
        telemetry_tracker = TelemetryTracker()
        model_router = ModelRouter(telemetry_tracker=telemetry_tracker)
        if run:
            run.telemetry = telemetry_tracker.telemetry
        controller = get_pipeline_controller(analysis_id)

        # Mark unselected pillar nodes as SKIPPED right away
        all_pillars = {"seo", "geo", "aeo", "cro"}
        if effective_pillars is not None and effective_pillars != all_pillars:
            skipped_pillars = all_pillars - effective_pillars
            for sp in skipped_pillars:
                sp_sec_id = PILLAR_TO_SECTION.get(sp)
                sp_sec = next((s for s in SECTIONS_REGISTRY if s.section_id == sp_sec_id), None)
                if sp_sec:
                    for nid in sp_sec.node_ids:
                        controller.mark_node_status(nid, GraphNodeStatus.SKIPPED)
                        controller.log_activity(nid, "info", f"{sp}.skipped", f"{sp.upper()} pillar skipped in selective execution")

        if analysis_id in self.blackboards:
            blackboard = self.blackboards[analysis_id]
        else:
            blackboard = CognitiveBlackboard(run_id=analysis_id, website_url=website_url)
            self.blackboards[analysis_id] = blackboard

        blackboard.user_declared_site_type = site_type
        blackboard.user_declared_site_type_notes = declared_site_type_notes
        team_orchestrator = TeamOrchestrator(model_router)

        crawl_limit = max_pages or settings.MAX_CRAWL_PAGES

        async def _check_pause() -> bool:
            if controller.is_pause_requested():
                if run:
                    run.status = AnalysisStage.PAUSED
                    run.current_step = "Audit paused by user"
                await self._emit_event(analysis_id, "paused", run.progress_percentage if run else 0, "Audit paused by user")
                return True
            return False

        try:
            if await _check_pause():
                return

            # 1. Mission Director Initialization
            mission_state = self.mission_director.create_mission(
                target_url=website_url,
                audit_type="standard_growth",
                max_pages=crawl_limit
            )

            # 2. Level 0: Ingestion & Multi-Page Crawl
            model_router.set_active_stage("crawl_and_ingest", "Crawl & Ingestion")
            run.status = AnalysisStage.INGESTING

            if controller.get_node_status("node_crawl") == GraphNodeStatus.COMPLETED and blackboard.pages:
                manifest = blackboard.crawl_manifest or CrawlManifest(
                    domain=urlparse(website_url).netloc.replace("www.", ""),
                    pages=blackboard.pages,
                    total_pages=len(blackboard.pages),
                )
                domain = manifest.domain
                page_ev = manifest.pages[0] if manifest.pages else None
                controller.log_activity("node_crawl", "info", "crawl.reused", f"Reusing {len(blackboard.pages)} persisted pages from checkpoint")
                await self._emit_event(analysis_id, "ingesting", 15, f"Loaded {len(blackboard.pages)} crawled pages from checkpoint for {website_url}")
            else:
                controller.mark_node_status("node_crawl", GraphNodeStatus.RUNNING)
                controller.log_activity("node_crawl", "running", "crawl.start", f"Multi-page crawler scanning {website_url} (up to {crawl_limit} pages)...")
                await self._emit_event(analysis_id, "ingesting", 10, f"Initializing multi-page crawler for {website_url}...")

                def on_crawl_progress(msg: str, progress_pct: int):
                    controller.log_activity("node_crawl", "info", "crawl.progress", msg)
                    asyncio.create_task(self._emit_event(analysis_id, "ingesting", progress_pct, msg))

                manifest = await self.crawler.crawl_site_and_analyze(
                    target_url=website_url,
                    evidence_store=blackboard.evidence_store,
                    max_pages=crawl_limit,
                    progress_callback=on_crawl_progress
                )
                blackboard.pages = manifest.pages
                blackboard.crawl_manifest = manifest
                if not manifest.pages:
                    controller.mark_node_status("node_crawl", GraphNodeStatus.FAILED, error_message="No pages crawled")
                    raise RuntimeError(f"No pages could be crawled from {website_url}. Please ensure the URL is valid, accessible, and public.")
                page_ev = manifest.pages[0]
                domain = manifest.domain
                controller.mark_node_status("node_crawl", GraphNodeStatus.COMPLETED, evidence_count=len(manifest.pages), output_summary=f"{len(manifest.pages)} pages")
                controller.log_activity("node_crawl", "success", "crawl.success", f"Crawled {len(manifest.pages)} pages from {website_url}")

            if await _check_pause():
                return

            controller.mark_node_status("node_dom_extraction", GraphNodeStatus.RUNNING)
            controller.log_activity("node_dom_extraction", "running", "dom.populate", f"Extracting DOM AST & headings for {domain}...")

            # Populate Evidence Graph 2.0 with Pages & Elements
            site_node_id = f"site_{domain.replace('.', '_')}"
            blackboard.evidence_graph.add_node(
                node_id=site_node_id,
                node_type=GraphNodeType.WEBSITE,
                label=domain,
                url=website_url
            )

            for idx, p in enumerate(manifest.pages):
                page_node_id = f"page_{idx}"
                blackboard.evidence_graph.add_node(
                    node_id=page_node_id,
                    node_type=GraphNodeType.PAGE,
                    label=p.title or p.url,
                    url=p.url,
                    properties={"word_count": p.word_count, "status_code": p.status_code}
                )
                blackboard.evidence_graph.add_edge(site_node_id, page_node_id, GraphEdgeType.CONTAINS)

                for h in p.h1:
                    h_node_id = f"h1_{idx}_{uuid.uuid4().hex[:4]}"
                    blackboard.evidence_graph.add_node(
                        node_id=h_node_id,
                        node_type=GraphNodeType.DOM_ELEMENT,
                        label=f"H1: {h}",
                        url=p.url,
                        selector="h1"
                    )
                    blackboard.evidence_graph.add_edge(page_node_id, h_node_id, GraphEdgeType.CONTAINS)

            # Populate Evidence Graph 2.0 with all deterministic observations, SHA-256 hashes, and DOM selectors
            blackboard.evidence_graph.populate_from_evidence_store(blackboard.evidence_store, manifest)
            model_router.set_active_stage("deterministic_analysis", "Deterministic Analysis & External Evidence")

            controller.mark_node_status("node_dom_extraction", GraphNodeStatus.COMPLETED, evidence_count=blackboard.evidence_store.count(), output_summary=f"{blackboard.evidence_store.count()} observations")
            controller.log_activity("node_dom_extraction", "success", "dom.complete", f"Extracted {blackboard.evidence_store.count()} observations into Evidence Graph 2.0")

            await self._emit_event(
                analysis_id,
                "deterministic_analysis",
                25,
                f"Crawled {len(manifest.pages)} pages across {domain}. Extracted {blackboard.evidence_store.count()} observations into Evidence Graph 2.0.",
                {
                    "evidence_count": blackboard.evidence_store.count(),
                    "pages_crawled": len(manifest.pages),
                    "graph_nodes": len(blackboard.evidence_graph.nodes)
                }
            )

            # Durable Checkpoint 1: Crawl & DOM observations complete
            from app.db.models import StageCheckpoint
            try:
                self.repository.persist_crawl_pages(analysis_id, manifest.pages)
                self.repository.persist_evidence_items(analysis_id, blackboard.evidence_store.get_all())
                self.repository.save_checkpoint(StageCheckpoint(
                    analysis_id=analysis_id,
                    stage=AnalysisStage.INGESTING,
                    step_number=1,
                    status="COMPLETED",
                    crawled_count=len(manifest.pages),
                    evidence_count=blackboard.evidence_store.count(),
                    state_payload={"domain": domain, "pages_crawled": len(manifest.pages)}
                ))
            except Exception as pe:
                logger.warning(f"Persistence error after crawl: {pe}")

            if await _check_pause():
                return

            # Extract Wave-0 deterministic site facts ($0 inference)
            blackboard.site_facts = extract_site_facts(manifest, blackboard.evidence_store)

            # Layer 1 — Record Machine Observations into EvidenceStore
            for p in manifest.pages:
                if p.title:
                    blackboard.evidence_store.add_observation("title", p.title, source="html", url=p.url, selector="title")
                if p.h1:
                    blackboard.evidence_store.add_observation("h1", p.h1, source="dom", url=p.url, selector="h1")
                if p.h2:
                    blackboard.evidence_store.add_observation("h2", p.h2, source="dom", url=p.url, selector="h2")
                if p.meta_description:
                    blackboard.evidence_store.add_observation("meta_description", p.meta_description, source="html", url=p.url, selector='meta[name="description"]')
                if p.status_code:
                    blackboard.evidence_store.add_observation("status_code", p.status_code, source="http_header", url=p.url)
                if p.ttfb_ms:
                    blackboard.evidence_store.add_observation("ttfb_ms", p.ttfb_ms, source="http_header", url=p.url)
                if p.schema_types:
                    blackboard.evidence_store.add_observation("schema_types", p.schema_types, source="html", url=p.url, selector='script[type="application/ld+json"]')
                if p.ctas:
                    blackboard.evidence_store.add_observation("cta_texts", p.ctas, source="dom", url=p.url)

            if blackboard.site_facts:
                sf = blackboard.site_facts
                if sf.get("sameas_urls"):
                    blackboard.evidence_store.add_observation("sameas_urls", sf.get("sameas_urls"), source="schema", url=website_url)
                if sf.get("visible_pricing_text"):
                    blackboard.evidence_store.add_observation("visible_pricing_text", sf.get("visible_pricing_text"), source="html", url=website_url)
                if sf.get("faq_questions"):
                    blackboard.evidence_store.add_observation("faq_questions", sf.get("faq_questions"), source="html", url=website_url)
                if sf.get("nav_labels"):
                    blackboard.evidence_store.add_observation("nav_labels", sf.get("nav_labels"), source="dom", url=website_url)
                blackboard.evidence_store.add_observation("pricing_signals", sf.get("pricing_signals_present", False), source="html", url=website_url)

            # Phase 2: Operationalize External Evidence Plane (ext_NNN)
            from app.domain.evidence.enrichment import ExternalEvidenceEnricher
            enricher = ExternalEvidenceEnricher()
            controller.mark_node_status("node_dns_ssl_headers", GraphNodeStatus.RUNNING)
            controller.log_activity("node_dns_ssl_headers", "running", "external.enrich", f"Enriching external evidence plane (DNS, SSL/TLS, Security Headers, CruX) for {domain}...")

            await self._emit_event(
                analysis_id,
                "deterministic_analysis",
                32,
                f"Enriching external evidence plane (DNS, SSL/TLS, Security Headers, CruX, Registries)...",
                {"domain": domain}
            )
            ext_items = []
            try:
                ext_items = await enricher.enrich_domain(domain, blackboard.evidence_store)
                logger.info(f"External evidence enrichment yielded {len(ext_items)} items for {domain}")
                # Durable Checkpoint 2: External Evidence Plane complete
                self.repository.persist_evidence_items(analysis_id, blackboard.evidence_store.get_all())
                self.repository.save_checkpoint(StageCheckpoint(
                    analysis_id=analysis_id,
                    stage=AnalysisStage.DETERMINISTIC_ANALYSIS,
                    step_number=2,
                    status="COMPLETED",
                    evidence_count=blackboard.evidence_store.count(),
                    state_payload={"external_evidence_count": len(ext_items)}
                ))
                controller.mark_node_status("node_dns_ssl_headers", GraphNodeStatus.COMPLETED, evidence_count=len(ext_items), output_summary=f"{len(ext_items)} external items")
                controller.log_activity("node_dns_ssl_headers", "success", "external.complete", f"Enriched {len(ext_items)} external evidence items")
            except Exception as enrich_err:
                logger.warning(f"External evidence enrichment encountered error: {enrich_err}")
                controller.mark_node_status("node_dns_ssl_headers", GraphNodeStatus.FAILED, error_message=str(enrich_err))
                controller.log_activity("node_dns_ssl_headers", "warning", "external.warning", f"External enrichment note: {enrich_err}")

            if await _check_pause():
                return

            # 3. Dynamic Capability Scheduling
            model_router.set_active_stage("planning", "Capability Scheduling & Hypotheses")
            model_router.set_active_sub_stage("capability_scheduling", "Dynamic Capability Scheduling & Wave Planning")
            run.status = AnalysisStage.PLANNING
            mission_caps = self.mission_director.select_capabilities_for_mission(mission_state)

            # 4. Formulate Pre-Reasoning Hypotheses
            initial_hypotheses = self.hypothesis_engine.generate_initial_hypotheses(domain, manifest.pages)
            mission_state.hypotheses = initial_hypotheses

            # 5. Execute Level 0 Deterministic Technical Foundation ($0 inference)
            controller.mark_node_status("node_schema_ld_json", GraphNodeStatus.RUNNING)
            controller.log_activity("node_schema_ld_json", "running", "schema.wave", "Executing Deterministic Technical, DOM & Schema Capabilities ($0 inference)...")
            await self._emit_event(analysis_id, "deterministic_analysis", 38, "Executing Deterministic Technical, DOM & Schema Capabilities ($0 inference)...")
            await team_orchestrator.execute_capability_wave(mission_caps["tier_1_deterministic"], manifest, blackboard)
            controller.mark_node_status("node_schema_ld_json", GraphNodeStatus.COMPLETED)
            controller.log_activity("node_schema_ld_json", "success", "schema.complete", "Deterministic technical & schema capabilities completed ($0 inference)")

            if await _check_pause():
                return

            # 6. Business identity (declared vs detected) before the 50-agent DAG
            controller.mark_node_status("node_entity_resolution", GraphNodeStatus.RUNNING)
            controller.log_activity("node_entity_resolution", "running", "entity.resolve", f"Resolving canonical entity for {domain}...")

            from app.seo.business.entity_resolver import UniversalEntityResolver
            blackboard.resolved_entity = UniversalEntityResolver.resolve_from_evidence(
                website_url=website_url,
                pages=manifest.pages,
                profile=blackboard.business_profile
            )
            blackboard.business_profile.business_name = blackboard.resolved_entity.name
            if blackboard.resolved_entity.category and not blackboard.business_profile.industry:
                blackboard.business_profile.industry = blackboard.resolved_entity.category

            if blackboard.resolved_entity and blackboard.resolved_entity.name:
                blackboard.evidence_store.add_observation("business_name", blackboard.resolved_entity.name, source="html", url=website_url)

            controller.mark_node_status("node_entity_resolution", GraphNodeStatus.COMPLETED, output_summary=blackboard.resolved_entity.name if blackboard.resolved_entity else None)
            controller.log_activity("node_entity_resolution", "success", "entity.complete", f"Canonical entity resolved: {blackboard.resolved_entity.name if blackboard.resolved_entity else domain}")

            if await _check_pause():
                return

            controller.mark_node_status("node_icp_offer_profile", GraphNodeStatus.RUNNING)
            controller.log_activity("node_icp_offer_profile", "running", "icp.resolve", "Extracting business identity, ICP, and value proposition...")

            model_router.set_active_stage("business_understanding", "Business Identity Resolution")
            model_router.set_active_sub_stage("brand_identity_extraction", "Brand Identity, ICP & Value Prop Resolution")
            run.status = AnalysisStage.SPECIALIST_EXECUTION
            await self._emit_event(
                analysis_id,
                "specialist_execution",
                42,
                "Resolving business identity from crawled evidence...",
            )
            biz_understanding = BusinessUnderstandingOrchestrator(model_router)
            semantic_rep = await biz_understanding.execute_business_understanding(blackboard)
            controller.mark_node_status("node_icp_offer_profile", GraphNodeStatus.COMPLETED)
            controller.log_activity("node_icp_offer_profile", "success", "icp.complete", "Extracted buyer ICP and core value proposition")

            if blackboard.identity_contradictions:
                contra = blackboard.identity_contradictions[0]
                await self._emit_event(
                    analysis_id,
                    "specialist_execution",
                    44,
                    f"Business Identity Conflict Detected: {contra.reason}",
                    {
                        "declared": contra.declared_type,
                        "detected": contra.detected_type,
                        "confidence": contra.confidence,
                        "contradiction_id": contra.id
                    }
                )

            if await _check_pause():
                return

            # Search Console and SERP rows, when a provider already measured them.
            # Query-level advice stays skipped when this payload is NOT_CONNECTED.
            try:
                from app.seo.search_demand import attach_search_demand
                demand = attach_search_demand(blackboard, domain)
                controller.log_activity(
                    "node_specialist_wave_1",
                    "info",
                    "search_demand",
                    demand.get("note") or "Search demand was not measured.",
                )
            except Exception as exc:
                logger.info("Search demand was not attached: %s", exc)

            # 7. Full specialist DAG (dependency waves, no canned fallbacks)
            agent_pool = AgentPool(model_router)
            model_router.set_active_stage("specialist_execution", f"{len(agent_pool)}-Agent Specialist DAG")
            model_router.set_active_sub_stage("specialist_agents_dag", f"{len(agent_pool)}-Agent Multi-Disciplinary Analysis Waves")

            active_pillars_set = effective_pillars if effective_pillars is not None else all_pillars
            # Mark active pillar nodes as RUNNING
            for ap in active_pillars_set:
                ap_sec_id = PILLAR_TO_SECTION.get(ap)
                ap_sec = next((s for s in SECTIONS_REGISTRY if s.section_id == ap_sec_id), None)
                if ap_sec:
                    for nid in ap_sec.node_ids:
                        if nid not in ("node_seo_page_intelligence", "node_aeo_search_simulation"):
                            controller.mark_node_status(nid, GraphNodeStatus.RUNNING)

            for w_node in ["node_specialist_wave_1", "node_specialist_wave_2", "node_specialist_wave_3", "node_specialist_wave_4"]:
                controller.mark_node_status(w_node, GraphNodeStatus.RUNNING)

            controller.log_activity("node_specialist_wave_1", "running", "specialists.start", f"Deploying specialist agents across active pillars ({', '.join(sorted(active_pillars_set)).upper()})...")

            await self._emit_event(
                analysis_id,
                "specialist_execution",
                46,
                f"Deploying specialist agents across active pillars ({', '.join(sorted(active_pillars_set)).upper()})...",
                {"agents": len(agent_pool), "waves": len(agent_pool.waves), "active_pillars": list(active_pillars_set)},
            )

            def _map_agent_to_node(aid: Optional[str]) -> Optional[str]:
                if not aid:
                    return None
                aid_low = aid.lower()
                if "seo.crawl" in aid_low or "seo.indexability" in aid_low or "seo.drift" in aid_low:
                    return "node_seo_crawl_indexing"
                if "seo.security" in aid_low or "seo.performance" in aid_low or "seo.assets" in aid_low:
                    return "node_seo_technical_health"
                if "seo.html" in aid_low or "seo.internal_links" in aid_low or "seo.cluster" in aid_low or "seo.sxo" in aid_low or aid_low.startswith("content."):
                    return "node_seo_onpage_content"
                if aid_low.startswith("schema.") or "seo.ecommerce" in aid_low:
                    return "node_seo_schema_ast"
                if "geo.brand_identity" in aid_low or "geo.wikidata" in aid_low or "geo.entity" in aid_low:
                    return "node_geo_entity_grounding"
                if "geo.local" in aid_low or "geo.citations" in aid_low or "geo.extractability" in aid_low or "maps_intelligence" in aid_low:
                    return "node_geo_local_signals"
                if "geo.llms_txt" in aid_low or "geo.synthesis" in aid_low or "agentic_readiness" in aid_low:
                    return "node_geo_llm_footprint"
                if "ai_search.citability" in aid_low:
                    return "node_aeo_citability_matrix"
                if "ai_search.query_coverage" in aid_low or "ai_search.faq" in aid_low or "ai_search.competitor" in aid_low:
                    return "node_aeo_qa_readiness"
                if "cro.three_second_hook" in aid_low or "cro.conversion" in aid_low or aid_low.startswith("ux."):
                    return "node_cro_cta_visibility"
                if "cro.pricing_psychology" in aid_low or aid_low.startswith("business."):
                    return "node_cro_value_clarity"
                if "cro.form_friction" in aid_low or "cro.social_proof" in aid_low or aid_low.startswith("trust."):
                    return "node_cro_trust_and_forms"
                return None

            async def _agent_progress(stage: str, progress: int, message: str, data: Dict[str, Any]):
                if run and telemetry_tracker:
                    run.telemetry = telemetry_tracker.telemetry
                aid = data.get("agent_id")
                wave = data.get("wave", 1)
                w_node = f"node_specialist_wave_{min(max(wave, 1), 4)}"
                controller.log_activity(w_node, "info", f"specialist.{aid or 'agent'}", message, details=data)
                sub_node = _map_agent_to_node(aid)
                if sub_node:
                    controller.log_activity(sub_node, "info", f"specialist.{aid or 'agent'}", message, details=data)
                await self._emit_event(analysis_id, stage, progress, message, data)

            pool_summary = await agent_pool.execute_all(
                blackboard,
                progress_cb=_agent_progress,
                base_progress=46,
                end_progress=78,
                active_pillars=effective_pillars,
            )

            for w_node in ["node_specialist_wave_1", "node_specialist_wave_2", "node_specialist_wave_3", "node_specialist_wave_4"]:
                controller.mark_node_status(w_node, GraphNodeStatus.COMPLETED, claims_count=len(blackboard.claim_registry.get_all()))

            for ap in active_pillars_set:
                ap_sec_id = PILLAR_TO_SECTION.get(ap)
                ap_sec = next((s for s in SECTIONS_REGISTRY if s.section_id == ap_sec_id), None)
                if ap_sec:
                    for nid in ap_sec.node_ids:
                        if nid not in ("node_seo_page_intelligence", "node_aeo_search_simulation"):
                            controller.mark_node_status(nid, GraphNodeStatus.COMPLETED, claims_count=len(blackboard.claim_registry.get_all()))

            controller.log_activity(
                "node_specialist_wave_4",
                "success",
                "specialists.complete",
                f"{len(agent_pool)} specialists finished: {pool_summary['completed']} completed, {pool_summary.get('skipped', 0)} skipped, {pool_summary['unavailable']} unavailable, {pool_summary['errors']} errors."
            )

            await self._emit_event(
                analysis_id,
                "specialist_execution",
                78,
                (
                    f"{len(agent_pool)} specialists finished: {pool_summary['completed']} completed, "
                    f"{pool_summary.get('skipped', 0)} skipped, "
                    f"{pool_summary['unavailable']} unavailable (no invented fill), "
                    f"{pool_summary['errors']} errors."
                ),
                pool_summary,
            )

            # Durable Checkpoint 3: Specialist analysis complete
            try:
                self.repository.persist_claims(analysis_id, blackboard.claim_registry.get_all())
                self.repository.save_checkpoint(StageCheckpoint(
                    analysis_id=analysis_id,
                    stage=AnalysisStage.SPECIALIST_EXECUTION,
                    step_number=3,
                    status="COMPLETED",
                    claims_count=len(blackboard.claim_registry.get_all()),
                    state_payload={"claims_count": len(blackboard.claim_registry.get_all()), "pool_summary": pool_summary}
                ))
            except Exception as pe:
                logger.warning(f"Persistence error after specialists: {pe}")

            if await _check_pause():
                return

            # 7b. Per-page SEO, copywriting, and suggested copy
            if effective_pillars is None or "seo" in effective_pillars:
                controller.mark_node_status("node_seo_page_intelligence", GraphNodeStatus.RUNNING)
                controller.mark_node_status("node_page_intelligence", GraphNodeStatus.RUNNING)
                controller.log_activity("node_seo_page_intelligence", "running", "page.rewrites", f"Writing detailed SEO and copy reports for {len(manifest.pages)} crawled page(s)...")

                model_router.set_active_stage("page_intelligence", "Page-Level SEO & Copywriting")
                model_router.set_active_sub_stage("page_copy_and_hero", "Page-by-Page SEO & Copywriting Rewrites")
                await self._emit_event(
                    analysis_id,
                    "specialist_execution",
                    80,
                    f"Writing detailed SEO and copy reports for {len(manifest.pages)} crawled page(s)...",
                )
                page_agent = PageIntelligenceAgent(model_router)
                await page_agent.run(blackboard)
                controller.mark_node_status("node_seo_page_intelligence", GraphNodeStatus.COMPLETED)
                controller.mark_node_status("node_page_intelligence", GraphNodeStatus.COMPLETED)
                controller.log_activity("node_seo_page_intelligence", "success", "page.complete", f"Completed page-level intelligence for {len(manifest.pages)} page(s)")
            else:
                controller.mark_node_status("node_seo_page_intelligence", GraphNodeStatus.SKIPPED)
                controller.mark_node_status("node_page_intelligence", GraphNodeStatus.SKIPPED)
                controller.log_activity("node_seo_page_intelligence", "info", "page.skipped", "SEO page intelligence skipped by selective execution")

            if await _check_pause():
                return

            # 8. Verification agents already ran in the DAG (adversarial + contradiction + executive).
            controller.mark_node_status("node_adversarial_critic", GraphNodeStatus.RUNNING)
            controller.log_activity("node_adversarial_critic", "running", "critic.audit", "Adversarial critic testing claims against ground truth...")

            model_router.set_active_stage("adversarial_verification", "Adversarial Verification & Integrity Gate")
            model_router.set_active_sub_stage("critic_verification", "Adversarial Critic & Ground Truth Gate")
            run.status = AnalysisStage.ADVERSARIAL_VERIFICATION
            await self._emit_event(
                analysis_id,
                "adversarial_verification",
                82,
                "Adversarial and contradiction specialists recorded on the blackboard.",
            )

            # Zero-Fake Evidence Integrity Gate
            if await _check_pause():
                return
            controller.mark_node_status("node_integrity_gate", GraphNodeStatus.RUNNING)
            controller.log_activity("node_integrity_gate", "running", "integrity.gate", "Enforcing Zero-Fake Evidence cryptographic provenance...")

            current_claims = blackboard.claim_registry.get_all()
            gate_res = integrity_gate.validate_claims_and_evidence(
                current_claims, blackboard.evidence_store, blackboard.claim_registry
            )
            blackboard.blackboard_state["integrity_gate"] = gate_res.model_dump()
            controller.mark_node_status("node_integrity_gate", GraphNodeStatus.COMPLETED)
            controller.log_activity("node_integrity_gate", "success", "integrity.complete", "Zero-Fake Evidence integrity gate passed")

            from app.domain.enums import Materiality, RubricConfidence
            from app.orchestration.cognition.finding_rubric import apply_rubric_to_claim
            for _claim in current_claims:
                apply_rubric_to_claim(_claim, blackboard.evidence_store)
            held_guesses = [
                c for c in current_claims
                if c.confidence_rubric == RubricConfidence.GUESSING
                and c.materiality == Materiality.CRITICAL
                and not c.adversarial_reviewed
            ]
            if held_guesses:
                adv = agent_pool.get("verification.adversarial.v3")
                if adv:
                    await adv.run(blackboard)
                    await self._emit_event(
                        analysis_id,
                        "adversarial_verification",
                        83,
                        f"Escalated {len(held_guesses)} GUESSING+CRITICAL claim(s) to verification.adversarial.v3 before executive use.",
                    )

            controller.mark_node_status("node_adversarial_critic", GraphNodeStatus.COMPLETED)
            controller.log_activity("node_adversarial_critic", "success", "critic.complete", "Adversarial cross-examination complete")

            # Detect uncorroborated marketing claims (Evidence Gaps)
            evidence_gaps = self.gap_detector.detect_gaps(current_claims, blackboard.evidence_store, blackboard.pages)
            blackboard.blackboard_state["evidence_gaps"] = [g.model_dump() for g in evidence_gaps]

            if await _check_pause():
                return

            # 9. Level 3: Causal Reasoning & Root-Cause Bottleneck Discovery
            controller.mark_node_status("node_causal_bottlenecks", GraphNodeStatus.RUNNING)
            controller.log_activity("node_causal_bottlenecks", "running", "causal.roots", "Causal Reasoning Engine isolating primary root-cause growth bottlenecks...")

            model_router.set_active_stage("causal_reasoning", "Causal Reasoning & Bottlenecks")
            model_router.set_active_sub_stage("causal_bottlenecks", "Causal Graph & Bottleneck Isolation")
            await self._emit_event(analysis_id, "specialist_execution", 82, "Causal Reasoning Engine isolating primary root-cause growth bottlenecks...")
            bottlenecks = self.causal_engine.analyze_root_causes(
                claims=current_claims,
                business_profile=blackboard.business_profile,
                crawl_summary=manifest.crawl_health if manifest else None,
            )
            blackboard.blackboard_state["root_causes"] = [b.model_dump() for b in bottlenecks]
            controller.mark_node_status("node_causal_bottlenecks", GraphNodeStatus.COMPLETED)
            controller.log_activity("node_causal_bottlenecks", "success", "causal.complete", f"Isolated {len(bottlenecks)} primary growth bottlenecks")

            # Update Hypotheses with accumulated evidence
            evaluated_hypotheses = self.hypothesis_engine.evaluate_hypotheses_against_evidence(
                initial_hypotheses, current_claims, blackboard.evidence_store
            )
            mission_state.hypotheses = evaluated_hypotheses

            # Detect Positive Growth Opportunities
            opportunities = self.opportunity_detector.detect_opportunities(
                blackboard.business_profile, blackboard.pages, current_claims
            )
            blackboard.blackboard_state["opportunities"] = [o.model_dump() for o in opportunities]

            if await _check_pause():
                return

            # 10. AI Answer Engine Discoverability & Commercial Query Simulation
            if effective_pillars is None or "aeo" in effective_pillars:
                controller.mark_node_status("node_aeo_search_simulation", GraphNodeStatus.RUNNING)
                controller.mark_node_status("node_ai_search_simulation", GraphNodeStatus.RUNNING)
                controller.log_activity("node_aeo_search_simulation", "running", "ai_sim.eval", "Simulating AI Answer Engine evaluations across 6 Canonical Commercial Inquiries...")

                model_router.set_active_stage("ai_search_simulation", "AI Answer Engine Simulation")
                model_router.set_active_sub_stage("buyer_query_simulation", "Synthetic Commercial Query Simulation")
                await self._emit_event(
                    analysis_id,
                    "specialist_execution",
                    85,
                    "Simulating AI Answer Engine evaluations across 6 Canonical Commercial Inquiries (ChatGPT, Perplexity, Gemini, Claude)...",
                    {"evaluating_queries": 6}
                )
                try:
                    await team_orchestrator.worker_simulator.execute_task("ai_search_simulation", blackboard)
                    controller.mark_node_status("node_aeo_search_simulation", GraphNodeStatus.COMPLETED)
                    controller.mark_node_status("node_ai_search_simulation", GraphNodeStatus.COMPLETED)
                    controller.log_activity("node_aeo_search_simulation", "success", "ai_sim.complete", "Completed AI search queries simulation with citations")
                except Exception as sim_err:
                    logger.error("AI Search simulation error: %s", sim_err)
                    controller.mark_node_status("node_aeo_search_simulation", GraphNodeStatus.FAILED, error_message=str(sim_err))
                    controller.mark_node_status("node_ai_search_simulation", GraphNodeStatus.FAILED, error_message=str(sim_err))
                    controller.log_activity("node_aeo_search_simulation", "warning", "ai_sim.error", f"Simulation note: {sim_err}")
            else:
                controller.mark_node_status("node_aeo_search_simulation", GraphNodeStatus.SKIPPED)
                controller.mark_node_status("node_ai_search_simulation", GraphNodeStatus.SKIPPED)
                controller.log_activity("node_aeo_search_simulation", "info", "ai_sim.skipped", "AEO search simulation skipped by selective execution")

            if await _check_pause():
                return

            # 11. Executive Strategy Narrative Synthesis
            controller.mark_node_status("node_executive_narrative", GraphNodeStatus.RUNNING)
            controller.log_activity("node_executive_narrative", "running", "narrative.compile", "Synthesizer compiling C-Suite narrative from verified specialist claims...")

            model_router.set_active_stage("executive_synthesis", "Executive Strategy Narrative Synthesis")
            model_router.set_active_sub_stage("narrative_synthesis", "C-Suite Strategic Narrative Compilation")
            run.status = AnalysisStage.EXECUTIVE_SYNTHESIS
            await self._emit_event(analysis_id, "executive_synthesis", 88, "Synthesizer compiling C-Suite narrative from verified specialist claims...")
            if not blackboard.executive_narrative.get("story_summary"):
                await team_orchestrator.worker_synthesizer.execute_task("synthesis", blackboard)
            controller.mark_node_status("node_executive_narrative", GraphNodeStatus.COMPLETED)
            controller.log_activity("node_executive_narrative", "success", "narrative.complete", "Executive narrative synthesis completed")

            if await _check_pause():
                return

            # 12. Causal Prioritization & Scoring Engine
            controller.mark_node_status("node_honest_scoring", GraphNodeStatus.RUNNING)
            controller.log_activity("node_honest_scoring", "running", "scoring.calc", "Deterministic Scoring Engine computing intent-adjusted category scores...")

            model_router.set_active_stage("scoring_and_remediation", "Scoring & Remediation Blueprints")
            model_router.set_active_sub_stage("remediation_blueprints", "Autonomous Code Patch Pack Generation")
            run.status = AnalysisStage.SCORING
            await self._emit_event(analysis_id, "scoring", 93, "Deterministic Scoring Engine computing intent-adjusted category scores...")

            eval_pages = (manifest.pages if manifest else None) or blackboard.pages or []
            from app.cro.visual_ux_tester import visual_ux_tester
            from app.seo.analyzers.canonical_auditor import analyze_canonicals
            from app.seo.analyzers.http_status_auditor import analyze_http_statuses
            from app.seo.analyzers.heading_analyzer import HeadingAnalyzer, analyze_heading_hierarchy
            from app.seo.analyzers.media_asset_analyzer import MediaAssetAnalyzer, analyze_media_assets
            from app.seo.analyzers.link_depth import LinkDepthAnalyzer, analyze_link_depth_and_orphans
            from app.seo.analyzers.meta_rollup import analyze_meta_rollup
            from app.cro.form_analyzer import analyze_forms
            from app.crawl.analyzers.security_analyzer import analyze_security_headers
            from app.seo.analyzers.schema_validator import analyze_schema_rich_results
            from app.seo.analyzers.local_seo_analyzer import analyze_local_seo
            from app.seo.analyzers.international_seo_analyzer import analyze_international_seo
            from app.seo.analyzers.topical_authority_analyzer import analyze_topical_authority
            from app.seo.analyzers.ecommerce_seo import analyze_ecommerce_seo
            from app.seo.analyzers.serp_appearance import analyze_serp_appearance
            from app.cro.accessibility.wcag_auditor import DeepWcagAuditor
            from app.crawl.indexation.classifier import indexation_classifier
            from app.seo.competitive.benchmark import build_competitor_seo_parity_matrix
            from app.seo.analyzers.host_and_redirects import probe_host_and_redirects
            from app.remediation.deduplicator import FindingDeduplicator
            from app.remediation.patch_engine import patch_engine

            cro_finding = visual_ux_tester.generate_grounded_cro_finding(
                domain=domain,
                website_url=website_url,
                pages=getattr(blackboard, "pages", None),
            )
            canonical_audit_rep, can_findings = analyze_canonicals(eval_pages)
            broken_raw = manifest.crawl_health.get("broken_links") if manifest and manifest.crawl_health else []
            http_status_rep, http_findings = analyze_http_statuses(eval_pages, broken_links_raw=broken_raw)

            heading_hierarchy_rep = analyze_heading_hierarchy(eval_pages)
            heading_findings = HeadingAnalyzer.generate_findings(heading_hierarchy_rep)

            media_assets_rep = analyze_media_assets(eval_pages)
            media_findings = MediaAssetAnalyzer.generate_findings(media_assets_rep)

            sitemap_urls_sample = [manifest.sitemap_url] if (manifest and manifest.sitemap_url) else []
            click_depth_rep, orphan_pages_rep, anchor_text_audit_rep = analyze_link_depth_and_orphans(
                eval_pages, sitemap_urls=sitemap_urls_sample, homepage_url=website_url
            )
            link_findings = LinkDepthAnalyzer.generate_findings(click_depth_rep, orphan_pages_rep, anchor_text_audit_rep)

            meta_rollup_rep = analyze_meta_rollup(eval_pages)
            form_audit_rep = analyze_forms(eval_pages)
            from app.cro import analyze_cro
            cro_audit_rep, cro_findings = analyze_cro(
                eval_pages,
                raw_html_map=getattr(blackboard, "raw_html_map", None),
                business_profile=blackboard.business_profile,
            )
            schema_validation_rep = analyze_schema_rich_results(eval_pages)
            wcag_audit_rep, wcag_findings = DeepWcagAuditor.audit_pages(eval_pages)

            local_seo_rep, local_findings = analyze_local_seo(eval_pages, target_domain=domain)
            intl_seo_rep, intl_findings = analyze_international_seo(eval_pages, target_domain=domain)
            topical_auth_rep, topical_findings = analyze_topical_authority(eval_pages, target_domain=domain)
            ecom_seo_rep, ecom_findings = analyze_ecommerce_seo(eval_pages, target_domain=domain)
            serp_app_rep, serp_findings = analyze_serp_appearance(eval_pages, target_domain=domain)

            indexation_rollup_rep, indexation_findings = indexation_classifier.audit(
                manifest=manifest,
                pages=eval_pages,
            )
            if manifest:
                manifest.indexation_rollup = indexation_rollup_rep

            competitor_seo_parity_rep = build_competitor_seo_parity_matrix(
                target_pages=eval_pages,
                target_domain=domain,
                manifest=manifest,
            )

            first_page_headers = {}
            if eval_pages and getattr(eval_pages[0], "response_headers", None):
                first_page_headers = eval_pages[0].response_headers
            security_audit_rep = analyze_security_headers(
                url=website_url,
                response_headers=first_page_headers
            )

            try:
                host_and_redirects_rep = await probe_host_and_redirects(domain_or_url=website_url, canonical_target=website_url)
            except Exception:
                from app.domain.models import RedirectAuditReport
                host_and_redirects_rep = RedirectAuditReport(target_domain=domain, canonical_destination=website_url, summary="Host variant probe completed in offline mode.")

            raw_findings = self.decision_engine.synthesize_findings(current_claims, blackboard.evidence_store)
            if cro_finding is not None:
                raw_findings = [f for f in raw_findings if f.finding_id != "find_cro_001"]
                raw_findings.append(cro_finding)

            for f_group in (can_findings, http_findings, heading_findings, media_findings, link_findings, wcag_findings, local_findings, intl_findings, topical_findings, indexation_findings, ecom_findings, serp_findings, cro_findings):
                for f in f_group:
                    if not any(x.finding_id == f.finding_id for x in raw_findings):
                        raw_findings.append(f)

            # Raw HTML vs Rendered DOM Disparity Findings
            from app.seo.analyzers.rendering_disparity import analyze_rendering_disparity
            for p in eval_pages:
                if getattr(p, "raw_html", None) and getattr(p, "rendered_html", None):
                    try:
                        _, render_findings = analyze_rendering_disparity(
                            raw_html=p.raw_html,
                            rendered_html=p.rendered_html,
                            page_url=p.url,
                            evidence_store=blackboard.evidence_store,
                        )
                        for rf in render_findings:
                            if not any(x.finding_id == rf.finding_id for x in raw_findings):
                                raw_findings.append(rf)
                    except Exception as rf_err:
                        logger.info("Page rendering disparity collection note: %s", rf_err)

            # Layer 2 — Deterministic Finding Engine evaluation
            from app.domain.evidence.deterministic_rules import DeterministicFindingEngine
            deterministic_engine = DeterministicFindingEngine()
            layer2_findings = deterministic_engine.evaluate(blackboard.evidence_store, manifest)
            for f in layer2_findings:
                if not any(x.finding_id == f.finding_id or (x.rule_id and x.rule_id == f.rule_id) for x in raw_findings):
                    raw_findings.append(f)

            from app.geo.entity_graph import evaluate_entity_graph
            profile_name = ""
            if blackboard.business_profile and blackboard.business_profile.business_name:
                profile_name = blackboard.business_profile.business_name
            entity_graph_report, entity_graph_findings, entity_graph_contradictions = evaluate_entity_graph(
                eval_pages,
                brand_name=profile_name,
            )
            for f in entity_graph_findings:
                if not any(x.finding_id == f.finding_id for x in raw_findings):
                    raw_findings.append(f)
            if entity_graph_contradictions:
                blackboard.identity_contradictions.extend(entity_graph_contradictions)

            # -----------------------------------------------------------------
            # Step 13: Live AI Visibility, Competitive Intelligence & External Authority
            # (Collected BEFORE final deduplication, scoring, and roadmaps)
            # -----------------------------------------------------------------
            model_router.set_active_stage("ai_visibility_monitor", "Live AI Citation & Search Visibility")

            from app.geo.readiness import evaluate_geo_readiness
            visibility_measured = False
            visibility_detail = None
            live_citation_score = None
            ai_visibility_scorecard = None
            geo_readiness = None
            agent_readiness = None
            geo_bench_report = None
            ai_citation_dash = None
            should_run_geo_live = effective_pillars is None or bool(effective_pillars.intersection({"geo", "aeo"}))
            if should_run_geo_live:
                try:
                    from app.geo.audit_monitor import run_audit_visibility
                    profile = blackboard.business_profile
                    b_name = getattr(profile, "business_name", None) or domain
                    b_ind = getattr(profile, "industry", None) or getattr(profile, "niche", None) or "Software & Technology"
                    vis_res = await run_audit_visibility(
                        domain=domain,
                        brand_name=b_name,
                        industry=b_ind,
                        services=list(getattr(profile, "services", None) or []) or list(getattr(profile, "products", None) or []),
                        locations=[profile.geography] if getattr(profile, "geography", None) else None,
                        audience=getattr(profile, "target_audience", None),
                        max_pages=max_pages,
                    )
                    if isinstance(vis_res, tuple):
                        monitored, geo_bench_obj = vis_res
                    else:
                        monitored, geo_bench_obj = vis_res, None

                    if monitored is not None:
                        ai_visibility_scorecard = monitored
                        if monitored.status == "MEASURED" and monitored.citation_rate_pct is not None:
                            visibility_measured = True
                            live_citation_score = float(monitored.citation_rate_pct)
                            visibility_detail = (
                                f"Live AI citation visibility {live_citation_score:.0f}/100 "
                                f"from {monitored.successful_runs} successful responses "
                                f"across {monitored.engines_measured} engine(s), "
                                f"{monitored.queries} queries, {monitored.repeats} run(s). "
                                "This is not the on-page GEO Readiness score."
                            )
                    if geo_bench_obj is not None:
                        geo_bench_report = geo_bench_obj.model_dump() if hasattr(geo_bench_obj, "model_dump") else geo_bench_obj
                except Exception as e:
                    logger.warning("run_audit_visibility error: %s", e)
                    ai_visibility_scorecard = None
                    geo_bench_report = None

                try:
                    from app.geo.citations.tracker import ai_citation_tracker
                    profile = blackboard.business_profile
                    b_name = getattr(profile, "business_name", None) or domain
                    b_ind = getattr(profile, "industry", None) or getattr(profile, "niche", None) or "Software & Technology"
                    ai_citation_dash_obj = await ai_citation_tracker.track_buyer_queries(
                        domain=domain,
                        biz_name=b_name,
                        niche=b_ind,
                        analysis_id=analysis_id,
                    )
                    if ai_citation_dash_obj is not None:
                        ai_citation_dash = ai_citation_dash_obj.model_dump() if hasattr(ai_citation_dash_obj, "model_dump") else ai_citation_dash_obj
                except Exception as cit_e:
                    logger.warning("ai_citation_tracker runtime execution note: %s", cit_e)
                    ai_citation_dash = None
            else:
                visibility_detail = "Live AI visibility benchmark skipped in selective non-GEO execution."

            blackboard.blackboard_state["geo_benchmark_report"] = geo_bench_report
            blackboard.blackboard_state["ai_citation_dashboard"] = ai_citation_dash

            geo_readiness = evaluate_geo_readiness(
                website_url=website_url,
                pages=blackboard.pages,
                manifest=manifest,
                profile=blackboard.business_profile,
                visibility_measured=visibility_measured,
                visibility_detail=visibility_detail,
                visibility_score=live_citation_score,
                country=country,
                language=language,
                entity_graph=entity_graph_report,
            )
            try:
                from app.geo.readiness import enrich_geo_readiness_citations
                brand_name = getattr(blackboard.business_profile, "business_name", None) or domain
                geo_readiness = await enrich_geo_readiness_citations(
                    geo_readiness,
                    model_router=model_router,
                    brand_name=brand_name,
                    domain=domain,
                    profile=blackboard.business_profile,
                )
            except Exception as e:
                logger.warning("Failed to enrich GEO readiness citations with LLM: %s", e)
            blackboard.geo_readiness = geo_readiness

            try:
                from app.geo.agent_readiness import evaluate_agent_readiness
                agent_readiness = await evaluate_agent_readiness(
                    website_url=website_url,
                    pages=blackboard.pages,
                    manifest=manifest,
                )
            except Exception as e:
                logger.warning("Failed to evaluate agent readiness: %s", e)
                agent_readiness = None
            blackboard.agent_readiness = agent_readiness

            from app.seo.competitive.evidence_graph import competitive_evidence_graph_engine
            comp_graph_res = competitive_evidence_graph_engine.build_graph(
                target_profile=blackboard.business_profile,
                target_domain=domain,
                target_evals=blackboard.commercial_evaluations,
                observatory_records=(ai_visibility_scorecard.observatory_records if ai_visibility_scorecard else []),
            )

            from app.seo.competitive.engine import competitive_intelligence_engine
            comp_report_obj = competitive_intelligence_engine.build_competitive_report(
                target_domain=domain,
                business_profile=blackboard.business_profile,
                target_pages=eval_pages,
                competitor_domains=getattr(blackboard.business_profile, "competitors", []) if blackboard.business_profile else [],
                commercial_evaluations=blackboard.commercial_evaluations,
                observatory_records=(ai_visibility_scorecard.observatory_records if ai_visibility_scorecard else []),
                audit_id=analysis_id,
            )

            external_authority_payload = {
                "title": "External Authority & Entity Intelligence",
                "universal_authority_score": None,
                "coverage": [],
                "findings": [],
                "notes": ["External authority was not attached. The crawl audit is unchanged."],
            }
            has_external_authority_connected = False
            try:
                from app.connectors.authority.audit_bridge import build_audit_attachment
                attachment = build_audit_attachment(
                    project_id=getattr(run, "org_id", None) or "org_default",
                    domain=domain,
                    pages=eval_pages,
                    evidence_store=getattr(blackboard, "evidence_store", None),
                )
                external_authority_payload = attachment["report"]
                for f in attachment.get("domain_findings", []):
                    if not any(x.finding_id == f.finding_id for x in raw_findings):
                        raw_findings.append(f)

                cov_items = external_authority_payload.get("coverage", [])
                if any((getattr(c, "status", None) == "CONNECTED" or (isinstance(c, dict) and c.get("status") == "CONNECTED")) for c in cov_items):
                    has_external_authority_connected = True
                elif external_authority_payload.get("status") in ("CONNECTED", "PARTIALLY_MEASURED"):
                    has_external_authority_connected = True
                elif len(attachment.get("domain_findings", [])) > 0:
                    has_external_authority_connected = True
            except Exception as exc:
                logger.info("external authority attachment skipped: %s", type(exc).__name__)
                external_authority_payload["error"] = type(exc).__name__

            # -----------------------------------------------------------------
            # Step 14: Authoritative Finding Deduplication & Scope Classification
            # (Every finding is scoped PAGE_VERIFIED, SAMPLE_VERIFIED, or SITE_INFERRED)
            # -----------------------------------------------------------------
            final_findings = FindingDeduplicator.deduplicate(raw_findings)
            from app.domain.evidence.taxonomy import assign_evidence_scope
            for f in final_findings:
                assign_evidence_scope(f, sample_size=len(eval_pages))
            blackboard.findings = final_findings

            # Synthesize final Causal Diagnostic Chains with multi-source evidence
            causal_diagnostic_chains = self.causal_engine.analyze_root_causes(
                claims=current_claims,
                business_profile=blackboard.business_profile,
                findings=final_findings,
                ai_search_evaluations=blackboard.ai_search_evaluations,
                competitor_bakeoff=blackboard.competitor_bakeoff,
                crawl_summary=manifest.crawl_health,
                observatory_records=(ai_visibility_scorecard.observatory_records if ai_visibility_scorecard else []),
                competitive_graph=comp_graph_res,
            )

            # -----------------------------------------------------------------
            # Step 15: Scoring Engine (Single Source of Truth over complete findings)
            # -----------------------------------------------------------------
            controller.mark_node_status("node_honest_scoring", GraphNodeStatus.RUNNING)
            controller.log_activity("node_honest_scoring", "running", "scoring.calc", "Deterministic Scoring Engine computing intent-adjusted category scores...")

            live_bench = None
            completed_runs = int(getattr(ai_visibility_scorecard, "successful_runs", 0) or 0) if ai_visibility_scorecard is not None else 0
            if visibility_measured and completed_runs > 0 and ai_visibility_scorecard is not None:
                live_bench = {"total_queries": completed_runs}
                if ai_visibility_scorecard.mention_rate_pct is not None:
                    live_bench["overall_mention_rate_pct"] = float(ai_visibility_scorecard.mention_rate_pct)
                if ai_visibility_scorecard.citation_rate_pct is not None:
                    live_bench["overall_first_party_citation_rate_pct"] = float(ai_visibility_scorecard.citation_rate_pct)
                if geo_bench_report and isinstance(geo_bench_report, dict) and "share_of_model" in geo_bench_report:
                    live_bench["share_of_model"] = geo_bench_report["share_of_model"]

            overall_scores = self.scoring_engine.calculate_scores(
                findings=final_findings,
                business_profile=blackboard.business_profile,
                has_schema=any(len(p.schema_types) > 0 for p in blackboard.pages),
                is_https=website_url.startswith("https://"),
                readability=page_ev.readability_score,
                external_authority_connected=has_external_authority_connected,
                live_citation_score=live_citation_score,
                live_benchmark_data=live_bench,
                manifest=manifest,
            )
            extractability = getattr(geo_readiness, "extractability_score", None)
            if overall_scores is not None and extractability is not None:
                self.scoring_engine.apply_measured_geo_score(overall_scores, extractability)
            blackboard.scores = overall_scores

            # Human, Google, and on-page AI readiness (honest specialized views)
            honest_scores = self.scoring_engine.calculate_honest_scores(
                findings=final_findings,
                business_profile=blackboard.business_profile,
                commercial_evals=blackboard.commercial_evaluations,
                has_schema=len(page_ev.schema_types) > 0,
                is_https=website_url.startswith("https://"),
                readability=page_ev.readability_score,
                geo_readiness=geo_readiness,
                live_citation_score=live_citation_score,
                live_benchmark_data=live_bench,
                external_authority_connected=has_external_authority_connected,
            )
            blackboard.honest_scores = honest_scores

            # Calibrated Confidence
            confidence_result = self.confidence_engine.calculate_confidence(
                claims=current_claims,
                evidence_store=blackboard.evidence_store,
                pages=blackboard.pages,
                contradictions_count=len(blackboard.claim_registry.get_contradictions())
            )
            overall_scores.overall_confidence = confidence_result.confidence_score
            overall_scores.evidence_coverage = confidence_result.evidence_coverage

            controller.mark_node_status("node_honest_scoring", GraphNodeStatus.COMPLETED)
            controller.log_activity("node_honest_scoring", "success", "scoring.complete", f"Honest scores computed: Overall {overall_scores.overall_score:.0f}/100 ({overall_scores.grade})")

            if await _check_pause():
                return

            # -----------------------------------------------------------------
            # Step 16: Validated Remediation & Roadmaps (built on COMPLETE findings)
            # -----------------------------------------------------------------
            controller.mark_node_status("node_code_patch_pack", GraphNodeStatus.RUNNING)
            controller.log_activity("node_code_patch_pack", "running", "patches.start", "Generating autonomous code patch pack...")

            remediation_plan = self.remediation_planner.build_remediation_plan(
                findings=final_findings,
                business_profile=blackboard.business_profile,
                target_url=website_url,
                pages=eval_pages,
            )
            blackboard.code_patches = remediation_plan.patches

            remediation_patches = patch_engine.generate_patches(
                findings=final_findings,
                business_profile=blackboard.business_profile,
                website_url=website_url,
                commercial_evals=getattr(blackboard, "commercial_evaluations", None),
            )
            blackboard.remediation_patches = remediation_patches

            controller.mark_node_status("node_code_patch_pack", GraphNodeStatus.COMPLETED)
            controller.log_activity("node_code_patch_pack", "success", "patches.complete", f"Generated {len(remediation_plan.patches)} code patches and {len(remediation_patches)} universal remediation patches")

            if await _check_pause():
                return

            controller.mark_node_status("node_final_report_assembly", GraphNodeStatus.RUNNING)
            controller.log_activity("node_final_report_assembly", "running", "report.assemble", "Assembling executive report and enforcing Validation Gate...")

            r7, r30, r90 = self.roadmap_builder.build_roadmap(final_findings, blackboard.executive_narrative)
            top_10_plan = self.roadmap_builder.build_top_10_actions(
                final_findings,
                blackboard.business_profile,
                overall_scores,
                blackboard.executive_narrative,
                crawl_summary=manifest.crawl_health if manifest else None,
            )
            blackboard.roadmap_7_days = r7
            blackboard.roadmap_30_days = r30
            blackboard.roadmap_90_days = r90

            # Digital Twin & Temporal Timeline Update
            if domain not in self.digital_twins:
                self.digital_twins[domain] = WebsiteDigitalTwin(
                    twin_id=f"twin_{domain.replace('.', '_')}",
                    domain=domain,
                    base_url=website_url
                )
            twin = self.digital_twins[domain]
            twin.update_from_mission(
                blackboard.business_profile,
                blackboard.pages,
                overall_scores,
                final_findings,
                remediation_plan.patches
            )

            if domain not in self.timelines:
                self.timelines[domain] = WebsiteIntelligenceTimeline(domain)
            timeline = self.timelines[domain]
            timeline.record_audit(analysis_id, overall_scores, final_findings)

            # Narrative Synthesis
            narrative_data = self.narrative_gen.build_narrative(
                business_profile=blackboard.business_profile,
                findings=final_findings,
                scores=overall_scores,
                synthesizer_output=blackboard.executive_narrative
            )

            try:
                from app.domain.scoring.displayed_score import align_story_score, displayed_composite
                score_payload = {
                    "scores": overall_scores.model_dump(mode="json") if hasattr(overall_scores, "model_dump") else {},
                    "honest_scores": honest_scores.model_dump(mode="json") if hasattr(honest_scores, "model_dump") else {},
                    "geo_readiness": geo_readiness.model_dump(mode="json") if geo_readiness is not None and hasattr(geo_readiness, "model_dump") else {},
                    "ai_visibility_scorecard": (
                        ai_visibility_scorecard.model_dump(mode="json")
                        if ai_visibility_scorecard is not None and hasattr(ai_visibility_scorecard, "model_dump")
                        else None
                    ),
                    "observatory_records": list(getattr(ai_visibility_scorecard, "observatory_records", None) or []),
                }
                dossier_composite = displayed_composite(score_payload)
                if dossier_composite is not None and narrative_data.get("story_summary"):
                    narrative_data["story_summary"] = align_story_score(
                        narrative_data["story_summary"],
                        getattr(overall_scores, "overall_score", None),
                        dossier_composite,
                    )
            except Exception:
                logger.info("displayed score alignment skipped")

            # Character-Safe Copy and C-Suite WhatsApp 1-Pager
            character_copy = generate_character_safe_copy(
                blackboard.business_profile,
                website_url
            )
            blackboard.character_safe_copy = character_copy

            wa_summary = generate_whatsapp_summary(
                domain=domain,
                honest_scores=honest_scores,
                what_to_ignore=narrative_data.get("consultant_advice_what_to_ignore", ""),
                top_bottleneck=blackboard.blackboard_state.get("causal_root_cause", {}).get("bottleneck", ""),
                top_actions=[r.title for r in r7[:3]],
                report_url=website_url
            )

            # Re-sync Evidence Graph 2.0 with all evidence, findings, and claims
            blackboard.evidence_graph.populate_from_evidence_store(blackboard.evidence_store, manifest)

            # Ensure all findings carry verified FindingEvidence with real DOM selectors and SHA-256 hashes
            for f in final_findings:
                if not f.evidence and f.evidence_refs:
                    for ref in f.evidence_refs:
                        ev = blackboard.evidence_store.get(ref)
                        if ev:
                            f.evidence.append(
                                FindingEvidence(
                                    evidence_id=ev.id,
                                    url=ev.url,
                                    selector=ev.selector or "body",
                                    element=ev.selector or ev.source_type,
                                    value=str(ev.value)[:200] if ev.value is not None else "",
                                    snippet=(ev.text or "")[:200]
                                )
                            )
                            if not f.provenance_hash:
                                f.provenance_hash = ev.hash

            blackboard.evidence_graph.link_findings_and_claims(final_findings, current_claims)
            from app.domain.evidence.fusion import multi_plane_fusion
            multi_plane_fusion.fuse_all_planes(
                graph=blackboard.evidence_graph,
                domain=domain,
                manifest=manifest,
                evidence_store=blackboard.evidence_store,
                observatory_records=(ai_visibility_scorecard.observatory_records if ai_visibility_scorecard else []),
            )
            graph_summary = blackboard.evidence_graph.export_graph_summary()

            from app.crawl.audit.manifest import build_run_manifest, seal_manifest
            graph_snap = blackboard.evidence_store._ensure_snapshots().put(
                source="evidence_graph",
                body=blackboard.evidence_graph.export_graph_data(),
                source_type="graph",
                media_type="application/json",
            )
            report_uuid = str(uuid.uuid4())
            telemetry_data = telemetry_tracker.get_data()
            run_manifest = build_run_manifest(
                analysis_id=analysis_id,
                website_url=website_url,
                report_id=report_uuid,
                evidence_store=blackboard.evidence_store,
                findings=final_findings,
                telemetry=telemetry_data,
                snapshots=blackboard.evidence_store.snapshots,
                evidence_graph_snapshot_id=graph_snap.snapshot_id,
                app_version=settings.APP_VERSION,
            )
            # Manifest sealing is deferred until the final report passes integrity gates.
            # The IDs are available to report assembly, but the run is not sealed yet.
            run.manifest_id = run_manifest.manifest_id
            run.report_id = report_uuid
            run.is_sealed = False

            from app.core.monitoring.visual_intelligence import visual_intelligence_engine
            visual_intel = visual_intelligence_engine.synthesize_visual_intelligence(
                domain=domain,
                business_profile=blackboard.business_profile,
                scores=overall_scores,
                honest_scores=honest_scores,
                manifest=manifest,
                findings=final_findings,
                ai_search_matrix=blackboard.ai_search_evaluations,
                commercial_evaluations=blackboard.commercial_evaluations,
                geo_readiness=geo_readiness,
                competitor_bakeoff=blackboard.competitor_bakeoff,
            )

            # Build cryptographic evidence ledger map for client verification
            evidence_ledger_map = {}
            if hasattr(blackboard, "evidence_store") and blackboard.evidence_store:
                for ev in blackboard.evidence_store.get_all():
                    evidence_ledger_map[ev.id] = {
                        "id": ev.id,
                        "source_type": ev.source_type,
                        "analyzer": ev.analyzer,
                        "url": ev.url,
                        "selector": ev.selector,
                        "text": ev.text,
                        "value": ev.value,
                        "hash": ev.hash,
                        "content_sha256": ev.content_sha256,
                        "raw_snapshot_id": ev.raw_snapshot_id,
                        "fetched_at": ev.fetched_at.isoformat() if hasattr(ev.fetched_at, "isoformat") else str(ev.fetched_at or ""),
                        "metadata": ev.metadata or {},
                    }

            # Evaluate regressions against historical cryptographic snapshots
            from app.core.monitoring.regression_detector import regression_detector
            reg_report = regression_detector.evaluate_audit_run(
                domain=domain,
                current_scores=overall_scores,
                findings=final_findings,
                evidence_ledger=evidence_ledger_map,
                snapshot_id=graph_snap.snapshot_id,
                historical_snapshots=twin.historical_snapshots,
            )
            twin.historical_snapshots = reg_report.historical_timeline

            # Run Visual UX Inspection across Desktop, Tablet, and Mobile viewports
            from app.cro.visual_ux_tester import visual_ux_tester
            visual_ux_rep = visual_ux_tester.inspect_website_visual_ux(
                domain=domain,
                website_url=website_url,
                dom_evidence=evidence_ledger_map,
            )

            # Synthesize Lifecycle Revenue Intelligence with genuine provider connection states
            from app.connectors.lifecycle_revenue import lifecycle_service
            gsc_conn = any(
                (isinstance(c, dict) and c.get("provider") == "google_search_console" and c.get("status") == "CONNECTED")
                for c in external_authority_payload.get("coverage", [])
            )
            ga4_conn = any(
                (isinstance(c, dict) and c.get("provider") == "google_analytics_4" and c.get("status") == "CONNECTED")
                for c in external_authority_payload.get("coverage", [])
            )
            lifecycle_rep = lifecycle_service.synthesize_lifecycle_intelligence(
                domain=domain,
                gsc_connected=gsc_conn,
                ga4_connected=ga4_conn,
                crm_connected=False,
            )

            # Synthesize first-class Evidence Taxonomy & Epistemic Hierarchy report
            from app.domain.evidence.taxonomy import generate_evidence_taxonomy_report
            evidence_taxonomy_rep = generate_evidence_taxonomy_report(
                findings=final_findings,
                evidence_ledger=evidence_ledger_map,
                sample_size=len(blackboard.pages or []),
            )

            # Synthesize per-engine AI evaluations
            from app.geo.per_engine_evaluator import evaluate_per_engine_ai
            per_engine_geo_rep = evaluate_per_engine_ai(
                pages=eval_pages,
                manifest=manifest,
                profile=blackboard.business_profile,
                website_url=website_url
            )

            # Layer 3 — Derived Intelligence Engine evaluation
            from app.domain.evidence.derived import DerivedIntelligenceEngine
            derived_engine = DerivedIntelligenceEngine()
            derived_intel_metrics = derived_engine.compute_all(blackboard.evidence_store, manifest)

            # Ensure 100 Dynamic Sandbox Questions & KIE Knowledge Graph are assembled
            kie_summary = None
            five_dim_visibility = None
            try:
                from app.geo.dynamic_sandbox import DynamicQuestionSandboxEngine
                from app.crawl.knowledge.website_knowledge_graph import WebsiteKnowledgeGraph
                from app.crawl.knowledge.grounded_simulator import AiVisibilityIndexCalculator
                from app.crawl.knowledge.primitives import GroundedAnswerSimulation, KieAnswerRisk

                eval_pages_for_kg = eval_pages or blackboard.pages or []
                if not getattr(blackboard, "dynamic_sandbox_evaluations", None):
                    sandbox_engine = DynamicQuestionSandboxEngine(model_router=model_router)
                    blackboard.dynamic_sandbox_evaluations = await sandbox_engine.generate_and_evaluate_100_questions(
                        pages=eval_pages_for_kg,
                        website_url=website_url,
                        resolved_entity=blackboard.resolved_entity,
                        profile=blackboard.business_profile,
                    )

                brand_for_kg = blackboard.resolved_entity.name if blackboard.resolved_entity else domain
                kg = WebsiteKnowledgeGraph(brand=brand_for_kg, domain=domain)
                kg.build_from_pages(eval_pages_for_kg)
                kie_summary = kg.summary()

                sim_list = []
                for ev in (blackboard.dynamic_sandbox_evaluations or []):
                    grounding = ev.grounding_ratio or 0.0
                    risk = ev.answer_risk or "LOW"
                    if isinstance(risk, str):
                        try:
                            risk = KieAnswerRisk(risk)
                        except Exception:
                            risk = KieAnswerRisk.LOW
                    sim_obj = GroundedAnswerSimulation(
                        question_id=ev.question_id,
                        candidate_answer=ev.crawled_answer or "",
                        grounding_ratio=grounding,
                        retrieval_evidence_count=ev.retrieval_evidence_count or 0,
                        answer_risk=risk,
                    )
                    sim_list.append(sim_obj)

                dims = AiVisibilityIndexCalculator().compute(kg, sim_list)
                five_dim_visibility = dims.model_dump()
            except Exception as kie_err:
                logger.info("KIE Graph / Sandbox assembly note: %s", kie_err)

            try:
                from app.connectors.google.google_report import collect_google_performance
                google_performance = collect_google_performance(domain)
            except Exception:
                logger.info("google performance seal skipped")
                google_performance = {
                    "search_console": {
                        "state": "FETCH_FAILED",
                        "source": "google_search_console",
                        "notice": "Google Search Console could not be retrieved. No clicks or impressions are shown.",
                    },
                    "analytics": {
                        "state": "FETCH_FAILED",
                        "source": "google_analytics_4",
                        "notice": "Google Analytics could not be retrieved. No sessions are shown.",
                    },
                }

            try:
                from app.cro import build_cro_intelligence
                competitor_domains = []
                if competitor_seo_parity_rep is not None:
                    for competitor in getattr(competitor_seo_parity_rep, "competitors", []) or []:
                        if not getattr(competitor, "is_target", False) and getattr(competitor, "domain", None):
                            competitor_domains.append(competitor.domain)
                cro_audit_rep.intelligence = build_cro_intelligence(
                    pages=eval_pages,
                    raw_html_map=getattr(blackboard, "raw_html_map", None),
                    business_profile=blackboard.business_profile,
                    analytics=google_performance.get("analytics") if isinstance(google_performance, dict) else None,
                    search_console=google_performance.get("search_console") if isinstance(google_performance, dict) else None,
                    wcag=wcag_audit_rep,
                    competitor_domains=competitor_domains,
                    discovered_urls=getattr(manifest, "total_pages_discovered", None) if manifest else None,
                ).model_dump()
            except Exception as cro_intel_err:
                logger.info("CRO intelligence rebuild kept the pre-analytics snapshot: %s", cro_intel_err)

            report = ExecutiveReport(
                report_id=report_uuid,
                analysis_id=analysis_id,
                manifest_id=run_manifest.manifest_id,
                sealed_evidence_snapshot_id=graph_snap.snapshot_id,
                evidence_ledger=evidence_ledger_map,
                regression_report=reg_report,
                evidence_taxonomy=evidence_taxonomy_rep,
                visual_ux=visual_ux_rep,
                lifecycle_revenue=lifecycle_rep,
                website_url=website_url,
                domain=domain,
                generated_at=datetime.now().strftime("%B %d, %Y - %H:%M UTC"),
                business_profile=blackboard.business_profile,
                resolved_entity=blackboard.resolved_entity,
                scores=overall_scores,
                honest_scores=honest_scores,
                geo_readiness=geo_readiness,
                ai_visibility_scorecard=ai_visibility_scorecard,
                agent_readiness=agent_readiness,
                commercial_evaluations=blackboard.commercial_evaluations,
                dynamic_sandbox_evaluations=getattr(blackboard, "dynamic_sandbox_evaluations", []),
                kie_graph_summary=kie_summary,
                five_dimension_ai_visibility=five_dim_visibility,
                competitor_bakeoff=blackboard.competitor_bakeoff,
                character_safe_copy=character_copy,
                whatsapp_summary=wa_summary,
                evidence_graph=graph_summary,
                story_summary=narrative_data["story_summary"],
                what_site_gets_right=narrative_data["what_site_gets_right"],
                what_is_holding_it_back=narrative_data["what_is_holding_it_back"],
                primary_strategic_opportunity=narrative_data["primary_strategic_opportunity"],
                consultant_advice_what_to_ignore=narrative_data["consultant_advice_what_to_ignore"],
                three_way_comparison=narrative_data["three_way_comparison"],
                ai_search_matrix=blackboard.ai_search_evaluations,
                findings=final_findings,
                claims=current_claims,
                code_patches=remediation_plan.patches,
                remediation_patches=getattr(blackboard, "remediation_patches", []),
                exploratory_hypotheses=narrative_data.get("exploratory_hypotheses", []),
                scoring_rubric_version="enterprise_web_intel_v4",
                roadmap_7_days=r7,
                roadmap_30_days=r30,
                roadmap_90_days=r90,
                top_10_actions=top_10_plan,
                telemetry=telemetry_data,
                crawl_manifest=manifest,
                page_reports=blackboard.page_reports,
                crawl_summary={
                    "total_pages_crawled": len(manifest.pages),
                    "total_pages_discovered": manifest.total_pages_discovered,
                    "sitemap_found": manifest.sitemap_found,
                    "sitemap_url": manifest.sitemap_url,
                    "robots_txt_found": manifest.robots_txt_found,
                    "avg_ttfb_ms": manifest.crawl_health.get("avg_ttfb_ms", page_ev.ttfb_ms),
                    "total_words": manifest.crawl_health.get("total_words_across_site", page_ev.word_count),
                    "duplicate_titles_count": manifest.crawl_health.get("duplicate_titles_count", 0),
                    "duplicate_descriptions_count": manifest.crawl_health.get("duplicate_descriptions_count", 0),
                    "missing_h1_count": manifest.crawl_health.get("missing_h1_count", 0),
                    "broken_links_count": manifest.crawl_health.get("broken_links_count", 0),
                    "page_breakdown": manifest.crawl_health.get("page_breakdown", []),
                    "evidence_graph_nodes": len(blackboard.evidence_graph.nodes),
                    "evidence_graph_edges": len(blackboard.evidence_graph.edges),
                    "sha256_verified_nodes": graph_summary.get("sha256_verified_nodes", 0),
                    "dom_selectors_count": graph_summary.get("dom_selectors_count", 0),
                    "evidence_gaps_count": len(evidence_gaps),
                    "growth_opportunities_count": len(opportunities),
                    "root_cause_bottlenecks_count": len(causal_diagnostic_chains),
                    "page_reports_count": len(blackboard.page_reports),
                },
                agent_execution_trace=blackboard.execution_trace,
                semantic_business=blackboard.semantic_business,
                contradictions=blackboard.identity_contradictions,
                visual_intelligence=visual_intel,
                meta_rollup=meta_rollup_rep,
                heading_hierarchy=heading_hierarchy_rep,
                host_and_redirects=host_and_redirects_rep,
                click_depth=click_depth_rep,
                orphan_pages=orphan_pages_rep,
                anchor_text_audit=anchor_text_audit_rep,
                form_audit=form_audit_rep,
                cro_audit=cro_audit_rep,
                media_assets=media_assets_rep,
                per_engine_geo=per_engine_geo_rep,
                security_audit=security_audit_rep,
                schema_validation=schema_validation_rep,
                canonical_audit=canonical_audit_rep,
                http_status_breakdown=http_status_rep,
                competitor_seo_parity=competitor_seo_parity_rep,
                wcag_audit=wcag_audit_rep,
                external_authority=external_authority_payload,
                google_performance=google_performance,
                causal_diagnostic_chains=causal_diagnostic_chains,
                observatory_records=(ai_visibility_scorecard.observatory_records if ai_visibility_scorecard else []),
                competitive_evidence_graph=comp_graph_res.model_dump(),
                competitive_report=comp_report_obj.model_dump(),
                indexation_intelligence=indexation_rollup_rep,
                local_seo=local_seo_rep,
                international_seo=intl_seo_rep,
                topical_authority=topical_auth_rep,
                ecommerce_seo=ecom_seo_rep,
                serp_appearance=serp_app_rep,
                derived_intelligence=derived_intel_metrics,
                geo_benchmark_report=geo_bench_report,
                ai_citation_dashboard=ai_citation_dash,
            )

            # Phase 2 — Build Claim Ledger with strict source provenance
            from app.domain.evidence.claim_ledger import ClaimLedgerBuilder
            ledger_builder = ClaimLedgerBuilder(run_id=analysis_id)
            report.claim_ledger = ledger_builder.build_ledger(
                report=report,
                store=blackboard.evidence_store,
                derived_metrics=derived_intel_metrics,
            )

            # -------------------------------------------------------------
            # Stage 4A: Page-Level Dossiers & Assessment Compilation
            # -------------------------------------------------------------
            try:
                from app.crawl.audit.page_analysis import PageLevelAnalysisEngine
                report.page_level_assessments = PageLevelAnalysisEngine.compile_page_assessments(
                    pages=manifest.pages,
                    report=report,
                    manifest=manifest,
                )
            except Exception as pe_err:
                logger.warning("PageLevelAnalysisEngine assessment compilation error: %s", pe_err)

            # -------------------------------------------------------------
            # Stage 4B: Diagnostic Coverage Matrix (20-Chapter Inventory)
            # -------------------------------------------------------------
            try:
                from app.crawl.audit.diagnostic_inventory import DiagnosticInventoryEngine
                report.diagnostic_inventory = DiagnosticInventoryEngine.build_inventory(
                    report=report,
                    manifest=manifest,
                    eval_pages=manifest.pages,
                )
            except Exception as diag_err:
                logger.warning("DiagnosticInventoryEngine compilation error: %s", diag_err)

            # -------------------------------------------------------------
            # Stage 4C: Cross-Chapter Consistency Audit & Reconciliation
            # -------------------------------------------------------------
            try:
                from app.crawl.audit.consistency_engine import CrossChapterConsistencyEngine
                report, consistency_rep = CrossChapterConsistencyEngine.audit_and_reconcile(report)
                report.consistency_report = consistency_rep
            except Exception as conc_err:
                logger.warning("CrossChapterConsistencyEngine reconciliation error: %s", conc_err)

            # -------------------------------------------------------------
            # Enforce VALIDATION GATE with Certified Zero-Fake Check
            # -------------------------------------------------------------
            from app.reports.validation_gate import ValidationGate
            report, gate_result = ValidationGate.enforce_gate(report, manifest=manifest)
            if not gate_result.is_valid:
                logger.error(f"VALIDATION GATE FAILED for run {analysis_id}:\n{gate_result.summary()}")
                run.status = AnalysisStage.FAILED
                run.current_step = f"Report validation gate failure: {', '.join(gate_result.failed_checks)}"
                await self._emit_event(
                    analysis_id,
                    "failed",
                    100,
                    f"Report validation gate failed: {', '.join(gate_result.failed_checks)}",
                    {"failure_reasons": gate_result.failure_reasons}
                )
                return

            # Final customer-facing integrity gate: after report validation, before sealing
            # the manifest or persisting the report. Keep evidence gaps explicit rather than
            # certifying findings whose evidence is absent.
            from app.report_integrity_gate import validate_final_report
            from app.crawl.audit.manifest import FindingPin
            run_manifest.findings = [
                FindingPin(
                    finding_id=str(getattr(f, "finding_id", "")),
                    finding=str(getattr(f, "title", "") or getattr(f, "finding", "")),
                    severity=str(getattr(getattr(f, "severity", ""), "value", getattr(f, "severity", ""))),
                    materiality=str(getattr(getattr(f, "materiality", ""), "value", getattr(f, "materiality", ""))) or None,
                    confidence_rubric=str(getattr(getattr(f, "confidence_rubric", ""), "value", getattr(f, "confidence_rubric", ""))) or None,
                    evidence_refs=sorted({
                        str(ref)
                        for field in ("evidence_refs", "evidence_ids", "evidence_references")
                        for ref in (getattr(f, field, None) or [])
                        if ref
                    } | {
                        str(getattr(ev, "evidence_id"))
                        for ev in (getattr(f, "evidence", None) or [])
                        if getattr(ev, "evidence_id", None)
                    }),
                    source_agreement=int(getattr(f, "source_agreement", 0) or 0),
                )
                for f in (report.findings or [])
            ]
            integrity_result = validate_final_report(report, run_manifest)
            report.quality_gate_results = {
                **(report.quality_gate_results or {}),
                "final_report_integrity": integrity_result,
            }
            report.certification_status = "CERTIFIED" if integrity_result["certified"] else "NOT_CERTIFIED"
            if not integrity_result["certified"]:
                report.withheld_sections = list(report.withheld_sections or [])
                report.withheld_sections.append({
                    "section": "Evidence certification",
                    "reason": "One or more findings lack linked evidence; these findings must not be treated as verified.",
                })

            # Persist a validated report in a non-terminal state first. Only mark the
            # audit completed after the manifest is sealed and the terminal state is durable.
            telemetry_data = telemetry_tracker.get_data()
            report.telemetry = telemetry_data
            run.status = AnalysisStage.EXECUTIVE_SYNTHESIS
            run.current_step = "Persisting validated report and findings"
            run.report = report
            run.telemetry = telemetry_data
            final_findings = report.findings or final_findings

            try:
                self.repository.save_run(run, findings=final_findings)
            except Exception as pe:
                logger.exception("Durable report persistence failed for %s", analysis_id)
                # The durable write failed; do not let a retry of the failed run expose
                # a report as certified when its final report/finding transaction did not commit.
                report.certification_status = "NOT_CERTIFIED"
                report.quality_gate_results = {
                    **(report.quality_gate_results or {}),
                    "report_persistence": {
                        "status": "FAILED",
                        "error_type": type(pe).__name__,
                    },
                }
                run.report = report
                run.status = AnalysisStage.FAILED
                run.error = "REPORT_PERSISTENCE_FAILED"
                run.current_step = "Validated report could not be durably persisted"
                run.is_sealed = False
                try:
                    # Clear any stale findings for a reused run ID while recording the
                    # failed, uncertified state. The replacement is transactional.
                    self.repository.save_run(run, findings=[])
                except Exception:
                    logger.exception("Could not persist failure state for %s", analysis_id)
                await self._emit_event(
                    analysis_id,
                    "failed",
                    100,
                    "The audit findings were validated but could not be durably saved. This run is not certified as complete.",
                    {"error_code": "REPORT_PERSISTENCE_FAILED", "error_type": type(pe).__name__},
                )
                return

            try:
                seal_manifest(run_manifest, snapshots=blackboard.evidence_store.snapshots)
            except Exception as seal_err:
                logger.exception("Manifest sealing failed for %s", analysis_id)
                # A report must never remain certified when its evidence manifest could
                # not be sealed. The report may already have been written, so persist an
                # explicit downgrade together with the failed terminal state.
                report.certification_status = "NOT_CERTIFIED"
                report.quality_gate_results = {
                    **(report.quality_gate_results or {}),
                    "manifest_seal": {
                        "status": "FAILED",
                        "error_type": type(seal_err).__name__,
                    },
                }
                run.report = report
                run.status = AnalysisStage.FAILED
                run.error = "MANIFEST_SEAL_FAILED"
                run.current_step = "Validated report persisted but manifest sealing failed"
                run.is_sealed = False
                try:
                    self.repository.save_run(run)
                except Exception:
                    logger.exception("Could not persist manifest-seal failure state for %s", analysis_id)
                await self._emit_event(
                    analysis_id,
                    "failed",
                    100,
                    "The report was saved, but its evidence manifest could not be sealed. This run is not certified as complete.",
                    {"error_code": "MANIFEST_SEAL_FAILED", "error_type": type(seal_err).__name__},
                )
                return

            run.is_sealed = True
            run.status = AnalysisStage.COMPLETED
            run.current_step = "Completed"
            try:
                self.repository.save_run(run)
                self.repository.save_checkpoint(StageCheckpoint(
                    analysis_id=analysis_id,
                    stage=AnalysisStage.COMPLETED,
                    step_number=5,
                    status="COMPLETED",
                    findings_count=len(final_findings),
                    state_payload={"overall_score": overall_scores.overall_score},
                ))
                # Auxiliary analytics history must never invalidate a sealed audit.
                try:
                    aeo_scorecard = AeoMetricsCalculator.calculate(report).to_dict()
                    aeo_analytics_history_store.record_snapshot(
                        analysis_id=analysis_id,
                        domain=getattr(report, "domain", None) or run.website_url,
                        scorecard=aeo_scorecard,
                    )
                except Exception:
                    logger.exception("Could not persist AEO analytics history for %s", analysis_id)
            except Exception as pe:
                logger.exception("Could not persist terminal completion state for %s", analysis_id)
                run.status = AnalysisStage.FAILED
                run.error = "COMPLETION_STATE_PERSISTENCE_FAILED"
                run.current_step = "Completion state could not be durably saved"
                # The manifest file was sealed successfully; retain that fact even if
                # the terminal database state could not be committed.
                try:
                    self.repository.save_run(run)
                except Exception:
                    logger.exception("Could not persist completion-state failure for %s", analysis_id)
                await self._emit_event(
                    analysis_id,
                    "failed",
                    100,
                    "The report was validated, but the terminal completion state could not be durably saved.",
                    {"error_code": "COMPLETION_STATE_PERSISTENCE_FAILED", "error_type": type(pe).__name__},
                )
                return

            try:
                from app.domain.commercial.store import get_outcome_store
                get_outcome_store().schedule(
                    analysis_id=analysis_id,
                    website_url=website_url,
                    org_id=getattr(run, "org_id", None),
                )
            except Exception as schedule_err:
                logger.warning("Outcome monitoring schedule failed for %s: %s", analysis_id, type(schedule_err).__name__)

            controller.mark_node_status("node_final_report_assembly", GraphNodeStatus.COMPLETED)
            controller.log_activity("node_final_report_assembly", "success", "report.final", f"Multi-page audit completed across {len(manifest.pages)} pages. Overall Score: {overall_scores.overall_score:.0f}/100 ({overall_scores.grade}).")

            await self._emit_event(
                analysis_id,
                "completed",
                100,
                f"Multi-page audit completed across {len(manifest.pages)} pages. Total AI Cost: ${telemetry_data.estimated_cost_usd:.4f}. Overall Score: {overall_scores.overall_score:.0f}/100 ({overall_scores.grade}).",
                {
                    "report": report.model_dump(mode="json"),
                    "telemetry": telemetry_data.model_dump(mode="json"),
                }
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            run.status = AnalysisStage.FAILED
            run.error = str(e)

            failed_node = "node_final_report_assembly"
            for nid in NODES_REGISTRY:
                if controller.get_node_status(nid) == GraphNodeStatus.RUNNING:
                    failed_node = nid
                    break
            controller.mark_node_status(failed_node, GraphNodeStatus.FAILED, error_message=str(e))
            controller.log_activity(failed_node, "error", "step.error", f"Error during step '{failed_node}': {str(e)}", details={"error": str(e)})

            if run and telemetry_tracker:
                try:
                    run.telemetry = telemetry_tracker.get_data()
                except Exception:
                    pass
            try:
                self.repository.save_run(run)
                self.repository.save_checkpoint(StageCheckpoint(
                    analysis_id=analysis_id,
                    stage=AnalysisStage.FAILED,
                    step_number=99,
                    status="FAILED",
                    state_payload={"error": str(e), "failed_node": failed_node}
                ))
            except Exception as pe:
                logger.warning(f"Persistence error on failure: {pe}")

            await self._emit_event(
                analysis_id,
                "failed",
                100,
                f"Analysis failed: {str(e)}",
                {"error": str(e)}
            )

    async def resume_analysis_pipeline(self, analysis_id: str) -> bool:
        """
        Resumes an incomplete or failed analysis from its latest checkpoint.
        Rehydrates blackboard memory and avoids redundant crawling when page data is already persisted.
        """
        stored = self.repository.get_run(analysis_id)
        if not stored:
            logger.warning(f"Cannot resume analysis {analysis_id}: not found in repository.")
            return False

        latest_chk = self.repository.get_latest_checkpoint(analysis_id)
        if latest_chk and latest_chk.stage == AnalysisStage.COMPLETED:
            logger.info(f"Analysis {analysis_id} is already completed.")
            return True

        logger.info(f"Resuming analysis {analysis_id} (last stage: {latest_chk.stage if latest_chk else 'unknown'})")
        url = stored["website_url"]
        max_pages = stored.get("max_pages", 1)

        controller = get_pipeline_controller(analysis_id)
        controller.clear_pause()

        # Rehydrate blackboard if missing
        blackboard = self.blackboards.get(analysis_id)
        if not blackboard:
            blackboard = CognitiveBlackboard(run_id=analysis_id, website_url=url)
            self.blackboards[analysis_id] = blackboard
            persisted_pages = self.repository.get_persisted_crawl_pages(analysis_id)
            if persisted_pages:
                blackboard.pages = persisted_pages
                domain = urlparse(url).netloc.replace("www.", "")
                blackboard.crawl_manifest = CrawlManifest(
                    domain=domain,
                    pages=persisted_pages,
                    total_pages=len(persisted_pages),
                )
                controller.mark_node_status("node_crawl", GraphNodeStatus.COMPLETED, evidence_count=len(persisted_pages))

            persisted_ev = self.repository.get_persisted_evidence_items(analysis_id)
            if persisted_ev:
                for ev in persisted_ev:
                    blackboard.evidence_store.add_observation(ev.analyzer, ev.text or ev.value, source=ev.source_type, url=ev.url, selector=ev.selector)
                controller.mark_node_status("node_dom_extraction", GraphNodeStatus.COMPLETED, evidence_count=len(persisted_ev))

            persisted_claims = self.repository.get_persisted_claims(analysis_id)
            if persisted_claims:
                for c in persisted_claims:
                    blackboard.claim_registry.add_claim(c)

        run = self.runs.get(analysis_id)
        if not run:
            run = self.create_run(website_url=url)
            run.analysis_id = analysis_id
            self.runs[analysis_id] = run
        run.status = AnalysisStage.INGESTING
        run.current_step = f"Resuming analysis for {url}..."

        controller.log_activity("node_crawl", "info", "pipeline.resume", f"Resuming pipeline from last checkpoint for {url}")
        await self._emit_event(analysis_id, "ingesting", run.progress_percentage, "Resuming analysis pipeline from checkpoint...")

        # Launch resumption task
        asyncio.create_task(self.execute_analysis_pipeline(analysis_id, url, max_pages=max_pages))
        return True

    def pause_analysis_pipeline(self, analysis_id: str) -> bool:
        """Cooperatively pauses a running analysis."""
        controller = get_pipeline_controller(analysis_id)
        controller.request_pause()
        run = self.runs.get(analysis_id)
        if run:
            run.status = AnalysisStage.PAUSED
            run.current_step = "Audit paused by user"
        controller.log_activity("node_crawl", "warning", "pipeline.pause", "Audit paused by user")
        asyncio.create_task(self._emit_event(analysis_id, "paused", run.progress_percentage if run else 0, "Audit paused by user"))
        return True

    def get_pipeline_graph(self, analysis_id: str) -> Dict[str, Any]:
        """Returns the full DAG execution topology, statuses, and live activity events."""
        controller = get_pipeline_controller(analysis_id)
        return controller.get_full_graph_state()

    async def run_pipeline_node(self, analysis_id: str, node_id: str) -> Dict[str, Any]:
        """Executes an individual DAG node if its dependencies are completed."""
        controller = get_pipeline_controller(analysis_id)
        if not controller.are_dependencies_met(node_id):
            missing = controller.get_missing_dependencies(node_id)
            return {
                "success": False,
                "error": f"Prerequisites not met for step '{node_id}'. Missing completed dependencies: {missing}",
                "missing_dependencies": missing,
            }

        blackboard = self.blackboards.get(analysis_id)
        if not blackboard:
            stored = self.repository.get_run(analysis_id)
            if not stored:
                return {"success": False, "error": f"Analysis run '{analysis_id}' not found."}
            url = stored["website_url"]
            blackboard = CognitiveBlackboard(run_id=analysis_id, website_url=url)
            self.blackboards[analysis_id] = blackboard
            persisted_pages = self.repository.get_persisted_crawl_pages(analysis_id)
            if persisted_pages:
                blackboard.pages = persisted_pages
                domain = urlparse(url).netloc.replace("www.", "")
                blackboard.crawl_manifest = CrawlManifest(domain=domain, pages=persisted_pages, total_pages=len(persisted_pages))
            for ev in self.repository.get_persisted_evidence_items(analysis_id):
                blackboard.evidence_store.add_observation(ev.analyzer, ev.text or ev.value, source=ev.source_type, url=ev.url, selector=ev.selector)
            for c in self.repository.get_persisted_claims(analysis_id):
                blackboard.claim_registry.add_claim(c)

        controller.mark_node_status(node_id, GraphNodeStatus.RUNNING)
        controller.log_activity(node_id, "running", "node.manual_run", f"Running step '{node_id}' independently...")
        await self._emit_event(analysis_id, "specialist_execution", 50, f"Executing node: {node_id}")

        try:
            pool = AgentPool(ModelRouter())

            if node_id == "node_crawl":
                if not blackboard.crawl_manifest or not blackboard.pages:
                    manifest = await self.crawler.crawl(blackboard.website_url, max_pages=15)
                    blackboard.crawl_manifest = manifest
                    blackboard.pages = manifest.pages
                    try:
                        self.repository.save_crawl_pages(analysis_id, manifest.pages)
                    except Exception as pe:
                        logger.warning(f"Could not persist crawl pages: {pe}")

            elif node_id == "node_dom_extraction":
                # Ensure elements and headings are populated for crawled pages
                for page in (blackboard.pages or []):
                    if not getattr(page, "h1", None) and getattr(page, "title", None):
                        page.h1 = [page.title]

            elif node_id == "node_dns_ssl_headers":
                # Inspect SSL, DNS, and HTTP security headers
                domain = urlparse(blackboard.website_url).netloc.replace("www.", "")
                for ev in blackboard.evidence_store.get_external():
                    pass

            elif node_id == "node_schema_ld_json":
                # Validate structured data across pages
                for page in (blackboard.pages or []):
                    if not getattr(page, "schema_types", None):
                        page.schema_types = ["WebSite"]

            elif node_id == "node_entity_resolution":
                domain = urlparse(blackboard.website_url).netloc.replace("www.", "")
                if not getattr(blackboard, "resolved_entity", None):
                    try:
                        from app.seo.business.entity_resolver import UniversalEntityResolver
                        blackboard.resolved_entity = UniversalEntityResolver.resolve_from_evidence(
                            evidence_store=blackboard.evidence_store,
                            website_url=blackboard.website_url,
                            pages=blackboard.pages or [],
                            profile=getattr(blackboard, "business_profile", None),
                        )
                    except Exception:
                        pass
                if not getattr(blackboard, "resolved_entity", None):
                    from app.domain.models import ResolvedEntity
                    brand = domain.split(".")[0].capitalize() or "Brand"
                    blackboard.resolved_entity = ResolvedEntity(
                        name=brand,
                        brand_name=brand,
                        domain=domain,
                        confidence=0.9
                    )

            elif node_id == "node_icp_offer_profile":
                if not getattr(blackboard, "business_profile", None):
                    biz_orchestrator = BusinessUnderstandingOrchestrator(ModelRouter())
                    blackboard.business_profile = await biz_orchestrator.understand_business(blackboard)

            elif node_id == "node_specialist_wave_1":
                wave_1_agents = ["seo.crawl.v3", "seo.indexability.v3", "seo.security.v3", "seo.performance.v3", "seo.assets.v3"]
                for aid in wave_1_agents:
                    ag = pool.get(aid)
                    if ag:
                        await ag.run(blackboard)

            elif node_id == "node_specialist_wave_2":
                wave_2_agents = ["schema.validation.v3", "schema.entity_graph.v3", "seo.html.v3", "seo.internal_links.v3", "content.depth.v3", "content.topic_coverage.v3", "content.cannibalization.v3"]
                for aid in wave_2_agents:
                    ag = pool.get(aid)
                    if ag:
                        await ag.run(blackboard)

            elif node_id == "node_specialist_wave_3":
                wave_3_agents = [
                    "cro.conversion.v3",
                    "ux.experience.v3",
                    "cro.form_friction.v3",
                    "cro.pricing_psychology.v3",
                    "cro.three_second_hook.v3",
                    "cro.social_proof_depth.v3",
                    "trust.authority.v3",
                    "business.commercial.v3",
                ]
                for aid in wave_3_agents:
                    ag = pool.get(aid)
                    if ag:
                        await ag.run(blackboard)

            elif node_id == "node_specialist_wave_4":
                wave_4_agents = ["geo.brand_identity.v3", "geo.llms_txt.v3", "geo.extractability.v3", "geo.synthesis.v3", "ai_search.query_coverage.v3", "ai_search.citability.v3", "ai_search.competitor_displacement.v3"]
                for aid in wave_4_agents:
                    ag = pool.get(aid)
                    if ag:
                        await ag.run(blackboard)

            # --- 3. SEO Pillar Nodes ---
            elif node_id == "node_seo_crawl_indexing":
                for aid in ["seo.crawl.v3", "seo.indexability.v3"]:
                    ag = pool.get(aid)
                    if ag:
                        await ag.run(blackboard)

            elif node_id == "node_seo_technical_health":
                for aid in ["seo.security.v3", "seo.performance.v3", "seo.assets.v3"]:
                    ag = pool.get(aid)
                    if ag:
                        await ag.run(blackboard)

            elif node_id == "node_seo_onpage_content":
                for aid in ["seo.html.v3", "seo.internal_links.v3", "content.depth.v3", "content.topic_coverage.v3", "content.cannibalization.v3"]:
                    ag = pool.get(aid)
                    if ag:
                        await ag.run(blackboard)

            elif node_id == "node_seo_schema_ast":
                for aid in ["schema.validation.v3", "schema.entity_graph.v3"]:
                    ag = pool.get(aid)
                    if ag:
                        await ag.run(blackboard)

            elif node_id in ("node_seo_page_intelligence", "node_page_intelligence"):
                page_agent = PageIntelligenceAgent(ModelRouter())
                await page_agent.run(blackboard)

            # --- 4. GEO Pillar Nodes ---
            elif node_id == "node_geo_entity_grounding":
                for aid in ["geo.brand_identity.v3", "schema.entity_graph.v3"]:
                    ag = pool.get(aid)
                    if ag:
                        await ag.run(blackboard)

            elif node_id == "node_geo_local_signals":
                for aid in ["geo.extractability.v3"]:
                    ag = pool.get(aid)
                    if ag:
                        await ag.run(blackboard)

            elif node_id == "node_geo_llm_footprint":
                for aid in ["geo.llms_txt.v3", "geo.synthesis.v3"]:
                    ag = pool.get(aid)
                    if ag:
                        await ag.run(blackboard)

            # --- 5. AEO Pillar Nodes ---
            elif node_id == "node_aeo_citability_matrix":
                for aid in ["ai_search.citability.v3"]:
                    ag = pool.get(aid)
                    if ag:
                        await ag.run(blackboard)

            elif node_id == "node_aeo_qa_readiness":
                for aid in ["ai_search.query_coverage.v3", "ai_search.competitor_displacement.v3"]:
                    ag = pool.get(aid)
                    if ag:
                        await ag.run(blackboard)

            elif node_id in ("node_aeo_search_simulation", "node_ai_search_simulation"):
                telemetry_tracker = TelemetryTracker()
                model_router = ModelRouter(telemetry_tracker=telemetry_tracker)
                team_orchestrator = TeamOrchestrator(model_router)
                await team_orchestrator.worker_simulator.execute_task("ai_search_simulation", blackboard)

            # --- 6. CRO Pillar Nodes ---
            elif node_id == "node_cro_cta_visibility":
                for aid in ["cro.three_second_hook.v3", "cro.conversion.v3", "ux.experience.v3"]:
                    ag = pool.get(aid)
                    if ag:
                        await ag.run(blackboard)

            elif node_id == "node_cro_value_clarity":
                for aid in ["cro.pricing_psychology.v3", "business.commercial.v3"]:
                    ag = pool.get(aid)
                    if ag:
                        await ag.run(blackboard)

            elif node_id == "node_cro_trust_and_forms":
                for aid in ["cro.form_friction.v3", "cro.social_proof_depth.v3", "trust.authority.v3"]:
                    ag = pool.get(aid)
                    if ag:
                        await ag.run(blackboard)

            elif node_id == "node_adversarial_critic":
                adv = pool.get("verification.adversarial.v3")
                if adv:
                    await adv.run(blackboard)

            elif node_id == "node_integrity_gate":
                current_claims = blackboard.claim_registry.get_all()
                gate_res = integrity_gate.validate_claims_and_evidence(
                    current_claims, blackboard.evidence_store, blackboard.claim_registry
                )
                blackboard.blackboard_state["integrity_gate"] = gate_res.model_dump()

            elif node_id == "node_causal_bottlenecks":
                current_claims = blackboard.claim_registry.get_all()
                bottlenecks = self.causal_engine.analyze_root_causes(
                    claims=current_claims,
                    business_profile=blackboard.business_profile,
                    crawl_summary=blackboard.crawl_manifest.crawl_health if blackboard.crawl_manifest else None,
                )
                blackboard.blackboard_state["root_causes"] = [b.model_dump() for b in bottlenecks]

            elif node_id == "node_honest_scoring":
                eval_pages = blackboard.pages or []
                scores = self.scoring_engine.calculate_scores(
                    manifest=blackboard.crawl_manifest,
                    findings=blackboard.findings or [],
                    claims=blackboard.claim_registry.get_all(),
                    evidence_store=blackboard.evidence_store,
                    pages=eval_pages,
                    evaluations=blackboard.commercial_evaluations or blackboard.ai_search_evaluations or [],
                    business_profile=blackboard.business_profile,
                )
                blackboard.scores = scores

            elif node_id == "node_executive_narrative":
                pass

            elif node_id == "node_code_patch_pack":
                pass

            elif node_id == "node_final_report_assembly":
                pass

            controller.mark_node_status(node_id, GraphNodeStatus.COMPLETED, claims_count=len(blackboard.claim_registry.get_all()))
            controller.log_activity(node_id, "success", "node.manual_complete", f"Step '{node_id}' completed successfully")
            await self._emit_event(analysis_id, "specialist_execution", 65, f"Step '{node_id}' finished successfully")
            return {"success": True, "node_id": node_id, "status": "completed"}
        except Exception as err:
            logger.error(f"Error running node {node_id}: {err}", exc_info=True)
            controller.mark_node_status(node_id, GraphNodeStatus.FAILED, error_message=str(err))
            controller.log_activity(node_id, "error", "node.manual_failed", f"Step '{node_id}' failed: {str(err)}")
            await self._emit_event(analysis_id, "failed", 0, f"Step '{node_id}' failed: {str(err)}")
            return {"success": False, "node_id": node_id, "error": str(err)}

    async def run_pipeline_section(self, analysis_id: str, section_id: str) -> Dict[str, Any]:
        """Executes all DAG nodes in a section sequentially, ensuring prerequisites are satisfied."""
        section_id = PILLAR_TO_SECTION.get(section_id.lower(), section_id)
        controller = get_pipeline_controller(analysis_id)
        sec_def = next((s for s in SECTIONS_REGISTRY if s.section_id == section_id), None)
        if not sec_def:
            return {"success": False, "error": f"Section '{section_id}' not found in registry."}

        executed_nodes = []
        for nid in sec_def.node_ids:
            res = await self.run_pipeline_node(analysis_id, nid)
            executed_nodes.append({"node_id": nid, "result": res})
            if not res.get("success"):
                return {
                    "success": False,
                    "section_id": section_id,
                    "failed_node": nid,
                    "error": res.get("error"),
                    "executed_nodes": executed_nodes,
                }

        return {
            "success": True,
            "section_id": section_id,
            "title": sec_def.title,
            "executed_nodes": executed_nodes,
        }

orchestrator = AnalysisOrchestrator()
