"""CRO audit engine.

Runs the specialist registry against a representative page sample and any
measured analytics that were actually connected. Missing rates stay missing.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.cro.metrics import MEASUREMENT_RULES, METRIC_CATALOG, rate
from app.cro.taxonomy import (
    APPENDICES,
    EVIDENCE_STATES,
    PARTS,
    REPORT_CHAPTERS,
    SCORING_DIMENSIONS,
    SPECIALISTS,
    catalog,
)

PRINCIPLE = (
    "Every CRO recommendation connects an observed problem to a testable hypothesis, "
    "a success metric, guardrail metrics, and a verification plan. An observed friction "
    "is not proof that a particular design change will raise conversions."
)

GUARDRAILS = ["Lead quality", "Downstream completion", "Errors", "Abandonment"]
VALIDATION = (
    "Run a properly designed experiment, or a documented post-deployment evaluation when "
    "randomization is impractical. Do not declare a winner because a variant has a higher "
    "observed conversion rate. The test has to be powered, instrumented, and interpreted "
    "with an appropriate statistical method."
)
IMPACT_UNAVAILABLE = (
    "Not estimated. Baseline conversion data was not used to forecast lift, and this audit "
    "does not multiply an assumed lift by traffic."
)

_PASSIVE = re.compile(
    r"^(submit|click\s+here|learn\s+more|read\s+more|continue|next|more|go|here|download|view\s+more|check\s+it\s+out)$",
    re.I,
)
_HIGH_INTENT = re.compile(
    r"\b(get\s+started|start\s+(free|now|trial|your)|book\s+(a\s+)?(demo|call|consultation|appointment)|"
    r"schedule|request\s+(a\s+)?(demo|quote|consultation)|buy\s+now|sign\s+up|add\s+to\s+cart|"
    r"checkout|subscribe|get\s+quote|contact\s+sales|call\s+(us|now))\b",
    re.I,
)
_URGENCY = re.compile(
    r"\b(only\s+\d+\s+left|limited\s+time|act\s+now|hurry|today\s+only|expires\s+soon|last\s+chance)\b",
    re.I,
)
_PRICE = re.compile(r"(?:[$£€₹]\s?\d[\d,]*(?:\.\d+)?)|(?:\b\d[\d,]*(?:\.\d+)?\s?(?:/mo|per\s+month|per\s+year|/yr)\b)", re.I)
_EMAIL_NAME = re.compile(r"email", re.I)

_OWNERS = {
    "landing": "Design",
    "ux_navigation": "Design",
    "trust": "Marketing",
    "form": "Engineering",
    "checkout": "Engineering",
    "mobile": "Engineering",
    "accessibility": "Engineering",
    "analytics_qa": "Marketing",
    "funnel": "Marketing",
    "conversion_goal": "Marketing",
    "behavioral": "Research",
    "experiment": "Growth",
    "statistics": "Growth",
    "revenue": "Finance",
    "remediation": "Product",
    "verification": "Engineering",
}


class CroCheckRecord(BaseModel):
    check_id: str
    section: int
    part: str
    section_title: str
    label: str
    specialist: str
    key: str
    evidence_state: str
    outcome: str
    summary: str
    evidence: List[str] = Field(default_factory=list)
    page_url: Optional[str] = None


class CroFindingRecord(BaseModel):
    finding_id: str
    priority: str
    status: str = "Needs validation"
    finding: str
    evidence: str
    observed_scope: str
    hypothesis: str
    recommended_action: str
    primary_metric: str
    guardrail_metrics: List[str] = Field(default_factory=lambda: list(GUARDRAILS))
    validation: str = VALIDATION
    impact_estimate: str = IMPACT_UNAVAILABLE
    owner: str
    evidence_state: str
    section: int
    specialist: str
    effort: str
    confidence: str
    funnel_stage: str
    affected_scope: str
    negative_risk: str
    root_cause: str = "Not established. The sample shows the defect. It does not show why visitors leave."


class CroDimensionScore(BaseModel):
    id: str
    name: str
    status: str
    score: Optional[float] = None
    note: str
    passed_checks: int = 0
    failed_checks: int = 0
    excluded_checks: int = 0


class CroMetricResult(BaseModel):
    metric: str
    formula: str
    status: str
    value: Optional[float] = None
    display: str
    denominator: Optional[str] = None
    numerator: Optional[str] = None
    window: Optional[str] = None
    note: str


class CroAppendix(BaseModel):
    id: str
    title: str
    contents: str
    status: str
    summary: str


class CroSpecialistRollup(BaseModel):
    id: str
    name: str
    responsibility: str
    checks: int = 0
    failed: int = 0
    unmeasured: int = 0


class CroSectionRecord(BaseModel):
    number: str
    part: str
    title: str
    specialist: str
    status: str
    checks: List[CroCheckRecord] = Field(default_factory=list)


class CroIntelligenceReport(BaseModel):
    scope_note: str
    principle: str = PRINCIPLE
    business_model: str
    model_basis: str
    sample_size: int
    discovered_urls: Optional[int] = None
    coverage: Dict[str, Any] = Field(default_factory=dict)
    scoring_calibration: Dict[str, Any] = Field(default_factory=dict)
    evidence_states: List[str] = Field(default_factory=lambda: list(EVIDENCE_STATES))
    dimensions: List[CroDimensionScore] = Field(default_factory=list)
    metrics: List[CroMetricResult] = Field(default_factory=list)
    measurement_rules: List[str] = Field(default_factory=lambda: list(MEASUREMENT_RULES))
    sections: List[CroSectionRecord] = Field(default_factory=list)
    findings: List[CroFindingRecord] = Field(default_factory=list)
    roadmap: Dict[str, List[str]] = Field(default_factory=dict)
    appendices: List[CroAppendix] = Field(default_factory=list)
    specialists: List[CroSpecialistRollup] = Field(default_factory=list)
    chapters: List[Dict[str, str]] = Field(default_factory=lambda: [dict(item) for item in REPORT_CHAPTERS])
    parts: List[Dict[str, str]] = Field(default_factory=lambda: [dict(item) for item in PARTS])
    scoring_model: List[Dict[str, str]] = Field(default_factory=lambda: [dict(item) for item in SCORING_DIMENSIONS])


def _get(page: Any, name: str, default: Any = None) -> Any:
    if isinstance(page, dict):
        return page.get(name, default)
    return getattr(page, name, default)


def _clip(value: str, limit: int = 180) -> str:
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _join(items: Sequence[str], limit: int = 5) -> str:
    shown = [item for item in items if item][:limit]
    if not shown:
        return ""
    extra = len(items) - len(shown)
    text = ", ".join(shown)
    if extra > 0:
        text += f" (+{extra} more)"
    return text


def _models_from_text(raw: str) -> Set[str]:
    text = raw.lower()
    found: Set[str] = set()
    if any(token in text for token in ("add to cart", "checkout", "shopping cart", "buy now")):
        found.add("ecommerce")
    if any(token in text for token in ("free trial", "per month", "/mo", "book a demo", "start free")):
        found.add("saas")
    if any(token in text for token in ("request a quote", "book a consultation", "talk to sales")):
        found.add("lead_gen")
    if any(token in text for token in ("book an appointment", "opening hours", "get directions")):
        found.add("local")
    return found


def _contains_term(raw: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term)}\b", raw) is not None


def _profile_models(profile: Any) -> Set[str]:
    if profile is None:
        return set()
    status = str(_get(profile, "evidence_status", "") or "").lower()
    if not status or "insufficient" in status:
        return set()
    raw = " ".join(
        str(part)
        for part in (
            _get(profile, "business_model", ""),
            _get(profile, "industry", ""),
            _get(profile, "niche", ""),
        )
        if part
    ).lower()
    found: Set[str] = set()
    if any(_contains_term(raw, token) for token in ("ecommerce", "e-commerce", "shop", "store", "retail")):
        found.add("ecommerce")
    if any(_contains_term(raw, token) for token in ("saas", "subscription", "software")):
        found.add("saas")
    if any(_contains_term(raw, token) for token in ("local", "appointment", "clinic", "restaurant")):
        found.add("local")
    if any(_contains_term(raw, token) for token in ("lead", "agency", "b2b", "service", "consult")):
        found.add("lead_gen")
    return found


def _read_analytics(channel: Any) -> Dict[str, Any]:
    """Normalize optional GA4 data without turning malformed values into measurements.

    GA4 key events are event counts, not necessarily unique converting users. A
    conversion rate is published only when unique converters and eligible users
    are explicitly supplied by the connector.
    """
    result: Dict[str, Any] = {
        "state": "NOT_CONNECTED",
        "notice": "Google Analytics 4 was not connected for this audit. Sessions, landing pages, engagement, and conversions were not retrieved.",
        "property": None,
        "period": None,
        "sessions": None,
        "key_events": None,
        "key_events_present": False,
        "unique_converters": None,
        "eligible_users": None,
        "eligible_visitors": None,
        "engagement_rate_pct": None,
        "landing_pages": None,
        "revenue": None,
        "orders": None,
    }
    if not isinstance(channel, dict):
        return result

    state = str(channel.get("state") or "NOT_CONNECTED").upper()
    result["state"] = state
    result["notice"] = str(channel.get("notice") or result["notice"])
    result["property"] = channel.get("property")
    result["period"] = channel.get("period")
    if state != "MEASURED":
        # Never accept numeric payload fields from a failed/disconnected provider.
        return result

    def invalidate(notice: str) -> Dict[str, Any]:
        result["state"] = "INVALID_DATA"
        result["notice"] = notice
        # A malformed provider payload invalidates the measurement snapshot as a whole.
        # Do not let downstream CRO checks consume partially parsed values.
        for field in (
            "sessions", "key_events", "unique_converters", "eligible_users", "eligible_visitors",
            "engagement_rate_pct", "landing_pages", "revenue", "orders",
        ):
            result[field] = None
        result["key_events_present"] = False
        return result

    def count_value(*keys: str) -> Optional[int]:
        for key in keys:
            value = channel.get(key)
            if value is None:
                continue
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or value < 0
                or not float(value).is_integer()
            ):
                invalidate(f"GA4 returned an invalid non-negative integer for {key}; affected metrics were withheld.")
                return None
            return int(value)
        return None

    sessions = count_value("sessions")
    key_events = count_value("key_events", "keyEvents", "conversions")
    # Accept only explicit semantic fields. Generic GA4 "conversions" and "users"
    # are not silently relabelled as unique converters or eligible users.
    unique_converters = count_value("unique_converters")
    eligible_users = count_value("eligible_users")
    eligible_visitors = count_value("eligible_visitors")
    if result["state"] == "INVALID_DATA":
        return result
    result["sessions"] = sessions
    result["key_events"] = key_events
    result["key_events_present"] = key_events is not None
    result["unique_converters"] = unique_converters
    result["eligible_users"] = eligible_users
    result["eligible_visitors"] = eligible_visitors

    engagement = channel.get("engagement_rate_pct")
    if engagement is not None:
        if (
            isinstance(engagement, bool)
            or not isinstance(engagement, (int, float))
            or not math.isfinite(float(engagement))
            or not 0 <= float(engagement) <= 100
        ):
            return invalidate("GA4 returned an invalid engagement percentage; affected metrics were withheld.")
        result["engagement_rate_pct"] = float(engagement)

    if isinstance(channel.get("landing_pages"), list):
        result["landing_pages"] = channel["landing_pages"]

    for key in ("revenue", "purchase_revenue", "total_revenue"):
        value = channel.get(key)
        if value is None:
            continue
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or value < 0
        ):
            return invalidate(f"GA4 returned an invalid non-negative amount for {key}; revenue metrics were withheld.")
        result["revenue"] = float(value)
        break

    orders = count_value("orders", "transactions", "ecommerce_purchases")
    if result["state"] == "INVALID_DATA":
        return result
    result["orders"] = orders
    return result

def _read_search(channel: Any) -> Dict[str, Any]:
    """Normalize Search Console totals; malformed values remain unavailable."""
    if not isinstance(channel, dict) or str(channel.get("state") or "").upper() != "MEASURED":
        return {"state": "NOT_MEASURED", "clicks": None, "period": None, "property": None}
    base = {
        "state": "MEASURED",
        "clicks": None,
        "period": channel.get("period"),
        "property": channel.get("property"),
    }
    clicks = channel.get("clicks")
    if (
        isinstance(clicks, bool)
        or not isinstance(clicks, (int, float))
        or not math.isfinite(float(clicks))
        or clicks < 0
        or not float(clicks).is_integer()
    ):
        base["state"] = "INVALID_DATA"
        return base
    base["clicks"] = int(clicks)
    return base


def _read_wcag(wcag: Any) -> Optional[Dict[str, Any]]:
    if wcag is None:
        return None
    violations = list(getattr(wcag, "violations", None) or [])

    def count(predicate) -> int:
        return sum(1 for item in violations if predicate(item))

    def text_of(item: Any) -> str:
        return " ".join(
            str(getattr(item, name, "") or "")
            for name in ("category", "wcag_criterion", "description")
        ).lower()

    return {
        "total": len(violations),
        "contrast": count(lambda item: "contrast" in text_of(item) or "1.4.3" in text_of(item)),
        "keyboard": count(lambda item: "keyboard" in text_of(item) or "2.1.1" in text_of(item)),
        "names": count(lambda item: "label" in text_of(item) or "name" in text_of(item) or "4.1.2" in text_of(item)),
        "status": getattr(wcag, "conformance_status", None),
        "note": "Automated screening of the crawled sample. This is not a WCAG conformance certificate.",
    }


def _kind(url: str, schema_types: Iterable[str], text: str) -> str:
    path = urlparse(url).path.lower()
    schemas = {item.lower() for item in schema_types}
    if any(token in path for token in ("/cart", "/checkout", "/payment")):
        return "checkout"
    if any(token in path for token in ("/pricing", "/plans")):
        return "pricing"
    if "product" in schemas or any(token in path for token in ("/product", "/shop", "/item")):
        return "product"
    if any(token in path for token in ("/contact", "/demo", "/quote", "/consult")):
        return "contact"
    if any(token in path for token in ("/signup", "/register", "/login", "/account")):
        return "account"
    if any(token in path for token in ("/privacy", "/terms")):
        return "legal"
    if "localbusiness" in schemas or any(token in path for token in ("/locations", "/stores")):
        return "location"
    if any(token in path for token in ("/blog", "/article", "/news")):
        return "article"
    if any(token in path for token in ("/services", "/solutions")):
        return "service"
    if path in ("", "/"):
        return "home"
    if "appointment" in text or "book now" in text:
        return "booking"
    return "general"


def _parse_page(page: Any, raw_html_map: Optional[Dict[str, str]]) -> Dict[str, Any]:
    url = str(_get(page, "url", "") or "")
    html = ""
    if raw_html_map and url in raw_html_map:
        html = raw_html_map.get(url) or ""
    if not html:
        html = _get(page, "rendered_dom", "") or _get(page, "html", "") or _get(page, "raw_html", "") or ""
    schema_types = [str(item) for item in (_get(page, "schema_types", []) or [])]
    status_raw = _get(page, "status_code", None)
    status = (
        int(status_raw)
        if isinstance(status_raw, (int, float)) and not isinstance(status_raw, bool)
        and math.isfinite(float(status_raw)) and float(status_raw).is_integer()
        else None
    )
    title = str(_get(page, "title", "") or "")
    h1_values = [str(item) for item in (_get(page, "h1", []) or []) if str(item).strip()]
    h2_values = [str(item) for item in (_get(page, "h2", []) or []) if str(item).strip()]
    word_count = int(_get(page, "word_count", 0) or 0)
    viewport = _get(page, "viewport", None)
    ttfb = _get(page, "ttfb_ms", 0) or 0
    ttfb_ms = float(ttfb) if isinstance(ttfb, (int, float)) and not isinstance(ttfb, bool) and float(ttfb) > 0 else None
    internal_links = [str(item) for item in (_get(page, "internal_links", []) or [])]
    images_missing_alt = int(_get(page, "images_without_alt", 0) or 0)
    total_images = int(_get(page, "total_images", 0) or 0)
    field = _get(page, "field_performance", None)
    field_cwv = None
    if field is not None and getattr(field, "has_field_data", False):
        field_cwv = {
            "lcp_ms": getattr(field, "p75_lcp_ms", None),
            "inp_ms": getattr(field, "p75_inp_ms", None),
            "cls": getattr(field, "p75_cls", None),
            "origin": getattr(field, "origin", ""),
        }
    text = str(_get(page, "body_text", "") or _get(page, "text_content", "") or "")
    ctas: List[Dict[str, Any]] = []
    forms: List[Dict[str, Any]] = []
    nav_labels: List[str] = []
    has_search = False
    breadcrumbs = False
    videos = 0
    captions = 0
    proof = 0
    tel_links = 0
    mailto = 0
    broken_ctas: List[str] = []
    analytics_tags: List[str] = []
    replay_tags: List[str] = []
    consent = False
    third_party = 0
    images_from_html = False

    if html:
        soup = BeautifulSoup(html, "html.parser")
        if not h1_values:
            h1_values = [node.get_text(" ", strip=True) for node in soup.find_all("h1") if node.get_text(strip=True)]
        if not h2_values:
            h2_values = [node.get_text(" ", strip=True) for node in soup.find_all("h2") if node.get_text(strip=True)]
        if not title and soup.title:
            title = soup.title.get_text(" ", strip=True)
        text = soup.get_text(" ", strip=True)
        word_count = word_count or len(text.split())
        if viewport is None:
            meta = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
            viewport = meta.get("content") if meta else None
        host = urlparse(url).netloc.lower()
        for script in soup.find_all("script"):
            src = (script.get("src") or "") + " " + (script.string or "")
            low = src.lower()
            if any(token in low for token in ("googletagmanager", "gtag(", "google-analytics", "gtm.js")):
                analytics_tags.append("GA/GTM")
            if "hotjar" in low:
                replay_tags.append("Hotjar")
            if "clarity.ms" in low:
                replay_tags.append("Clarity")
            if "fullstory" in low:
                replay_tags.append("FullStory")
            if script.get("src"):
                script_host = urlparse(script.get("src")).netloc.lower()
                if script_host and host and script_host != host:
                    third_party += 1
        page_html_l = html.lower()
        consent = any(token in page_html_l for token in ("cookiebot", "onetrust", "cookie consent", "we use cookies"))
        for anchor in soup.find_all("a"):
            href = str(anchor.get("href") or "")
            label = anchor.get_text(" ", strip=True)
            if href.lower().startswith("tel:"):
                tel_links += 1
            if href.lower().startswith("mailto:"):
                mailto += 1
            parent_names = {node.name for node in anchor.parents}
            if "nav" in parent_names or "header" in parent_names:
                if label and len(label) < 40:
                    nav_labels.append(label)
            classes = " ".join(anchor.get("class") or []).lower()
            is_cta = any(token in classes for token in ("btn", "button", "cta")) or any(
                token in href.lower() for token in ("contact", "pricing", "signup", "demo", "checkout", "quote", "cart")
            )
            if is_cta and label and len(label) <= 50:
                ctas.append({"text": label, "href": href, "tag": "a", "page_url": url})
            if is_cta and href.strip().lower() in {"", "#", "javascript:void(0)", "javascript:;"}:
                broken_ctas.append(f"{label or 'link'} → {href or '(empty)'} on {url}")
        for button in soup.find_all("button"):
            label = button.get_text(" ", strip=True)
            if label and len(label) <= 50:
                ctas.append({"text": label, "href": "", "tag": "button", "page_url": url})
        for control in soup.find_all("input"):
            if control.get("type") in ("submit", "button"):
                label = str(control.get("value") or "").strip()
                if label:
                    ctas.append({"text": label, "href": "", "tag": "input", "page_url": url})
        if soup.find("input", attrs={"type": "search"}) or soup.find("input", attrs={"name": re.compile(r"^(q|s|search)$", re.I)}):
            has_search = True
        breadcrumbs = bool(soup.find(attrs={"aria-label": re.compile(r"breadcrumb", re.I)}) or soup.find(class_=re.compile(r"breadcrumb", re.I)))
        videos = len(soup.find_all("video")) + len(soup.find_all("iframe"))
        captions = len(soup.find_all("track"))
        proof = len(soup.find_all("blockquote")) + len(soup.find_all(class_=re.compile(r"testimonial|review", re.I)))
        images = soup.find_all("img")
        if images:
            images_from_html = True
            total_images = len(images)
            images_missing_alt = sum(1 for image in images if image.get("alt") is None)
        for form in soup.find_all("form"):
            controls = []
            missing = 0
            placeholder_only = 0
            types: List[str] = []
            required = 0
            autocomplete = 0
            email_as_text = 0
            for control in form.find_all(["input", "textarea", "select"]):
                kind = (control.get("type") or control.name or "text").lower()
                if kind in ("hidden", "submit", "image", "button"):
                    continue
                name = " ".join(str(control.get(key) or "") for key in ("name", "id", "aria-label", "placeholder"))
                control_id = control.get("id")
                labelled = bool(control_id and form.find("label", attrs={"for": control_id}))
                labelled = labelled or bool(control.find_parent("label")) or bool(control.get("aria-label") or control.get("aria-labelledby"))
                if not labelled:
                    missing += 1
                    if control.get("placeholder"):
                        placeholder_only += 1
                if control.has_attr("required"):
                    required += 1
                if control.get("autocomplete"):
                    autocomplete += 1
                if kind == "text" and _EMAIL_NAME.search(name):
                    email_as_text += 1
                types.append(kind)
                controls.append(kind)
            submit = form.find(["button", "input"], attrs={"type": "submit"}) or form.find("button")
            submit_text = ""
            if submit is not None:
                submit_text = submit.get_text(" ", strip=True) or str(submit.get("value") or "")
            form_html = str(form).lower()
            forms.append({
                "page_url": url,
                "action": str(form.get("action") or ""),
                "fields": len(controls),
                "missing_labels": missing,
                "placeholder_only": placeholder_only,
                "types": types,
                "required": required,
                "autocomplete": autocomplete,
                "email_as_text": email_as_text,
                "submit_text": submit_text,
                "has_submit": submit is not None,
                "honeypot": any(token in form_html for token in ("honeypot", "recaptcha", "hcaptcha", "turnstile")),
                "multistep": bool(form.find_all("fieldset")) and len(form.find_all("fieldset")) > 1 or "data-step" in form_html,
            })
    else:
        for label in list(_get(page, "ctas", []) or []) + list(_get(page, "call_to_actions", []) or []):
            text = str(label).strip()
            if text:
                ctas.append({"text": text, "href": "", "tag": "text", "page_url": url})

    for cta in ctas:
        lowered = cta["text"].strip().lower()
        cta["passive"] = bool(_PASSIVE.search(lowered))
        cta["high_intent"] = bool(_HIGH_INTENT.search(lowered))
    kind = _kind(url, schema_types, text.lower())
    return {
        "url": url,
        "title": title,
        "h1": h1_values[0] if h1_values else "",
        "h2": h2_values[0] if h2_values else "",
        "word_count": word_count,
        "status": status,
        "viewport": bool(viewport),
        "ttfb_ms": ttfb_ms,
        "internal_links": internal_links,
        "schema_types": schema_types,
        "kind": kind,
        "text": text[:20000],
        "ctas": ctas,
        "forms": forms,
        "nav_labels": nav_labels,
        "has_search": has_search,
        "breadcrumbs": breadcrumbs,
        "videos": videos,
        "captions": captions,
        "tel_links": tel_links,
        "mailto": mailto,
        "broken_ctas": broken_ctas,
        "images_missing_alt": images_missing_alt,
        "total_images": total_images,
        "images_from_html": images_from_html,
        "analytics_tags": sorted(set(analytics_tags)),
        "replay_tags": sorted(set(replay_tags)),
        "consent": consent,
        "third_party": third_party,
        "field_cwv": field_cwv,
        "proof": proof,
    }


class _Obs:
    def __init__(self) -> None:
        self.pages: List[Dict[str, Any]] = []
        self.sample_size = 0
        self.discovered: Optional[int] = None
        self.sample_note = ""
        self.business_name = ""
        self.detected_models: Set[str] = set()
        self.model_known = False
        self.model_basis = "The business model was not classified from the sample or the business profile."
        self.model_label = "unclassified"
        self.profile_audience = ""
        self.profile_products: List[str] = []
        self.profile_cta = ""
        self.h1 = ""
        self.subhead = ""
        self.ctas: List[Dict[str, Any]] = []
        self.passive: List[Dict[str, Any]] = []
        self.high_intent: List[Dict[str, Any]] = []
        self.pages_without_cta: List[str] = []
        self.broken_ctas: List[str] = []
        self.forms: List[Dict[str, Any]] = []
        self.nav_labels: List[str] = []
        self.has_search = False
        self.breadcrumbs = 0
        self.viewport_missing: List[str] = []
        self.images_missing_alt = 0
        self.total_images = 0
        self.videos = 0
        self.captions = 0
        self.tel_links = 0
        self.mailto = 0
        self.status_errors: List[str] = []
        self.analytics_tags: List[str] = []
        self.replay_tags: List[str] = []
        self.consent = False
        self.third_party = 0
        self.ttfb_values: List[float] = []
        self.field_cwv: Optional[Dict[str, Any]] = None
        self.privacy = False
        self.terms = False
        self.contact = False
        self.testimonials = 0
        self.logos = 0
        self.reviews = 0
        self.case_studies: List[str] = []
        self.badges: List[str] = []
        self.claims: List[str] = []
        self.pricing_urls: List[str] = []
        self.prices: List[str] = []
        self.urgency: List[str] = []
        self.guarantee = False
        self.trial = False
        self.refund = False
        self.cancel = False
        self.faq = False
        self.billing = False
        self.tax_words = False
        self.hidden_fee = False
        self.shipping = False
        self.support = False
        self.security = False
        self.about = False
        self.demo = False
        self.appointment = False
        self.guest_checkout = False
        self.add_to_cart = False
        self.confirmation_urls: List[str] = []
        self.dead_ends: List[str] = []
        self.competitor_domains: List[str] = []
        self.wcag: Optional[Dict[str, Any]] = None
        self.analytics: Dict[str, Any] = {}
        self.organic_clicks: Optional[int] = None
        self.organic_period: Optional[str] = None
        self.you_words = 0
        self.we_words = 0


def _observe(
    pages: Sequence[Any],
    raw_html_map: Optional[Dict[str, str]],
    business_profile: Any,
    analytics: Any,
    search_console: Any,
    wcag: Any,
    competitor_domains: Optional[Sequence[str]],
    discovered_urls: Optional[int],
) -> _Obs:
    obs = _Obs()
    obs.discovered = discovered_urls
    obs.analytics = _read_analytics(analytics)
    search = _read_search(search_console)
    obs.organic_clicks = search["clicks"]
    obs.organic_period = search["period"]
    obs.wcag = _read_wcag(wcag)
    obs.competitor_domains = [domain for domain in (competitor_domains or []) if domain]
    obs.business_name = str(_get(business_profile, "business_name", "") or "")
    obs.profile_audience = str(_get(business_profile, "target_audience", "") or "")
    obs.profile_products = [str(item) for item in (_get(business_profile, "products", []) or []) if item]
    obs.profile_products += [str(item) for item in (_get(business_profile, "services", []) or []) if item]
    obs.profile_cta = str(_get(business_profile, "primary_cta", "") or "")
    for page in pages:
        try:
            parsed = _parse_page(page, raw_html_map)
        except Exception as exc:
            parsed = {
                "url": str(_get(page, "url", "") or ""),
                "title": "",
                "h1": "",
                "h2": "",
                "word_count": 0,
                "status": 0,
                "viewport": False,
                "ttfb_ms": None,
                "internal_links": [],
                "schema_types": [],
                "kind": "general",
                "text": f"Page parse failed: {exc}",
                "ctas": [],
                "forms": [],
                "nav_labels": [],
                "has_search": False,
                "breadcrumbs": False,
                "videos": 0,
                "captions": 0,
                "tel_links": 0,
                "mailto": 0,
                "broken_ctas": [],
                "images_missing_alt": 0,
                "total_images": 0,
                "images_from_html": False,
                "analytics_tags": [],
                "replay_tags": [],
                "consent": False,
                "third_party": 0,
                "field_cwv": None,
                "proof": 0,
            }
        obs.pages.append(parsed)
    obs.sample_size = len(obs.pages)
    discovered_clause = ""
    if obs.discovered and obs.discovered != obs.sample_size:
        discovered_clause = f" out of {obs.discovered} discovered URL(s)"
    obs.sample_note = (
        f"This CRO audit inspected {obs.sample_size} crawled page(s){discovered_clause}. "
        "Dristik uses a representative sample, not a full-site crawl. A finding describes the inspected "
        "pages and flows. It is not exhaustive sitewide coverage. Recorded labels, forms, and broken "
        "controls are evidence. They do not show why a visitor left, and they do not estimate conversion lift."
    )
    combined = []
    for page in obs.pages:
        combined.append(page["url"].lower())
        combined.append(page["text"].lower())
        combined.extend(item.lower() for item in page["schema_types"])
        if page["h1"] and not obs.h1:
            obs.h1 = page["h1"]
            obs.subhead = page["h2"]
        if page["status"] is not None and page["status"] >= 400:
            obs.status_errors.append(f"{page['url']} returned HTTP {page['status']}")
        if not page["viewport"]:
            obs.viewport_missing.append(page["url"])
        if page["ttfb_ms"] is not None:
            obs.ttfb_values.append(page["ttfb_ms"])
        if page["field_cwv"] and obs.field_cwv is None:
            obs.field_cwv = page["field_cwv"]
        obs.ctas.extend(page["ctas"])
        if not page["ctas"] and page["word_count"] > 80:
            obs.pages_without_cta.append(page["url"])
        obs.forms.extend(page["forms"])
        obs.nav_labels.extend(page["nav_labels"])
        obs.has_search = obs.has_search or page["has_search"]
        obs.breadcrumbs += 1 if page["breadcrumbs"] else 0
        obs.videos += page["videos"]
        obs.captions += page["captions"]
        obs.tel_links += page["tel_links"]
        obs.mailto += page["mailto"]
        obs.broken_ctas.extend(page["broken_ctas"])
        obs.images_missing_alt += page["images_missing_alt"]
        obs.total_images += page["total_images"]
        obs.analytics_tags.extend(page["analytics_tags"])
        obs.replay_tags.extend(page["replay_tags"])
        obs.consent = obs.consent or page["consent"]
        obs.third_party += page["third_party"]
        if page["kind"] == "pricing":
            obs.pricing_urls.append(page["url"])
        if page["kind"] == "legal" or "privacy" in page["url"].lower():
            obs.privacy = True
        if "terms" in page["url"].lower():
            obs.terms = True
        if page["kind"] in ("contact", "booking") or page["tel_links"] or page["mailto"]:
            obs.contact = True
        if any(token in page["url"].lower() for token in ("thank", "confirm", "success")):
            obs.confirmation_urls.append(page["url"])
        if any(token in page["url"].lower() for token in ("case-stud", "customers", "work")):
            obs.case_studies.append(page["url"])
        if page["word_count"] > 150 and not page["ctas"] and not page["internal_links"]:
            obs.dead_ends.append(page["url"])
        low = page["text"].lower()
        if "privacy" in low:
            obs.privacy = True
        if "terms of service" in low or "terms and conditions" in low:
            obs.terms = True
        obs.testimonials += page.get("proof", 0) + low.count("testimonial")
        if "review" in low:
            obs.reviews += 1
        obs.logos += low.count("logo")
        for badge in ("soc 2", "iso 27001", "gdpr", "hipaa"):
            if badge in low and badge.upper() not in obs.badges:
                obs.badges.append(badge.upper())
        obs.prices.extend(_PRICE.findall(page["text"])[:8])
        found_urgency = _URGENCY.findall(page["text"])
        obs.urgency.extend(found_urgency[:4])
        obs.guarantee = obs.guarantee or "guarantee" in low or "money back" in low
        obs.trial = obs.trial or "free trial" in low or "no credit card" in low
        obs.refund = obs.refund or "refund" in low
        obs.cancel = obs.cancel or "cancel" in low
        obs.faq = obs.faq or "faq" in low or "frequently asked" in low
        obs.billing = obs.billing or any(token in low for token in ("per month", "per year", "/mo", "billed annually", "monthly"))
        obs.tax_words = obs.tax_words or any(token in low for token in ("plus tax", "excluding tax", "vat", "gst"))
        obs.hidden_fee = obs.hidden_fee or "additional fees may apply" in low
        obs.shipping = obs.shipping or "shipping" in low or "returns" in low
        obs.support = obs.support or any(token in low for token in ("customer support", "contact support", "help center"))
        obs.security = obs.security or any(token in low for token in ("ssl", "encrypted", "security"))
        obs.about = obs.about or any(token in low for token in ("about us", "our company", "founded"))
        obs.demo = obs.demo or "demo" in low
        obs.appointment = obs.appointment or "appointment" in low or "book now" in low
        obs.guest_checkout = obs.guest_checkout or "guest checkout" in low
        obs.add_to_cart = obs.add_to_cart or "add to cart" in low
        if page["tel_links"] or page["mailto"] or page["kind"] == "contact":
            obs.contact = True
    blob = " ".join(combined)
    crawl_models = _models_from_text(blob)
    if any(page["kind"] in ("product", "checkout") for page in obs.pages):
        crawl_models.add("ecommerce")
    if any(page["kind"] == "pricing" for page in obs.pages) and obs.trial:
        crawl_models.add("saas")
    if any(page["kind"] == "location" for page in obs.pages) or obs.tel_links:
        crawl_models.add("local")
    if any(page["kind"] == "contact" for page in obs.pages):
        crawl_models.add("lead_gen")
    profile_models = _profile_models(business_profile)
    obs.detected_models = set(crawl_models) | set(profile_models)
    obs.model_known = bool(obs.detected_models)
    obs.model_label = ", ".join(sorted(obs.detected_models)) if obs.detected_models else "unclassified"
    bits = []
    if crawl_models:
        bits.append("crawl signals: " + ", ".join(sorted(crawl_models)))
    if profile_models:
        bits.append("business profile: " + ", ".join(sorted(profile_models)))
    if bits:
        obs.model_basis = "Classified from " + "; ".join(bits) + ". A profile label is not a measured revenue model."
    obs.passive = [cta for cta in obs.ctas if cta.get("passive")]
    obs.high_intent = [cta for cta in obs.ctas if cta.get("high_intent")]
    obs.analytics_tags = sorted(set(obs.analytics_tags))
    obs.replay_tags = sorted(set(obs.replay_tags))
    headline = f"{obs.h1} {obs.subhead}".lower()
    obs.you_words = len(re.findall(r"\b(you|your)\b", headline))
    obs.we_words = len(re.findall(r"\b(we|our)\b", headline))
    obs.claims = obs.prices[:6]
    return obs


class _Verdict(dict):
    pass


def _record(check: Dict[str, Any], state: str, outcome: str, summary: str, evidence: Optional[List[str]] = None, page_url: Optional[str] = None, **extra: Any) -> Dict[str, Any]:
    payload = {
        "check_id": check["check_id"],
        "section": check["section"],
        "part": check["part"],
        "section_title": check["section_title"],
        "label": check["label"],
        "specialist": check["specialist"],
        "key": check["key"],
        "evidence_state": state,
        "outcome": outcome,
        "summary": summary,
        "evidence": evidence or [],
        "page_url": page_url,
    }
    payload.update(extra)
    return payload


class _Rules:
    def __init__(self, obs: _Obs) -> None:
        self.obs = obs

    def applies(self, check: Dict[str, Any]) -> bool:
        if check["models"] == "*":
            return True
        if not self.obs.model_known:
            return False
        return bool(set(check["models"].split("|")) & self.obs.detected_models)

    def na(self, check: Dict[str, Any], summary: str) -> Dict[str, Any]:
        return _record(check, "NOT_APPLICABLE", "not_applicable", summary)

    def un(self, check: Dict[str, Any], summary: str, evidence: Optional[List[str]] = None) -> Dict[str, Any]:
        return _record(check, "DATA_UNAVAILABLE", "unmeasured", summary, evidence)

    def nt(self, check: Dict[str, Any], summary: str) -> Dict[str, Any]:
        return _record(check, "NOT_TESTED", "not_tested", summary)

    def observed(self, check: Dict[str, Any], summary: str, evidence: Optional[List[str]] = None, page_url: Optional[str] = None, state: str = "SAMPLE_VERIFIED") -> Dict[str, Any]:
        return _record(check, state, "observed", summary, evidence, page_url)

    def inferred(self, check: Dict[str, Any], summary: str, evidence: Optional[List[str]] = None) -> Dict[str, Any]:
        return _record(check, "INFERRED", "observed", summary, evidence)

    def ok(self, check: Dict[str, Any], summary: str, evidence: Optional[List[str]] = None, page_url: Optional[str] = None) -> Dict[str, Any]:
        return _record(check, "SAMPLE_VERIFIED", "pass", summary, evidence, page_url)

    def fail(self, check: Dict[str, Any], summary: str, *, priority: str, effort: str, action: str, evidence: Optional[List[str]] = None, page_url: Optional[str] = None, stage: str = "Conversion") -> Dict[str, Any]:
        return _record(
            check,
            "SAMPLE_VERIFIED",
            "fail",
            summary,
            evidence,
            page_url,
            priority=priority,
            effort=effort,
            action=action,
            stage=stage,
            owner=_OWNERS.get(check["specialist"], "Product"),
        )

    def by_need(self, check: Dict[str, Any]) -> Dict[str, Any]:
        label = check["label"]
        need = check["need"]
        if need in ("analytics", "crm", "revenue"):
            notice = self.obs.analytics.get("notice") if need == "analytics" else "The required business system was not connected."
            return self.un(check, f"{label}: {notice} No number was substituted.")
        if need == "research":
            return self.nt(check, f"{label}: no usability test, survey, or interview was supplied. A page pattern is not a motive.")
        if need == "experiment":
            return self.nt(check, f"{label}: no experiment registry was supplied. A higher observed rate would not be treated as a win.")
        if need == "competitor":
            return self.competitor(check)
        if need == "governance":
            return self.governance(check)
        return self.nt(check, f"{label}: this check is in the CRO registry and was not executed on the sample.")

    def rate_line(self) -> Optional[str]:
        analytics = self.obs.analytics
        if not analytics.get("key_events_present") or analytics.get("sessions") is None:
            return None
        value = rate(analytics["key_events"], analytics["sessions"])
        if value is None:
            return None
        window = analytics.get("period") or "the connected period"
        return (
            f"{analytics['key_events']} key events ÷ {analytics['sessions']} sessions = {value:.1%} "
            f"over {window}. Denominator: sessions. This is a property key-event rate, not a qualified-lead rate."
        )

    def business_overview(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.pages:
            return self.un(check, "Website overview was not written. No crawled pages were available.")
        name = self.obs.business_name or urlparse(self.obs.pages[0]["url"]).netloc or "The site"
        headline = f" Headline in the sample: “{self.obs.h1}”." if self.obs.h1 else " No H1 was found on the first inspected page."
        return self.observed(check, f"{name} was inspected on {self.obs.sample_size} page(s).{headline}", [page["url"] for page in self.obs.pages[:5]])

    def primary_objectives(self, check: Dict[str, Any]) -> Dict[str, Any]:
        labels = [cta["text"] for cta in self.obs.high_intent[:5]]
        if self.obs.profile_cta:
            labels = [self.obs.profile_cta] + labels
        if not labels:
            return self.inferred(check, "No primary conversion was confirmed with the business. The sample did not show a high-intent action label.")
        return self.inferred(check, "Observed action labels, not a confirmed business goal: " + _join(labels) + ".")

    def conversion_paths(self, check: Dict[str, Any]) -> Dict[str, Any]:
        hrefs = [f"{cta['text']} → {cta['href']}" for cta in self.obs.ctas if cta.get("href")][:6]
        if not hrefs:
            return self.inferred(check, "No CTA destination was recorded, so the path after the click was not mapped.")
        return self.inferred(check, "Observed destinations in the sample, not a measured path: " + _join(hrefs) + ".")

    def conversion_health(self, check: Dict[str, Any]) -> Dict[str, Any]:
        line = self.rate_line()
        if line:
            return self.observed(check, line, state="VERIFIED")
        return self.un(check, "Overall conversion health was not scored. " + self.obs.analytics.get("notice", ""))

    def high_friction(self, check: Dict[str, Any]) -> Dict[str, Any]:
        bits = []
        if self.obs.passive:
            bits.append(f"{len(self.obs.passive)} generic CTA label(s)")
        if any(form["missing_labels"] for form in self.obs.forms):
            bits.append("form fields without labels")
        if self.obs.broken_ctas:
            bits.append(f"{len(self.obs.broken_ctas)} empty or placeholder CTA link(s)")
        if self.obs.status_errors:
            bits.append(f"{len(self.obs.status_errors)} error response(s)")
        if not bits:
            if not self.obs.pages:
                return self.un(check, "Friction was not inspected. No pages were available.")
            return self.ok(check, "The sample did not show a generic CTA, an unlabeled field, a broken CTA href, or an error response.")
        return self.observed(check, "Friction observed in the sample: " + "; ".join(bits) + ". These are defects, not measured drop-off.")

    def business_model(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.observed(check, f"Business model: {self.obs.model_label}. {self.obs.model_basis}")

    def revenue_streams(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.model_known:
            return self.un(check, "Revenue streams were not classified, and no revenue ledger was connected.")
        return self.inferred(check, f"Possible commercial motion from the classification ({self.obs.model_label}). This is not a revenue breakdown.")

    def products_services(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.profile_products:
            return self.observed(check, "Named on the business profile: " + _join(self.obs.profile_products) + ".")
        if self.obs.h1:
            return self.inferred(check, f"The sample headline is the offer statement: “{self.obs.h1}”. Offer details were not confirmed.")
        return self.un(check, "Products and services were not named in the profile or the sample headline.")

    def audience(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.profile_audience:
            return self.observed(check, f"Target audience on the profile: {self.obs.profile_audience}.")
        return self.nt(check, "Target audience was not stated on the profile and was not inferred from the copy.")

    def primary_actions(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.ctas:
            return self.fail(check, "No call to action was found on the inspected pages.", priority="High", effort="Low", action="Add one explicit next step on the primary landing page.", stage="Landing")
        high = _join([cta["text"] for cta in self.obs.high_intent]) or "none"
        passive = _join([cta["text"] for cta in self.obs.passive]) or "none"
        return self.observed(check, f"{len(self.obs.ctas)} CTA label(s) in the sample. High-intent: {high}. Generic: {passive}.")

    def secondary_actions(self, check: Dict[str, Any]) -> Dict[str, Any]:
        exploratory = [cta["text"] for cta in self.obs.ctas if not cta.get("high_intent") and not cta.get("passive")]
        if not exploratory:
            return self.observed(check, "No secondary action label was separated from the primary labels.")
        return self.observed(check, "Other action labels in the sample: " + _join(exploratory) + ".")

    def weak_value_prop(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.pages:
            return self.un(check, "The value proposition was not read. No pages were available.")
        if not self.obs.h1:
            return self.fail(check, "The first inspected page has no H1, so the offer is not stated.", priority="High", effort="Low", action="State the customer outcome in one H1.", page_url=self.obs.pages[0]["url"], stage="Landing")
        words = len(self.obs.h1.split())
        if words > 18:
            return self.fail(check, f"The H1 is {words} words: “{self.obs.h1}”.", priority="Medium", effort="Low", action="Shorten the H1 so the offer can be read quickly.", page_url=self.obs.pages[0]["url"], stage="Landing")
        return self.ok(check, f"H1 in the sample ({words} words): “{self.obs.h1}”.", [self.obs.pages[0]["url"]])

    def headline(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.weak_value_prop(check)

    def subheadline(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.subhead:
            return self.observed(check, "No supporting H2 was found next to the first H1. Viewport placement was not measured.")
        return self.ok(check, f"Supporting H2: “{self.obs.subhead}”.")

    def cta_wording(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.ctas:
            return self.observed(check, "No CTA label was available to judge wording.")
        if not self.obs.passive:
            return self.ok(check, "Inspected CTA labels name an action. Examples: " + _join([cta["text"] for cta in self.obs.ctas]) + ".")
        samples = _join([f"“{cta['text']}” on {cta['page_url']}" for cta in self.obs.passive])
        return self.fail(
            check,
            f"{len(self.obs.passive)} CTA label(s) are generic ({samples}). A label is not a measured click rate.",
            priority="Medium",
            effort="Low",
            action="Test a label that names the result of the click, and keep the current label as the control.",
            page_url=self.obs.passive[0]["page_url"],
            stage="Landing",
        )

    def cta_presence(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.pages and not self.obs.ctas:
            return self.fail(check, "No CTA was found on the inspected pages.", priority="High", effort="Low", action="Add one action that states what happens next.", page_url=self.obs.pages[0]["url"], stage="Landing")
        if not self.obs.pages:
            return self.un(check, "CTA presence was not inspected.")
        return self.ok(check, f"{len(self.obs.ctas)} CTA control(s) were found. Placement above the fold was not measured.")

    def cta_hierarchy(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.high_intent and self.obs.passive:
            return self.observed(check, "The sample mixes specific actions and generic labels. Visual priority was not measured.")
        if self.obs.high_intent:
            return self.ok(check, "At least one specific action label is present: " + _join([cta["text"] for cta in self.obs.high_intent]) + ".")
        return self.observed(check, "Primary versus secondary hierarchy was not assigned from style alone.")

    def cta_destination(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.broken_ctas:
            return self.fail(check, "CTA links with an empty, hash, or javascript destination: " + _join(self.obs.broken_ctas) + ".", priority="High", effort="Low", action="Point the control at the real next step.", stage="Landing")
        hrefs = [cta["href"] for cta in self.obs.ctas if cta.get("href")]
        if not hrefs:
            return self.observed(check, "Button CTAs had no href. Their click destination was not executed.")
        return self.ok(check, "CTA destinations recorded in the sample: " + _join(hrefs) + ".")

    def broken_ctas(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.cta_destination(check)

    def intent_mix(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.observed(
            check,
            f"Label classification only: {len(self.obs.high_intent)} high-intent, {len(self.obs.passive)} generic, "
            f"{len(self.obs.ctas) - len(self.obs.high_intent) - len(self.obs.passive)} other. This does not measure visitor intent.",
        )

    def missing_trust(self, check: Dict[str, Any]) -> Dict[str, Any]:
        gaps = []
        if not self.obs.privacy:
            gaps.append("no privacy link or mention")
        if self.obs.testimonials == 0 and self.obs.reviews == 0 and self.obs.logos == 0:
            gaps.append("no testimonial, review, or logo mention")
        if not self.obs.contact:
            gaps.append("no phone, email, or contact path")
        if not gaps:
            return self.ok(check, "The sample includes a privacy mention and at least one contact path or proof mention.")
        priority = "High" if "no phone, email, or contact path" in gaps and "lead_gen" in self.obs.detected_models else "Medium"
        return self.fail(check, "In the inspected sample: " + "; ".join(gaps) + ".", priority=priority, effort="Low", action="Put a real contact path and a privacy disclosure next to the conversion action.", stage="Trust")

    def privacy(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.privacy:
            return self.ok(check, "A privacy mention or privacy URL was found in the sample.")
        return self.fail(check, "No privacy policy link or mention was found in the sample.", priority="Medium", effort="Low", action="Add a crawlable privacy disclosure.", stage="Trust")

    def contact_info(self, check: Dict[str, Any]) -> Dict[str, Any]:
        methods = []
        if self.obs.tel_links:
            methods.append(f"{self.obs.tel_links} tel link(s)")
        if self.obs.mailto:
            methods.append(f"{self.obs.mailto} mailto link(s)")
        if any(page["kind"] == "contact" for page in self.obs.pages):
            methods.append("a contact URL")
        if methods:
            return self.ok(check, "Contact paths in the sample: " + "; ".join(methods) + ".")
        if "lead_gen" in self.obs.detected_models or "local" in self.obs.detected_models:
            return self.fail(check, "No phone, email, or contact URL was found.", priority="High", effort="Low", action="Publish a contact method on the primary landing page.", stage="Trust")
        return self.observed(check, "No phone, email, or contact URL was found in the sample.")

    def testimonials(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.testimonials or self.obs.reviews or self.obs.case_studies:
            return self.ok(check, "Proof language or a case-study URL was present. The quotes were not verified with the customers.")
        return self.observed(check, "No testimonial, review, or case-study URL was found in the sample. Absence in the sample is not absence on the whole site.")

    def customer_logos(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.logos:
            return self.observed(check, "The sample mentions logos. The audit did not verify that each logo is a real customer.")
        return self.observed(check, "No customer-logo mention was found in the sample.")

    def credentials(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.badges:
            return self.observed(check, "Credential phrases in the sample: " + _join(self.obs.badges) + ". The certificates were not verified with the issuer.")
        return self.observed(check, "No SOC 2, ISO 27001, GDPR, or HIPAA phrase was found.")

    def price_clarity(self, check: Dict[str, Any]) -> Dict[str, Any]:
        commercial = bool(self.obs.detected_models & {"ecommerce", "saas"})
        if self.obs.prices or self.obs.pricing_urls:
            where = _join(self.obs.pricing_urls) or "page copy"
            return self.ok(check, f"Price text or a pricing URL was found ({where}). Examples: {_join(self.obs.prices) or 'pricing URL only'}.")
        if commercial:
            return self.fail(check, "No price and no pricing URL were found for a site classified as e-commerce or SaaS.", priority="High", effort="Medium", action="Publish the price, or say clearly that pricing is quoted.", stage="Pricing")
        return self.observed(check, "No public price was found. Sales-assisted pricing was not judged a defect.")

    def billing_frequency(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if "saas" not in self.obs.detected_models and not self.obs.billing:
            return self.na(check, "Billing frequency was not applicable. The sample was not classified as a subscription and did not mention a billing period.")
        if self.obs.billing:
            return self.ok(check, "The sample mentions a billing period such as monthly or annual. The terms were not executed.")
        return self.fail(check, "A subscription classification had no monthly or annual billing language.", priority="Medium", effort="Low", action="State the billing period next to the price.", stage="Pricing")

    def hidden_fees(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.hidden_fee:
            return self.fail(check, "The sample says additional fees may apply and does not show the amounts.", priority="Medium", effort="Low", action="List the extra charges before the commitment step.", stage="Pricing")
        if self.obs.tax_words:
            return self.ok(check, "Tax is mentioned in the sample. Whether the amount is complete was not calculated.")
        return self.observed(check, "No hidden-fee phrase was found. Checkout was not completed, so undisclosed fees can still exist.")

    def urgency(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.urgency:
            return self.ok(check, "No unsupported urgency phrase was found in the sample.")
        return self.fail(
            check,
            "Urgency or scarcity language was present (" + _join(self.obs.urgency) + ") without a dated condition in the same sample.",
            priority="Low",
            effort="Low",
            action="Remove the urgency line unless a real, dated limit can be shown beside it.",
            stage="Trust",
        )

    def non_manipulative(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.urgency:
            return self.observed(check, "Pressure language was found. It is recorded as a trust defect, not as a tactic to copy.")
        return self.ok(check, "No pressure phrase from the urgency list was found. Tone was not reviewed by a person.")

    def field_labels(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.forms:
            return self.observed(check, "No form was found in the sample, so labels were not judged.")
        missing = sum(form["missing_labels"] for form in self.obs.forms)
        if missing:
            page = next(form["page_url"] for form in self.obs.forms if form["missing_labels"])
            return self.fail(check, f"{missing} form control(s) have no label, wrapping label, or aria name.", priority="High", effort="Low", action="Give every control a visible label that stays present.", page_url=page, stage="Form")
        return self.ok(check, f"All {sum(form['fields'] for form in self.obs.forms)} substantive control(s) in the sample have a label or an accessible name.")

    def placeholder_misuse(self, check: Dict[str, Any]) -> Dict[str, Any]:
        count = sum(form["placeholder_only"] for form in self.obs.forms)
        if not self.obs.forms:
            return self.observed(check, "No form was available.")
        if count:
            return self.fail(check, f"{count} control(s) use a placeholder without a label.", priority="Medium", effort="Low", action="Keep the label visible. Do not use the placeholder as the name.", stage="Form")
        return self.ok(check, "No placeholder-only control was found.")

    def field_count(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.forms:
            return self.observed(check, "No form fields were counted because no form was in the sample.")
        largest = max(form["fields"] for form in self.obs.forms)
        return self.observed(check, f"{len(self.obs.forms)} form(s), {sum(form['fields'] for form in self.obs.forms)} substantive field(s), largest form {largest}. Necessity of each field was not judged.")

    def field_necessity(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Field necessity was not judged. The audit cannot know which questions the business must ask.")

    def required_optional(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.forms:
            return self.observed(check, "No form was available to separate required and optional fields.")
        required = sum(form["required"] for form in self.obs.forms)
        return self.observed(check, f"{required} control(s) carry a required attribute. Optional fields were not marked in a separate audit of copy.")

    def input_types(self, check: Dict[str, Any]) -> Dict[str, Any]:
        email_as_text = sum(form["email_as_text"] for form in self.obs.forms)
        if email_as_text:
            return self.fail(check, f"{email_as_text} email-named control(s) use type=text.", priority="Low", effort="Low", action="Use type=email so the mobile keyboard and autofill match the field.", stage="Form")
        if not self.obs.forms:
            return self.observed(check, "No inputs were inspected.")
        types = sorted({kind for form in self.obs.forms for kind in form["types"]})
        return self.ok(check, "Input types in the sample: " + _join(types) + ".")

    def autofill(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.forms:
            return self.observed(check, "Autocomplete was not inspected because no form was present.")
        with_auto = sum(form["autocomplete"] for form in self.obs.forms)
        return self.observed(check, f"{with_auto} control(s) set autocomplete. Browser autofill behavior was not run.")

    def mobile_keyboard(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.input_types(check)

    def broken_forms(self, check: Dict[str, Any]) -> Dict[str, Any]:
        bare = [form for form in self.obs.forms if form["fields"] and not form["has_submit"]]
        if bare:
            return self.fail(check, f"{len(bare)} form(s) have fields and no submit control.", priority="High", effort="Low", action="Add a submit control whose label names the result.", page_url=bare[0]["page_url"], stage="Form")
        if not self.obs.forms:
            return self.observed(check, "No form was present to break.")
        return self.ok(check, "Each inspected form has a submit control. Submission was not executed.")

    def spam_bots(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.forms:
            return self.observed(check, "Spam handling was not inspected.")
        protected = sum(1 for form in self.obs.forms if form["honeypot"])
        return self.observed(check, f"{protected} of {len(self.obs.forms)} form(s) mention a captcha or honeypot. Submissions were not classified as spam, and a captcha was not recommended as a conversion tactic.")

    def viewport(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.pages:
            return self.un(check, "Viewport was not inspected.")
        if self.obs.viewport_missing:
            return self.fail(check, "Pages without a viewport meta tag: " + _join(self.obs.viewport_missing) + ".", priority="Medium", effort="Low", action="Add a viewport meta tag so the layout can scale.", page_url=self.obs.viewport_missing[0], stage="Mobile")
        return self.ok(check, "Every inspected page has a viewport meta tag. A rendered mobile layout was not captured.")

    def mobile_gaps(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.viewport(check)

    def responsive_layout(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.viewport(check)

    def technical_failures(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.status_errors:
            return self.fail(check, "Error responses in the sample: " + _join(self.obs.status_errors) + ".", priority="High", effort="Medium", action="Restore a successful response before testing copy changes.", stage="Technical")
        if not self.obs.pages:
            return self.un(check, "HTTP status was not available.")
        return self.ok(check, "No HTTP 4xx or 5xx response was in the inspected sample.")

    def dead_ends(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.dead_ends:
            return self.fail(check, "Pages with substantial text, no CTA, and no internal link: " + _join(self.obs.dead_ends) + ".", priority="Medium", effort="Low", action="Add a next step or an internal link from those pages.", stage="Navigation")
        return self.ok(check, "No inspected page was both text-heavy and without a CTA or internal link.")

    def nav_clarity(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.pages:
            return self.un(check, "Navigation was not inspected.")
        if not self.obs.nav_labels:
            return self.observed(check, "No header or nav link labels were parsed. A navigation landmark may still be present without anchor text.")
        unique = list(dict.fromkeys(self.obs.nav_labels))
        return self.ok(check, f"{len(unique)} navigation label(s): " + _join(unique) + ".")

    def nav_labels(self, check: Dict[str, Any]) -> Dict[str, Any]:
        generic = [label for label in self.obs.nav_labels if _PASSIVE.search(label.strip().lower())]
        if generic:
            return self.fail(check, "Generic navigation labels: " + _join(generic) + ".", priority="Low", effort="Low", action="Rename the links to the destination.", stage="Navigation")
        if not self.obs.nav_labels:
            return self.observed(check, "Navigation labels were not parsed from a header or nav landmark.")
        return self.ok(check, "Parsed navigation labels are specific enough to name a destination.")

    def nav_complexity(self, check: Dict[str, Any]) -> Dict[str, Any]:
        unique = list(dict.fromkeys(self.obs.nav_labels))
        if len(unique) > 12:
            return self.observed(check, f"The sample nav exposes {len(unique)} labels. Whether that is too many was not tested with users.")
        return self.observed(check, f"{len(unique)} navigation label(s) were parsed. Menu complexity was not user-tested.")

    def site_search(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.has_search:
            return self.ok(check, "A search input was present. Result quality was not queried.")
        if "ecommerce" in self.obs.detected_models and len([page for page in self.obs.pages if page["kind"] == "product"]) > 3:
            return self.fail(check, "Several product URLs were sampled and no search input was found.", priority="Low", effort="Medium", action="Add search if the catalog is too large to scan.", stage="Navigation")
        return self.observed(check, "No search input was found. That is not treated as a defect for this sample.")

    def breadcrumbs(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.breadcrumbs:
            return self.ok(check, f"Breadcrumb markup was found on {self.obs.breadcrumbs} page(s).")
        return self.observed(check, "No breadcrumb markup was found. That alone is not a conversion defect.")

    def image_relevance(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.total_images == 0:
            return self.observed(check, "No images were counted in the sample.")
        if self.obs.images_missing_alt:
            return self.fail(check, f"{self.obs.images_missing_alt} of {self.obs.total_images} image(s) have no alt attribute.", priority="Low", effort="Low", action="Add alt text that says what the image shows, or an empty alt if it is decorative.", stage="Content")
        return self.ok(check, f"{self.obs.total_images} image(s) have an alt attribute. Relevance of the pictures was not judged by a person.")

    def cwv(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.field_cwv:
            values = self.obs.field_cwv
            return self.observed(
                check,
                f"Field data from {values.get('origin') or 'the origin'}: p75 LCP {values.get('lcp_ms')} ms, INP {values.get('inp_ms')} ms, CLS {values.get('cls')}.",
                state="VERIFIED",
            )
        timing = ""
        if self.obs.ttfb_values:
            average = sum(self.obs.ttfb_values) / len(self.obs.ttfb_values)
            timing = f" Average response timing was {average:.0f} ms. That is not Lighthouse and not CrUX."
        return self.un(check, "Core Web Vitals were not measured." + timing)

    def third_party(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.pages:
            return self.un(check, "Scripts were not inspected.")
        return self.observed(check, f"{self.obs.third_party} third-party script source(s) were counted. Their effect on conversion was not measured.")

    def analytics_tags(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.analytics.get("state") == "MEASURED":
            return self.observed(check, "GA4 returned a property total. The tag's event names were not validated.", state="VERIFIED")
        if self.obs.analytics_tags:
            return self.observed(check, "A GA or GTM script is present (" + _join(self.obs.analytics_tags) + "). Presence is not a working conversion event.")
        return self.un(check, "No analytics tag was found and GA4 was not connected. Event coverage was not scored.")

    def analytics_coverage(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.analytics_tags(check)

    def consent_gap(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.consent:
            return self.observed(check, "A consent interface or cookie notice was present. Whether it blocks conversion events was not tested.")
        return self.nt(check, "Consent behavior was not tested. A missing banner in the HTML is not proof of a tracking gap.")

    def behavior_not_clicks(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, f"{check['label']}: no click, scroll, or replay stream was connected. A CTA in the HTML is not a click, and a click pattern would not by itself establish motivation or explain why someone left.")

    def competitor(self, check: Dict[str, Any]) -> Dict[str, Any]:
        named = ""
        if self.obs.competitor_domains:
            named = " Recorded domains without a conversion crawl: " + _join(self.obs.competitor_domains) + "."
        return self.nt(check, f"{check['label']}: competitor journeys were not crawled.{named} No competitor conversion rate is stated.")

    def research_absent(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, f"{check['label']}: no moderated test, survey, or interview was attached to this run.")

    def psych_limit(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, f"{check['label']}: not diagnosed from the page. The sample does not establish motivation, and it is not a reason to pressure a purchase.")

    def governance(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, f"{check['label']}: this run is a point-in-time sample. Continuous monitoring, owners, and SLAs were not configured here.")

    def experiment_design(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.observed(check, f"{check['label']}: findings in this report name a problem, evidence, hypothesis, metric, guardrail, and validation plan. None of them has been run as a test.")

    def stats_rule(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.observed(check, f"{check['label']}: a winning variant is not declared from a higher observed rate. No experiment was supplied to evaluate.")

    def forecast_refused(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, f"{check['label']}: no lift is assumed. This audit does not multiply an assumed conversion change by traffic, and it does not publish a conservative, base, or upside revenue scenario.")

    def forecast_baseline(self, check: Dict[str, Any]) -> Dict[str, Any]:
        line = self.rate_line()
        if not line:
            return self.un(check, "Baseline traffic and conversion were not both available. " + self.obs.analytics.get("notice", ""))
        return self.observed(check, "Baseline only, with no lift applied. " + line, state="VERIFIED")

    def negative_effects(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.observed(check, "Proposed changes keep the current experience as the control when a test is possible. Guardrails are lead quality, downstream completion, errors, and abandonment.")

    def prioritization(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.observed(check, f"{check['label']}: findings are ordered by observed severity and effort. Affected users are not counted unless a measured visitor total exists, and the expected impact is not a revenue number.")

    def roadmap(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.observed(check, "The 30/60/90 roadmap lists hypotheses from observed defects. Dates are not assigned, and no lift is promised.")

    def ux_a11y_pointer(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.wcag:
            return self.observed(check, f"Automated screening recorded {self.obs.wcag['total']} violation(s). {self.obs.wcag['note']}", state="SAMPLE_VERIFIED")
        return self.observed(check, "Accessibility findings in this CRO pass are limited to labels, alt text, and viewport. That is not a conformance claim.")

    def wcag_scope(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.wcag is None:
            return self.nt(check, "No automated accessibility screening was attached. This CRO pass does not certify WCAG conformance.")
        return self.observed(check, self.obs.wcag["note"] + f" Status label from the screener: {self.obs.wcag.get('status') or 'unspecified'}.")

    def contrast(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.wcag:
            return self.nt(check, "Color contrast was not measured from static HTML.")
        if self.obs.wcag["contrast"]:
            return self.fail(check, f"Automated screening reported {self.obs.wcag['contrast']} contrast issue(s). This is not a WCAG certificate.", priority="Medium", effort="Low", action="Repair the flagged contrast pairs and re-run the screener.", stage="Accessibility")
        return self.ok(check, "The attached automated screening reported no contrast violations. This is not a WCAG certificate.")

    def keyboard(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.wcag:
            return self.nt(check, "Keyboard behavior was not executed.")
        if self.obs.wcag["keyboard"]:
            return self.fail(check, f"Automated screening reported {self.obs.wcag['keyboard']} keyboard issue(s).", priority="Medium", effort="Medium", action="Make the flagged controls operable from the keyboard.", stage="Accessibility")
        return self.ok(check, "The attached screening reported no keyboard violations. A person did not complete the task by keyboard.")

    def above_fold_limit(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, f"{check['label']}: DOM order is not a viewport measurement, so above-the-fold placement was not claimed.")

    def tap_targets(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Rendered tap-target size was not measured.")

    def js_errors(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Static HTML does not show runtime JavaScript exceptions.")

    def journey_stage(self, check: Dict[str, Any]) -> Dict[str, Any]:
        kinds = sorted({page["kind"] for page in self.obs.pages})
        if not kinds:
            return self.un(check, "No pages were available to sketch a journey.")
        return self.inferred(check, f"{check['label']}: page types in the sample are {', '.join(kinds)}. This is a map of URLs, not a path visitors took.")

    def funnel_definitions(self, check: Dict[str, Any]) -> Dict[str, Any]:
        stages = []
        if any(page["kind"] == "home" for page in self.obs.pages) or self.obs.pages:
            stages.append("landing")
        if self.obs.pricing_urls:
            stages.append("pricing")
        if self.obs.forms:
            stages.append("form")
        if any(page["kind"] == "checkout" for page in self.obs.pages):
            stages.append("checkout")
        if self.obs.confirmation_urls:
            stages.append("confirmation")
        if not stages:
            return self.un(check, "Funnel stages were not defined because no pages were inspected.")
        return self.inferred(check, "Working stage list from the sample: " + " → ".join(stages) + ". Entry and exit events were not measured, so this is not a conversion funnel.")

    def metric_conversion_rate(self, check: Dict[str, Any]) -> Dict[str, Any]:
        line = self.rate_line()
        if line:
            return self.observed(check, line, state="VERIFIED")
        if self.obs.analytics.get("state") == "MEASURED" and not self.obs.analytics.get("key_events_present"):
            return self.un(check, "Sessions were returned and key events were not. A missing event count was not treated as zero.")
        return self.un(check, "Primary conversion rate was not calculated. " + self.obs.analytics.get("notice", ""))

    def metric_secondary(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "A secondary conversion was not defined, so no secondary rate is shown.")

    def metric_qualified_lead(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Qualified lead rate was not calculated. CRM qualification was not connected, and spam was not separated from valid leads.")

    def metric_rpv(self, check: Dict[str, Any]) -> Dict[str, Any]:
        analytics = self.obs.analytics
        eligible_visitors = analytics.get("eligible_visitors")
        value = rate(analytics.get("revenue"), eligible_visitors)
        if value is None:
            return self.un(
                check,
                "Revenue per visitor was not calculated. Attributed revenue and an explicit eligible-visitor denominator were not both present; sessions were not substituted for visitors.",
            )
        return self.observed(
            check,
            f"{analytics['revenue']} attributed revenue ÷ {eligible_visitors} eligible visitors = {value:.4f} over {analytics.get('period') or 'the connected period'}.",
            state="VERIFIED",
        )

    def metric_aov(self, check: Dict[str, Any]) -> Dict[str, Any]:
        analytics = self.obs.analytics
        value = rate(analytics.get("revenue"), analytics.get("orders"))
        if value is not None:
            return self.observed(check, f"{analytics['revenue']} net sales ÷ {analytics['orders']} orders = {value:.2f}.", state="VERIFIED")
        if "ecommerce" not in self.obs.detected_models:
            return self.na(check, "Average order value does not apply. The site was not classified as e-commerce and no order total was connected.")
        return self.un(check, "Average order value was not calculated. Net sales and completed orders were not both present.")

    def metric_checkout(self, check: Dict[str, Any]) -> Dict[str, Any]:
        checkout_pages = [page["url"] for page in self.obs.pages if page["kind"] == "checkout"]
        if checkout_pages:
            return self.un(check, "Checkout URL(s) were seen (" + _join(checkout_pages) + "). The completion rate was not measured.")
        if "ecommerce" not in self.obs.detected_models:
            return self.na(check, "Checkout completion does not apply. No checkout flow was classified.")
        return self.un(check, "Checkout completion was not measured, and no checkout URL was in the sample.")

    def metric_cart_abandon(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if "ecommerce" not in self.obs.detected_models:
            return self.na(check, "Cart abandonment does not apply outside an e-commerce classification.")
        return self.un(check, "Cart abandonment was not measured. A cart URL is not an abandonment rate.")

    def metric_form_completion(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.forms:
            return self.un(check, f"{len(self.obs.forms)} form(s) were seen. Form starts and valid submissions were not measured, so the completion rate is unavailable.")
        return self.un(check, "Form completion was not measured. No form-start or submit events were connected.")

    def metric_funnel_completion(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Funnel completion was not measured. A property key-event rate, when present, is not a stage-to-stage funnel.")

    def metric_device_split(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Mobile and desktop conversion were not both returned. A viewport meta tag is not a device conversion rate, and the device is not assumed to be the cause.")

    def metric_landing_engagement(self, check: Dict[str, Any]) -> Dict[str, Any]:
        engagement = self.obs.analytics.get("engagement_rate_pct")
        if engagement is None:
            return self.un(check, "Landing-page engagement was not measured. " + self.obs.analytics.get("notice", ""))
        return self.observed(
            check,
            f"GA4 engagement rate is {engagement}% of sessions for {self.obs.analytics.get('period') or 'the connected period'}. This is a property engagement rate, not a per-landing-page rate and not a conversion rate.",
            state="VERIFIED",
        )

    def landing_inventory(self, check: Dict[str, Any]) -> Dict[str, Any]:
        pages = self.obs.analytics.get("landing_pages") or []
        if not pages:
            urls = [page["url"] for page in self.obs.pages[:8]]
            if not urls:
                return self.un(check, "No landing-page list was returned and no pages were crawled.")
            return self.observed(check, "Crawled URLs only. Traffic volume was not attached: " + _join(urls) + ".")
        names = []
        for row in pages[:8]:
            if isinstance(row, dict):
                names.append(str(row.get("page") or row.get("landingPage") or ""))
        return self.observed(check, "GA4 landing pages were listed without treating a missing conversion field as zero: " + _join(names) + ".", state="VERIFIED")

    def landing_conversion(self, check: Dict[str, Any]) -> Dict[str, Any]:
        pages = self.obs.analytics.get("landing_pages") or []
        measured = []
        for row in pages:
            if not isinstance(row, dict):
                continue
            for key in ("conversions", "keyEvents", "key_events"):
                if key in row and isinstance(row[key], (int, float)) and not isinstance(row[key], bool):
                    measured.append(f"{row.get('page')}: {row[key]}")
                    break
        if measured:
            return self.observed(check, "Landing-page conversion fields that were actually present: " + _join(measured) + ".", state="VERIFIED")
        if pages:
            return self.un(check, "Landing pages were listed without a conversion field. Missing conversions were not treated as zero.")
        return self.un(check, "Conversion by landing page was not returned.")

    def acquisition_channels(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.organic_clicks is None and self.obs.analytics.get("sessions") is None:
            return self.un(check, "Acquisition channels were not measured. Search Console clicks and GA4 sessions were not both unavailable by substitution: neither source returned a measured total.")
        bits = []
        if self.obs.organic_clicks is not None:
            bits.append(f"Search Console clicks: {self.obs.organic_clicks} over {self.obs.organic_period or 'the connected period'}. Clicks are not conversions.")
        if self.obs.analytics.get("sessions") is not None:
            bits.append(f"GA4 sessions: {self.obs.analytics['sessions']}. Sessions were not split into channels.")
        return self.observed(check, " ".join(bits), state="VERIFIED")

    def channel_organic(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.organic_clicks is None:
            return self.un(check, "Organic conversions were not returned.")
        return self.un(check, f"Organic clicks were {self.obs.organic_clicks}. Organic conversions were not returned. Clicks were not treated as conversions.")

    def add_to_cart(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.add_to_cart:
            return self.ok(check, "Add-to-cart language was found. The cart interaction was not executed.")
        return self.fail(check, "The e-commerce sample has no add-to-cart language.", priority="High", effort="Medium", action="Expose an add-to-cart control on the product page.", stage="Checkout")

    def cart_checkout_pair(self, check: Dict[str, Any]) -> Dict[str, Any]:
        kinds = {page["kind"] for page in self.obs.pages}
        if "checkout" in kinds or self.obs.add_to_cart:
            return self.observed(check, "Cart or checkout language was present. The flow was not purchased through.")
        return self.fail(check, "No cart or checkout URL or add-to-cart language was in the e-commerce sample.", priority="High", effort="Medium", action="Provide a path from product to checkout.", stage="Checkout")

    def guest_checkout(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.guest_checkout:
            return self.ok(check, "Guest checkout is mentioned. The flow was not completed.")
        return self.observed(check, "Guest checkout was not mentioned. Whether an account is required was not executed.")

    def saas_pricing(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.price_clarity(check)

    def trial_vs_freemium(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.trial:
            return self.observed(check, "Free-trial or no-credit-card language was found. The trial terms were not confirmed in a product account.")
        return self.observed(check, "No free-trial or freemium path was named in the sample.")

    def demo_booking(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.demo or any(page["kind"] == "contact" for page in self.obs.pages):
            return self.ok(check, "A demo or contact path is present in the sample.")
        return self.fail(check, "No demo or contact path was found for the SaaS sample.", priority="High", effort="Low", action="Offer a demo or a signup path from the primary page.", stage="Lead")

    def service_pages(self, check: Dict[str, Any]) -> Dict[str, Any]:
        pages = [page["url"] for page in self.obs.pages if page["kind"] in ("service", "home", "contact")]
        if pages:
            return self.ok(check, "Service or contact URLs in the sample: " + _join(pages) + ".")
        return self.observed(check, "No service URL pattern was found. The home page may still describe the service.")

    def qualification_forms(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.forms:
            return self.fail(check, "No qualification or contact form was in the lead-generation sample.", priority="High", effort="Medium", action="Add a form that asks only what sales needs for the first response.", stage="Lead")
        return self.observed(check, f"{len(self.obs.forms)} form(s) were found. Whether the questions match sales qualification was not confirmed with the sales team.")

    def click_to_call(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.tel_links:
            return self.ok(check, f"{self.obs.tel_links} telephone link(s) were found.")
        return self.fail(check, "No click-to-call link was found in the local sample.", priority="High", effort="Low", action="Add a tel link on the location page.", stage="Lead")

    def appointment(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.appointment or any(page["kind"] == "booking" for page in self.obs.pages):
            return self.ok(check, "Appointment or booking language was found. Availability was not queried.")
        return self.fail(check, "No appointment or booking path was found.", priority="High", effort="Medium", action="Show how a visitor books, including what happens if a slot is taken.", stage="Lead")

    def directions(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.contact or self.obs.tel_links:
            return self.ok(check, "A contact or telephone path is present. A map was not required to pass this check.")
        return self.fail(check, "No directions or contact path was found.", priority="Medium", effort="Low", action="Publish the address and a contact method.", stage="Trust")

    def shipping_returns(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if "ecommerce" not in self.obs.detected_models and not self.obs.shipping:
            return self.na(check, "Shipping and returns were not applicable. The sample was not classified as e-commerce and did not mention shipping.")
        if self.obs.shipping:
            return self.ok(check, "Shipping or returns language was found. The policy was not checked out.")
        return self.fail(check, "No shipping or returns language was found on the e-commerce sample.", priority="Medium", effort="Low", action="State shipping and returns before checkout.", stage="Checkout")

    def refund_policy(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.refund or self.obs.cancel or self.obs.guarantee:
            return self.ok(check, "Refund, cancel, or guarantee language was found. The policy text was not legally reviewed.")
        if self.obs.detected_models & {"ecommerce", "saas"}:
            return self.fail(check, "No refund, cancellation, or guarantee language was found.", priority="Medium", effort="Low", action="State the refund or cancellation terms next to the price.", stage="Trust")
        return self.observed(check, "No refund language was found. It was not required for the classified model.")

    def guarantees(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.refund_policy(check)

    def support_availability(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.support or self.obs.contact:
            return self.ok(check, "Support or contact language was found. Response time was not measured.")
        return self.observed(check, "No support offer was found in the sample.")

    def confirmation_page(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.confirmation_urls:
            return self.ok(check, "Confirmation-like URLs: " + _join(self.obs.confirmation_urls) + ".")
        return self.observed(check, "No thank-you or confirmation URL was in the sample. That does not prove the flow has no confirmation.")

    def finding_template(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.observed(check, f"{check['label']}: each opened finding carries an id, evidence, scope, hypothesis, metric, guardrails, validation, owner, and an impact statement that does not invent a lift.")

    def personalization(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, f"{check['label']}: one crawl cannot show a personalized experience. Incorrect personalization was not tested.")

    def identity_gap(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, f"{check['label']}: identity resolution was not available. Users were not stitched across devices or sessions, and duplicate people were not counted.")

    def form_persistence(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Cart and form persistence were not tested by leaving and returning to the page.")

    def search_intent_match(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.h1:
            return self.inferred(check, f"The landing H1 is “{self.obs.h1}”. Match to a query was not measured because no query and landing pair was supplied.")
        return self.un(check, "Search intent match was not assessed. No query was paired with a landing page.")

    def ad_message_match(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Advertising message match was not assessed. No ad copy was supplied.")

    def claim_specificity(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.h1:
            return self.observed(check, "No headline was available to judge specificity.")
        return self.inferred(check, f"The headline “{self.obs.h1}” is the claim that was read. Customer proof for it was not established.")

    def proof_for_claims(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.prices and not (self.obs.testimonials or self.obs.case_studies):
            return self.inferred(check, "Numbers were found in the copy (" + _join(self.obs.prices) + "). The sample does not show the source of those numbers.")
        if self.obs.testimonials or self.obs.case_studies:
            return self.observed(check, "A testimonial mention or case-study URL sits in the sample. The underlying result was not audited.")
        return self.observed(check, "No performance number requiring proof was isolated.")

    def benefit_orientation(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.h1:
            return self.observed(check, "No headline was available.")
        if self.obs.you_words > self.obs.we_words:
            return self.ok(check, "The headline block uses more you/your than we/our.")
        return self.observed(check, "The headline block does not use more you/your than we/our. That ratio is not a conversion result.")

    def readability(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "A readability score was not used. A stored zero cannot be told apart from an unmeasured score.")

    def content_hierarchy(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.h1 and self.obs.subhead:
            return self.ok(check, "The first page has an H1 and an H2.")
        if self.obs.h1:
            return self.observed(check, "An H1 is present and no H2 was captured on that page.")
        return self.fail(check, "No H1 was found to start the content hierarchy.", priority="Medium", effort="Low", action="Add one H1 that states the offer.", stage="Landing")

    def type_hierarchy(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.content_hierarchy(check)

    def page_length(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.pages:
            return self.un(check, "Page length was not measured.")
        words = [page["word_count"] for page in self.obs.pages]
        return self.observed(check, f"Word counts in the sample range from {min(words)} to {max(words)}. Length was not judged as too short or too long.")

    def social_proof(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.testimonials(check)

    def business_identity(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.business_name or self.obs.about:
            name = self.obs.business_name or "a company description"
            return self.ok(check, f"Business identity evidence: {name}.")
        if self.obs.pages:
            host = urlparse(self.obs.pages[0]["url"]).netloc
            return self.observed(check, f"The host is {host}. A company name was not stated in the profile or an about passage.")
        return self.un(check, "Business identity was not available.")

    def security_info(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.security or self.obs.badges:
            return self.observed(check, "Security language or a credential phrase was found. It was not treated as a penetration test or a certificate.")
        return self.observed(check, "No security reassurance phrase was found near the copy that was sampled.")

    def payment_security(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Payment data handling was not tested. This audit does not submit card numbers and does not claim PCI compliance.")

    def duplicate_submission(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Duplicate submission was not tested. The form was not posted twice.")

    def processing_states(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Loading and disabled states were not observed because the control was not activated.")

    def currency_consistency(self, check: Dict[str, Any]) -> Dict[str, Any]:
        currencies = set()
        for price in self.obs.prices:
            for symbol in ("$", "£", "€", "₹"):
                if symbol in price:
                    currencies.add(symbol)
        if len(currencies) > 1:
            return self.observed(check, "More than one currency symbol appears (" + ", ".join(sorted(currencies)) + "). Whether that is a contradiction was not established.")
        if currencies:
            return self.ok(check, "One currency symbol was found among the sampled prices.")
        return self.observed(check, "No currency symbol was available to compare.")

    def inconsistent_offers(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if len(self.obs.prices) > 1:
            return self.inferred(check, "Multiple prices were found (" + _join(self.obs.prices) + "). They were not matched to plans, so inconsistency was not established.")
        return self.observed(check, "No conflicting offer was established from the sample.")

    def misleading_claims(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "A claim was not marked misleading. That judgment needs a contradicting source, which was not attached.")

    def high_intent_friction(self, check: Dict[str, Any]) -> Dict[str, Any]:
        hot = [page for page in self.obs.pages if page["kind"] in ("pricing", "contact", "checkout", "account")]
        if not hot:
            return self.observed(check, "No pricing, contact, checkout, or account URL was in the sample.")
        problems = []
        for page in hot:
            if any(cta.get("passive") for cta in page["ctas"]):
                problems.append(f"generic CTA on {page['url']}")
            if any(form["missing_labels"] for form in page["forms"]):
                problems.append(f"unlabeled fields on {page['url']}")
        if problems:
            return self.fail(check, "High-intent URLs with friction: " + _join(problems) + ".", priority="High", effort="Low", action="Remove the generic label or the missing field name on that step.", stage="Conversion")
        return self.ok(check, "High-intent URLs in the sample did not show a generic CTA or an unlabeled field.")

    def recovery_opportunities(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Abandonment recovery was not measured. No email or return-session program was connected.")

    def top_opportunities(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.observed(check, "Opportunities are the hypotheses in the finding list. They are not ranked by a forecasted revenue lift.")

    def priority_recommendations(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.top_opportunities(check)

    def revenue_risk(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Revenue and lead-quality risk were not quantified. No revenue, margin, or qualified-lead ledger was connected.")

    def tracking_gaps(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.analytics_tags(check)

    def recordings(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.replay_tags:
            return self.nt(check, f"{_join(self.obs.replay_tags)} is present. Recordings were not opened, and lawful collection was not reviewed.")
        return self.nt(check, "No session recording was supplied for review.")

    def heatmaps(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "No heatmap was supplied. A script that might collect one was not treated as a heatmap result.")

    def product_pages(self, check: Dict[str, Any]) -> Dict[str, Any]:
        pages = [page["url"] for page in self.obs.pages if page["kind"] == "product"]
        if pages:
            return self.ok(check, "Product URLs: " + _join(pages) + ".")
        return self.fail(check, "No product URL was in the e-commerce sample.", priority="Medium", effort="Medium", action="Give each sold item a page that states the offer and the next step.", stage="Consideration")

    def feature_pages(self, check: Dict[str, Any]) -> Dict[str, Any]:
        pages = [page["url"] for page in self.obs.pages if page["kind"] in ("service", "home")]
        if pages:
            return self.observed(check, "Pages that can carry the product story: " + _join(pages) + ".")
        return self.observed(check, "No feature or solution URL pattern was found.")

    def industry_pages(self, check: Dict[str, Any]) -> Dict[str, Any]:
        pages = [page["url"] for page in self.obs.pages if "industr" in page["url"].lower()]
        if pages:
            return self.ok(check, "Industry URLs: " + _join(pages) + ".")
        return self.observed(check, "No industry URL was in the sample. That is not proof the business needs one.")

    def location_pages(self, check: Dict[str, Any]) -> Dict[str, Any]:
        pages = [page["url"] for page in self.obs.pages if page["kind"] == "location"]
        if pages:
            return self.ok(check, "Location URLs: " + _join(pages) + ".")
        if self.obs.tel_links:
            return self.observed(check, "A telephone link was found without a separate location URL.")
        return self.fail(check, "No location page was in the local sample.", priority="Medium", effort="Medium", action="Publish the location, the service, and how to book.", stage="Landing")

    def local_reviews(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.testimonials(check)

    def case_studies(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.case_studies:
            return self.ok(check, "Case-study URLs: " + _join(self.obs.case_studies) + ".")
        return self.observed(check, "No case-study URL was in the sample.")

    def faq_objections(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.faq:
            return self.ok(check, "FAQ language was found. Whether it answers a real objection was not tested with customers.")
        return self.observed(check, "No FAQ block was found. A missing FAQ is not by itself a conversion defect.")

    def next_step(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.cta_presence(check)

    def offer_clarity(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.weak_value_prop(check)

    def value_prop_visibility(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.weak_value_prop(check)

    def primary_objective_clarity(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.weak_value_prop(check)

    def cta_prominence(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.cta_presence(check)

    def path_clarity(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.conversion_paths(check)

    def landing_transitions(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.conversion_paths(check)

    def signup_confirmation(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.confirmation_page(check)

    def order_confirmation(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.confirmation_page(check)

    def transaction_confirmation(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.confirmation_page(check)

    def demo_consult(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.demo_booking(check)

    def meeting_booking(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.demo_booking(check)

    def local_pricing(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.price_clarity(check)

    def booking_friction(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.forms and not self.obs.appointment:
            return self.appointment(check)
        return self.field_labels(check)

    def saas_home(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.h1 and (self.obs.high_intent or self.obs.demo):
            return self.ok(check, f"The sample states “{self.obs.h1}” and offers a next step.")
        return self.weak_value_prop(check)

    def signup_friction(self, check: Dict[str, Any]) -> Dict[str, Any]:
        account = [page for page in self.obs.pages if page["kind"] == "account"]
        if not account and not self.obs.forms:
            return self.observed(check, "No signup form was in the sample.")
        return self.field_labels(check)

    def plan_selection(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.pricing_urls:
            return self.observed(check, "Pricing URL(s): " + _join(self.obs.pricing_urls) + ". Plan selection was not clicked through.")
        return self.price_clarity(check)

    def ecom_nav(self, check: Dict[str, Any]) -> Dict[str, Any]:
        products = [page["url"] for page in self.obs.pages if page["kind"] == "product"]
        if products and self.obs.nav_labels:
            return self.ok(check, "Navigation labels and product URLs are both in the sample.")
        if products:
            return self.observed(check, "Product URLs were found. A category navigation label was not parsed.")
        return self.product_pages(check)

    def product_media(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.image_relevance(check)

    def promotions(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.price_clarity(check)

    def payment_methods(self, check: Dict[str, Any]) -> Dict[str, Any]:
        names = []
        blob = " ".join(page["text"].lower() for page in self.obs.pages)
        for name in ("visa", "mastercard", "paypal", "upi", "apple pay", "google pay", "invoice"):
            if name in blob:
                names.append(name)
        if names:
            return self.observed(check, "Payment names in the copy: " + _join(names) + ". A payment was not submitted.")
        if "ecommerce" in self.obs.detected_models or any(page["kind"] == "checkout" for page in self.obs.pages):
            return self.observed(check, "No card, wallet, or invoice name was found on the sampled checkout copy.")
        return self.na(check, "Payment methods were not applicable. No checkout was classified.")

    def delivery_estimates(self, check: Dict[str, Any]) -> Dict[str, Any]:
        blob = " ".join(page["text"].lower() for page in self.obs.pages)
        if any(token in blob for token in ("delivery", "arrives", "ships in", "business days")):
            return self.ok(check, "Delivery language was found. The estimate was not checked against an order.")
        if "ecommerce" in self.obs.detected_models:
            return self.observed(check, "No delivery estimate was found in the sample.")
        return self.na(check, "Delivery estimates were not applicable.")

    def tax_fees(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.hidden_fees(check)

    def cancellation_terms(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.refund_policy(check)

    def trial_terms(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.trial_vs_freemium(check)

    def support_access(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.support_availability(check)

    def company_info(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.business_identity(check)

    def reviews(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.testimonials(check)

    def visual_proof(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.customer_logos(check)

    def screenshots(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.image_relevance(check)

    def video_preview(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.videos:
            caption = f" {self.obs.captions} caption track(s) were found." if self.obs.captions else " No caption track was found."
            return self.observed(check, f"{self.obs.videos} video or iframe embed(s) were found.{caption} Playback was not run.")
        return self.observed(check, "No video or iframe embed was found.")

    def captions(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.videos:
            return self.na(check, "Captions were not applicable. No video was in the sample.")
        if self.obs.captions:
            return self.ok(check, f"{self.obs.captions} caption track(s) were found.")
        return self.fail(check, "A video or embed is present and no caption track was found.", priority="Low", effort="Low", action="Add captions or a transcript for the media that carries the offer.", stage="Content")

    def mobile_landing(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.viewport(check)

    def mobile_content(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.viewport(check)

    def mobile_pricing(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Price readability on a phone was not rendered.")

    def one_handed(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "One-handed reach was not tested on a device.")

    def sticky_cta(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Sticky positioning was not measured from static HTML.")

    def mobile_nav(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "The mobile menu was not opened. A viewport tag is not a menu test.")

    def layout_shift(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.field_cwv and self.obs.field_cwv.get("cls") is not None:
            return self.observed(check, f"Field CLS p75 is {self.obs.field_cwv['cls']}.", state="VERIFIED")
        return self.nt(check, "Layout shift was not measured. Missing image dimensions were not treated as a CLS score.")

    def render_blocking(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Render-blocking resources were not measured. This pass does not invent a Lighthouse run.")

    def media_weight(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Image and video weight were not measured.")

    def device_performance(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Performance was not compared across devices.")

    def interaction_feedback(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, f"{check['label']}: the control was not activated, so latency was not measured.")

    def cta_responsiveness(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.interaction_feedback(check)

    def form_latency(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.interaction_feedback(check)

    def checkout_latency(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.interaction_feedback(check)

    def loading_indicators(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Loading indicators were not observed.")

    def network_recovery(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Network failure was not simulated.")

    def focus_indicators(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Focus indicators were not inspected in a browser.")

    def screen_reader(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "A screen reader was not used. Label presence is not a screen-reader pass.")

    def dialog_behavior(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Dialog focus behavior was not tested.")

    def reduced_motion(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Reduced-motion support was not tested.")

    def error_identification(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Form errors were not triggered, so error identification was not observed.")

    def inline_validation(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.error_identification(check)

    def error_clarity(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.error_identification(check)

    def accessible_validation(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.error_identification(check)

    def submission_confirmation(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.confirmation_page(check)

    def multistep(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if any(form["multistep"] for form in self.obs.forms):
            return self.observed(check, "Multi-step markup was found. The steps were not completed.")
        if self.obs.forms:
            return self.observed(check, "No multi-step markup was found. A single-step form is not a defect by itself.")
        return self.observed(check, "No form was available.")

    def progress_indicators(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.multistep(check)

    def conditional_fields(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Conditional fields were not exercised.")

    def field_order(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Field order was not judged against a task.")

    def form_persistence(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Form values were not reloaded after a refresh.")

    def qualification_questions(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.forms:
            return self.observed(check, "No form questions were available to compare with a qualification rule.")
        return self.nt(check, "Form questions were counted. They were not compared with a sales qualification standard.")

    def demo_workflow(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.demo_booking(check)

    def response_expectations(self, check: Dict[str, Any]) -> Dict[str, Any]:
        blob = " ".join(page["text"].lower() for page in self.obs.pages)
        if any(token in blob for token in ("we'll reply", "we will reply", "response within", "hear back")):
            return self.ok(check, "The sample states that someone will reply. The promise was not timed.")
        return self.observed(check, "No response-time promise was found.")

    def registration(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.signup_friction(check)

    def password_rules(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Password rules were not submitted or rejected.")

    def social_login(self, check: Dict[str, Any]) -> Dict[str, Any]:
        blob = " ".join(page["text"].lower() for page in self.obs.pages)
        if any(token in blob for token in ("sign in with", "continue with google", "continue with apple")):
            return self.observed(check, "A social login phrase was found. The login was not completed.")
        return self.observed(check, "No social login phrase was found. It was not required.")

    def sso(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Single sign-on was not tested.")

    def password_reset(self, check: Dict[str, Any]) -> Dict[str, Any]:
        blob = " ".join(page["text"].lower() + " " + page["url"].lower() for page in self.obs.pages)
        if "forgot" in blob or "reset password" in blob:
            return self.observed(check, "A password-reset path is mentioned. It was not completed.")
        return self.nt(check, "Password reset was not found and was not executed.")

    def email_verification(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Email verification was not executed.")

    def otp(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "One-time passwords were not executed.")

    def auth_errors(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Authentication errors were not triggered.")

    def duplicate_accounts(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Duplicate accounts were not created.")

    def session_persistence(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Session persistence was not tested.")

    def privacy_risk(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.privacy(check)

    def financial_risk(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.price_clarity(check)

    def evidence_near_risk(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.missing_trust(check)

    def trust_near_action(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.missing_trust(check)

    def service_commitments(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.response_expectations(check)

    def reliability_concerns(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.proof_for_claims(check)

    def customer_problem(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if not self.obs.h1:
            return self.un(check, "The customer problem was not stated in an H1.")
        return self.inferred(check, f"The only problem or solution statement inspected is “{self.obs.h1}”. It was not confirmed with customers.")

    def proposed_solution(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.customer_problem(check)

    def primary_benefits(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.benefit_orientation(check)

    def usp(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.claim_specificity(check)

    def differentiation(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.competitor(check) if check["need"] == "competitor" else self.inferred(check, "Differentiation against a named competitor was not crawled. The headline was not treated as a unique claim.")

    def outcomes_copy(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.proof_for_claims(check)

    def audience_fit(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.audience(check)

    def audience_message(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.audience(check)

    def reasons_to_choose(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.proof_for_claims(check)

    def hesitation_reasons(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.faq_objections(check)

    def objection_copy(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.faq_objections(check)

    def feature_to_benefit(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Feature-to-benefit rewriting was not scored from a word list.")

    def jargon(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Jargon was not scored. A glossary was not requested from a customer.")

    def message_consistency(self, check: Dict[str, Any]) -> Dict[str, Any]:
        headlines = [page["h1"] for page in self.obs.pages if page["h1"]]
        if len(set(headlines)) > 1:
            return self.observed(check, "Distinct H1s in the sample: " + _join(headlines) + ". They were not marked inconsistent.")
        if headlines:
            return self.ok(check, f"One H1 was repeated or only one page had an H1: “{headlines[0]}”.")
        return self.observed(check, "No H1s were available to compare.")

    def reassurance_copy(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.refund_policy(check)

    def cta_placement(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.above_fold_limit(check)

    def cta_repetition(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if len(self.obs.ctas) > 1:
            return self.observed(check, f"The sample contains {len(self.obs.ctas)} CTA labels. Repetition was not judged as too much.")
        return self.cta_presence(check)

    def cta_contrast(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.contrast(check)

    def cta_consistency(self, check: Dict[str, Any]) -> Dict[str, Any]:
        labels = list(dict.fromkeys(cta["text"] for cta in self.obs.ctas))
        if not labels:
            return self.cta_presence(check)
        return self.observed(check, "Distinct CTA labels: " + _join(labels) + ".")

    def cta_transition(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.cta_destination(check)

    def cta_states(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.processing_states(check)

    def button_affordance(self, check: Dict[str, Any]) -> Dict[str, Any]:
        buttons = [cta for cta in self.obs.ctas if cta["tag"] in ("button", "input", "a")]
        if buttons:
            return self.ok(check, f"{len(buttons)} button or button-styled control(s) were found.")
        return self.cta_presence(check)

    def competing_actions(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if len(self.obs.high_intent) > 3:
            return self.observed(check, f"{len(self.obs.high_intent)} high-intent labels were found. Whether they compete was not tested.")
        return self.observed(check, "Competing actions were not inferred from the count of links.")

    def visual_hierarchy_limit(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.above_fold_limit(check)

    def spacing_limit(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, f"{check['label']}: spacing was not measured from rendered boxes.")

    def clutter(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.spacing_limit(check)

    def content_density(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.page_length(check)

    def design_consistency(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Design consistency across templates was not reviewed by a person.")

    def cognitive_load_limit(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.psych_limit(check)

    def visual_distraction(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Visual distraction was not judged from a screenshot.")

    def content_cta_relation(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.h1 and self.obs.ctas:
            return self.observed(check, f"The H1 “{self.obs.h1}” and {len(self.obs.ctas)} CTA label(s) are both present. Their relationship was not user-tested.")
        return self.weak_value_prop(check)

    def feature_descriptions(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.page_length(check)

    def demonstrations(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.video_preview(check)

    def specifications(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Specifications were not checked against a required field list.")

    def compatibility(self, check: Dict[str, Any]) -> Dict[str, Any]:
        blob = " ".join(page["text"].lower() for page in self.obs.pages)
        if any(token in blob for token in ("compatible", "works with", "integrates with", "requires")):
            return self.ok(check, "Compatibility or requirement language was found.")
        return self.observed(check, "No compatibility statement was found.")

    def service_process(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.journey_stage(check)

    def deliverables(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.products_services(check)

    def limitations(self, check: Dict[str, Any]) -> Dict[str, Any]:
        blob = " ".join(page["text"].lower() for page in self.obs.pages)
        if any(token in blob for token in ("does not include", "limitation", "not included", "except")):
            return self.ok(check, "A limitation or exclusion phrase was found.")
        return self.observed(check, "No limitation or exclusion was stated in the sample.")

    def image_usefulness(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.image_relevance(check)

    def video_value(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.video_preview(check)

    def demo_discoverability(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.video_preview(check)

    def video_loading(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Video loading was not played.")

    def interactive_demo(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "An interactive demo was not operated.")

    def embedded_performance(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.video_loading(check)

    def media_placement(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Media placement relative to a decision was not measured in the viewport.")

    def mobile_media(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Media was not played on a phone.")

    def media_distraction(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Media was not judged as a distraction.")

    def pricing_faq(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.faq_objections(check)

    def cost_to_value(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.inferred(check, "Cost-to-value was not calculated. A price next to a headline is not a value model.")

    def plan_comparison(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.plan_selection(check)

    def feature_limits(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.limitations(check)

    def discounts(self, check: Dict[str, Any]) -> Dict[str, Any]:
        blob = " ".join(page["text"].lower() for page in self.obs.pages)
        if any(token in blob for token in ("discount", "save ", "% off", "coupon")):
            return self.observed(check, "A discount or coupon phrase was found. Eligibility was not validated.")
        return self.observed(check, "No discount phrase was found.")

    def renewal_terms(self, check: Dict[str, Any]) -> Dict[str, Any]:
        blob = " ".join(page["text"].lower() for page in self.obs.pages)
        if "renew" in blob:
            return self.ok(check, "Renewal language was found.")
        if "saas" in self.obs.detected_models:
            return self.observed(check, "No renewal condition was found on the SaaS sample.")
        return self.na(check, "Renewal terms were not applicable.")

    def fee_structure(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.billing_frequency(check)

    def pricing_concerns(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.price_clarity(check)

    def risk_uncertainty(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.refund_policy(check)

    def implementation_concerns(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.service_process(check)

    def delivery_timelines(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.delivery_estimates(check)

    def comparison_criteria(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Comparison criteria were not taken from a buyer interview.")

    def sales_escalation(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.contact_info(check)

    def intent_match(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.search_intent_match(check)

    def content_order(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Content order was not tested with a reader. Benefits-before-detail was not scored from headings alone.")

    def benefits_before_detail(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.content_order(check)

    def feature_comparisons(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "A feature comparison table was not required and was not judged for fairness.")

    def customer_outcomes(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.proof_for_claims(check)

    def use_cases(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.industry_pages(check)

    def appeal_balance(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Emotional and rational appeal were not scored.")

    def redundant_content(self, check: Dict[str, Any]) -> Dict[str, Any]:
        titles = [page["title"] for page in self.obs.pages if page["title"]]
        duplicates = len(titles) - len(set(titles))
        if duplicates > 0:
            return self.observed(check, f"{duplicates} duplicate title(s) were in the sample. Redundant persuasion was not judged.")
        return self.observed(check, "Duplicate titles were not found. Redundant paragraphs were not scored.")

    def important_pages(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nav_clarity(check)

    def discoverability(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nav_clarity(check)

    def nav_organization(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nav_clarity(check)

    def extra_nav_steps(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "The number of steps a person needs was not walked.")

    def search_quality(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Internal search results were not queried.")

    def journey_friction(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.high_friction(check)

    def inventory(self, check: Dict[str, Any]) -> Dict[str, Any]:
        blob = " ".join(page["text"].lower() for page in self.obs.pages)
        if any(token in blob for token in ("in stock", "out of stock", "available")):
            return self.observed(check, "Stock language was found. Inventory was not queried.")
        return self.observed(check, "No stock status was found on the sampled product copy.")

    def variants(self, check: Dict[str, Any]) -> Dict[str, Any]:
        blob = " ".join(page["text"].lower() for page in self.obs.pages)
        if any(token in blob for token in ("size", "color", "variant")):
            return self.observed(check, "Variant language was found. A variant was not selected.")
        return self.observed(check, "No variant selector was identified.")

    def cart_visibility(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.cart_checkout_pair(check)

    def cart_editing(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Cart editing was not performed.")

    def account_wall(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.guest_checkout(check)

    def checkout_steps(self, check: Dict[str, Any]) -> Dict[str, Any]:
        pages = [page["url"] for page in self.obs.pages if page["kind"] == "checkout"]
        if not pages:
            return self.observed(check, "No checkout URL was sampled, so the step count is unknown.")
        return self.observed(check, f"{len(pages)} checkout URL(s) were sampled. The step count inside the flow was not walked.")

    def shipping_disclosure(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.shipping_returns(check)

    def coupons(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.discounts(check)

    def address_entry(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Address entry was not completed.")

    def order_summary(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "An order summary was not rendered in a checkout session.")

    def checkout_validation(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Checkout validation was not triggered.")

    def abandonment_recovery(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.recovery_opportunities(check)

    def cart_recovery(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.recovery_opportunities(check)

    def payment_form(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.payment_security(check)

    def payment_auth(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Payment authentication challenges were not triggered.")

    def upgrade_paths(self, check: Dict[str, Any]) -> Dict[str, Any]:
        blob = " ".join(page["text"].lower() for page in self.obs.pages)
        if any(token in blob for token in ("upgrade", "downgrade")):
            return self.observed(check, "Upgrade or downgrade language was found. The path was not taken.")
        return self.observed(check, "No upgrade or downgrade path was named.")

    def lead_magnets(self, check: Dict[str, Any]) -> Dict[str, Any]:
        blob = " ".join(page["text"].lower() for page in self.obs.pages)
        if any(token in blob for token in ("download", "guide", "white paper", "checklist")):
            return self.observed(check, "A downloadable or guide is mentioned. Completion was not measured.")
        return self.observed(check, "No lead magnet was named.")

    def availability(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.appointment(check)

    def cross_sell(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Cross-sell and upsell relevance were not judged, and no attach rate was measured.")

    def upsell(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.cross_sell(check)

    def repeat_conversion(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Repeat conversion was not measured.")

    def onboarding_handoff(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "The post-conversion handoff was not followed.")

    def receipts(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "A receipt was not generated.")

    def account_setup(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.signup_friction(check)

    def fulfillment_updates(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Fulfillment messages were not inspected.")

    def empty_states(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Product empty states were not opened.")

    def first_use(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "First-use guidance inside a product was not opened.")

    def product_education(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "In-product education was not reviewed.")

    def feature_discovery(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Feature discovery after signup was not observed.")

    def setup_friction(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Setup after signup was not performed.")

    def mobile_first_limit(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Mobile-first behavior was not established from a desktop HTML sample.")

    def responsive_forms(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.forms and not self.obs.viewport_missing:
            return self.observed(check, "Forms exist and the sampled pages have a viewport tag. The form was not used on a phone.")
        return self.viewport(check)

    def mobile_checkout(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Checkout was not completed on a phone.")

    def mobile_performance(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.cwv(check)

    def bad_redirects(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.technical_failures(check)

    def broken_checkout(self, check: Dict[str, Any]) -> Dict[str, Any]:
        errors = [page["url"] for page in self.obs.pages if page["kind"] == "checkout" and page["status"] is not None and page["status"] >= 400]
        if errors:
            return self.fail(check, "Checkout URLs with an error status: " + _join(errors) + ".", priority="High", effort="High", action="Restore the checkout response before changing the offer.", stage="Checkout")
        return self.observed(check, "No broken checkout response was in the sample. The flow was not purchased.")

    def confirmation_failures(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.confirmation_page(check)

    def consent_interference(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.consent_gap(check)

    def consent_aware(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.consent_gap(check)

    def failed_apis(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "API requests during the conversion flow were not captured.")

    def session_expiry(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Session expiry was not waited out.")

    def cross_domain_failures(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Cross-domain conversion steps were not followed.")

    def blocked_integrations(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Third-party integrations were not blocked or unblocked in a browser.")

    def browser_defects(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "The sample was not repeated across browsers.")

    def accessible_auth(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Authentication was not completed with an assistive technology.")

    def alternative_input(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Voice, switch, or other alternative input was not used.")

    def instrumentation_limits(self, check: Dict[str, Any]) -> Dict[str, Any]:
        parts = [self.obs.analytics.get("notice") or ""]
        if self.obs.analytics.get("state") == "MEASURED":
            parts = ["A GA4 property total was returned. Event names, deduplication, and revenue were not validated."]
        return self.observed(check, " ".join(part for part in parts if part), state="VERIFIED" if self.obs.analytics.get("state") == "MEASURED" else "DATA_UNAVAILABLE")

    def event_definitions(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.analytics.get("key_events_present"):
            return self.observed(check, "Key events were returned as a property total. The event name and its deduplication were not inspected.", state="VERIFIED")
        return self.un(check, "Conversion event definitions were not validated. " + self.obs.analytics.get("notice", ""))

    def forecast_audience(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.analytics.get("sessions") is not None:
            return self.observed(check, f"GA4 sessions in the window: {self.obs.analytics['sessions']}. This is not an eligible-audience forecast.", state="VERIFIED")
        return self.un(check, "Eligible audience size was not available.")

    def activation(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, f"{check['label']}: product analytics after signup were not connected.")

    def time_to_value(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.activation(check)

    def onboarding_completion(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.activation(check)

    def trial_to_paid(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Trial-to-paid conversion was not measured. Trial language on a page is not a cohort.")

    def early_churn(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Churn was not measured.")

    def repeat_purchase(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Repeat purchase was not measured.")

    def renewal(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Renewal was not measured from a subscription ledger.")

    def reengagement(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Re-engagement was not measured.")

    def cohorts(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Retention cohorts were not supplied.")

    def expansion(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Expansion revenue was not connected.")

    def lead_to_customer(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Lead-to-customer conversion was not calculated. No customer count was tied to a lead cohort.")

    def gross_profit(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Gross profit was not calculated. Margin was not supplied.")

    def cac(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Customer acquisition cost was not calculated. Spend and new customers were not both supplied.")

    def ltv(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Customer lifetime value was not calculated.")

    def margin(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.gross_profit(check)

    def pipeline(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Pipeline and closed-won revenue were not connected.")

    def refund_rate(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Refund and cancellation rates were not connected.")

    def repeat_purchase_rate(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.repeat_purchase(check)

    def churn(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.early_churn(check)

    def discount_impact(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Discount impact on profit was not calculated.")

    def contribution_margin(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.gross_profit(check)

    def incremental_profit(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Incremental profit was not calculated. No experiment result and no cost figure were supplied.")

    def sales_cycle(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Sales cycle length was not supplied by the business.")

    def constraints(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Operational capacity was not supplied.")

    def lead_criteria(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Lead qualification criteria were not supplied by CRM or by the business.")

    def personas(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "No persona research was attached. The audience field, when present, is not a persona study.")

    def awareness_stage(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Buyer awareness stage was not researched.")

    def purchase_readiness(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Purchase readiness was not researched.")

    def b2b_firmographics(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Industry and company size were not measured for visitors.")

    def lifecycle_stage(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Customer lifecycle stage was not available from a ledger.")

    def segment_unavailable(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, f"{check['label']}: this segment was not returned. The crawl is not a visitor segment, and a missing segment was not filled with zero.")

    def high_traffic_low_conversion(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "High-traffic, low-conversion pages need both traffic and a conversion field. They were not both present, and neither was invented.")

    def high_value_abandon(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "High-value abandonment was not measured.")

    def unqualified_leads(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.metric_qualified_lead(check)

    def payment_failures(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Payment failures were not returned by a gateway or by analytics.")

    def funnel_dropoff(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.metric_funnel_completion(check)

    def conversion_baselines(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.metric_conversion_rate(check)

    def stage_rates(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.metric_funnel_completion(check)

    def funnel_events(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, f"{check['label']}: stage entry and exit events were not in the connected payload.")

    def stage_timing(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Time between stages was not measured.")

    def repeated_attempts(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Repeated attempts were not measured.")

    def abandonment_patterns(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Abandonment patterns were not measured from an event stream.")

    def resumed_funnels(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Returning users who resume a funnel were not identified.")

    def channel_leakage(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Channel-specific leakage was not measured.")

    def value_leakage(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "High-value and low-value losses were not separated. No order value was connected.")

    def exit_pages(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, f"{check['label']}: exit and abandonment events were not connected.")

    def form_abandon(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.exit_pages(check)

    def cart_abandon_event(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.metric_cart_abandon(check)

    def checkout_abandon(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.metric_checkout(check)

    def trial_abandon(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.trial_to_paid(check)

    def signup_abandon(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Signup abandonment was not measured.")

    def pricing_exits(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Pricing-page exits were not measured.")

    def failed_onboarding(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.activation(check)

    def repeat_without_conversion(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Repeat visits without conversion were not measured.")

    def return_to_purchase(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Return-to-purchase behavior was not measured.")

    def post_conversion_dropoff(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Post-conversion drop-off was not measured.")

    def referral_quality(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Referral conversion quality was not returned.")

    def branded_split(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Branded and non-branded traffic were not separated.")

    def low_engagement_entries(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.metric_landing_engagement(check)

    def cta_completion(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "CTA click-to-completion was not measured. A label in the HTML is not a click.")

    def cta_events(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.cta_completion(check)

    def scroll_events(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.behavior_not_clicks(check)

    def field_progression(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Form field progression was not instrumented.")

    def error_events(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Error events were not returned.")

    def checkout_events(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Checkout events were not returned.")

    def repeated_patterns(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.behavior_not_clicks(check)

    def analytics_sessions(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.analytics.get("sessions") is None:
            return self.un(check, self.obs.analytics.get("notice") or "Sessions were not retrieved.")
        return self.observed(check, f"GA4 sessions: {self.obs.analytics['sessions']} over {self.obs.analytics.get('period') or 'the connected period'}.", state="VERIFIED")

    def form_events(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.metric_form_completion(check)

    def validation_events(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Form validation errors were not collected as events.")

    def signup_events(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Signup events were not validated.")

    def payment_events(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.payment_failures(check)

    def purchase_events(self, check: Dict[str, Any]) -> Dict[str, Any]:
        if self.obs.analytics.get("revenue") is None and self.obs.analytics.get("orders") is None:
            return self.un(check, "Purchase and revenue events were not present. A key-event total was not relabeled as revenue.")
        return self.metric_rpv(check)

    def deduplication(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Event deduplication was not audited. Totals were not assumed to be unique people.")

    def event_parameters(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Event parameters were not validated.")

    def cross_domain_tracking(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.identity_gap(check)

    def backend_reconciliation(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "CRM and backend totals were not reconciled to analytics.")

    def channel_paid(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, f"{check['label']}: this channel was not broken out in the connected payload.")

    def channel_social(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.channel_paid(check)

    def channel_email(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.channel_paid(check)

    def channel_referral(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.channel_paid(check)

    def channel_direct(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.channel_paid(check)

    def assisted(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Assisted conversions were not returned.")

    def touch_models(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "First-touch and last-touch reports were not supplied. A single total was not assigned to a touch model.")

    def multitouch(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Multi-touch attribution was not calculated.")

    def campaign_consistency(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Campaign parameter consistency was not audited.")

    def offline_attribution(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Offline sales were not joined to a campaign.")

    def channel_mix(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Channel mix effects were not modeled.")

    def missing_success_events(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.event_definitions(check)

    def registration_recovery(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.signup_abandon(check)

    def mobile_errors(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.metric_device_split(check)

    def gateway_failures(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.payment_failures(check)

    def declined_payments(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.payment_failures(check)

    def payment_retry(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Payment retry was not observed.")

    def payment_analytics(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.payment_failures(check)

    def contact_completion(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.metric_form_completion(check)

    def crm_handoff(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "CRM handoff was not connected.")

    def lead_quality(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.metric_qualified_lead(check)

    def sales_speed(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Sales response time was not measured.")

    def mql_sql(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Marketing-qualified to sales-qualified conversion was not connected.")

    def sql_customer(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.lead_to_customer(check)

    def lead_scoring(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Lead scoring was not validated against closed customers.")

    def duplicate_leads(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Duplicate leads were not counted in a CRM.")

    def lead_routing(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.crm_handoff(check)

    def followup_timing(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.sales_speed(check)

    def sales_acceptance(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Sales acceptance rate was not connected.")

    def scheduling_conflicts(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Scheduling conflicts were not created in a booking tool.")

    def reminders(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Confirmation and reminder messages were not inspected.")

    def no_show(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "No-show rate was not measured.")

    def lead_to_appointment(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Lead-to-appointment conversion was not measured.")

    def appointment_to_customer(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.un(check, "Appointment-to-customer conversion was not measured.")

    def expectation_alignment(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Customer satisfaction after conversion was not surveyed.")

    def trust_by_segment(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Trust was not compared across audience segments.")

    def inconsistent_info(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.inconsistent_offers(check)

    def progressive_profiling(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, "Progressive profiling was not observed across visits.")

    def experiment_absent(self, check: Dict[str, Any]) -> Dict[str, Any]:
        return self.nt(check, f"{check['label']}: no experiment was supplied. A higher observed rate would not be treated as a win.")


_RULES = {
    name: name
    for name in dir(_Rules)
    if not name.startswith("_") and name not in {"applies", "na", "un", "nt", "observed", "inferred", "ok", "fail", "by_need", "rate_line"}
}


def _section_status(checks: Sequence[CroCheckRecord]) -> str:
    outcomes = {item.outcome for item in checks}
    if "fail" in outcomes:
        return "GAP"
    if outcomes <= {"not_applicable"}:
        return "NOT_APPLICABLE"
    if outcomes <= {"unmeasured"}:
        return "DATA_UNAVAILABLE"
    if outcomes <= {"not_tested"}:
        return "NOT_TESTED"
    if outcomes & {"unmeasured", "not_tested"}:
        return "PARTIAL"
    return "REVIEWED"


def _metrics(obs: _Obs) -> List[CroMetricResult]:
    analytics = obs.analytics
    window = analytics.get("period")
    conversion = rate(analytics.get("unique_converters"), analytics.get("eligible_users"))
    key_event_rate = rate(analytics.get("key_events"), analytics.get("sessions")) if analytics.get("key_events_present") else None
    # Revenue per visitor requires an eligible-visitor denominator; sessions are not people.
    revenue_per_visitor = rate(analytics.get("revenue"), analytics.get("eligible_visitors"))
    aov = rate(analytics.get("revenue"), analytics.get("orders"))
    values = {
        "Conversion rate": (
            conversion,
            "unique converters",
            "eligible users",
            "A conversion rate requires unique converters and an explicitly defined eligible-user denominator.",
        ),
        "Key-event rate per session": (
            key_event_rate,
            "key events",
            "sessions",
            "This is an event-count-per-session ratio, not a unique-user conversion rate; it can exceed 100%.",
        ),
        "Revenue per visitor": (
            revenue_per_visitor,
            "attributed revenue",
            "eligible visitors",
            "Shown only when attributed revenue and an explicitly defined eligible-visitor denominator were both present. Sessions are not substituted for visitors.",
        ),
        "Average order value": (aov, "net sales", "orders", "Shown only when both net sales and completed orders were present."),
    }
    results = []
    for spec in METRIC_CATALOG:
        measured = values.get(spec["metric"])
        if measured and measured[0] is not None:
            value, numerator, denominator, note = measured
            results.append(CroMetricResult(
                metric=spec["metric"],
                formula=spec["formula"],
                status="MEASURED",
                value=value,
                display=f"{value:.4f}",
                denominator=denominator,
                numerator=numerator,
                window=window,
                note=note,
            ))
            continue
        reason = (
            "sessions are not substituted for visitors. The numerator and denominator "
            "were not both available, so zero was not substituted and no lift was assumed."
        )
        if spec["metric"] == "Conversion rate":
            reason = "Unique converters and eligible users were not both returned by GA4. Key events ÷ sessions is not substituted for conversion rate."
        results.append(CroMetricResult(
            metric=spec["metric"],
            formula=spec["formula"],
            status="DATA_UNAVAILABLE",
            value=None,
            display="Not measured",
            denominator=None,
            numerator=None,
            window=window if analytics.get("state") == "MEASURED" else None,
            note=reason,
        ))
    return results


def _dimensions(checks: Sequence[Dict[str, Any]], obs: _Obs) -> List[CroDimensionScore]:
    passed = sum(1 for item in checks if item["outcome"] == "pass")
    failed = sum(1 for item in checks if item["outcome"] == "fail")
    excluded = len(checks) - passed - failed
    if passed + failed == 0:
        experience = CroDimensionScore(
            id="experience",
            name="Experience quality",
            status="UNMEASURED",
            score=None,
            note="No pass/fail observation was available. Unmeasured checks were not scored as zero.",
            excluded_checks=excluded,
        )
    else:
        experience = CroDimensionScore(
            id="experience",
            name="Experience quality",
            status="PARTIAL" if excluded else "MEASURED",
            score=round(100 * passed / (passed + failed), 1),
            note=(
                f"{passed} passed and {failed} failed among checks that could be observed on the sample. "
                f"{excluded} checks were excluded. This is not a conversion rate and it is not full-taxonomy coverage."
            ),
            passed_checks=passed,
            failed_checks=failed,
            excluded_checks=excluded,
        )
    funnel_note = "Stage completion, form completion, and checkout completion were not measured."
    if obs.analytics.get("key_events_present"):
        funnel_note = "A property key-event rate is available in the metrics. It is not a funnel score."
    funnel = CroDimensionScore(id="funnel", name="Funnel effectiveness", status="UNMEASURED", score=None, note=funnel_note)
    if obs.analytics.get("state") == "MEASURED":
        measurement = CroDimensionScore(
            id="measurement",
            name="Measurement reliability",
            status="PARTIAL",
            score=None,
            note="GA4 returned a property total. Event names, deduplication, funnel events, and revenue were not validated, so no reliability score is published.",
        )
    else:
        measurement = CroDimensionScore(
            id="measurement",
            name="Measurement reliability",
            status="UNMEASURED",
            score=None,
            note=obs.analytics.get("notice") or "Analytics was not connected.",
        )
    outcome_bits = []
    if obs.analytics.get("revenue") is not None:
        outcome_bits.append("revenue")
    if obs.analytics.get("orders") is not None:
        outcome_bits.append("orders")
    outcomes = CroDimensionScore(
        id="outcomes",
        name="Business outcomes",
        status="PARTIAL" if outcome_bits else "UNMEASURED",
        score=None,
        note=(
            "Connected economics fields: " + ", ".join(outcome_bits) + ". A blended business score was not published."
            if outcome_bits
            else "Qualified leads, revenue, margin, acquisition cost, and lifetime value were not connected. No business-outcome score was published."
        ),
    )
    return [experience, funnel, measurement, outcomes]


def _findings(failed: List[Dict[str, Any]], obs: _Obs) -> List[CroFindingRecord]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for item in failed:
        current = grouped.get(item["key"])
        if current is None or ("High", "Medium", "Low").index(item.get("priority", "Low")) < ("High", "Medium", "Low").index(current.get("priority", "Low")):
            grouped[item["key"]] = item
    ordered = sorted(grouped.values(), key=lambda item: (("High", "Medium", "Low").index(item.get("priority", "Low")), item["section"]))
    scope = f"Inspected sample of {obs.sample_size} page(s). Not sitewide."
    if obs.analytics.get("sessions") is not None:
        affected = f"The property recorded {obs.analytics['sessions']} sessions in {obs.analytics.get('period') or 'the connected period'}. That is not the number of people affected by this finding."
    else:
        affected = f"Not counted. The sample has {obs.sample_size} page(s). Visitor counts were not connected."
    records = []
    for index, item in enumerate(ordered, start=1):
        records.append(CroFindingRecord(
            finding_id=f"CRO-{index:03d}",
            priority=item.get("priority", "Medium"),
            finding=item["summary"],
            evidence="; ".join(
                [str(value) for value in (item.get("evidence") or []) if value]
                + ([item["summary"]] if item.get("summary") else [])
                + (["Evidence URL: " + item["page_url"]] if item.get("page_url") else [])
            ),
            observed_scope=scope,
            hypothesis=item.get("action", "Change the observed defect.") + " This is a hypothesis. The inspected sample does not show that the change will raise conversions.",
            recommended_action=item.get("action", "Change the observed defect and keep the current experience as the control."),
            primary_metric="Completed conversions per eligible visitor",
            owner=item.get("owner") or "Product",
            evidence_state=item["evidence_state"],
            section=item["section"],
            specialist=item["specialist"],
            effort=item.get("effort", "Medium"),
            confidence="Medium. The defect was seen on the sample. The effect on conversion was not measured.",
            funnel_stage=item.get("stage", "Conversion"),
            affected_scope=affected,
            negative_risk="The change can reduce qualified actions, add friction elsewhere, or conflict with an existing offer. Keep the current experience as the control when a test is possible.",
        ))
    return records


def _roadmap(findings: Sequence[CroFindingRecord]) -> Dict[str, List[str]]:
    buckets = {"days_30": [], "days_60": [], "days_90": []}
    for finding in findings:
        line = f"{finding.finding_id} ({finding.priority}, {finding.effort} effort): {finding.recommended_action}"
        if finding.priority == "High" and finding.effort == "Low":
            buckets["days_30"].append(line)
        elif finding.priority == "Low":
            buckets["days_90"].append(line)
        else:
            buckets["days_60"].append(line)
    for key, values in buckets.items():
        if not values:
            buckets[key] = ["No hypothesis was placed in this window."]
    return buckets


def _appendices(obs: _Obs, findings: Sequence[CroFindingRecord]) -> List[CroAppendix]:
    pages = obs.pages
    inventory = "; ".join(f"{page['url']} ({page['kind']}, sample)" for page in pages[:12]) or "No pages were stored."
    rate = _Rules(obs).rate_line() or "No conversion definition was measured."
    summaries = {
        "A": f"Model: {obs.model_label}. {obs.model_basis} Audience: {obs.profile_audience or 'not stated'}.",
        "B": "Primary actions are observed labels, not a confirmed goal. " + rate,
        "C": "Stages are inferred from URL types. Event names were not measured.",
        "D": inventory,
        "E": obs.analytics.get("notice") or "Analytics status was not recorded.",
        "F": "No usability test, survey, or interview was attached.",
        "G": "No experiment was registered. No winner is declared.",
        "H": "Technical evidence is limited to the sampled responses, forms, and links. Screenshots were not stored by this pass.",
        "I": "Device, channel, and new-versus-returning segments were not returned as conversion splits.",
        "J": "No revenue, margin, acquisition cost, or lifetime-value assumption was entered. No forecast was published.",
        "K": f"{len(findings)} finding(s) are open with status Needs validation." if findings else "No experience defect met the evidence bar for a finding.",
        "L": obs.sample_note + " " + PRINCIPLE,
        "M": "No implemented change or experiment outcome was supplied for this run.",
        "N": "Consent text may be present in the sample. Data retention, access control, and a review of lawful recording were not audited.",
    }
    statuses = {
        "A": "INFERRED" if obs.model_known else "DATA_UNAVAILABLE",
        "B": "VERIFIED" if rate.startswith(str(obs.analytics.get("key_events"))) else "DATA_UNAVAILABLE",
        "C": "INFERRED" if pages else "DATA_UNAVAILABLE",
        "D": "SAMPLE_VERIFIED" if pages else "DATA_UNAVAILABLE",
        "E": "VERIFIED" if obs.analytics.get("state") == "MEASURED" else "DATA_UNAVAILABLE",
        "F": "NOT_TESTED",
        "G": "NOT_TESTED",
        "H": "SAMPLE_VERIFIED" if pages else "NOT_TESTED",
        "I": "DATA_UNAVAILABLE",
        "J": "DATA_UNAVAILABLE",
        "K": "SAMPLE_VERIFIED",
        "L": "SAMPLE_VERIFIED",
        "M": "NOT_TESTED",
        "N": "NOT_TESTED",
    }
    return [
        CroAppendix(id=item["id"], title=item["title"], contents=item["contents"], status=statuses[item["id"]], summary=summaries[item["id"]])
        for item in APPENDICES
    ]


def _specialists(checks: Sequence[Dict[str, Any]]) -> List[CroSpecialistRollup]:
    rollups = []
    for spec in SPECIALISTS:
        owned = [item for item in checks if item["specialist"] == spec["id"]]
        rollups.append(CroSpecialistRollup(
            id=spec["id"],
            name=spec["name"],
            responsibility=spec["responsibility"],
            checks=len(owned),
            failed=sum(1 for item in owned if item["outcome"] == "fail"),
            unmeasured=sum(1 for item in owned if item["evidence_state"] in ("DATA_UNAVAILABLE", "NOT_TESTED")),
        ))
    return rollups


def build_cro_intelligence(
    pages: Optional[Sequence[Any]] = None,
    raw_html_map: Optional[Dict[str, str]] = None,
    business_profile: Any = None,
    analytics: Any = None,
    search_console: Any = None,
    wcag: Any = None,
    competitor_domains: Optional[Sequence[str]] = None,
    discovered_urls: Optional[int] = None,
) -> CroIntelligenceReport:
    """Build the CRO audit from a page sample and optional measured analytics."""
    source_pages = list(pages or [])
    rendered_page_count = sum(
        1
        for page in source_pages
        if _get(page, "rendered") is True
        and bool(_get(page, "rendered_dom") or _get(page, "html"))
    )
    rendered_dom_status = (
        "RENDERED_DOM_VERIFIED_FOR_SAMPLE"
        if source_pages and rendered_page_count == len(source_pages)
        else "PARTIAL_RENDERED_DOM_SAMPLE"
        if rendered_page_count > 0
        else "NOT_VERIFIED_BY_CRO_ENGINE"
    )
    obs = _observe(
        source_pages,
        raw_html_map,
        business_profile,
        analytics,
        search_console,
        wcag,
        competitor_domains,
        discovered_urls,
    )
    rules = _Rules(obs)
    resolved: List[Dict[str, Any]] = []
    for section in catalog():
        for check in section["checks"]:
            if not rules.applies(check):
                resolved.append(rules.na(check, f"{check['label']} does not apply. The sample was classified as {obs.model_label}."))
                continue
            if obs.sample_size == 0 and check["need"] == "crawl":
                resolved.append(rules.un(check, f"{check['label']} was not inspected. No crawled pages were available."))
                continue
            method_name = _RULES.get(check["key"])
            if method_name:
                resolved.append(getattr(rules, method_name)(check))
            else:
                resolved.append(rules.by_need(check))
    findings = _findings([item for item in resolved if item["outcome"] == "fail"], obs)
    sections: List[CroSectionRecord] = []
    for section in catalog():
        owned = [CroCheckRecord(**{key: item[key] for key in CroCheckRecord.model_fields}) for item in resolved if item["section"] == section["number"]]
        sections.append(CroSectionRecord(
            number=f"{section['number']:02d}",
            part=section["part"],
            title=section["title"],
            specialist=section["specialist"],
            status=_section_status(owned),
            checks=owned,
        ))
    return CroIntelligenceReport(
        scope_note=obs.sample_note,
        business_model=obs.model_label,
        model_basis=obs.model_basis,
        sample_size=obs.sample_size,
        discovered_urls=obs.discovered,
        scoring_calibration={
            "status": "NOT_BENCHMARK_CALIBRATED",
            "basis": "Experience quality is a transparent pass/fail ratio over checks observed on this sample, not a predicted conversion rate or industry percentile.",
            "priority_calibration": "RULE_BASED_NOT_OUTCOME_CALIBRATED",
            "experiment_outcomes_used": False,
            "note": "No validated benchmark corpus, historical remediation outcomes, or randomized experiment outcomes were supplied to calibrate score-to-business-impact predictions.",
        },
        coverage={
            "status": (
                "NO_PAGES" if obs.sample_size == 0
                else "DISCOVERY_COUNT_UNAVAILABLE" if obs.discovered is None or obs.discovered <= 0
                else "INCONSISTENT_COUNTS" if obs.sample_size > obs.discovered
                else "PARTIAL_SAMPLE" if obs.sample_size < obs.discovered
                else "DISCOVERED_SET_INSPECTED"
            ),
            "inspected_pages": obs.sample_size,
            "discovered_urls": obs.discovered,
            "sample_coverage_pct": (
                round(100 * obs.sample_size / obs.discovered, 1)
                if isinstance(obs.discovered, int) and not isinstance(obs.discovered, bool)
                and obs.discovered > 0 and obs.sample_size <= obs.discovered
                else None
            ),
            "rendered_dom_status": rendered_dom_status,
            "rendered_pages": rendered_page_count,
            "journey_execution_status": "NOT_EXECUTED",
            "note": (
                "The percentage compares inspected pages with the supplied discovery total only. "
                "It does not prove every URL was discovered, that JavaScript-rendered DOM was inspected, "
                "or that forms, checkout, and multi-step journeys were executed."
            ),
        },
        dimensions=_dimensions(resolved, obs),
        metrics=_metrics(obs),
        sections=sections,
        findings=findings,
        roadmap=_roadmap(findings),
        appendices=_appendices(obs, findings),
        specialists=_specialists(resolved),
    )


def build_from_executive_report(report: Any) -> CroIntelligenceReport:
    """Rebuild the CRO audit from a sealed report. Stored pages win over a stale snapshot."""
    manifest = getattr(report, "crawl_manifest", None)
    pages = list(getattr(manifest, "pages", None) or [])
    performance = getattr(report, "google_performance", None) or {}
    if not isinstance(performance, dict):
        performance = {}
    domains = []
    parity = getattr(report, "competitor_seo_parity", None)
    for competitor in getattr(parity, "competitors", None) or []:
        if not getattr(competitor, "is_target", False) and getattr(competitor, "domain", None):
            domains.append(competitor.domain)
    discovered = getattr(manifest, "total_pages_discovered", None) if manifest is not None else None
    if pages:
        return build_cro_intelligence(
            pages=pages,
            business_profile=getattr(report, "business_profile", None),
            analytics=performance.get("analytics"),
            search_console=performance.get("search_console"),
            wcag=getattr(report, "wcag_audit", None),
            competitor_domains=domains,
            discovered_urls=discovered,
        )
    stored = getattr(getattr(report, "cro_audit", None), "intelligence", None)
    if isinstance(stored, dict) and stored.get("sections"):
        return CroIntelligenceReport.model_validate(stored)
    return build_cro_intelligence(pages=[])
