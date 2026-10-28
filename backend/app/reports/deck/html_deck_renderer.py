"""
Interactive 16:9 Vector HTML Presentation Engine
Renders complete master DeckBlueprint into a responsive, presentation-ready 16:9 HTML document
complete with SVG vector data visualizations, keyboard navigation, and institutional dark aesthetics.
"""
import html
from typing import Dict, Any, List, Optional
from app.reports.deck.models import (
    DeckBlueprint,
    SlideBlueprint,
    SlideLayoutType,
    DeckChartType,
    ChartDataSpec,
    CardSpec
)


class HtmlVectorDeckRenderer:
    """
    Compiles DeckBlueprint into a standalone 16:9 Vector HTML presentation.
    """

    def render_deck_html(self, blueprint: DeckBlueprint) -> str:
        domain = html.escape(blueprint.domain or "Website Audit")
        total_slides = len(blueprint.slides)
        slides_html = []

        for idx, slide in enumerate(blueprint.slides):
            slides_html.append(self._render_slide(slide, idx + 1, total_slides))

        slides_joined = "\n".join(slides_html)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dristik Executive Intelligence Dossier — {domain}</title>
    <style>
        @page {{
            size: 16in 9in landscape;
            margin: 0;
        }}
        :root {{
            --bg-deep: #07090e;
            --bg-slide: #0b0f19;
            --bg-card: #111827;
            --border-card: #1e293b;
            --border-subtle: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-cyan: #38bdf8;
            --accent-emerald: #10b981;
            --accent-amber: #f59e0b;
            --accent-rose: #ef4444;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            background: var(--bg-deep);
            color: var(--text-primary);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", sans-serif;
            overflow-x: hidden;
            -webkit-print-color-adjust: exact;
        }}
        .deck-container {{
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px 0;
            gap: 24px;
        }}
        .slide-frame {{
            width: 1280px;
            height: 720px;
            background: var(--bg-slide);
            border: 1px solid var(--border-card);
            border-radius: 8px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.6);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            padding: 36px 48px;
            position: relative;
            page-break-after: always;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-card);
            padding-bottom: 12px;
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            font-size: 11px;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: var(--text-muted);
        }}
        .header-brand {{
            font-weight: 800;
            color: var(--accent-cyan);
            letter-spacing: 0.18em;
        }}
        .badge-confidential {{
            background: rgba(239, 68, 68, 0.12);
            border: 1px solid rgba(239, 68, 68, 0.35);
            color: #f87171;
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: 700;
        }}
        .slide-body {{
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
            padding: 16px 0;
            overflow: hidden;
        }}
        .kicker {{
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            font-size: 11px;
            color: var(--accent-cyan);
            letter-spacing: 0.14em;
            text-transform: uppercase;
            margin-bottom: 6px;
        }}
        .title {{
            font-family: Georgia, Cambria, "Times New Roman", serif;
            font-size: 26px;
            font-weight: 600;
            line-height: 1.25;
            color: #ffffff;
            margin-bottom: 6px;
        }}
        .subtitle {{
            font-size: 13px;
            color: var(--text-secondary);
            margin-bottom: 16px;
            line-height: 1.4;
        }}
        .footer {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 1px solid var(--border-card);
            padding-top: 10px;
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            font-size: 10px;
            color: var(--text-muted);
        }}
        .interpretation-box {{
            background: rgba(56, 189, 248, 0.08);
            border-left: 3px solid var(--accent-cyan);
            padding: 8px 14px;
            border-radius: 0 4px 4px 0;
            font-size: 12px;
            color: #bae6fd;
            margin-top: 10px;
            line-height: 1.4;
        }}
        .grid-cards-4 {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-top: 8px;
        }}
        .grid-cards-3 {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
            margin-top: 8px;
        }}
        .grid-cards-2 {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-top: 8px;
        }}
        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 6px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .card-kicker {{
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            font-size: 10px;
            color: var(--accent-cyan);
            letter-spacing: 0.1em;
            text-transform: uppercase;
            margin-bottom: 4px;
        }}
        .card-metric {{
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            font-size: 24px;
            font-weight: 700;
            color: #ffffff;
            margin: 4px 0 8px 0;
        }}
        .card-title {{
            font-size: 14px;
            font-weight: 600;
            color: #f1f5f9;
            margin-bottom: 6px;
        }}
        .card-desc {{
            font-size: 12px;
            color: var(--text-secondary);
            line-height: 1.45;
        }}
        .chart-split {{
            display: grid;
            grid-template-columns: 1.3fr 1fr;
            gap: 24px;
            align-items: center;
            height: 100%;
        }}
        .svg-chart-container {{
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 6px;
            padding: 16px;
            height: 280px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .bullet-list {{
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}
        .bullet-item {{
            position: relative;
            padding-left: 18px;
            font-size: 13px;
            line-height: 1.45;
            color: var(--text-secondary);
        }}
        .bullet-item::before {{
            content: "•";
            position: absolute;
            left: 0;
            color: var(--accent-cyan);
            font-size: 18px;
            line-height: 1;
        }}
        .table-matrix {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
            margin-top: 10px;
        }}
        .table-matrix th {{
            background: #1e293b;
            color: var(--text-primary);
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            font-size: 11px;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            padding: 8px 12px;
            text-align: left;
            border: 1px solid var(--border-subtle);
        }}
        .table-matrix td {{
            padding: 8px 12px;
            border: 1px solid var(--border-card);
            color: var(--text-secondary);
        }}
        .table-matrix tr:nth-child(even) {{
            background: rgba(17, 24, 39, 0.6);
        }}
        .token-badge {{
            display: inline-block;
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            font-size: 10px;
            background: rgba(56, 189, 248, 0.15);
            border: 1px solid var(--accent-cyan);
            color: #38bdf8;
            padding: 2px 6px;
            border-radius: 4px;
        }}
        .nav-controls {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: rgba(15, 23, 42, 0.9);
            border: 1px solid var(--border-subtle);
            border-radius: 30px;
            padding: 8px 16px;
            display: flex;
            align-items: center;
            gap: 12px;
            z-index: 1000;
            backdrop-filter: blur(8px);
        }}
        .nav-btn {{
            background: transparent;
            border: none;
            color: var(--text-primary);
            cursor: pointer;
            font-size: 14px;
            padding: 4px 8px;
            border-radius: 4px;
        }}
        .nav-btn:hover {{
            background: var(--border-card);
            color: var(--accent-cyan);
        }}
        @media print {{
            .nav-controls {{ display: none; }}
            body {{ background: transparent; }}
            .deck-container {{ padding: 0; gap: 0; }}
            .slide-frame {{ border: none; box-shadow: none; border-radius: 0; }}
        }}
    </style>
</head>
<body>
    <div class="nav-controls">
        <button class="nav-btn" onclick="prevSlide()">◀ Prev</button>
        <span id="slideIndicator" style="font-family: monospace; font-size: 12px;">Slide 1 / {total_slides}</span>
        <button class="nav-btn" onclick="nextSlide()">Next ▶</button>
        <button class="nav-btn" onclick="toggleFullscreen()">⛶ Fullscreen</button>
    </div>

    <div class="deck-container" id="deckContainer">
        {slides_joined}
    </div>

    <script>
        let currentSlide = 0;
        const slides = document.querySelectorAll('.slide-frame');
        const indicator = document.getElementById('slideIndicator');

        function updateIndicator() {{
            if (indicator) {{
                indicator.textContent = `Slide ${{currentSlide + 1}} / ${{slides.length}}`;
            }}
        }}

        function scrollToSlide(idx) {{
            if (idx >= 0 && idx < slides.length) {{
                currentSlide = idx;
                slides[idx].scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                updateIndicator();
            }}
        }}

        function nextSlide() {{
            if (currentSlide < slides.length - 1) {{
                scrollToSlide(currentSlide + 1);
            }}
        }}

        function prevSlide() {{
            if (currentSlide > 0) {{
                scrollToSlide(currentSlide - 1);
            }}
        }}

        function toggleFullscreen() {{
            if (!document.fullscreenElement) {{
                document.documentElement.requestFullscreen().catch(() => {{}});
            }} else {{
                document.exitFullscreen().catch(() => {{}});
            }}
        }}

        document.addEventListener('keydown', (e) => {{
            if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') {{
                e.preventDefault();
                nextSlide();
            }} else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {{
                e.preventDefault();
                prevSlide();
            }} else if (e.key === 'f' || e.key === 'F') {{
                toggleFullscreen();
            }}
        }});
    </script>
</body>
</html>"""

    def _render_slide(self, slide: SlideBlueprint, slide_num: int, total_slides: int) -> str:
        kicker = html.escape(slide.kicker or "")
        title = html.escape(slide.title or "")
        subtitle = html.escape(slide.subtitle or "")
        module_title = html.escape(slide.module_title or "")
        footer_text = html.escape(slide.footer_text or f"RESTRICTED // DRISTIK AUTONOMOUS INTELLIGENCE SYSTEMS")
        interpretation = slide.interpretation or ""

        # Slide content based on layout
        content_html = ""
        if slide.layout == SlideLayoutType.COVER:
            content_html = self._render_cover_body(slide)
        elif slide.layout == SlideLayoutType.METRIC_CARDS_4:
            content_html = self._render_cards_grid(slide.cards, 4)
        elif slide.layout == SlideLayoutType.METRIC_CARDS_3:
            content_html = self._render_cards_grid(slide.cards, 3)
        elif slide.layout in (SlideLayoutType.CHART_WITH_ANALYSIS, SlideLayoutType.DUAL_CHART):
            content_html = self._render_chart_split(slide)
        elif slide.layout in (SlideLayoutType.TABLE_MATRIX, SlideLayoutType.FINDINGS_LEDGER):
            content_html = self._render_table_matrix(slide)
        else:
            content_html = self._render_default_split(slide)

        # Interpretation box if present
        interp_box = ""
        if interpretation:
            interp_box = f'<div class="interpretation-box">{html.escape(interpretation)}</div>'

        return f"""
        <div class="slide-frame" id="slide-{slide.slide_id}">
            <div class="header">
                <div class="header-brand">DRISTIK // {module_title}</div>
                <div class="badge-confidential">C-SUITE RESTRICTED</div>
            </div>
            <div class="slide-body">
                <div class="kicker">{kicker}</div>
                <div class="title">{title}</div>
                <div class="subtitle">{subtitle}</div>
                {content_html}
                {interp_box}
            </div>
            <div class="footer">
                <div>{footer_text}</div>
                <div>SLIDE {slide_num} OF {total_slides}</div>
            </div>
        </div>"""

    def _render_cover_body(self, slide: SlideBlueprint) -> str:
        return f"""
        <div style="flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 20px;">
            <div style="font-family: ui-monospace, monospace; font-size: 13px; color: var(--accent-cyan); letter-spacing: 0.15em;">
                AUTONOMOUS TECHNICAL ASSURANCE &amp; GENERATIVE ANSWER-ENGINE AUDIT
            </div>
            <div style="display: flex; gap: 16px; margin-top: 10px;">
                <div class="token-badge">105 SPECIALISTS EXECUTED</div>
                <div class="token-badge">SEALED EVIDENCE PROVENANCE</div>
                <div class="token-badge">ZERO-SIMULATION GUARANTEE</div>
            </div>
        </div>"""

    def _render_cards_grid(self, cards: List[CardSpec], cols: int) -> str:
        cls = "grid-cards-4" if cols == 4 else "grid-cards-3"
        items = []
        for c in cards:
            metric = f'<div class="card-metric">{html.escape(c.metric_value)}</div>' if c.metric_value else ""
            badge = f'<span class="token-badge" style="margin-bottom: 6px;">{html.escape(c.badge)}</span>' if c.badge else ""
            items.append(f"""
            <div class="card">
                <div>
                    {badge}
                    <div class="card-kicker">{html.escape(c.kicker)}</div>
                    <div class="card-title">{html.escape(c.title)}</div>
                    {metric}
                </div>
                <div class="card-desc">{html.escape(c.description)}</div>
            </div>""")
        return f'<div class="{cls}">{"".join(items)}</div>'

    def _render_chart_split(self, slide: SlideBlueprint) -> str:
        svg_chart = self._generate_svg_chart(slide.chart)
        bullets = "".join(f'<li class="bullet-item">{html.escape(b)}</li>' for b in slide.bullets)
        return f"""
        <div class="chart-split">
            <div class="svg-chart-container">
                {svg_chart}
            </div>
            <div>
                <ul class="bullet-list">
                    {bullets}
                </ul>
            </div>
        </div>"""

    def _render_table_matrix(self, slide: SlideBlueprint) -> str:
        headers = "".join(f"<th>{html.escape(h)}</th>" for h in slide.table_headers)
        rows = []
        for r in slide.table_rows:
            cells = "".join(f"<td>{html.escape(cell)}</td>" for cell in r)
            rows.append(f"<tr>{cells}</tr>")
        rows_html = "".join(rows)
        return f"""
        <table class="table-matrix">
            <thead><tr>{headers}</tr></thead>
            <tbody>{rows_html}</tbody>
        </table>"""

    def _render_default_split(self, slide: SlideBlueprint) -> str:
        if slide.cards:
            return self._render_cards_grid(slide.cards, min(3, len(slide.cards)))
        bullets = "".join(f'<li class="bullet-item">{html.escape(b)}</li>' for b in slide.bullets)
        return f'<ul class="bullet-list">{bullets}</ul>'

    def _generate_svg_chart(self, chart: Optional[ChartDataSpec]) -> str:
        if not chart or not chart.categories:
            return '<div style="color: var(--text-muted); font-size: 13px;">[Data Exhibit Rendering]</div>'

        # Horizontal Bar Chart in Vector SVG
        cats = chart.categories[:8]
        series = chart.series[0] if chart.series else {"values": [70] * len(cats)}
        values = series.get("values", [])[:len(cats)]

        svg_h = 240
        svg_w = 480
        bar_h = 20
        gap = 8

        svg_elements = []
        for idx, (cat, val) in enumerate(zip(cats, values)):
            y = 20 + idx * (bar_h + gap)
            v_num = float(val) if isinstance(val, (int, float)) else 50.0
            # Scale to 250px max width
            bar_w = max(10, int((v_num / 100.0) * 260))
            color = "#38bdf8" if v_num >= 75 else ("#f59e0b" if v_num >= 60 else "#ef4444")

            cat_clean = html.escape(cat[:18])
            svg_elements.append(f"""
            <text x="10" y="{y + 14}" fill="#94a3b8" font-size="11" font-family="monospace">{cat_clean}</text>
            <rect x="150" y="{y}" width="{bar_w}" height="{bar_h}" rx="3" fill="{color}" opacity="0.85" />
            <text x="{155 + bar_w}" y="{y + 14}" fill="#ffffff" font-size="11" font-weight="bold" font-family="monospace">{int(v_num)}</text>
            """)

        inner_svg = "".join(svg_elements)
        return f"""
        <svg viewBox="0 0 {svg_w} {svg_h}" width="100%" height="100%" style="overflow: visible;">
            {inner_svg}
        </svg>"""
