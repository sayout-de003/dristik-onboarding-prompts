"""
Dristik AI Mission Director
Top-level strategic mission planner and dynamic capability selector.
Decomposes user objectives into an adaptive execution plan tailored to site complexity and business type.
"""
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from app.core.config import settings
from app.orchestration.mission.state import MissionState, WebsiteTarget, MissionObjective, BudgetState
from app.orchestration.mission.policies import get_industry_policy
from app.domain.capability import CAPABILITY_REGISTRY, CapabilityDomain, ExecutionTier

class MissionDirector:
    """
    Deconstructs high-level audit intents into concrete, budgeted cognitive mission DAGs.
    """

    def create_mission(
        self,
        target_url: str,
        audit_type: str = "standard_growth",
        industry: Optional[str] = None,
        competitors: Optional[List[str]] = None,
        max_pages: Optional[int] = None,
        budget_usd: Optional[float] = None,
        org_id: str = "org_default",
        workspace_id: str = "ws_default"
    ) -> MissionState:
        parsed = urlparse(target_url)
        domain = parsed.netloc.lower()
        if ":" in domain:
            domain = domain.split(":")[0]

        # Audit mode presets
        depth_map = {
            "quick": 1,
            "standard_growth": 2,
            "deep_enterprise": 3,
            "competitive_intel": 3,
            "ai_visibility": 2
        }
        budget_map = {
            "quick": 0.10,
            "standard_growth": 0.25,
            "deep_enterprise": 0.50,
            "competitive_intel": 0.40,
            "ai_visibility": 0.25
        }

        depth = depth_map.get(audit_type, 2)
        effective_budget = budget_usd or budget_map.get(audit_type, 0.25)
        effective_pages = max_pages or (5 if audit_type == "quick" else settings.MAX_CRAWL_PAGES)

        target = WebsiteTarget(
            url=target_url,
            domain=domain,
            industry=industry,
            competitors=competitors or []
        )

        objective = MissionObjective(
            audit_type=audit_type,
            depth=depth,
            max_pages=effective_pages,
            budget_usd=effective_budget,
            deadline_seconds=180 if audit_type == "quick" else 300
        )

        import uuid
        mission_id = f"msn_{uuid.uuid4().hex[:10]}"

        policy = "ECONOMY" if audit_type == "quick" else ("ENTERPRISE" if audit_type == "deep_enterprise" else "BALANCED")

        return MissionState(
            mission_id=mission_id,
            org_id=org_id,
            workspace_id=workspace_id,
            target=target,
            objective=objective,
            budget=BudgetState(
                max_budget_usd=effective_budget,
                policy=policy
            )
        )

    def select_capabilities_for_mission(self, mission_state: MissionState, site_type: str = "general") -> Dict[str, List[str]]:
        """
        Dynamically activates capabilities based on site type, audit depth, and budget.
        Activates appropriate capabilities for lightweight or specific sites.
        """
        audit_type = mission_state.objective.audit_type

        tier_1_deterministic = [
            "01_discovery", "02_semantic_structure", "03_indexability", "04_link_architecture",
            "05_performance", "06_security", "07_asset_optimization", "08_mobile_readiness",
            "09_schema_syntax", "11_opengraph_metadata", "19_readability", "21_cannibalization"
        ]

        # 35-capability routing taxonomy for deterministic $0 pre-pass and legacy routing.
        # Active workforce executes 105 specialist agents across 12 domains via AGENT_REGISTRY.
        all_ids = list(CAPABILITY_REGISTRY.keys())
        tier_2_business = [c for c in all_ids if c.startswith("1") and c.split("_")[0] in {"12", "13", "14", "15", "16"}]
        tier_3_specialists = [
            c for c in all_ids
            if c.split("_")[0] in {
                "10", "17", "18", "20", "22", "23", "24", "25",
                "26", "27", "28", "29", "30", "31", "32", "33",
            }
        ]
        tier_4_verification = ["34_adversarial_verification", "35_contradiction_resolution"]

        if audit_type == "quick":
            tier_2_business = ["12_positioning", "13_icp_alignment"]
            tier_3_specialists = ["22_direct_extractability", "26_ai_discoverability"]
            tier_4_verification = ["34_adversarial_verification"]

        return {
            "tier_1_deterministic": tier_1_deterministic,
            "tier_2_business": tier_2_business,
            "tier_3_specialists": tier_3_specialists,
            "tier_4_verification": tier_4_verification,
            "all": all_ids,
        }
