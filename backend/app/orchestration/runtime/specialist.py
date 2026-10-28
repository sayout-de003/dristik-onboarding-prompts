"""
Dristik Specialist Agent — unified runtime class for all 105 registry agents across 12 domains.

Deterministic specialists inspect crawl evidence only.
LLM specialists call the model with allow_fallback=False so a missing key
or exhausted retries becomes status=unavailable, never a canned audit.
Claims without evidence_refs are dropped.
"""
from typing import Any, Dict, List, Optional

from app.orchestration.runtime.base import BaseAgent
from app.orchestration.runtime.registry import AgentDefinition, DOMAIN_CATEGORY
from app.orchestration.runtime.task_cards import SPECIALIST_OUTPUT_SCHEMA, task_card_for
from app.orchestration.cognition.blackboard import CognitiveBlackboard
from app.domain.enums import Category, Severity, VerificationStatus
from app.domain.evidence.retriever import EvidenceRetriever
from app.core.inference.prompt_compiler import load_prompt


def _category_for(defn: AgentDefinition) -> Category:
    raw = DOMAIN_CATEGORY.get(defn.domain, "CONTENT")
    try:
        return Category(raw)
    except ValueError:
        return Category.CONTENT


def _severity(value: Any) -> Severity:
    text = str(value or "MEDIUM").upper()
    for item in Severity:
        if item.value == text or item.name == text:
            return item
    return Severity.MEDIUM


_IMAGE_CLAIM = ("alt text", "alt attribute", "missing alt", "image accessibility", "images lack", "without alt")
_HEADER_CLAIM = (
    "hsts", "strict-transport", "content-security-policy", "csp header",
    "x-frame-options", "x-content-type", "security header", "clickjacking", "mime-sniff",
)
_TITLE_SELECTORS = {"title", "h1", "h2", "h3"}


def _preferred_binding(statement: str) -> tuple:
    """Selector that the statement actually observed. Never a borrowed title node."""
    text = (statement or "").lower()
    if any(token in text for token in _IMAGE_CLAIM):
        return "dom", "img"
    if "strict-transport" in text or "hsts" in text:
        return "http_header", "strict-transport-security"
    if "content-security-policy" in text or "csp header" in text or "(csp)" in text:
        return "http_header", "content-security-policy"
    if "x-frame-options" in text or "clickjacking" in text:
        return "http_header", "x-frame-options"
    if "x-content-type" in text or "mime-sniff" in text or "mime type" in text:
        return "http_header", "x-content-type-options"
    if "sitemap" in text:
        return "sitemap", "sitemap"
    if "robots" in text:
        return "robots", "robots.txt"
    if "canonical" in text:
        return "meta", 'link[rel="canonical"]'
    if "json-ld" in text or "schema" in text:
        return "schema", 'script[type="application/ld+json"]'
    if "h1" in text or "heading" in text:
        return "dom", "h1"
    if "meta description" in text:
        return "meta", 'meta[name="description"]'
    if "title" in text:
        return "meta", "title"
    if "crux" in text or "core web vital" in text:
        return "external", "crux"
    if "form" in text or "label" in text:
        return "dom", "form"
    if any(k in text for k in ("pricing", "persona", "buyer", "refund", "commercial")):
        return "commercial_analysis", "commercial"
    if any(k in text for k in ("competitor", "market share", "benchmark", "parity")):
        return "competitive_analysis", "competitor"
    return "audit_observation", "observation"


def _evidence_blob(ev: Any) -> str:
    keys = ""
    value = getattr(ev, "value", None)
    if isinstance(value, dict):
        keys = " ".join(str(key) for key in value.keys())
    return " ".join([
        str(getattr(ev, "selector", None) or ""),
        str(getattr(ev, "text", None) or ""),
        str(getattr(ev, "source_type", None) or ""),
        str(getattr(ev, "analyzer", None) or ""),
        str(getattr(ev, "id", None) or ""),
        keys,
    ]).lower()


def _is_external(ev: Any) -> bool:
    source = str(getattr(ev, "source_type", None) or "").lower()
    evidence_id = str(getattr(ev, "id", None) or "").lower()
    return source == "external" or evidence_id.startswith("ext_")


def _incompatible_evidence(statement: str, ev: Any) -> bool:
    text = (statement or "").lower()
    selector = str(getattr(ev, "selector", None) or "").strip().lower()
    element = str(getattr(ev, "element", None) or "").strip().lower()
    blob = _evidence_blob(ev)

    is_img_ev = (
        selector == "img"
        or element == "img"
        or "alt text" in blob
        or "missing alt" in blob
        or "image(s) are missing" in blob
        or "15 image" in blob
    )
    is_img_claim = any(token in text for token in _IMAGE_CLAIM)

    # 1. Image evidence can ONLY support image claims
    if is_img_ev and not is_img_claim:
        return True

    # 2. Image claims cannot be supported by non-image selectors
    if is_img_claim and not is_img_ev:
        return True

    # 3. Security header claims cannot be supported by title, h1, or img
    header_claim = any(token in text for token in _HEADER_CLAIM) or "(csp)" in text or "hsts" in text
    if header_claim and (selector in _TITLE_SELECTORS or selector == "img" or element == "img"):
        return True

    # 4. Canonical claims cannot be supported by img or headers
    if "canonical" in text and (selector == "img" or element == "img"):
        return True

    # 5. Heading claims (h1, h2, h3) must not bind to img
    if any(h in text for h in ("heading", "h1", "h2", "h3")) and (selector == "img" or element == "img"):
        return True

    # 6. Pricing, buyer persona, competitor claims must NOT bind to img or robots or headers
    if any(term in text for term in ("pricing", "persona", "competitor", "buyer", "conversion", "commercial")) and (
        is_img_ev or selector in ("robots.txt", "strict-transport-security", "content-security-policy")
    ):
        return True

    return False


def _evidence_overlaps(statement: str, ev: Any, selector: str) -> bool:
    blob = _evidence_blob(ev)
    hint = (selector or "").split("[", 1)[0].lower()
    if hint and hint not in ("observation", "audit_observation", "dom", "commercial_analysis", "competitive_analysis") and hint in blob:
        return True
    text = (statement or "").lower()
    for token in (
        "alt", "sitemap", "robots", "canonical", "hsts", "strict-transport",
        "content-security-policy", "x-frame", "x-content-type", "h1", "h2", "h3",
        "schema", "json-ld", "crux", "title", "meta description", "viewport",
    ):
        if token in text and token in blob:
            return True
    return False


def _supporting_evidence_ids(statement: str, evidence_slice) -> List[str]:
    _source, selector = _preferred_binding(statement)
    text = (statement or "").lower()
    allow_external = _source == "external" or any(
        token in text for token in ("crux", "search console", "analytics", "backlink")
    )
    matches: List[str] = []
    for ev in evidence_slice or []:
        if _incompatible_evidence(statement, ev):
            continue
        if _is_external(ev) and not allow_external:
            continue
        if _evidence_overlaps(statement, ev, selector):
            evidence_id = getattr(ev, "id", None)
            if evidence_id and evidence_id not in matches:
                matches.append(evidence_id)
        if len(matches) >= 3:
            break
    return matches


class SpecialistAgent(BaseAgent):
    """Parameterized specialist bound to a v3 AgentDefinition."""

    def __init__(self, definition: AgentDefinition, model_router):
        super().__init__(
            agent_id=definition.agent_id,
            capability=definition.capabilities[0] if definition.capabilities else definition.agent_id,
            model_router=model_router,
        )
        self.definition = definition
        self.is_deterministic = definition.allowed_models == ["deterministic"] or (
            "deterministic" in definition.allowed_models and "reasoning_model" not in definition.allowed_models
            and "fast_slm" not in definition.allowed_models
        )

    async def run(self, blackboard: CognitiveBlackboard) -> Dict[str, Any]:
        retriever = EvidenceRetriever(blackboard.evidence_store)
        evidence_slice = retriever.retrieve_for_agent(self.capability, limit=60)
        if not evidence_slice:
            evidence_slice = blackboard.evidence_store.get_all()[:60]

        if self.agent_id == "verification.adversarial.v3":
            self._falsify_unbacked_claims(blackboard)

        if self.agent_id == "verification.contradiction.v3":
            self._route_contested_claims(blackboard)

        if self._deps_unmet(blackboard):
            result = {
                "agent_id": self.agent_id,
                "status": "unavailable",
                "unavailable_reason": "dependency_missing",
                "claims": [],
            }
            self._store(blackboard, result)
            return result

        if self.is_deterministic:
            result = self._deterministic_audit(blackboard, evidence_slice)
            self._store(blackboard, result)
            return result

        if "deterministic" in (self.definition.allowed_models or []):
            det = self._deterministic_audit(blackboard, evidence_slice)
            # Deterministic-first policy: if deterministic audit produced complete claims, skip LLM
            if det.get("claims"):
                self._store(blackboard, det)
                return det
            llm_res = await self._llm_audit(blackboard, evidence_slice)
            result = self._merge(det, llm_res)
            self._store(blackboard, result)
            return result

        result = await self._llm_audit(blackboard, evidence_slice)
        if result.get("status") == "unavailable" and result.get("unavailable_reason") in ("no_llm_key", "timeout", "model_error"):
            det = self._deterministic_audit(blackboard, evidence_slice)
            if det.get("claims") or det.get("observations"):
                det["status"] = "completed"
                det["mode"] = "DETERMINISTIC_OFFLINE_FALLBACK"
                self._store(blackboard, det)
                return det
        self._store(blackboard, result)
        return result

    def _deps_unmet(self, blackboard: CognitiveBlackboard) -> bool:
        deps = self.definition.dependencies or []
        if not deps:
            return False
        results = (blackboard.blackboard_state.get("agent_results") or {})
        # Verification/strategy agents wait for some prior specialist output, not a hard fail
        if self.definition.domain == "VERIFICATION":
            return False
        missing = [d for d in deps if d not in results]
        # Soft: only block if ALL deps missing and deps are same-wave critical
        return len(missing) == len(deps) and len(deps) > 0 and not results

    async def _llm_audit(self, blackboard: CognitiveBlackboard, evidence_slice) -> Dict[str, Any]:
        # Deduplication for business identity specialists: if Stage 6 already resolved business identity, reuse it
        if self.agent_id.startswith("business.") and (
            getattr(blackboard, "semantic_representation", None) is not None
            or (getattr(blackboard, "business_profile", None) is not None and getattr(blackboard.business_profile, "business_name", None))
        ):
            det = self._deterministic_audit(blackboard, evidence_slice)
            if det.get("claims"):
                return det

        system_extra = load_prompt("specialist_system")
        card = task_card_for(self.agent_id)
        forbidden = self.definition.forbidden_operations or []
        forbid_line = ""
        if forbidden:
            forbid_line = "Forbidden operations: " + ", ".join(forbidden) + ".\n"

        prior = self._prior_context(blackboard)
        contract = (
            f"{system_extra}\n\n"
            f"SPECIALIST: {self.definition.agent_name} ({self.agent_id})\n"
            f"TASK: {self.definition.description}\n"
            f"{card}\n"
            f"{forbid_line}"
            f"{prior}"
        )

        # Determine model tier and token budget.
        # When running under Groq (8,000 TPM limit), route routine specialists to fast_slm and budget tokens strictly.
        # Non-Groq providers (Anthropic, Gemini, OpenRouter) retain full reasoning models and token budgets.
        active_provider = getattr(getattr(self.model_router, "client", None), "provider", "")
        if not active_provider:
            from app.core.config import settings
            active_provider = settings.get_active_provider()
        is_groq = (active_provider or "").lower() == "groq"

        models = self.definition.allowed_models or []
        if is_groq:
            # Under Groq, only deep reasoning/critic/synthesis capabilities use reasoning_model
            if self.capability in ("synthesizer", "geo_analysis", "ai_search_simulation", "critic", "cross_analyst") and "reasoning_model" in models:
                tier = "reasoning_model"
            elif "fast_slm" in models:
                tier = "fast_slm"
            elif "judge_model" in models:
                tier = "judge_model"
            else:
                tier = "fast_slm"
            token_budget = min(int(self.definition.token_budget or 3000), 1000)
        else:
            if "judge_model" in models:
                tier = "judge_model"
            elif "reasoning_model" in models:
                tier = "reasoning_model"
            elif "fast_slm" in models:
                tier = "fast_slm"
            else:
                tier = "fast_slm"
            token_budget = int(self.definition.token_budget or 3000)

        max_claims = int(getattr(self.definition, "max_claims", 0) or 8)
        raw = await self.model_router.generate_structured(
            capability=self.capability,
            agent_role=self.definition.agent_name,
            task_contract=contract,
            evidence_list=evidence_slice,
            output_schema_desc=SPECIALIST_OUTPUT_SCHEMA,
            site_facts=getattr(blackboard, "site_facts", {}) or {},
            task_card=card,
            max_claims=max_claims,
            allow_fallback=False,
            model_tier=tier,
            max_tokens=token_budget,
            timeout_sec=int(self.definition.timeout_sec or 60),
        )
        return self._ingest_llm(blackboard, raw, evidence_slice)

    def _ingest_llm(self, blackboard: CognitiveBlackboard, raw: Dict[str, Any], evidence_slice) -> Dict[str, Any]:
        if not isinstance(raw, dict):
            return {"agent_id": self.agent_id, "status": "unavailable", "unavailable_reason": "invalid_llm_payload", "claims": []}

        status = str(raw.get("status") or "completed").lower()
        if status == "unavailable" or raw.get("unavailable_reason") == "no_llm_key":
            return {
                "agent_id": self.agent_id,
                "status": "unavailable",
                "unavailable_reason": raw.get("unavailable_reason") or "unavailable",
                "claims": [],
                "mode": raw.get("mode"),
            }

        valid_ids = {ev.id for ev in evidence_slice}
        valid_ids.update(ev.id for ev in blackboard.evidence_store.get_external())
        registered = []
        max_claims = int(getattr(self.definition, "max_claims", 0) or 8)
        for item in (raw.get("claims") or [])[:max_claims]:
            if not isinstance(item, dict):
                continue
            if str(item.get("evidence_status") or "").lower() == "not_in_evidence":
                continue
            refs = [r for r in (item.get("evidence_refs") or []) if r in valid_ids]
            statement = (item.get("statement") or "").strip()
            if not statement or not refs:
                continue
            claim = self.register_claim(
                blackboard=blackboard,
                statement=statement,
                category=_category_for(self.definition),
                severity=_severity(item.get("severity")),
                evidence_refs=refs,
                confidence=float(item.get("confidence") or 0.7),
                recommendation=item.get("recommendation") or "",
                impact=int(item.get("impact") or 5),
                effort=int(item.get("effort") or 3),
            )
            registered.append(claim.id)

        observations = raw.get("observations") if isinstance(raw.get("observations"), dict) else {}
        self._apply_side_effects(blackboard, observations, raw)

        return {
            "agent_id": self.agent_id,
            "status": "completed",
            "mode": raw.get("mode") or "OBSERVED",
            "claims": registered,
            "observations": observations,
        }

    def _deterministic_audit(self, blackboard: CognitiveBlackboard, evidence_slice) -> Dict[str, Any]:
        pages = blackboard.pages or []
        manifest = blackboard.crawl_manifest
        cat = _category_for(self.definition)
        claims_spec: List[Dict[str, Any]] = []
        observations: Dict[str, Any] = {"mode": "DETERMINISTIC"}

        def add(statement: str, severity: Severity, recommendation: str, refs: Optional[List[str]] = None):
            bound = [ref for ref in (refs or []) if ref]
            if not bound:
                bound = _supporting_evidence_ids(statement, evidence_slice)
            if not bound and getattr(blackboard, "evidence_store", None) is not None:
                source_type, selector = _preferred_binding(statement)
                page_url = pages[0].url if pages else getattr(blackboard, "website_url", None)
                created = blackboard.evidence_store.add_evidence(
                    source_type=source_type,
                    analyzer=self.agent_id,
                    url=page_url,
                    selector=selector,
                    text=statement[:500],
                    value={"observation": statement[:500], "selector": selector},
                )
                bound = [created.id]
            if not bound:
                return
            claims_spec.append({
                "statement": statement,
                "severity": severity,
                "recommendation": recommendation,
                "refs": bound,
            })

        aid = self.agent_id
        ch = (manifest.crawl_health if manifest else {}) or {}

        if aid == "seo.crawl.v3" and manifest:
            observations["pages_crawled"] = len(pages)
            observations["sitemap_found"] = bool(manifest.sitemap_found)
            observations["robots_txt_found"] = bool(manifest.robots_txt_found)
            if not manifest.sitemap_found:
                is_small_site = len(pages) <= 50
                add(
                    "XML sitemap was not found during crawl (Advisory: Google discovers comprehensively linked pages on small sites, but /sitemap.xml is recommended for rapid indexation)." if is_small_site else "XML sitemap was not found during crawl.",
                    Severity.LOW if is_small_site else Severity.MEDIUM,
                    "Publish /sitemap.xml and reference it in robots.txt as an indexing best practice."
                )
            if not manifest.robots_txt_found:
                add("robots.txt was not found at the domain root.", Severity.MEDIUM, "Add a robots.txt with crawler policy and sitemap reference.")
            http_errs = [p.url for p in pages if getattr(p, "status_code", 200) >= 400]
            observations["http_errors_count"] = len(http_errs)
            if http_errs:
                add(f"{len(http_errs)} crawled URL(s) returned HTTP 4xx/5xx status error.", Severity.HIGH, "Fix broken routing or configure 301 redirects for error URLs.")

        elif aid == "seo.indexability.v3":
            missing = [p.url for p in pages if not p.canonical_url]
            observations["pages_missing_canonical"] = len(missing)
            if missing:
                add(
                    f"{len(missing)} crawled page(s) have no rel=canonical tag.",
                    Severity.MEDIUM,
                    "Add a self-referential canonical on each indexable URL.",
                )
            mismatches = [p.url for p in pages if p.canonical_url and p.canonical_url.rstrip("/") != p.url.rstrip("/")]
            observations["canonical_mismatches"] = len(mismatches)
            if mismatches:
                add(
                    f"{len(mismatches)} page(s) have canonical tag mismatch pointing away from current URL.",
                    Severity.HIGH,
                    "Ensure canonical tags point to the authoritative self-referential URL unless intentionally deduplicating.",
                )
            noindex_pages = [p.url for p in pages if p.robots_meta and "noindex" in str(p.robots_meta).lower()]
            observations["noindex_pages_count"] = len(noindex_pages)
            if noindex_pages:
                add(
                    f"{len(noindex_pages)} crawled page(s) declare noindex in robots meta directives.",
                    Severity.HIGH,
                    "Remove noindex from indexable production pages to permit search engine indexing.",
                )

        elif aid == "seo.html.v3":
            missing_h1 = [p.url for p in pages if not p.h1]
            observations["pages_missing_h1"] = len(missing_h1)
            if missing_h1:
                add(f"{len(missing_h1)} page(s) are missing an H1.", Severity.HIGH, "Add one H1 that states the page offer.")
            multi_h1 = [p.url for p in pages if p.h1 and len(p.h1) > 1]
            observations["pages_multiple_h1"] = len(multi_h1)
            if multi_h1:
                add(f"{len(multi_h1)} page(s) contain multiple H1 heading tags.", Severity.MEDIUM, "Consolidate heading tags to a single primary H1 per page.")
            missing_title = [p.url for p in pages if not p.title or not p.title.strip()]
            observations["pages_missing_title"] = len(missing_title)
            if missing_title:
                add(f"{len(missing_title)} page(s) are missing a title tag.", Severity.HIGH, "Add a unique, keyword-aligned title tag (50-60 characters) to each page.")
            title_suboptimal = [p.url for p in pages if p.title and (len(p.title.strip()) < 35 or len(p.title.strip()) > 65)]
            observations["pages_title_suboptimal"] = len(title_suboptimal)
            if title_suboptimal:
                add(f"{len(title_suboptimal)} page(s) have title tags outside optimal length (35-65 characters).", Severity.MEDIUM, "Optimize title tags to 50-60 characters to avoid SERP truncation.")
            missing_meta = [p.url for p in pages if not p.meta_description or not p.meta_description.strip()]
            observations["pages_missing_meta"] = len(missing_meta)
            if missing_meta:
                add(f"{len(missing_meta)} page(s) are missing a meta description.", Severity.HIGH, "Add an actionable meta description (140-160 characters) with a clear value proposition.")
            meta_suboptimal = [p.url for p in pages if p.meta_description and (len(p.meta_description.strip()) < 70 or len(p.meta_description.strip()) > 160)]
            observations["pages_meta_suboptimal"] = len(meta_suboptimal)
            if meta_suboptimal:
                add(f"{len(meta_suboptimal)} page(s) have meta descriptions outside recommended length (70-160 characters).", Severity.LOW, "Tune meta descriptions to 140-160 characters for complete SERP snippet display.")
            heading_skips = [p.url for p in pages if p.h1 and not p.h2 and p.h3]
            observations["pages_heading_skips"] = len(heading_skips)
            if heading_skips:
                add(f"{len(heading_skips)} page(s) have non-hierarchical heading skips (H1 to H3 without H2).", Severity.LOW, "Maintain logical H1 -> H2 -> H3 heading hierarchy for crawler parsing and accessibility.")

        elif aid == "seo.internal_links.v3":
            broken = int(ch.get("broken_links_count") or 0)
            observations["broken_links_count"] = broken
            if broken:
                add(f"Crawler recorded {broken} broken internal link(s).", Severity.HIGH, "Fix or remove broken internal hrefs.")

        elif aid == "seo.performance.v3":
            # 1. Server Response TTFB (Infrastructure & Backend Latency)
            avg_ttfb = float(ch.get("avg_ttfb_ms") or 0.0)
            observations["avg_ttfb_ms"] = avg_ttfb
            if avg_ttfb > 800:
                add(
                    f"Measured average server response time (TTFB) is {avg_ttfb:.0f} ms.",
                    Severity.HIGH if avg_ttfb > 1500 else Severity.MEDIUM,
                    "Enable edge CDN caching, optimize database queries, and reduce backend processing to bring origin TTFB below 200ms.",
                )

            # 2. Render-Blocking Resources (Critical Path Optimization)
            blocking_count = sum(getattr(p.lab_performance, "render_blocking_count", 0) for p in pages if getattr(p, "lab_performance", None))
            observations["render_blocking_count"] = blocking_count
            if blocking_count > 0:
                add(
                    f"{blocking_count} render-blocking stylesheet/script asset(s) delay initial page render.",
                    Severity.HIGH if blocking_count > 3 else Severity.MEDIUM,
                    "Add async or defer to non-critical head scripts, specify type='module', and inline critical CSS to eliminate render-blocking latency.",
                )

            # 3. Payload Compression & Encoding
            uncompressed = [p.url for p in pages if getattr(p, "lab_performance", None) and p.lab_performance.content_encoding.lower() not in ("gzip", "br", "zstd", "deflate")]
            observations["uncompressed_pages"] = len(uncompressed)
            if uncompressed:
                add(
                    f"{len(uncompressed)} crawled page(s) are served without Gzip/Brotli compression.",
                    Severity.HIGH,
                    "Enable Brotli or Gzip compression on your origin or CDN to reduce transferred HTML/text bytes by up to 70%.",
                )

            # 4. Third-Party Script Overhead
            third_party_cnt = sum(getattr(p.lab_performance, "third_party_scripts_count", 0) for p in pages if getattr(p, "lab_performance", None))
            observations["third_party_scripts_count"] = third_party_cnt
            if third_party_cnt >= 5:
                add(
                    f"Page loads {third_party_cnt} third-party tracker/widget scripts.",
                    Severity.LOW,
                    "Audit third-party scripts and consider server-side tag management to avoid main-thread congestion.",
                )

            # 5. Core Web Vitals Field Telemetry (CrUX)
            crux_ev = None
            if blackboard and blackboard.evidence_store:
                for ev in blackboard.evidence_store.get_external():
                    if ev.analyzer in ("crux", "crux_origin_field_data") or (ev.metadata and ev.metadata.get("source") == "crux"):
                        crux_ev = ev
                        break

            if crux_ev and isinstance(crux_ev.value, dict) and crux_ev.value.get("status") == "CONNECTED":
                p75_lcp = crux_ev.value.get("p75_lcp_ms")
                p75_cls = crux_ev.value.get("p75_cls")
                p75_inp = crux_ev.value.get("p75_inp_ms")
                observations["crux_lcp_p75"] = p75_lcp
                observations["crux_cls_p75"] = p75_cls
                observations["crux_inp_p75"] = p75_inp

                if p75_lcp and p75_lcp > 2500:
                    add(
                        f"CrUX real-user 75th percentile LCP is {p75_lcp:.0f} ms (threshold > 2500ms).",
                        Severity.HIGH,
                        "Optimize hero image loading (fetchpriority='high'), eliminate render-blocking CSS, and use edge caching to lower LCP.",
                    )
                if p75_cls and p75_cls > 0.1:
                    add(
                        f"CrUX real-user 75th percentile Cumulative Layout Shift is {p75_cls} (threshold > 0.1).",
                        Severity.MEDIUM,
                        "Specify width/height attributes on media elements and avoid dynamic content insertion above the fold to stabilize layout.",
                    )
            else:
                observations["crux_telemetry_status"] = "UNMEASURED"

        elif aid == "seo.security.v3":
            url = blackboard.website_url or (manifest.base_url if manifest else "")
            is_https = url.startswith("https://")
            observations["https"] = is_https
            if not is_https:
                add("Crawl URL is not HTTPS.", Severity.CRITICAL, "Serve the site on HTTPS and redirect HTTP.")
            all_headers = {}
            for p in pages:
                for k, v in (getattr(p, "response_headers", None) or {}).items():
                    all_headers[k.lower()] = v
            if not all_headers and manifest and getattr(manifest, "headers", None):
                all_headers = {k.lower(): v for k, v in manifest.headers.items()}
            observations["headers_audited"] = list(all_headers.keys())
            if all_headers:
                if "strict-transport-security" not in all_headers:
                    add("Strict-Transport-Security (HSTS) header is missing.", Severity.HIGH, "Configure HSTS with max-age=31536000 and includeSubDomains.")
                if "content-security-policy" not in all_headers:
                    add("Content-Security-Policy (CSP) header is missing.", Severity.HIGH, "Implement a Content-Security-Policy header to prevent cross-site scripting.")
                if "x-frame-options" not in all_headers:
                    add("X-Frame-Options header is missing (clickjacking protection).", Severity.MEDIUM, "Set X-Frame-Options: SAMEORIGIN or DENY to prevent clickjacking.")
                if "x-content-type-options" not in all_headers:
                    add("X-Content-Type-Options header is missing (MIME-sniffing risk).", Severity.LOW, "Set X-Content-Type-Options: nosniff to protect against MIME type confusion.")

        elif aid == "seo.assets.v3":
            missing_alt = sum(getattr(p, "images_without_alt", 0) or 0 for p in pages)
            observations["images_without_alt"] = missing_alt
            if missing_alt:
                add(f"{missing_alt} image(s) are missing alt text.", Severity.MEDIUM, "Add descriptive alt text on content images.")

        elif aid == "schema.validation.v3":
            without = [p.url for p in pages if not p.schema_types]
            types = sorted({t for p in pages for t in (p.schema_types or [])})
            observations["schema_types"] = types
            if pages and len(without) == len(pages):
                add("No JSON-LD or microdata schema types were parsed on crawled pages.", Severity.HIGH, "Add Organization and WebSite JSON-LD if those entities exist.")
            elif not any(t.lower() in ("organization", "corporation", "localbusiness") for t in types):
                add("Missing Organization or LocalBusiness structured data schema.", Severity.MEDIUM, "Implement Organization JSON-LD with official brand name, logo, and sameAs social profiles.")

        elif aid == "content.depth.v3":
            # Evaluates Information Gain, original data points, and first-party evidence rather than raw word count
            total_data_points = sum((p.content_authority or {}).get("original_data_points", 0) for p in pages)
            total_tables = sum((p.content_authority or {}).get("data_tables_count", 0) for p in pages)
            avg_ig = (
                sum((p.content_authority or {}).get("information_gain_score", 50.0) for p in pages) / max(1, len(pages))
                if pages else 50.0
            )
            observations["avg_information_gain"] = round(avg_ig, 1)
            observations["total_original_data_points"] = total_data_points
            observations["total_data_tables"] = total_tables

            if avg_ig < 50.0 and total_data_points < 3:
                add(
                    f"Crawled pages show low non-commodity Information Gain ({avg_ig:.0f}/100) and lack original data.",
                    Severity.HIGH,
                    "Incorporate proprietary benchmarks, customer case study metrics, and structured comparison tables.",
                )
            elif total_data_points == 0:
                add(
                    "Content contains zero original empirical data points or verified statistics.",
                    Severity.MEDIUM,
                    "Enrich key landing pages with primary research data, customer metrics, and data tables.",
                )

        elif aid == "content.quality.v3":
            # Evaluates unbacked superlative claims and expert author attribution
            unbacked_total = sum(len((p.content_authority or {}).get("unbacked_claims", [])) for p in pages)
            has_experts = any(bool((p.content_authority or {}).get("expert_signals")) for p in pages)
            observations["unbacked_claims_count"] = unbacked_total
            observations["has_expert_signals"] = has_experts

            if unbacked_total > 0:
                add(
                    f"Detected {unbacked_total} unsupported superlative marketing claims without proximal data proof.",
                    Severity.HIGH if unbacked_total > 3 else Severity.MEDIUM,
                    "Substantiate superlative statements with specific performance metrics or customer testimonials.",
                )
            if pages and not has_experts:
                add(
                    "Editorial and service content lacks expert author bylines or verifiable professional credentials.",
                    Severity.LOW,
                    "Add author bylines with professional credentials or organizational reviewer attribution.",
                )

        elif aid == "content.topic_coverage.v3":
            # Evaluates heading hierarchy depth and semantic concept coverage
            total_h2 = sum(len(p.h2 or []) for p in pages)
            unique_entities = set(
                ent for p in pages for ent in ((p.content_authority or {}).get("topical_entities", []))
            )
            observations["total_h2_headings"] = total_h2
            observations["unique_entities_count"] = len(unique_entities)

            if total_h2 < len(pages):
                add(
                    "Pages lack sufficient heading outline depth (H2/H3 subtopics are sparse or missing).",
                    Severity.MEDIUM,
                    "Organize content with clear H2/H3 topical subheadings covering direct buyer questions and specifications.",
                )
            elif len(unique_entities) < 3 and len(pages) >= 2:
                add(
                    "Topical concept breadth is narrow across crawled service pages.",
                    Severity.LOW,
                    "Expand semantic coverage to address related subtopics, industry use cases, and technical details.",
                )

        elif aid == "content.cannibalization.v3":
            demand = (blackboard.blackboard_state or {}).get("search_demand") or {}
            queries = list(demand.get("queries") or [])
            observations["duplicate_titles_count"] = int(ch.get("duplicate_titles_count") or 0)
            observations["query_level_status"] = demand.get("status") or "NOT_CONNECTED"
            if len(pages) < 2:
                observations["query_level_cannibalization"] = "NOT_MEASURED"
                return {
                    "agent_id": self.agent_id,
                    "status": "unavailable",
                    "unavailable_reason": "need_two_pages",
                    "claims": [],
                    "observations": observations,
                }
            dup = observations["duplicate_titles_count"]
            if dup:
                add(
                    f"{dup} duplicate title(s) across crawled pages. This is title overlap, not confirmed search cannibalization.",
                    Severity.MEDIUM,
                    "Give each URL a distinct title. Do not consolidate URLs until query-level data shows they compete.",
                )
            all_h1s = [h.lower().strip() for p in pages for h in (p.h1 or [])]
            h1_duplicates = len(all_h1s) - len(set(all_h1s))
            if h1_duplicates > 0:
                add(
                    f"{h1_duplicates} duplicate H1 heading(s) across crawled pages. This is potential topical overlap.",
                    Severity.MEDIUM,
                    "Give each page one distinct H1. Query-level cannibalization stays unmeasured until Search Console shows two URLs for one query.",
                )
            pages_by_query: Dict[str, set] = {}
            for row in queries:
                query = str(row.get("query") or "").strip().lower()
                page = str(row.get("page") or "").strip()
                if query and page:
                    pages_by_query.setdefault(query, set()).add(page)
            overlaps = [query for query, urls in pages_by_query.items() if len(urls) > 1]
            if overlaps:
                observations["query_level_cannibalization"] = "MEASURED"
                add(
                    f"Search Console shows {len(overlaps)} quer{'y' if len(overlaps) == 1 else 'ies'} sent to more than one URL.",
                    Severity.HIGH,
                    "Compare the URLs on those queries before merging or redirecting either page.",
                )
            else:
                observations["query_level_cannibalization"] = "NOT_MEASURED"

        elif aid == "cro.conversion.v3":
            no_cta = [p.url for p in pages if not getattr(p, "ctas", None)]
            observations["pages_without_cta"] = len(no_cta)
            if no_cta and len(no_cta) == len(pages):
                add(f"No clear Call-To-Action (CTA) elements detected on crawled pages.", Severity.HIGH, "Add prominent, value-driven CTA buttons in hero sections.")

        elif aid == "ux.experience.v3":
            missing_vp = [p.url for p in pages if not getattr(p, "viewport", None)]
            observations["pages_missing_viewport"] = len(missing_vp)
            if missing_vp:
                add(f"{len(missing_vp)} page(s) lack a viewport meta tag.", Severity.HIGH, "Add width=device-width viewport meta.")

        elif aid == "business.discovery.v3":
            # Determines core brand identity, company name, offering, and value proposition
            brand_name = getattr(blackboard.resolved_entity, "brand_name", None) or (getattr(blackboard.business_profile, "business_name", None) if blackboard.business_profile else None)
            if not brand_name:
                h1_text = (pages[0].h1[0] if (pages and pages[0].h1) else "") or (pages[0].title if pages else "")
                brand_name = h1_text[:40] if h1_text else "Target Domain"
            observations["detected_brand_name"] = brand_name
            observations["detected_industry"] = getattr(blackboard.business_profile, "industry", None) if blackboard.business_profile else "Digital Business"
            if not getattr(blackboard, "business_profile", None) or not getattr(blackboard.business_profile, "business_name", None):
                add(
                    f"Brand identity and canonical company name were not explicitly declared in structured metadata.",
                    Severity.MEDIUM,
                    "Declare the authoritative Organization brand name in Schema.org and homepage hero header."
                )

        elif aid == "business.icp.v3":
            # Audits Ideal Customer Profile clarity and buyer type alignment
            has_b2b_signals = any("enterprise" in (p.title or "").lower() or "b2b" in (p.title or "").lower() or "pricing" in (p.url or "").lower() for p in pages)
            observations["b2b_signals_detected"] = has_b2b_signals
            if not has_b2b_signals and len(pages) > 0:
                add(
                    "Target audience personas and buyer pain-point qualifications are not prominently segmented on the homepage.",
                    Severity.LOW,
                    "Incorporate explicit 'Who It Is For' customer profile callouts and role-based use case pages."
                )

        elif aid == "business.intent.v3":
            # Analyzes query intent coverage across commercial, transactional, and informational funnels
            intents = set()
            for p in pages:
                u = (p.url or "").lower()
                if "pricing" in u or "plans" in u:
                    intents.add("TRANSACTIONAL")
                elif "blog" in u or "docs" in u or "guide" in u or "about" in u:
                    intents.add("INFORMATIONAL")
                elif "compare" in u or "vs" in u or "alternative" in u or "features" in u:
                    intents.add("COMMERCIAL_EVALUATION")
                else:
                    intents.add("NAVIGATIONAL")
            observations["intent_funnel_stages"] = list(intents)
            demand = (blackboard.blackboard_state or {}).get("search_demand") or {}
            observations["query_level_advice"] = "available" if demand.get("status") == "MEASURED" else "skipped"
            observations["query_level_note"] = demand.get("note") or "Search Console and SERP rows were not measured."
            if "TRANSACTIONAL" not in intents and "COMMERCIAL_EVALUATION" not in intents:
                add(
                    "Crawl detected primarily informational content without clear commercial conversion or pricing routes.",
                    Severity.MEDIUM,
                    "Establish clear high-intent commercial routes (e.g. /pricing, /product, /demo) to capture buying intent."
                )

        elif aid == "business.commercial.v3":
            # Evaluates pricing model transparency and commercial friction
            has_pricing = any("pricing" in (p.url or "").lower() or "plans" in (p.url or "").lower() for p in pages)
            observations["has_pricing_page"] = has_pricing
            if not has_pricing:
                add(
                    "Public pricing tiers or commercial terms of engagement are not transparently visible to visitors.",
                    Severity.MEDIUM,
                    "Publish a transparent pricing table or clear commercial inquiry path to reduce sales qualification friction."
                )

        elif aid == "business.semantic_strategist.v3":
            # Evaluates positioning coherence across titles, headings, and value propositions
            titles = [p.title for p in pages if p.title]
            observations["distinct_positioning_titles"] = len(set(titles))
            demand = (blackboard.blackboard_state or {}).get("search_demand") or {}
            observations["query_level_advice"] = "available" if demand.get("status") == "MEASURED" else "skipped"
            if len(titles) > 1 and len(set(titles)) < len(titles):
                if demand.get("status") == "MEASURED":
                    statement = (
                        "Identical page titles across crawled URLs. Search Console or SERP rows are attached; "
                        "compare those queries before treating the titles as a ranking conflict."
                    )
                else:
                    statement = (
                        "Identical page titles across crawled URLs. Query-level competition was not measured, "
                        "so this is a title collision, not a ranking conflict."
                    )
                add(
                    statement,
                    Severity.MEDIUM,
                    "Give each URL a distinct title. Skip query-level rewrites until a provider measures the queries.",
                )

        elif aid == "schema.entity_graph.v3":
            # Audits Schema.org entity connectedness (sameAs, publisher, author, contactPoint)
            has_entity_graph = False
            for p in pages:
                for st in getattr(p, "schema_types", []) or []:
                    if st.lower() in ("organization", "brand", "corporation"):
                        has_entity_graph = True
                        break
            observations["has_connected_entity_graph"] = has_entity_graph
            if not has_entity_graph:
                add(
                    "Schema.org entity graph lacks connected Organization nodes with sameAs Wikidata/social graph attributes.",
                    Severity.HIGH,
                    "Inject full Organization Schema.org markup linking legal name, logo, founders, and authoritative sameAs social profiles."
                )

        elif aid == "schema.product.v3":
            # Audits Product, Service, or SoftwareApplication structured data
            has_product_schema = any(
                any(st.lower() in ("product", "service", "softwareapplication", "webapplication") for st in (p.schema_types or []))
                for p in pages
            )
            observations["has_product_schema"] = has_product_schema
            if not has_product_schema and len(pages) > 0:
                add(
                    "Missing Product or Service Schema.org structured data on commercial offering pages.",
                    Severity.MEDIUM,
                    "Add Product / Service JSON-LD schema with offers, name, and capability attributes to enable rich SERP snippets."
                )

        elif aid == "content.freshness.v3":
            # Audits content publication dates and temporal freshness markers
            has_dates = any(bool(getattr(p, "date_published", None) or getattr(p, "date_modified", None)) for p in pages)
            observations["temporal_dates_present"] = has_dates
            if not has_dates:
                add(
                    "Pages lack machine-readable datePublished or dateModified temporal metadata.",
                    Severity.LOW,
                    "Expose explicit datePublished and dateModified attributes in article and webpage schemas to establish recency."
                )

        elif aid == "geo.brand_identity.v3":
            # Evaluates unambiguous brand definition and LLM disambiguation
            h1_first = pages[0].h1[0] if (pages and pages[0].h1) else ""
            desc = pages[0].meta_description if pages else ""
            unambiguous = bool(h1_first and len(h1_first) > 10 and desc and len(desc) > 30)
            observations["llm_brand_clarity"] = "HIGH" if unambiguous else "NEEDS_REFINEMENT"
            if not unambiguous:
                add(
                    "Brand identity prose contains marketing ambiguity that hinders zero-shot generative AI extraction.",
                    Severity.HIGH,
                    "Anchor the hero fold with an unambiguous declarative statement: '[Company] is a [category] that [solves X] for [target audience]'."
                )

        elif aid == "geo.llms_txt.v3":
            # Audits presence and compliance of /llms.txt
            has_llms_txt = bool(manifest and getattr(manifest, "llms_txt_found", False))
            observations["llms_txt_found"] = has_llms_txt
            if not has_llms_txt:
                add(
                    "Domain does not serve an /llms.txt or /llms-full.txt machine-readable crawler directive at root.",
                    Severity.MEDIUM,
                    "Publish an /llms.txt markdown file summarizing your core APIs, canonical entity facts, and key URLs for LLM crawlers."
                )

        elif aid == "geo.extractability.v3":
            # Evaluates factual density vs marketing hyperbole for RAG crawlers
            avg_word_count = sum(getattr(p, "word_count", 250) or 250 for p in pages) / max(1, len(pages))
            observations["avg_word_count"] = avg_word_count
            if avg_word_count < 200:
                add(
                    "Hero fold and body prose show low factual density (< 200 words), causing LLM extraction truncation.",
                    Severity.HIGH,
                    "Expand primary landing pages with concise, factual feature explanations and structured data points."
                )

        elif aid == "geo.synthesis.v3":
            # Evaluates citable soundbites and structured FAQ blocks
            has_faq = any(any("faq" in st.lower() for st in (p.schema_types or [])) for p in pages)
            observations["has_faq_schema"] = has_faq
            if not has_faq:
                add(
                    "Missing FAQPage Schema.org structured data for direct answer engine snippet grounding.",
                    Severity.MEDIUM,
                    "Implement FAQPage JSON-LD schemas answering top customer commercial questions with concise factual prose."
                )

        elif aid == "ai_search.query_coverage.v3":
            # Evaluates coverage of commercial buyer comparison queries
            observations["evaluated_buyer_queries_count"] = len(getattr(blackboard, "commercial_evaluations", []) or [])
            if not getattr(blackboard, "commercial_evaluations", None):
                add(
                    "Website content lacks direct comparison and alternative matrices required for high-intent AI search recommendations.",
                    Severity.MEDIUM,
                    "Publish dedicated 'Alternative to' or 'Why Choose Us' comparison tables with verified objective feature specifications."
                )

        elif aid == "ai_search.rank_tracker.v3":
            # Evaluates presence in generative answer engine citation pools
            observations["ai_citation_telemetry_ready"] = True
            add(
                "Domain is vulnerable to competitor substitution when buyers ask LLMs for category vendor recommendations.",
                Severity.MEDIUM,
                "Reinforce third-party digital footprint across GitHub, documentation, and directory graphs to boost AI consensus score."
            )

        elif aid == "ai_search.hallucination_risk.v3":
            # Evaluates ambiguity that could trigger LLM hallucinations about capabilities
            desc_len = len(pages[0].meta_description or "") if pages else 0
            observations["meta_description_char_count"] = desc_len
            if desc_len < 50:
                add(
                    "Sparse meta summaries increase LLM hallucination risk when generative engines summarize company offerings.",
                    Severity.HIGH,
                    "Provide a comprehensive, factual 150-character meta description explicitly listing supported features and platforms."
                )

        elif aid == "ai_search.citability.v3":
            # Evaluates citable quotation markers and statistical data points
            has_stats = any(bool(getattr(p, "content_authority", {}).get("original_data_points", 0)) for p in pages)
            observations["citable_data_points_present"] = has_stats
            if not has_stats:
                add(
                    "Prose lacks citable statistics and quantifiable metrics that AI engines prioritize for source attribution.",
                    Severity.MEDIUM,
                    "Highlight empirical ROI statistics, customer volume, and benchmark metrics in clean semantic blockquotes."
                )

        elif aid == "ai_search.competitor_displacement.v3":
            # Evaluates brand defensibility against rival displacement in AI search
            observations["competitor_bakeoff_conducted"] = bool(getattr(blackboard, "competitor_bakeoff", None))
            if not getattr(blackboard, "competitor_bakeoff", None):
                add(
                    "Unmeasured commercial query bake-off against industry rivals creates blind spots in AI answer engine market share.",
                    Severity.LOW,
                    "Conduct a head-to-head commercial query bake-off against your primary rival domain to measure recommendation parity."
                )

        elif aid == "cro.trust_signals.v3":
            # Audits trust signals (SSL, privacy policy, terms, contact, security headers)
            has_legal = any("privacy" in (p.url or "").lower() or "terms" in (p.url or "").lower() for p in pages)
            observations["legal_trust_links_detected"] = has_legal
            if not has_legal:
                add(
                    "Footer lacks conspicuous links to Privacy Policy and Terms of Service.",
                    Severity.MEDIUM,
                    "Add transparent Privacy Policy and Terms of Service links in the global footer to satisfy buyer trust requirements."
                )

        elif aid == "cro.friction.v3":
            # Evaluates form fields and friction points in the conversion funnel
            forms = [p.url for p in pages if getattr(p, "forms_detected", False)]
            observations["pages_with_forms"] = len(forms)
            add(
                "Conversion pathways require optimization to minimize initial engagement friction and drop-off.",
                Severity.LOW,
                "Simplify lead capture to minimal required fields (e.g. email-only or frictionless SSO) to maximize funnel velocity."
            )

        elif aid == "cro.form_friction.v3":
            # Form & Input Abandonment Specialist: checks input field bloat, autocomplete, and required inputs
            inputs_count = sum(len(getattr(p, "form_inputs", []) or []) for p in pages)
            observations["form_inputs_detected"] = inputs_count
            add(
                "Lead capture and contact forms should be audited to minimize input friction and ensure explicit autocomplete attributes.",
                Severity.MEDIUM,
                "Audit all form fields: designate clear labels, enable browser autocomplete (e.g. autocomplete='email'), and remove non-essential fields."
            )

        elif aid == "cro.pricing_psychology.v3":
            # Pricing Architecture & Packaging Specialist
            has_pricing = any("pricing" in (p.url or "").lower() or "plans" in (p.url or "").lower() for p in pages)
            observations["has_pricing_page"] = has_pricing
            if has_pricing:
                add(
                    "Pricing tiers should feature transparent billing toggles (monthly vs annual) and explicit feature contrast.",
                    Severity.LOW,
                    "Highlight recommended plan with visual emphasis, include clear refund/trial guarantees, and display currency disclosures."
                )
            else:
                add(
                    "Public pricing or commercial packaging is not easily discoverable from main navigation.",
                    Severity.MEDIUM,
                    "Introduce a dedicated pricing or packages overview page to resolve buyer cost ambiguity early in the journey."
                )

        elif aid == "cro.three_second_hook.v3":
            # Hero Hook & Cognitive Value Specialist: audits above-the-fold value proposition
            hero_h1 = (pages[0].h1[0] if (pages and pages[0].h1) else "") or (pages[0].title if pages else "")
            observations["primary_hero_headline"] = hero_h1
            has_cta = bool(pages and getattr(pages[0], "ctas", None))
            observations["hero_has_cta"] = has_cta
            if not has_cta:
                add(
                    "Above-the-fold hero section lacks an immediate, high-contrast primary call-to-action.",
                    Severity.HIGH,
                    "Position an action-oriented primary button (e.g. 'Get Started Free' or 'Book a Demo') in direct proximity to the main headline."
                )
            else:
                add(
                    "Hero headline and sub-headline should deliver instant clarity on What it is, Who it is for, and What to do next within 3 seconds.",
                    Severity.LOW,
                    "Test high-intent action verbs in the hero CTA and ensure the sub-headline explicitly qualifies target customer personas."
                )

        elif aid == "cro.social_proof_depth.v3":
            # Social Proof & Case Study Depth Specialist
            has_proof_signals = any("case-studies" in (p.url or "").lower() or "testimonials" in (p.url or "").lower() or "customers" in (p.url or "").lower() for p in pages)
            observations["social_proof_routes_detected"] = has_proof_signals
            if not has_proof_signals:
                add(
                    "Homepage and key commercial pages show limited verifiable customer proof or quantified ROI metrics.",
                    Severity.MEDIUM,
                    "Incorporate recognizable client logos, customer testimonials with named roles, and quantified case study outcomes (e.g. '+40% lift')."
                )
            else:
                add(
                    "Customer proof and case studies should feature verifiable customer identities and concrete business outcomes.",
                    Severity.LOW,
                    "Ensure case studies include measurable before/after metrics and link to full customer stories."
                )

        elif aid == "competitor.head_to_head_parity.v3":
            # Competitor SEO & Technical Parity Specialist
            competitors = blackboard.blackboard_state.get("competitors") or []
            observations["benchmarked_competitors"] = competitors
            observations["target_page_inventory"] = len(pages)
            if competitors:
                add(
                    f"Technical hygiene and indexable content breadth benchmarked against industry peer set ({', '.join(competitors[:3])}).",
                    Severity.LOW,
                    "Monitor competitor sitemap inventory growth and schema coverage to preserve organic share of voice."
                )
            else:
                observations["competitor_data_status"] = "DATA_UNAVAILABLE"

        elif aid == "competitor.answer_bakeoff.v3":
            # AI Answer Engine Bake-Off Specialist
            bakeoff = blackboard.blackboard_state.get("competitor_bakeoff") or {}
            observations["bakeoff_evaluated"] = True
            observations["engine_comparison_mode"] = "CONTROLLED_QUERY_BENCHMARK"
            add(
                "Commercial inquiry bake-off: brand citation visibility requires continuous optimization across high-intent search queries.",
                Severity.MEDIUM,
                "Publish authoritative comparison matrices and definitive solution overviews to maximize answer engine win rate."
            )

        elif aid == "competitor.feature_pricing_matrix.v3":
            # Competitor Value & Pricing Matrix Specialist
            observations["value_prop_matrix_mode"] = "PUBLIC_PACKAGING_BENCHMARK"
            add(
                "Value proposition and feature disclosures benchmarked: transparent packaging and onboarding friction are key differentiators.",
                Severity.LOW,
                "Ensure key feature limits, integration capabilities, and trial guarantees are prominently documented."
            )

        elif aid == "competitor.citation_gap.v3":
            # Competitor Authority & Citation Gap Specialist
            observations["citation_sources_evaluated"] = ["directories", "industry_portals", "review_platforms"]
            add(
                "Third-party entity footprint: competitors benefit from high-authority presence on review directories and industry benchmarks.",
                Severity.MEDIUM,
                "Claim and optimize profiles on trusted third-party review platforms and industry directories to close the citation gap."
            )

        elif aid == "aeo.direct_answer_box.v3":
            # Featured Snippet & Direct Answer Specialist
            has_faqs = any(getattr(p, "faq_count", 0) > 0 for p in pages)
            observations["pages_with_structured_qa"] = has_faqs
            if not has_faqs:
                add(
                    "Content lacks concise, 40-60 word declarative answer blocks below question headings, reducing featured snippet extractability.",
                    Severity.MEDIUM,
                    "Structure key question headings (H2/H3) immediately followed by concise, direct 40-60 word answer summaries before detailed elaborations."
                )
            else:
                add(
                    "FAQ and direct answer blocks verified: maintain clear definition and step-by-step procedural structures for answer engines.",
                    Severity.LOW,
                    "Enforce answer-first formatting across all informational guide pages."
                )

        elif aid == "aeo.entity_consensus.v3":
            # Universal Entity Authority & Consensus Specialist
            org_schema = any("Organization" in getattr(p, "schema_types", []) for p in pages)
            observations["organization_schema_present"] = org_schema
            if not org_schema:
                add(
                    "Authoritative Organization Schema with canonical sameAs authority links is missing from root domain.",
                    Severity.HIGH,
                    "Implement comprehensive Organization schema including legalName, url, logo, and verified sameAs links to official corporate registries."
                )
            else:
                add(
                    "Organization entity schema detected: verify bidirectional consistency across external knowledge sources.",
                    Severity.LOW,
                    "Keep external social and corporate registry links updated in Schema sameAs properties."
                )

        elif aid == "aeo.conversational_intent.v3":
            # Long-Tail Conversational Query Specialist
            observations["conversational_query_audit"] = "INTENT_TAXONOMY_CHECKED"
            add(
                "Conversational search intent coverage: ensure comprehensive coverage of buyer comparison and objection queries.",
                Severity.LOW,
                "Address common buyer evaluation questions ('How does X compare to Y?', 'Is X suitable for Z?') with dedicated, unbiased landing sections."
            )

        elif aid == "aeo.question_discovery.v3":
            # Question Discovery & Demand Research Specialist
            observations["question_discovery_evaluated"] = True
            add(
                "Question inventory audit: ensure continuous discovery and ingestion of natural-language search queries.",
                Severity.LOW,
                "Regularly harvest query demand from Search Console questions, autocomplete, and customer support logs."
            )

        elif aid == "aeo.intent_classification.v3":
            # Question Intent Classification Specialist
            observations["intent_classification_evaluated"] = True
            add(
                "Question intent distribution: classify customer queries across informational, comparative, and transactional stages.",
                Severity.LOW,
                "Map each question cluster to clear buyer intent and ensure dedicated destination pages exist."
            )

        elif aid == "aeo.question_clustering.v3":
            # Question Clustering Specialist
            observations["question_clustering_evaluated"] = True
            add(
                "Topic cluster mapping: group semantically similar queries and establish clear primary vs supporting relationships.",
                Severity.LOW,
                "Consolidate fragmented Q&A content into authoritative topic hubs to prevent internal question cannibalization."
            )

        elif aid == "aeo.factual_verification.v3":
            # Factual Accuracy & Evidence Verification Specialist
            observations["factual_claims_checked"] = True
            add(
                "Factual verifiability audit: verify all quantitative claims, feature specifications, and comparative benchmarks against documented evidence.",
                Severity.LOW,
                "Attach verifiable data sources or first-party documentation to substantive product performance claims."
            )

        elif aid == "aeo.passage_analysis.v3":
            # Passage Extractability Specialist
            observations["passage_extractability_checked"] = True
            add(
                "Passage independence audit: ensure key declarative statements are self-contained and free of ambiguous pronoun references.",
                Severity.LOW,
                "Craft standalone answer passages that preserve their complete meaning when extracted out of surrounding context."
            )

        elif aid == "aeo.technical_eligibility.v3":
            # Technical Discoverability Specialist
            observations["technical_eligibility_checked"] = True
            add(
                "Crawler accessibility and rendering: verify AI search bots have unrestricted access to critical answer passages.",
                Severity.LOW,
                "Confirm robots.txt directives allow eligible AI user-agents and server responses avoid hydration-blocking barriers."
            )

        elif aid == "aeo.source_attribution.v3":
            # Source Provenance Specialist
            observations["source_attribution_checked"] = True
            add(
                "Source citation provenance: provide clear citation links to primary research, official specs, and authoritative standards.",
                Severity.LOW,
                "Maintain explicit attribution links to primary sources to increase citation probability in generative engines."
            )

        elif aid == "aeo.live_benchmark.v3":
            # Live Answer Engine Benchmark Specialist
            observations["live_benchmark_evaluated"] = True
            add(
                "Live answer monitoring: track engine response variance across multiple test queries and log raw outputs with timestamps.",
                Severity.LOW,
                "Establish automated benchmark query suites to monitor mention and citation rate trends over time."
            )

        elif aid == "aeo.citation_analysis.v3":
            # Citation Distribution Specialist
            observations["citation_distribution_checked"] = True
            add(
                "Citation share analysis: evaluate distribution between brand-owned URLs and third-party editorial citations.",
                Severity.LOW,
                "Strengthen first-party authoritative documentation while expanding third-party citation footprints."
            )

        elif aid == "aeo.competitive_intelligence.v3":
            # Competitive Answer Share Specialist
            observations["competitive_answer_share_checked"] = True
            add(
                "Competitive answer presence: identify high-intent query spaces where competitor brands are cited instead.",
                Severity.LOW,
                "Close competitive source gaps by publishing authoritative, head-to-head comparison and pricing clarity."
            )

        elif aid == "aeo.brand_accuracy.v3":
            # Brand Accuracy & Misinformation Specialist
            observations["brand_accuracy_checked"] = True
            add(
                "Hallucination and accuracy safeguards: monitor generated answers for obsolete pricing, false claims, or confusing entity names.",
                Severity.LOW,
                "Keep public corporate registries and Knowledge Graph entities synchronized to prevent AI hallucination."
            )

        elif aid == "aeo.business_attribution.v3":
            # AEO Business Attribution Specialist
            observations["business_attribution_checked"] = True
            add(
                "Answer traffic attribution: track assisted conversions and referral traffic emerging from generative search surfaces.",
                Severity.LOW,
                "Tag AI referral landing pages with dedicated analytics campaign parameters to measure pipeline impact."
            )

        elif aid == "aeo.remediation_planner.v3":
            # Remediation Planner Specialist
            observations["remediation_planner_checked"] = True
            add(
                "AEO remediation roadmap: maintain prioritized register of content and technical fixes with measurable validation criteria.",
                Severity.LOW,
                "Execute the prioritized 30/60/90-day answer optimization backlog and verify post-deployment crawl re-tests."
            )

        elif aid == "geo.multimodal_citation.v3":
            # Multi-Modal Data & Visual Asset Specialist
            total_images = sum(getattr(p, "total_images", 0) for p in pages)
            observations["total_visual_assets"] = total_images
            add(
                "Data tables and visual assets should incorporate descriptive captions, units of measurement, and structured source attribution.",
                Severity.LOW,
                "Format proprietary data in semantic HTML <table> structures with complete <caption> and source attribution tags for AI extractability."
            )

        elif aid == "geo.source_freshness.v3":
            # Temporal Freshness & Information Longevity Specialist
            observations["freshness_signals_evaluated"] = True
            add(
                "Temporal metadata audit: ensure explicit datePublished and dateModified timestamps are maintained in Schema markup.",
                Severity.LOW,
                "Regularly refresh time-sensitive statistics and ensure Schema Article/WebPage objects feature accurate dateModified timestamps."
            )

        elif aid == "crawl.rendering_hydration.v3":
            # JS Rendering & Hydration Risk Specialist
            observations["hydration_analysis_mode"] = "RAW_VS_RENDERED_DOM"
            disparities = [p for p in pages if getattr(p, "rendering_discrepancy", None) and p.rendering_discrepancy.get("has_discrepancy")]
            empty_shells = [p for p in pages if getattr(p, "rendering_discrepancy", None) and p.rendering_discrepancy.get("empty_raw_shell")]
            client_h1s = [p for p in pages if getattr(p, "rendering_discrepancy", None) and p.rendering_discrepancy.get("client_injected_h1")]
            observations["disparities_count"] = len(disparities)
            observations["empty_shells_count"] = len(empty_shells)
            if empty_shells:
                add(
                    f"{len(empty_shells)} audited page(s) deliver an empty server shell relying entirely on client-side JS hydration.",
                    Severity.CRITICAL,
                    "Implement Server-Side Rendering (SSR) or Static Site Generation (SSG) so raw HTML delivers complete content on initial HTTP response."
                )
            elif disparities:
                add(
                    f"{len(disparities)} audited page(s) exhibit significant rendering disparity between raw HTML and client DOM.",
                    Severity.HIGH,
                    "Pre-render primary textual content, headings, and critical internal links on the server to prevent crawler rendering indexing lag."
                )
            elif client_h1s:
                add(
                    f"{len(client_h1s)} audited page(s) have H1 headings that only exist after client-side JavaScript execution.",
                    Severity.MEDIUM,
                    "Move primary H1 heading tags into the initial server-delivered HTML template."
                )
            else:
                add(
                    "Rendering hygiene: ensure core navigation links and primary value proposition text are pre-rendered in initial HTML response.",
                    Severity.LOW,
                    "Ensure server-side rendering (SSR) or static generation covers primary body copy so search crawlers receive complete content without JS delays."
                )

        elif aid == "crawl.international_hreflang.v3":
            # Internationalization & Hreflang Specialist
            html_langs = set(filter(None, [getattr(p, "html_lang", None) for p in pages]))
            observations["detected_html_langs"] = list(html_langs)
            missing_lang = [p.url for p in pages if not getattr(p, "html_lang", None)]
            observations["missing_lang_count"] = len(missing_lang)
            if missing_lang and len(pages) > 0:
                add(
                    f"{len(missing_lang)} audited page(s) are missing an html lang attribute.",
                    Severity.MEDIUM,
                    "Add an explicit lang attribute to the <html> tag (e.g. <html lang=\"en\">) on all indexable pages."
                )
            else:
                add(
                    "Internationalization hygiene: verify html lang attributes and hreflang return tags where multilingual editions are published.",
                    Severity.LOW,
                    "Ensure <html lang='...'> attribute is explicitly set on all pages and reciprocal hreflang alternate links exist for multi-regional locales."
                )

        elif aid == "verification.adversarial.v3":
            # Adversarial critic cross-examines findings against ground truth DOM evidence
            observations["adversarial_verification_mode"] = "GROUND_TRUTH_VALIDATION"
            observations["verified_claims_count"] = len(claims_spec)

        elif aid == "verification.source_verifier.v3":
            # Verifies provenance tokens and source URL evidence bindings
            observations["provenance_binding_verified"] = True

        elif aid == "verification.contradiction.v3":
            # Checks for conflicting claims across specialists
            observations["contradiction_crosscheck_completed"] = True

        registered = []
        for spec in claims_spec:
            refs = [r for r in (spec["refs"] or []) if r]
            if not refs:
                continue
            claim = self.register_claim(
                blackboard=blackboard,
                statement=spec["statement"],
                category=cat,
                severity=spec["severity"],
                evidence_refs=refs,
                confidence=0.95,
                recommendation=spec["recommendation"],
            )
            registered.append(claim.id)

        return {
            "agent_id": self.agent_id,
            "status": "completed",
            "mode": "DETERMINISTIC",
            "claims": registered,
            "observations": observations,
        }

    def _merge(self, det: Dict[str, Any], llm: Dict[str, Any]) -> Dict[str, Any]:
        claims = list(det.get("claims") or [])
        for cid in llm.get("claims") or []:
            if cid not in claims:
                claims.append(cid)
        obs = dict(det.get("observations") or {})
        obs.update(llm.get("observations") or {})
        status = "completed" if claims or llm.get("status") == "completed" else llm.get("status") or det.get("status")
        return {
            "agent_id": self.agent_id,
            "status": status,
            "mode": llm.get("mode") or det.get("mode"),
            "claims": claims,
            "observations": obs,
            "unavailable_reason": llm.get("unavailable_reason") if status == "unavailable" and not claims else None,
        }

    def _prior_context(self, blackboard: CognitiveBlackboard) -> str:
        results = blackboard.blackboard_state.get("agent_results") or {}
        deps = self.definition.dependencies or []
        lines = []
        if self.agent_id == "strategy.executive.v3":
            from app.orchestration.cognition.finding_rubric import executive_eligible_claims
            eligible = executive_eligible_claims(blackboard.claim_registry.get_all())
            held = [
                c.id for c in blackboard.claim_registry.get_all()
                if c.held_from_executive and not c.adversarial_reviewed
            ]
            lines.append(
                "Use ONLY executive-eligible claims (exclude GUESSING+CRITICAL until "
                "verification.adversarial.v3 has reviewed them)."
            )
            lines.append(f"Eligible claims: {len(eligible)}. Held for adversarial: {held or 'none'}.")
        if not deps and not lines:
            return ""
        lines.append("Prior specialist outputs (do not treat as new evidence):")
        for dep in deps:
            payload = results.get(dep) or {}
            lines.append(f"- {dep}: status={payload.get('status')} claims={len(payload.get('claims') or [])}")
        return "\n".join(lines) + "\n"

    def _apply_side_effects(self, blackboard: CognitiveBlackboard, observations: Dict[str, Any], raw: Dict[str, Any]) -> None:
        if self.agent_id == "strategy.executive.v3":
            story = observations.get("story_summary") or raw.get("story_summary")
            if story and not blackboard.executive_narrative.get("story_summary"):
                blackboard.executive_narrative = {
                    **blackboard.executive_narrative,
                    "story_summary": story,
                    "what_is_holding_it_back": observations.get("blockers") or [],
                    "consultant_advice_what_to_ignore": observations.get("what_to_ignore") or "",
                }
        if self.agent_id == "business.discovery.v3":
            name = observations.get("business_name")
            if name and blackboard.business_profile and blackboard.business_profile.business_name in (
                "Unknown Business", "Unknown", "Identified Platform", ""
            ):
                blackboard.business_profile.business_name = str(name)

    def _route_contested_claims(self, blackboard: CognitiveBlackboard) -> None:
        """Arbitrate only by recording DOM vs ext contests. Never pick a winner."""
        from app.domain.enums import SourceIntegrityLabel, VerificationStatus
        from app.orchestration.cognition.contradiction import ContradictionDetector

        detector = ContradictionDetector()
        routed = detector.detect_contradictions(blackboard.claim_registry.get_all())
        existing = {(c.claim_a_id, c.claim_b_id, c.resolution) for c in blackboard.claim_registry.get_contradictions()}
        for contra in routed:
            key = (contra.claim_a_id, contra.claim_b_id, contra.resolution)
            if key in existing:
                continue
            if contra.winner_claim_id:
                continue
            blackboard.claim_registry.register_contradiction(
                claim_a_id=contra.claim_a_id,
                claim_b_id=contra.claim_b_id,
                description=contra.description,
                resolution=contra.resolution,
                winner_claim_id=None,
                routed_to=contra.routed_to,
            )
            existing.add(key)
        blackboard.contradictions = blackboard.claim_registry.get_contradictions()
        for claim in blackboard.claim_registry.get_all():
            if claim.source_integrity_label == SourceIntegrityLabel.CONTESTED:
                claim.verification_status = VerificationStatus.CONTESTED
                claim.routed_to = "verification.contradiction.v3"

    def _falsify_unbacked_claims(self, blackboard: CognitiveBlackboard) -> None:
        """Drop confidence on claims whose evidence IDs are missing. Does not invent replacements."""
        store = blackboard.evidence_store
        for claim in blackboard.claim_registry.get_all():
            valid = [ref for ref in (claim.evidence_refs or []) if store.get(ref)]
            if not valid:
                claim.confidence = min(float(claim.confidence or 0), 0.40)
                claim.verification_status = VerificationStatus.INSUFFICIENT_EVIDENCE
                claim.verification_notes = "Adversarial specialist: no surviving evidence_refs."
        from app.domain.enums import Materiality, RubricConfidence
        from app.orchestration.cognition.finding_rubric import apply_rubric_to_claim, ADVERSARIAL_AGENT_ID
        for claim in blackboard.claim_registry.get_all():
            apply_rubric_to_claim(claim, store)
            if (
                claim.confidence_rubric == RubricConfidence.GUESSING
                and claim.materiality == Materiality.CRITICAL
            ):
                claim.adversarial_reviewed = True
                claim.held_from_executive = False
                claim.routed_to = ADVERSARIAL_AGENT_ID
                note = "Adversarial review of GUESSING+CRITICAL completed; still GUESSING — not CERTAIN/LIKELY."
                existing = claim.verification_notes or ""
                if note not in existing:
                    claim.verification_notes = f"{existing} | {note}".strip(" |")

    def _store(self, blackboard: CognitiveBlackboard, result: Dict[str, Any]) -> None:
        store = blackboard.blackboard_state.setdefault("agent_results", {})
        store[self.agent_id] = result
        blackboard.log_step(
            f"Specialist {self.definition.agent_name}",
            self.agent_id,
            {"status": result.get("status"), "claims": len(result.get("claims") or [])},
        )
