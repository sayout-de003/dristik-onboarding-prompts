"""
Dristik AI Media Payload & Mixed Content Analyzer
Parses all <img> elements and page subresources to evaluate:
- Missing alt text or empty alt="" attributes
- Missing explicit width and height dimensions (causing Cumulative Layout Shift / CLS)
- Next-gen image format adoption (WebP, AVIF, SVG vs PNG, JPEG, GIF)
- Mixed content: scans HTTPS pages for subresources loaded over insecure http://
"""
import hashlib
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
from app.domain.models import PageEvidence, MediaAssetItem, MediaAssetAuditReport, Finding, FindingEvidence
from app.domain.enums import Category, Severity

_MODERN_FORMATS = {"webp", "avif", "svg"}
_LEGACY_FORMATS = {"png", "jpeg", "jpg", "gif", "bmp", "tiff"}


def _extract_dom_elements(html: str):
    """Robust extractor supporting BeautifulSoup, lxml.html, and html.parser fallback."""
    if BeautifulSoup is not None:
        try:
            soup = BeautifulSoup(html, "html.parser")
            imgs = []
            for tag in soup.find_all("img"):
                attrs = dict(tag.attrs)
                attrs["_is_linked"] = bool(tag.find_parent("a"))
                attrs["_tag_str"] = str(tag)
                imgs.append(attrs)
            subresources = []
            for tag in soup.find_all(["img", "script", "link", "iframe", "video", "audio"]):
                src = tag.get("src") or tag.get("href")
                if src:
                    subresources.append(src)
            return imgs, subresources
        except Exception:
            pass

    try:
        import lxml.html
        doc = lxml.html.fromstring(html)
        imgs = []
        for tag in doc.xpath("//img"):
            attrs = dict(tag.attrib)
            parent = tag.getparent()
            attrs["_is_linked"] = (parent is not None and parent.tag == "a")
            attrs["_tag_str"] = lxml.html.tostring(tag, encoding="unicode")
            imgs.append(attrs)
        subresources = []
        for tag in doc.xpath("//img | //script | //link | //iframe | //video | //audio"):
            src = tag.attrib.get("src") or tag.attrib.get("href")
            if src:
                subresources.append(src)
        return imgs, subresources
    except Exception:
        pass

    from html.parser import HTMLParser
    class SimpleMediaParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.imgs = []
            self.subresources = []
            self._in_a = False
        def handle_starttag(self, tag, attrs):
            attr_dict = dict(attrs)
            if tag == "a":
                self._in_a = True
            elif tag == "img":
                attr_dict["_is_linked"] = self._in_a
                attr_dict["_tag_str"] = f"<img src='{attr_dict.get('src', '')}'>"
                self.imgs.append(attr_dict)
            if tag in ("img", "script", "link", "iframe", "video", "audio"):
                src = attr_dict.get("src") or attr_dict.get("href")
                if src:
                    self.subresources.append(src)
        def handle_endtag(self, tag):
            if tag == "a":
                self._in_a = False

    parser = SimpleMediaParser()
    try:
        parser.feed(html)
    except Exception:
        pass
    return parser.imgs, parser.subresources


class MediaAssetAnalyzer:
    @staticmethod
    def analyze_media(pages: List[PageEvidence], raw_html_map: Optional[Dict[str, str]] = None) -> MediaAssetAuditReport:
        raw_html_map = raw_html_map or {}
        flagged_images: List[MediaAssetItem] = []
        cls_risks: List[Dict[str, str]] = []
        missing_alt_images: List[Dict[str, Any]] = []
        mixed_content_urls: List[str] = []

        total_images = 0
        missing_alt_count = 0
        empty_alt_count = 0
        missing_dim_count = 0
        modern_count = 0
        non_modern_count = 0

        for p in pages:
            is_page_https = (p.url or "").startswith("https://")
            html = raw_html_map.get(p.url) or getattr(p, "raw_html", None) or getattr(p, "rendered_html", None)
            if not html and getattr(p, "snapshot_path", None):
                try:
                    from pathlib import Path
                    sp = Path(p.snapshot_path)
                    if sp.exists():
                        html = sp.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    pass

            if html:
                imgs, subresources = _extract_dom_elements(html)
                total_images += len(imgs)

                # Check mixed content across all subresources on HTTPS pages (img, script, link, iframe)
                if is_page_https:
                    for src in subresources:
                        if src and src.strip().lower().startswith("http://"):
                            mixed_content_urls.append(src)

                for img in imgs:
                    src = (img.get("src") or img.get("data-src") or "").strip()
                    alt = img.get("alt")
                    has_alt = alt is not None
                    is_empty_alt = (alt == "" or (alt is not None and not alt.strip()))
                    is_decorative = (
                        is_empty_alt
                        or (img.get("role") or "").lower() in ("presentation", "none")
                        or img.get("aria-hidden") == "true"
                    )

                    has_w = bool(img.get("width") or (img.get("style") and "width" in img.get("style")))
                    has_h = bool(img.get("height") or (img.get("style") and "height" in img.get("style")))
                    has_dimensions = has_w and has_h

                    # Determine image format extension
                    parsed_path = urlparse(src).path.lower()
                    ext = parsed_path.split(".")[-1] if "." in parsed_path else "other"
                    is_modern = ext in _MODERN_FORMATS
                    is_legacy = ext in _LEGACY_FORMATS

                    if is_modern:
                        modern_count += 1
                    elif is_legacy:
                        non_modern_count += 1

                    # WCAG 2.2: Only flag as missing alt if it has no alt attribute and is not declared decorative
                    if not has_alt and not is_decorative:
                        missing_alt_count += 1
                        if len(missing_alt_images) < 25:
                            is_linked = img.get("_is_linked", False)
                            img_filename = src.split("/")[-1].split("?")[0] or "inline-image"
                            missing_alt_images.append({
                                "page_url": p.url,
                                "response_status": getattr(p, "status_code", None),
                                "img_src": src,
                                "filename": img_filename,
                                "tag_snippet": img.get("_tag_str", f"<img src='{src}'>")[:200],
                                "is_linked": is_linked,
                                "image_role": "functional" if is_linked else "informative",
                                "reason": f"Image '{img_filename}' lacks alt attribute (WCAG non-compliant)",
                            })
                    elif is_decorative:
                        empty_alt_count += 1

                    if not has_dimensions:
                        missing_dim_count += 1
                        if len(cls_risks) < 10:
                            cls_risks.append({
                                "page_url": p.url,
                                "img_src": src[:120],
                                "reason": "Missing explicit width/height causing layout shift (CLS hazard)"
                            })

                    is_insecure = is_page_https and src.startswith("http://")

                    # An image is flagged only if it has a genuine defect:
                    # missing alt (non-decorative), missing dimensions (CLS), legacy format (optimization), or insecure HTTP
                    has_defect = (not has_alt and not is_decorative) or (not has_dimensions) or (not is_modern and is_legacy) or is_insecure

                    if has_defect:
                        flagged_images.append(MediaAssetItem(
                            url=src,
                            page_url=p.url,
                            alt_text=alt,
                            has_alt=has_alt,
                            is_empty_alt=is_empty_alt,
                            has_dimensions=has_dimensions,
                            format=ext,
                            is_modern_format=is_modern,
                            is_insecure_http=is_insecure
                        ))
            else:
                # Derive from page evidence metrics if raw html not present
                page_img_count = p.total_images or 0
                page_missing_alt = p.images_without_alt or 0
                total_images += page_img_count
                missing_alt_count += page_missing_alt

        summary = (
            f"Evaluated {total_images} total image assets across {len(pages)} pages: "
            f"{missing_alt_count} informative images missing alt text (WCAG 2.2 non-compliant), "
            f"{empty_alt_count} decorative images with alt=\"\" or role=\"presentation\" (WCAG compliant), "
            f"{missing_dim_count} missing dimensions (CLS risk), "
            f"{non_modern_count} legacy formats (PNG/JPEG) vs {modern_count} modern (WebP/AVIF), "
            f"{len(mixed_content_urls)} mixed content HTTP subresources detected."
        )

        return MediaAssetAuditReport(
            total_images_analyzed=total_images,
            missing_alt_count=missing_alt_count,
            empty_alt_count=empty_alt_count,
            decorative_alt_compliant_count=empty_alt_count,
            missing_dimensions_count=missing_dim_count,
            modern_format_count=modern_count,
            non_modern_format_count=non_modern_count,
            mixed_content_count=len(mixed_content_urls),
            mixed_content_urls=mixed_content_urls,
            cls_risk_images=cls_risks,
            missing_alt_images=missing_alt_images,
            flagged_images=flagged_images,
            summary=summary
        )

    @staticmethod
    def generate_findings(report: MediaAssetAuditReport) -> List[Finding]:
        findings: List[Finding] = []

        if report.missing_alt_count > 0:
            sample = report.missing_alt_images[0] if getattr(report, "missing_alt_images", None) else None
            sample_fn = sample.get("filename", "image asset") if sample else "image asset"
            sample_page = urlparse(sample.get("page_url", "/")).path or "/" if sample else "/"
            
            title = f"{report.missing_alt_count} Image Asset(s) Missing Alternative Text"
            if report.missing_alt_count == 1 and sample:
                title = f"On '{sample_page}', image '{sample_fn}' is missing an alt attribute"
            elif sample:
                title = f"{report.missing_alt_count} Image Asset(s) Missing Alternative Text (e.g. '{sample_fn}' on '{sample_page}')"

            evidence_items: List[FindingEvidence] = []
            alt_images = getattr(report, "missing_alt_images", []) or []
            for item in alt_images[:8]:
                page_url = item.get("page_url") or ""
                img_src = item.get("img_src") or ""
                ev_id = f"EV-IMG-ALT-{hashlib.sha256(f'{page_url}:{img_src}'.encode()).hexdigest()[:8]}"
                evidence_items.append(FindingEvidence(
                    evidence_id=ev_id,
                    url=page_url,
                    response_status=item.get("response_status"),
                    element="img",
                    value=img_src,
                    observed_value=img_src,
                    expected_condition="Informative content image must declare a non-empty alt attribute describing its content or function",
                    snippet=item.get("tag_snippet") or f'<img src="{img_src}">',
                    test_method="crawl_html_dom",
                    source="crawl",
                    is_decorative=False,
                    image_role=item.get("image_role", "informative"),
                ))

            findings.append(Finding(
                finding_id="finding_missing_image_alt",
                category=Category.ON_PAGE_SEO,
                severity=Severity.LOW if report.missing_alt_count <= 2 else Severity.MEDIUM,
                title=title,
                description=(
                    f"Observed {report.missing_alt_count} informative image asset(s) lacking an alt attribute. "
                    f"Sample finding: on '{sample_page}', image '{sample_fn}' has no alt text. "
                    "Informative images require descriptive text for search engine image indexation and assistive technology."
                ),
                recommendation="Add descriptive, concise alternative text to all informative images. Mark purely decorative images with alt='' or role='presentation'.",
                why_it_matters="Search engines utilize image alt text to understand topical relevance and image search placement. Screen readers rely on alt text to convey non-text content.",
                validation_criteria="Every non-decorative <img> tag must include a non-empty alt attribute describing its visual content or function.",
                owner="Content Editor",
                responsible_role="Content Editor",
                estimated_effort="Low (< 2 hours)",
                dependencies=["CMS image asset editor access"],
                priority_rationale="Medium Priority: Essential for WCAG accessibility and search engine image context, but does not block document indexation.",
                verification_command=f"curl -s '{sample_page}' | grep -i '<img' | grep -v 'alt='",
                evidence=evidence_items,
                evidence_refs=[ev.evidence_id for ev in evidence_items if ev.evidence_id] or ["media_audit"],
                evidence_ids=[ev.evidence_id for ev in evidence_items if ev.evidence_id],
                impact=4,
                effort=2,
                priority=4
            ))

        if report.missing_dimensions_count > 0:
            evidence_items = []
            for item in report.cls_risk_images[:8]:
                page_url = item.get("page_url") or ""
                img_src = item.get("img_src") or ""
                ev_id = f"EV-IMG-CLS-{hashlib.sha256(f'{page_url}:{img_src}'.encode()).hexdigest()[:8]}"
                evidence_items.append(FindingEvidence(
                    evidence_id=ev_id,
                    url=item.get("page_url") or "",
                    element="img",
                    value=item.get("img_src") or "",
                    observed_value="Missing explicit width/height attributes",
                    expected_condition="Images must declare explicit width and height attributes or CSS aspect-ratio",
                    snippet=item.get("reason"),
                    test_method="crawl_html_dom",
                    source="crawl",
                ))

            cls_sample_url = report.cls_risk_images[0].get("page_url") if report.cls_risk_images else "https://example.com/"
            findings.append(Finding(
                finding_id="finding_image_cls_risk",
                category=Category.TECHNICAL_SEO,
                severity=Severity.HIGH if report.missing_dimensions_count > 3 else Severity.MEDIUM,
                title=f"{report.missing_dimensions_count} Image(s) Missing Explicit Dimensions (CLS Risk)",
                description=(
                    f"Discovered {report.missing_dimensions_count} image asset(s) lacking explicit width and height attributes. "
                    "This prevents the browser layout engine from reserving image aspect ratio before download, causing layout shifts."
                ),
                recommendation="Declare explicit width and height attributes or CSS aspect-ratio on all <img> elements.",
                why_it_matters="Cumulative Layout Shift (CLS) is a Core Web Vital. Visual instability harms user reading flow and suppresses mobile experience scores.",
                validation_criteria="All <img> tags must declare intrinsic width and height attributes.",
                owner="Developer",
                responsible_role="Developer",
                estimated_effort="Low (< 2 hours)",
                dependencies=["Frontend template or CSS styling access"],
                priority_rationale="High: Cumulative Layout Shift directly degrades Google Core Web Vitals compliance.",
                verification_command=f"curl -s '{cls_sample_url}' | grep -E '<img[^>]+src=[^>]+>' | grep -v 'width='",
                evidence=evidence_items,
                evidence_refs=[ev.evidence_id for ev in evidence_items if ev.evidence_id] or ["media_audit"],
                evidence_ids=[ev.evidence_id for ev in evidence_items if ev.evidence_id],
                impact=6,
                effort=2,
                priority=6
            ))

        if report.mixed_content_count > 0:
            evidence_items = []
            for u in report.mixed_content_urls[:8]:
                ev_id = f"EV-SEC-MIXED-{hashlib.sha256(u.encode()).hexdigest()[:8]}"
                evidence_items.append(FindingEvidence(
                    evidence_id=ev_id,
                    url=u,
                    element="mixed_content",
                    value=u,
                    observed_value="Insecure http:// asset URL",
                    expected_condition="All subresources on HTTPS pages must load securely over https://",
                    snippet=f"Insecure HTTP subresource: {u}",
                    test_method="crawl_html_dom",
                    source="crawl",
                ))

            findings.append(Finding(
                finding_id="finding_mixed_content_assets",
                category=Category.TECHNICAL_SEO,
                severity=Severity.HIGH,
                title=f"{report.mixed_content_count} Insecure HTTP Subresource(s) on HTTPS Pages",
                description=(
                    f"Identified {report.mixed_content_count} image or script asset(s) requested over insecure HTTP on HTTPS pages. "
                    "Modern browsers block active mixed content and display security warnings for passive mixed content."
                ),
                recommendation="Update all image, script, and stylesheet URLs to use HTTPS protocol.",
                why_it_matters="Mixed content degrades browser padlock security status and causes asset loading failures.",
                validation_criteria="All subresources on HTTPS pages must load over HTTPS.",
                evidence=evidence_items,
                evidence_refs=[ev.evidence_id for ev in evidence_items if ev.evidence_id] or ["media_audit"],
                evidence_ids=[ev.evidence_id for ev in evidence_items if ev.evidence_id],
                impact=7,
                effort=1,
                priority=7
            ))

        return findings


def analyze_media_assets(pages: List[PageEvidence], raw_html_map: Optional[Dict[str, str]] = None) -> MediaAssetAuditReport:
    return MediaAssetAnalyzer.analyze_media(pages, raw_html_map)
