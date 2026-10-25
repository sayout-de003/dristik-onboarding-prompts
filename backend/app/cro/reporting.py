"""
HTML and JSON rendering for the 55-section CRO audit report and audit book.

The four dimensions stay separate. Missing rates stay unmeasured.
"""
from __future__ import annotations

import html
from typing import Any, Dict, Optional

from app.cro.engine import CroIntelligenceReport, build_from_executive_report


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _score_label(score: Optional[float], status: str) -> str:
    if score is None:
        return "Unmeasured"
    return f"{score:.1f}"


class CroReportGenerator:
    """Renders the CRO intelligence report. It does not blend a conversion rate."""

    def render_json_report(
        self,
        intel: CroIntelligenceReport,
        *,
        domain: str = "",
        website_url: str = "",
        generated_at: str = "",
        analysis_id: str = "",
    ) -> Dict[str, Any]:
        payload = intel.model_dump()
        payload["domain"] = domain
        payload["website_url"] = website_url
        payload["generated_at"] = generated_at
        payload["analysis_id"] = analysis_id
        payload["chapters"] = intel.chapters
        return payload

    def render_html_report(
        self,
        intel: CroIntelligenceReport,
        *,
        domain: str = "",
        website_url: str = "",
        generated_at: str = "",
        analysis_id: str = "",
    ) -> str:
        parts = []
        for part in intel.parts:
            owned = [section for section in intel.sections if section.part == part["id"]]
            blocks = []
            for section in owned:
                checks = "".join(
                    "<li><strong>{state}</strong> — {label}: {summary}</li>".format(
                        state=_esc(check.evidence_state),
                        label=_esc(check.label),
                        summary=_esc(check.summary),
                    )
                    for check in section.checks
                )
                blocks.append(
                    "<section id=\"cro-{number}\"><h3>{number}. {title}</h3>"
                    "<p class=\"meta\">{status} · {specialist}</p><ul>{checks}</ul></section>".format(
                        number=_esc(section.number),
                        title=_esc(section.title),
                        status=_esc(section.status),
                        specialist=_esc(section.specialist),
                        checks=checks,
                    )
                )
            parts.append(
                "<section class=\"part\"><h2>Part {pid}. {title}</h2><p class=\"meta\">{span}</p>{body}</section>".format(
                    pid=_esc(part["id"]),
                    title=_esc(part["title"]),
                    span=_esc(part.get("sections", "")),
                    body="".join(blocks),
                )
            )

        dimensions = "".join(
            "<article><h3>{name}</h3><p class=\"score\">{score}</p><p class=\"meta\">{status}</p><p>{note}</p></article>".format(
                name=_esc(item.name),
                score=_esc(_score_label(item.score, item.status)),
                status=_esc(item.status),
                note=_esc(item.note),
            )
            for item in intel.dimensions
        )
        metrics = "".join(
            "<tr><td>{metric}</td><td>{formula}</td><td>{status}</td><td>{display}</td><td>{denominator}</td><td>{note}</td></tr>".format(
                metric=_esc(item.metric),
                formula=_esc(item.formula),
                status=_esc(item.status),
                display=_esc(item.display),
                denominator=_esc(item.denominator or "—"),
                note=_esc(item.note),
            )
            for item in intel.metrics
        )
        findings = "".join(
            "<article class=\"finding\"><h3>{fid} · {priority}</h3>"
            "<p><strong>Status.</strong> {status}</p>"
            "<p><strong>Finding.</strong> {finding}</p>"
            "<p><strong>Evidence.</strong> {evidence}</p>"
            "<p><strong>Observed scope.</strong> {scope}</p>"
            "<p><strong>Hypothesis.</strong> {hypothesis}</p>"
            "<p><strong>Recommended action.</strong> {action}</p>"
            "<p><strong>Primary metric.</strong> {metric}</p>"
            "<p><strong>Guardrails.</strong> {guards}</p>"
            "<p><strong>Validation.</strong> {validation}</p>"
            "<p><strong>Impact estimate.</strong> {impact}</p>"
            "<p><strong>Owner.</strong> {owner}</p></article>".format(
                fid=_esc(item.finding_id),
                priority=_esc(item.priority),
                status=_esc(item.status),
                finding=_esc(item.finding),
                evidence=_esc(item.evidence),
                scope=_esc(item.observed_scope),
                hypothesis=_esc(item.hypothesis),
                action=_esc(item.recommended_action),
                metric=_esc(item.primary_metric),
                guards=_esc(", ".join(item.guardrail_metrics)),
                validation=_esc(item.validation),
                impact=_esc(item.impact_estimate),
                owner=_esc(item.owner),
            )
            for item in intel.findings
        ) or "<p>No experience defect met the evidence bar for a finding.</p>"
        roadmap = "".join(
            "<article><h3>{label}</h3><ul>{items}</ul></article>".format(
                label=_esc(label),
                items="".join(f"<li>{_esc(line)}</li>" for line in intel.roadmap.get(key, [])),
            )
            for key, label in (("days_30", "30 days"), ("days_60", "60 days"), ("days_90", "90 days"))
        )
        appendices = "".join(
            "<article><h3>Appendix {aid}. {title}</h3><p class=\"meta\">{status}</p><p>{contents}</p><p>{summary}</p></article>".format(
                aid=_esc(item.id),
                title=_esc(item.title),
                status=_esc(item.status),
                contents=_esc(item.contents),
                summary=_esc(item.summary),
            )
            for item in intel.appendices
        )
        chapters = "".join(
            "<li><strong>{cid}.</strong> {title}</li>".format(cid=_esc(item["id"]), title=_esc(item["title"]))
            for item in intel.chapters
        )
        rules = "".join(f"<li>{_esc(rule)}</li>" for rule in intel.measurement_rules)
        coverage = intel.coverage or {}
        coverage_html = (
            "<section><h3>Coverage and execution limits</h3><p><strong>Status:</strong> {status}</p>"
            "<p><strong>Inspected pages:</strong> {inspected} · <strong>Discovered URLs:</strong> {discovered} · "
            "<strong>Sample coverage:</strong> {percentage}</p>"
            "<p><strong>Rendered DOM:</strong> {rendered} · <strong>Journey execution:</strong> {journeys}</p>"
            "<p>{note}</p></section>"
        ).format(
            status=_esc(coverage.get("status", "NOT_RECORDED")),
            inspected=_esc(coverage.get("inspected_pages", intel.sample_size)),
            discovered=_esc(coverage.get("discovered_urls", intel.discovered_urls)),
            percentage=(f"{coverage['sample_coverage_pct']:.1f}%" if isinstance(coverage.get("sample_coverage_pct"), (int, float)) else "Unavailable"),
            rendered=_esc(coverage.get("rendered_dom_status", "NOT_VERIFIED")),
            journeys=_esc(coverage.get("journey_execution_status", "NOT_EXECUTED")),
            note=_esc(coverage.get("note", "Coverage was not recorded.")),
        )
        calibration = intel.scoring_calibration or {}
        calibration_html = (
            "<section><h3>Scoring calibration</h3><p><strong>Status:</strong> {status}</p>"
            "<p>{basis}</p><p><strong>Priority model:</strong> {priority}</p><p>{note}</p></section>"
        ).format(
            status=_esc(calibration.get("status", "NOT_RECORDED")),
            basis=_esc(calibration.get("basis", "Scoring basis was not recorded.")),
            priority=_esc(calibration.get("priority_calibration", "NOT_RECORDED")),
            note=_esc(calibration.get("note", "Calibration limitations were not recorded.")),
        )
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CRO audit — {_esc(domain or "website")}</title>
<style>
body {{ margin: 0; background: #f6f4ef; color: #1c1915; font: 16px/1.5 "Source Sans 3", "Segoe UI", sans-serif; }}
main {{ max-width: 920px; margin: 0 auto; padding: 32px 20px 64px; }}
h1, h2, h3 {{ font-weight: 650; letter-spacing: 0; }}
h1 {{ font-family: "Iowan Old Style", "Palatino Linotype", serif; font-size: 2rem; margin-bottom: 0.25rem; }}
.meta {{ color: #5c564c; font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 0.78rem; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }}
article {{ border: 1px solid #ddd6c8; background: #fffdf8; border-radius: 6px; padding: 12px 14px; margin: 10px 0; }}
.score {{ font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 1.4rem; margin: 0; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; }}
th, td {{ border-bottom: 1px solid #ddd6c8; text-align: left; vertical-align: top; padding: 8px 6px; }}
a {{ color: #1c1915; }}
</style>
</head>
<body>
<main>
<p class="meta">CRO audit · {_esc(analysis_id)}</p>
<h1>{_esc(domain or website_url or "CRO audit")}</h1>
<p class="meta">{_esc(website_url)} · {_esc(generated_at)}</p>
<p>{_esc(intel.scope_note)}</p>
<p>{_esc(intel.principle)}</p>
<p class="meta">Business model: {_esc(intel.business_model)}. {_esc(intel.model_basis)}</p>
<h2>01. Cover and scope</h2>
<ol>{chapters}</ol>
<h2>02. Executive summary and funnel scorecard</h2>
<p>These four scores stay separate. None of them is a blended conversion rate.</p>
{coverage_html}
{calibration_html}
<div class="grid">{dimensions}</div>
<h2>Measurement</h2>
<ul>{rules}</ul>
<table>
<thead><tr><th>Metric</th><th>Formula</th><th>Status</th><th>Value</th><th>Denominator</th><th>Note</th></tr></thead>
<tbody>{metrics}</tbody>
</table>
<h2>03. Experience and behavioral diagnostics</h2>
{"".join(parts)}
<h2>04. Measurement and experimentation</h2>
<p>A higher observed rate is not a win. Missing numerators stay unavailable.</p>
<h2>05. Prioritized remediation roadmap</h2>
{findings}
<div class="grid">{roadmap}</div>
<h2>06. Appendices and evidence ledger</h2>
{appendices}
</main>
</body>
</html>
"""


cro_report_generator = CroReportGenerator()


def render_cro_audit_book(report: Any) -> str:
    """Renders the CRO audit book HTML from an executive report."""
    intel = build_from_executive_report(report)
    return cro_report_generator.render_html_report(
        intel,
        domain=getattr(report, "domain", "") or "",
        website_url=getattr(report, "website_url", "") or "",
        generated_at=str(getattr(report, "generated_at", "") or ""),
        analysis_id=str(getattr(report, "analysis_id", "") or getattr(report, "report_id", "") or ""),
    )


__all__ = [
    "CroReportGenerator",
    "cro_report_generator",
    "render_cro_audit_book",
]
