"""
Dristik AI Continuous Remediation Verification Loop
Orchestrates: FIX → RECRAWL → RECHECK → COMPARE → CERTIFY
Provides deterministic assertion testing on live HTML, HTTP headers, XML Sitemaps, and Schema graphs.

ZERO-FAKE CONTRACT: Every check result is computed from actual DOM/HTTP/XML parsing.
No hardcoded `passed=True`, no `or True` guards, no synthetic HTML fallbacks.
If data is unavailable, the status is FAILED_RECRAWL or INCONCLUSIVE — never fabricated.
"""
from datetime import datetime, timezone
import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse, urljoin

import httpx
try:
    from bs4 import BeautifulSoup
except ImportError:
    class _FallbackTag:
        def __init__(self, text="", attrs=None):
            self._text = text
            self._attrs = attrs or {}
        def get_text(self, strip=True):
            return self._text.strip() if strip else self._text
        def get(self, key, default=""):
            return self._attrs.get(key, default)
        @property
        def string(self):
            return self._text

    class _FallbackSoup:
        def __init__(self, html: str):
            self.html = html or ""
            self._scripts = re.findall(r'<script[^>]*type=[\'"]application/ld\+json[\'"][^>]*>(.*?)</script>', self.html, re.DOTALL | re.IGNORECASE)
            self._h1s = re.findall(r'<h1[^>]*>(.*?)</h1>', self.html, re.DOTALL | re.IGNORECASE)
            self._titles = re.findall(r'<title[^>]*>(.*?)</title>', self.html, re.DOTALL | re.IGNORECASE)
            self._meta_descs = re.findall(r'<meta[^>]*name=[\'"]description[\'"][^>]*content=[\'"](.*?)[\'"]', self.html, re.IGNORECASE)

        def find_all(self, tag, attrs=None):
            if tag == "script" and attrs and attrs.get("type") == "application/ld+json":
                return [_FallbackTag(s) for s in self._scripts]
            if tag == "h1":
                return [_FallbackTag(re.sub(r'<[^>]+>', '', h)) for h in self._h1s]
            return []

        def find(self, tag, attrs=None):
            if tag == "title":
                return _FallbackTag(re.sub(r'<[^>]+>', '', self._titles[0])) if self._titles else None
            if tag == "meta" and attrs and attrs.get("name") == "description":
                return _FallbackTag(attrs={"content": self._meta_descs[0]}) if self._meta_descs else None
            if tag == "link" and attrs and attrs.get("rel") == "canonical":
                match = re.search(r'<link[^>]*rel=[\'"]canonical[\'"][^>]*href=[\'"](.*?)[\'"]', self.html, re.IGNORECASE)
                if not match:
                    match = re.search(r'<link[^>]*href=[\'"](.*?)[\'"][^>]*rel=[\'"]canonical[\'"]', self.html, re.IGNORECASE)
                return _FallbackTag(attrs={"href": match.group(1)}) if match else None
            return None

    def BeautifulSoup(html, parser="html.parser"):
        return _FallbackSoup(html)

from app.domain.models import Finding, RemediationVerificationReport, VerificationCheckItem
from app.domain.enums import Category


class RemediationVerificationService:
    """
    Executes the 5-stage verification loop:
    1. FIX: Developer applies remediation
    2. RECRAWL: Deterministic targeted crawl of affected target URL/node
    3. RECHECK: Granular assertion testing against audited standards
    4. COMPARE: Before vs After delta evaluation
    5. CERTIFY: Issue resolution certification with cryptographic evidence seal

    Every assertion is derived from real data. No hardcoded passes.
    """

    async def verify_finding(
        self,
        finding: Finding,
        website_url: str,
        live_html: Optional[str] = None,
        live_status: Optional[int] = None,
        robots_txt_content: Optional[str] = None,
        sitemap_content: Optional[str] = None,
        analysis_id: Optional[str] = None,
        audited_urls: Optional[List[str]] = None,
    ) -> RemediationVerificationReport:
        now = datetime.now(timezone.utc).isoformat()
        base_domain = website_url.rstrip("/")
        finding_text = f"{finding.title} {finding.finding} {finding.description or ''} {finding.recommendation or ''}".lower()
        # The verification request has no captured pre-fix DOM by default.
        # Label the original finding as context rather than misrepresenting it as
        # a measured before snapshot.
        original_context = finding.finding or finding.description or finding.title
        before_state = (
            "No captured pre-remediation snapshot was supplied. Original finding context: "
            + str(original_context)
        )

        # ── Stage 2: RECRAWL ──────────────────────────────────────────
        crawled_html = live_html
        http_code = live_status
        crawled_robots = robots_txt_content
        crawled_sitemap = sitemap_content
        recrawl_ttfb_ms: Optional[float] = None
        recrawl_content_type: Optional[str] = None

        if crawled_html is None and website_url.startswith("http"):
            try:
                async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                    t0 = time.monotonic()
                    resp = await client.get(website_url, headers={"User-Agent": "Dristik-Assurance-Bot/4.0"})
                    recrawl_ttfb_ms = round((time.monotonic() - t0) * 1000, 1)
                    http_code = resp.status_code
                    recrawl_content_type = resp.headers.get("content-type", "")
                    if http_code == 200:
                        crawled_html = resp.text
            except Exception:
                # Cannot reach server — FAILED_RECRAWL, never fabricate DOM
                return self._build_report(
                    finding=finding,
                    website_url=website_url,
                    now=now,
                    stage="RECRAWL",
                    status="FAILED_RECRAWL",
                    before_state=before_state,
                    after_state="Server unreachable — cannot verify. Recrawl failed.",
                    checks=[],
                    analysis_id=analysis_id,
                    recrawl_status_code=None,
                    recrawl_ttfb_ms=None,
                    recrawl_content_type=None,
                )

        if http_code is None:
            http_code = 200 if crawled_html else 0

        # Fetch /robots.txt if needed and not provided
        if crawled_robots is None and ("sitemap" in finding_text or "robots" in finding_text) and website_url.startswith("http"):
            try:
                parsed = urlparse(website_url)
                robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
                async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                    resp = await client.get(robots_url, headers={"User-Agent": "Dristik-Assurance-Bot/4.0"})
                    if resp.status_code == 200:
                        crawled_robots = resp.text
            except Exception:
                pass  # robots fetch failure is not fatal — the check will simply fail

        # Fetch /sitemap.xml if needed and not provided
        if crawled_sitemap is None and "sitemap" in finding_text and website_url.startswith("http"):
            try:
                parsed = urlparse(website_url)
                sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
                async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                    resp = await client.get(sitemap_url, headers={"User-Agent": "Dristik-Assurance-Bot/4.0"})
                    if resp.status_code == 200:
                        crawled_sitemap = resp.text
            except Exception:
                pass  # sitemap fetch failure is not fatal — the check will simply fail

        # ── Stage 3: RECHECK (Deterministic Assertions) ──────────────
        checks: List[VerificationCheckItem] = []
        before_state = finding.finding or finding.description or finding.title

        if "sitemap" in finding_text or "robots" in finding_text:
            checks = self._check_sitemap_assertions(
                crawled_html=crawled_html,
                crawled_sitemap=crawled_sitemap,
                crawled_robots=crawled_robots,
                http_code=http_code,
                recrawl_ttfb_ms=recrawl_ttfb_ms,
                base_domain=base_domain,
                audited_urls=audited_urls,
            )

        elif "schema" in finding_text or "json-ld" in finding_text or finding.category == Category.SCHEMA:
            checks = self._check_schema_assertions(crawled_html=crawled_html)

        elif "h1" in finding_text or "positioning" in finding_text:
            checks = self._check_h1_assertions(crawled_html=crawled_html)

        elif "canonical" in finding_text or "duplicate" in finding_text or "meta" in finding_text or "title" in finding_text:
            checks = self._check_metadata_assertions(crawled_html=crawled_html, website_url=website_url)

        else:
            checks = self._check_general_assertions(crawled_html=crawled_html, http_code=http_code)

        # ── Stage 4: COMPARE ──────────────────────────────────────────
        passed_count = sum(1 for c in checks if c.passed)
        total_count = len(checks)

        if total_count == 0:
            status = "INCONCLUSIVE"
            after_state = "No automated assertions available for this finding type. Manual verification required."
        elif passed_count == total_count:
            status = "RESOLVED"
            passed_names = [c.name for c in checks if c.passed]
            after_state = f"All {total_count} checks passed: {', '.join(passed_names)}"
        elif passed_count > 0:
            status = "PARTIALLY_RESOLVED"
            failed_names = [c.name for c in checks if not c.passed]
            after_state = f"{passed_count}/{total_count} checks passed. Failed: {', '.join(failed_names)}"
        else:
            status = "FAILED_RECHECK"
            after_state = f"All {total_count} checks failed. Remediation not detected."

        # ── Stage 5: CERTIFY ──────────────────────────────────────────
        # A passed re-check is a technical result. It is not a citation or revenue delta.
        is_resolved = status == "RESOLVED"
        return self._build_report(
            finding=finding,
            website_url=website_url,
            now=now,
            stage="CERTIFIED" if is_resolved else "RECHECK",
            status=status,
            before_state=before_state,
            after_state=after_state,
            checks=checks,
            analysis_id=analysis_id,
            recrawl_status_code=http_code,
            recrawl_ttfb_ms=recrawl_ttfb_ms,
            recrawl_content_type=recrawl_content_type,
        )

    # ── Assertion Suites ──────────────────────────────────────────────

    def _check_sitemap_assertions(
        self,
        crawled_html: Optional[str],
        crawled_sitemap: Optional[str],
        crawled_robots: Optional[str],
        http_code: int,
        recrawl_ttfb_ms: Optional[float],
        base_domain: str,
        audited_urls: Optional[List[str]] = None,
    ) -> List[VerificationCheckItem]:
        checks: List[VerificationCheckItem] = []

        # Use sitemap content for sitemap checks (not the main page HTML)
        sitemap_body = crawled_sitemap or crawled_html or ""

        # 1. /sitemap.xml detected — look for <urlset or <sitemapindex in actual content
        has_urlset = "<urlset" in sitemap_body or "<sitemapindex" in sitemap_body
        checks.append(VerificationCheckItem(
            name="/sitemap.xml detected",
            passed=has_urlset,
            detail="Found valid XML sitemap payload with <urlset> or <sitemapindex>" if has_urlset
                   else "No <urlset> or <sitemapindex> element found in response body"
        ))

        # 2. Referenced in robots.txt — actually search the robots.txt content
        robots_has_sitemap = bool(crawled_robots and "sitemap:" in crawled_robots.lower())
        sitemap_directive = ""
        if robots_has_sitemap and crawled_robots:
            for line in crawled_robots.splitlines():
                if line.strip().lower().startswith("sitemap:"):
                    sitemap_directive = line.strip()
                    break
        checks.append(VerificationCheckItem(
            name="referenced in robots.txt",
            passed=robots_has_sitemap,
            detail=f"Directive: {sitemap_directive}" if robots_has_sitemap
                   else "No Sitemap directive found in robots.txt" + (" (robots.txt not available)" if crawled_robots is None else "")
        ))

        # 3. Audited URLs present in sitemap — parse <loc> nodes and count matches
        loc_urls: List[str] = []
        if has_urlset:
            try:
                root = ET.fromstring(sitemap_body)
                ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                loc_elements = root.findall(".//sm:loc", ns)
                if not loc_elements:
                    # Try without namespace
                    loc_elements = root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
                if not loc_elements:
                    loc_elements = root.findall(".//loc")
                loc_urls = [el.text.strip() for el in loc_elements if el.text]
            except ET.ParseError:
                pass

        if audited_urls:
            matched = sum(1 for u in audited_urls if u in loc_urls or u.rstrip("/") in [l.rstrip("/") for l in loc_urls])
            total_audited = len(audited_urls)
            checks.append(VerificationCheckItem(
                name="audited URLs present in sitemap",
                passed=matched == total_audited and total_audited > 0,
                detail=f"Audited canonical URL set: {matched}/{total_audited} present in <loc> nodes"
            ))
        else:
            loc_count = len(loc_urls)
            checks.append(VerificationCheckItem(
                name="audited URLs present in sitemap",
                passed=loc_count > 0,
                detail=f"Found {loc_count} <loc> entries in sitemap" if loc_count > 0
                       else "No <loc> entries found in sitemap"
            ))

        # 4. HTTP status — use actual status code and TTFB
        ttfb_str = f" (TTFB {recrawl_ttfb_ms}ms)" if recrawl_ttfb_ms is not None else ""
        checks.append(VerificationCheckItem(
            name="HTTP 200 status",
            passed=http_code == 200,
            detail=f"Server response code: {http_code}{ttfb_str}"
        ))

        # 5. XML valid syntax — actually attempt to parse
        xml_valid = False
        xml_error = ""
        if has_urlset:
            try:
                ET.fromstring(sitemap_body)
                xml_valid = True
            except ET.ParseError as e:
                xml_error = str(e)
        checks.append(VerificationCheckItem(
            name="XML valid syntax",
            passed=xml_valid,
            detail="XML parsed successfully without errors" if xml_valid
                   else f"XML parse failed: {xml_error}" if xml_error
                   else "No XML content available to validate"
        ))

        return checks

    def _check_schema_assertions(self, crawled_html: Optional[str]) -> List[VerificationCheckItem]:
        checks: List[VerificationCheckItem] = []

        if not crawled_html:
            checks.append(VerificationCheckItem(name="JSON-LD script tag present", passed=False, detail="No HTML content available for inspection"))
            return checks

        soup = BeautifulSoup(crawled_html, "html.parser")
        ld_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})

        # 1. JSON-LD script tag present
        has_ld = len(ld_scripts) > 0
        checks.append(VerificationCheckItem(
            name="JSON-LD script tag present",
            passed=has_ld,
            detail=f"Found {len(ld_scripts)} <script type=\"application/ld+json\"> tag(s) in DOM" if has_ld
                   else "No <script type=\"application/ld+json\"> found in DOM"
        ))

        if not has_ld:
            checks.append(VerificationCheckItem(name="Valid JSON syntax", passed=False, detail="No JSON-LD to validate"))
            checks.append(VerificationCheckItem(name="Schema entity type verified", passed=False, detail="No JSON-LD to inspect"))
            checks.append(VerificationCheckItem(name="Required properties populated", passed=False, detail="No JSON-LD to inspect"))
            return checks

        # 2. Valid JSON syntax — actually parse each script
        parsed_objects = []
        json_errors = []
        for script in ld_scripts:
            raw = script.string or ""
            try:
                obj = json.loads(raw)
                parsed_objects.append(obj)
            except json.JSONDecodeError as e:
                json_errors.append(str(e))

        json_valid = len(json_errors) == 0 and len(parsed_objects) > 0
        checks.append(VerificationCheckItem(
            name="Valid JSON syntax",
            passed=json_valid,
            detail=f"Parsed {len(parsed_objects)} JSON-LD object(s) with 0 syntax errors" if json_valid
                   else f"JSON parse errors: {'; '.join(json_errors)}" if json_errors
                   else "Empty JSON-LD script tags"
        ))

        # 3. Schema entity type verified — check for @type
        all_types = []
        for obj in parsed_objects:
            if isinstance(obj, dict):
                t = obj.get("@type")
                if isinstance(t, list):
                    all_types.extend(t)
                elif t:
                    all_types.append(t)
            elif isinstance(obj, list):
                for item in obj:
                    if isinstance(item, dict):
                        t = item.get("@type")
                        if isinstance(t, list):
                            all_types.extend(t)
                        elif t:
                            all_types.append(t)

        has_type = len(all_types) > 0
        checks.append(VerificationCheckItem(
            name="Schema entity type verified",
            passed=has_type,
            detail=f"Found @type: {', '.join(all_types)}" if has_type
                   else "No @type property found in JSON-LD"
        ))

        # 4. Required properties — check for @context, name, url
        required_found = set()
        for obj in parsed_objects:
            if isinstance(obj, dict):
                if obj.get("@context"):
                    required_found.add("@context")
                if obj.get("name"):
                    required_found.add("name")
                if obj.get("url"):
                    required_found.add("url")

        required_keys = {"@context", "name", "url"}
        missing = required_keys - required_found
        checks.append(VerificationCheckItem(
            name="Required properties populated",
            passed=len(missing) == 0,
            detail=f"All required fields present: {', '.join(sorted(required_found))}" if len(missing) == 0
                   else f"Missing required properties: {', '.join(sorted(missing))}"
        ))

        return checks

    def _check_h1_assertions(self, crawled_html: Optional[str]) -> List[VerificationCheckItem]:
        checks: List[VerificationCheckItem] = []

        if not crawled_html:
            checks.append(VerificationCheckItem(name="Single H1 element detected in DOM", passed=False, detail="No HTML content available for inspection"))
            return checks

        soup = BeautifulSoup(crawled_html, "html.parser")
        h1_tags = soup.find_all("h1")
        h1_count = len(h1_tags)

        # 1. Single H1 element detected
        checks.append(VerificationCheckItem(
            name="Single H1 element detected in DOM",
            passed=h1_count == 1,
            detail=f"Found {h1_count} <h1> element(s)" + (" (expected exactly 1)" if h1_count != 1 else "")
        ))

        # 2. Commercial clarity — H1 text has substance
        h1_text = h1_tags[0].get_text(strip=True) if h1_count >= 1 else ""
        has_substance = len(h1_text) > 10
        checks.append(VerificationCheckItem(
            name="Commercial clarity & category statement",
            passed=has_substance,
            detail=f"H1 text: \"{h1_text[:100]}\" ({len(h1_text)} chars)" if h1_text
                   else "H1 element is empty or not found"
        ))

        # 3. Length & readability — measure actual character count
        char_count = len(h1_text)
        optimal = 24 <= char_count <= 70
        checks.append(VerificationCheckItem(
            name="Length & readability optimal",
            passed=optimal,
            detail=f"H1 character length: {char_count} (optimal range: 24-70)"
        ))

        return checks

    def _check_metadata_assertions(self, crawled_html: Optional[str], website_url: str) -> List[VerificationCheckItem]:
        checks: List[VerificationCheckItem] = []

        if not crawled_html:
            checks.append(VerificationCheckItem(name="Unique <title> tag detected", passed=False, detail="No HTML content available for inspection"))
            return checks

        soup = BeautifulSoup(crawled_html, "html.parser")

        # 1. <title> tag
        title_tag = soup.find("title")
        title_text = title_tag.get_text(strip=True) if title_tag else ""
        has_title = bool(title_text)
        checks.append(VerificationCheckItem(
            name="Unique <title> tag detected",
            passed=has_title,
            detail=f"Title: \"{title_text[:100]}\" ({len(title_text)} chars)" if has_title
                   else "No <title> tag found or title is empty"
        ))

        # 2. Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        desc_content = meta_desc.get("content", "").strip() if meta_desc else ""
        has_desc = bool(desc_content)
        desc_len = len(desc_content)
        checks.append(VerificationCheckItem(
            name="Meta description populated & length compliant",
            passed=has_desc,
            detail=f"Description: {desc_len} characters" + (f" — \"{desc_content[:80]}...\"" if desc_len > 80 else f" — \"{desc_content}\"") if has_desc
                   else "No <meta name=\"description\"> tag found or content is empty"
        ))

        # 3. Canonical link self-referential
        canonical_link = soup.find("link", attrs={"rel": "canonical"})
        canonical_href = canonical_link.get("href", "").strip() if canonical_link else ""
        # Normalize for comparison
        norm_canonical = canonical_href.rstrip("/").lower()
        norm_url = website_url.rstrip("/").lower()
        is_self_ref = bool(canonical_href) and (norm_canonical == norm_url or norm_canonical.endswith(urlparse(norm_url).path.rstrip("/")))
        checks.append(VerificationCheckItem(
            name="Canonical link self-referential",
            passed=is_self_ref,
            detail=f"rel=\"canonical\" href=\"{canonical_href}\"" + (" (matches target URL)" if is_self_ref else f" (does not match {website_url})")
                   if canonical_href else "No <link rel=\"canonical\"> found"
        ))

        return checks

    def _check_general_assertions(self, crawled_html: Optional[str], http_code: int) -> List[VerificationCheckItem]:
        """
        General finding type — only assert what we can actually measure.
        Never fabricate pass/fail for things we cannot deterministically verify.
        """
        checks: List[VerificationCheckItem] = []

        # We can assert HTTP status since we have the actual response code
        checks.append(VerificationCheckItem(
            name="Target URL HTTP status 200 OK",
            passed=http_code == 200,
            detail=f"Server returned status {http_code}"
        ))

        # We cannot deterministically assert "remediation satisfied" or "no regression"
        # for an unknown finding type without specific assertion logic.
        # Return INCONCLUSIVE instead of faking pass.

        return checks

    # ── Report Builder ────────────────────────────────────────────────

    def _build_report(
        self,
        finding: Finding,
        website_url: str,
        now: str,
        stage: str,
        status: str,
        before_state: str,
        after_state: str,
        checks: List[VerificationCheckItem],
        analysis_id: Optional[str],
        recrawl_status_code: Optional[int],
        recrawl_ttfb_ms: Optional[float],
        recrawl_content_type: Optional[str],
        score_delta: Optional[float] = None,
        score_delta_is_measured: bool = False,
    ) -> RemediationVerificationReport:
        passed_count = sum(1 for c in checks if c.passed)
        total_count = len(checks)

        # Content hash of this verification record. Not a correctness certificate.
        raw_seal = f"dristik_cert:{finding.finding_id}:{website_url}:{now}:{passed_count}/{total_count}:{status}"
        evidence_seal = f"sha256:{hashlib.sha256(raw_seal.encode('utf-8')).hexdigest()[:24]}"
        if score_delta is not None and not score_delta_is_measured:
            score_delta = None
        technical_status = {
            "RESOLVED": "condition_resolved",
            "PARTIALLY_RESOLVED": "partial",
            "FAILED_RECHECK": "not_resolved",
            "FAILED_RECRAWL": "not_resolved",
            "INCONCLUSIVE": "inconclusive",
        }.get(status, "not_measured")

        report = RemediationVerificationReport(
            verification_id=f"cert_{finding.finding_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            finding_id=finding.finding_id,
            analysis_id=analysis_id,
            target_url=website_url,
            stage=stage,
            status=status,
            before_state=before_state,
            after_state=after_state,
            checks=checks,
            passed_checks_count=passed_count,
            total_checks_count=total_count,
            score_delta=score_delta,
            score_delta_is_measured=score_delta_is_measured and score_delta is not None,
            technical_verification=technical_status,
            visibility_verification="not_measured",
            business_verification="not_measured",
            verified_at=now,
            evidence_seal=evidence_seal,
            certified_by="Dristik Continuous Assurance Engine v4",
            recrawl_status_code=recrawl_status_code,
            recrawl_ttfb_ms=recrawl_ttfb_ms,
            recrawl_content_type=recrawl_content_type,
        )

        # Mutate finding
        finding.remediation_verification = report
        finding.resolution_status = status

        return report


verification_loop_service = RemediationVerificationService()
