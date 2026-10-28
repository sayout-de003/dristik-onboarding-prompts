"""
Dristik AI Full Lifecycle Revenue Intelligence Service

Unifies the 5 stages of business attribution:
Website (DOM & Architecture) -> Search (GSC) -> Visitor (GA4) -> Lead (CRM) -> Revenue Intelligence
"""
from typing import Dict, Any, Optional
from app.domain.models import (
    LifecycleRevenueIntelligence,
    GscAttributionData,
    Ga4AttributionData,
    CrmAttributionData,
)


class LifecycleRevenueService:
    """
    Coordinates multi-connector revenue attribution and grounds conversion bottlenecks.
    """

    def synthesize_lifecycle_intelligence(
        self,
        domain: str,
        gsc_connected: bool = False,
        ga4_connected: bool = False,
        crm_connected: bool = False,
        gsc_data: Optional[GscAttributionData] = None,
        ga4_data: Optional[Ga4AttributionData] = None,
        crm_data: Optional[CrmAttributionData] = None,
    ) -> LifecycleRevenueIntelligence:
        """Use only payloads returned by a live API. A connected flag alone is not a measurement."""
        gsc = gsc_data if gsc_data is not None and gsc_data.is_connected else GscAttributionData(is_connected=False)
        ga4 = ga4_data if ga4_data is not None and ga4_data.is_connected else Ga4AttributionData(is_connected=False)
        crm = crm_data if crm_data is not None and crm_data.is_connected else CrmAttributionData(is_connected=False)

        def _metric(connected: bool, value: Any) -> Any:
            return value if connected else "UNKNOWN"

        stages = {
            "website": {
                "name": "1. Website Architecture",
                "status": "SEE_CRAWL",
                "summary": "Page facts live on the audit. This panel does not repeat invented DOM counts.",
            },
            "search": {
                "name": "2. Search Performance (GSC)",
                "status": "MEASURED" if gsc.is_connected else "NOT_MEASURED",
                "metrics": {
                    "queries_tracked": _metric(gsc.is_connected, len(gsc.queries)),
                    "impressions": _metric(gsc.is_connected, gsc.impressions),
                    "ctr": _metric(gsc.is_connected, f"{gsc.ctr * 100:.1f}%" if gsc.ctr is not None else "UNKNOWN"),
                    "avg_position": _metric(gsc.is_connected, gsc.average_position),
                },
            },
            "visitor": {
                "name": "3. Visitor Engagement (GA4)",
                "status": "MEASURED" if ga4.is_connected else "NOT_MEASURED",
                "metrics": {
                    "engagement_rate": _metric(ga4.is_connected, f"{ga4.engagement_rate * 100:.1f}%" if ga4.engagement_rate is not None else "UNKNOWN"),
                    "conversion_rate": _metric(ga4.is_connected, f"{ga4.conversion_rate * 100:.1f}%" if ga4.conversion_rate is not None else "UNKNOWN"),
                    "abandonment_rate": "UNKNOWN",
                    "cta_click_rate": "UNKNOWN",
                },
            },
            "lead": {
                "name": "4. Lead Generation (CRM)",
                "status": "MEASURED" if crm.is_connected else "NOT_MEASURED",
                "metrics": {
                    "lead_quality": _metric(crm.is_connected, f"{crm.lead_quality_score:.1f}/100" if crm.lead_quality_score is not None else "UNKNOWN"),
                    "active_leads": _metric(
                        crm.is_connected,
                        sum(int(s.get("leads") or 0) for s in crm.lead_source),
                    ),
                },
            },
            "revenue": {
                "name": "5. Revenue Attribution (CRM / Stripe)",
                "status": "MEASURED" if crm.is_connected else "NOT_MEASURED",
                "metrics": {
                    "pipeline_value_inr": _metric(crm.is_connected, crm.pipeline_value_inr),
                    "closed_revenue_inr": _metric(crm.is_connected, crm.closed_revenue_inr),
                },
            },
        }

        measured = sum([gsc.is_connected, ga4.is_connected, crm.is_connected])
        flagged = sum([gsc_connected, ga4_connected, crm_connected])
        if measured:
            summary = f"{measured} connector response(s) included measured rows."
        elif flagged:
            summary = (
                "Connector flags were set, but no live GSC, GA4, or CRM response was supplied. "
                "Impressions, sessions, and revenue stay unmeasured."
            )
        else:
            summary = (
                "GSC, GA4, and CRM are not linked. "
                "Impressions, abandonment, conversion, and revenue are unmeasured."
            )

        return LifecycleRevenueIntelligence(
            domain=domain,
            stages=stages,
            gsc=gsc,
            ga4=ga4,
            crm=crm,
            summary=summary,
        )


lifecycle_service = LifecycleRevenueService()
