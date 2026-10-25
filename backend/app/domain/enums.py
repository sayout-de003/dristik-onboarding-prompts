"""
Dristik AI Domain Enums
Defines standardized types, severities, stages, and categories.
"""
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class Category(str, Enum):
    TECHNICAL_SEO = "TECHNICAL_SEO"
    ON_PAGE_SEO = "ON_PAGE_SEO"
    CONTENT = "CONTENT"
    GEO = "GEO"
    AI_SEARCH = "AI_SEARCH"
    SCHEMA = "SCHEMA"
    STRUCTURED_DATA = "SCHEMA"
    UX_CONVERSION = "UX_CONVERSION"
    EXPERIENCE = "UX_CONVERSION"
    TRUST_AUTHORITY = "TRUST_AUTHORITY"
    COMPETITIVE = "COMPETITIVE"
    EXTERNAL_AUTHORITY = "EXTERNAL_AUTHORITY"


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    OBSERVED = "observed"
    DERIVED = "derived"
    INFERRED = "inferred"
    UNVERIFIED = "unverified"
    CONTRADICTED = "contradicted"
    PARTIALLY_VERIFIED = "partially_verified"
    PROVISIONAL = "provisional"
    REJECTED = "rejected"
    CONFLICTED = "conflicted"
    CONTESTED = "contested"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_MEASURED = "not_measured"
    PENDING_VERIFICATION = "pending_verification"
    UNSUPPORTED = "unsupported"
    SINGLE_SOURCE_UNVERIFIED = "single_source_unverified"
    VALIDATED = "validated"
    VERIFIED_FIXED = "verified_fixed"
    UNRESOLVED = "unresolved"
    NOT_APPLICABLE = "not_applicable"
    NOT_TESTED = "not_tested"
    UNAVAILABLE = "unavailable"


class SourceIntegrityLabel(str, Enum):
    CORROBORATED = "CORROBORATED"
    CONTESTED = "CONTESTED"
    SINGLE_SOURCE_UNVERIFIED = "SINGLE_SOURCE_UNVERIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class GroundTruthRelation(str, Enum):
    CONFIRMS = "CONFIRMS"
    CONTRADICTS = "CONTRADICTS"
    MISSING_EXTERNAL = "MISSING_EXTERNAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ClaimFamily(str, Enum):
    ICP = "icp"
    PRICING = "pricing"
    PERFORMANCE = "performance"
    TRUST = "trust"
    AUTHORSHIP = "authorship"


class ConfidenceBand(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# ---------------------------------------------------------------------------
# PRIMARY CONFIDENCE MODEL (v2)
# Five-tier rigorous system replacing the GUESSING/LIKELY/CERTAIN rubric.
#
# VERIFIED          — Multiple independent evidence sources OR direct deterministic measurement.
# HIGH_CONFIDENCE   — Strong direct crawl/browser/HTTP evidence.
# MEDIUM_CONFIDENCE — Strong interpretation based on available evidence.
# LOW_CONFIDENCE    — Reasonable hypothesis requiring validation.
# UNVERIFIED        — Insufficient evidence; do NOT present as fact.
#
# Customer-facing display labels (use .customer_label property):
#   VERIFIED          → "Verified"
#   HIGH_CONFIDENCE   → "High confidence"
#   MEDIUM_CONFIDENCE → "Moderate confidence"
#   LOW_CONFIDENCE    → "Low confidence — requires verification"
#   UNVERIFIED        → "Requires verification"
# ---------------------------------------------------------------------------
class EpistemicConfidence(str, Enum):
    VERIFIED          = "VERIFIED"
    HIGH_CONFIDENCE   = "HIGH_CONFIDENCE"
    MEDIUM_CONFIDENCE = "MEDIUM_CONFIDENCE"
    LOW_CONFIDENCE    = "LOW_CONFIDENCE"
    UNVERIFIED        = "UNVERIFIED"

    @property
    def customer_label(self) -> str:
        return {
            "VERIFIED": "Verified",
            "HIGH_CONFIDENCE": "High confidence",
            "MEDIUM_CONFIDENCE": "Moderate confidence",
            "LOW_CONFIDENCE": "Low confidence — requires verification",
            "UNVERIFIED": "Requires verification",
        }[self.value]

    @property
    def affects_score(self) -> bool:
        """Only VERIFIED and HIGH_CONFIDENCE findings feed directly into category scores."""
        return self in (EpistemicConfidence.VERIFIED, EpistemicConfidence.HIGH_CONFIDENCE)


# ---------------------------------------------------------------------------
# BACKWARD-COMPAT RUBRIC (kept so existing tests/agents compile without changes)
# Maps old CERTAIN→VERIFIED, LIKELY→HIGH_CONFIDENCE, GUESSING→LOW_CONFIDENCE.
# New code should use EpistemicConfidence directly.
# The word "GUESSING" must NEVER appear in customer-facing output.
# ---------------------------------------------------------------------------
class RubricConfidence(str, Enum):
    # v2 canonical values
    VERIFIED          = "VERIFIED"
    HIGH_CONFIDENCE   = "HIGH_CONFIDENCE"
    MEDIUM_CONFIDENCE = "MEDIUM_CONFIDENCE"
    LOW_CONFIDENCE    = "LOW_CONFIDENCE"
    UNVERIFIED        = "UNVERIFIED"
    # v1 legacy aliases — do NOT use in new code
    CERTAIN = "CERTAIN"
    LIKELY  = "LIKELY"
    GUESSING = "GUESSING"   # Internal only — never display to customers

    @classmethod
    def from_legacy(cls, value: str) -> "RubricConfidence":
        """Translate old CERTAIN/LIKELY/GUESSING to the new tier."""
        _map = {
            "CERTAIN": cls.VERIFIED,
            "LIKELY": cls.HIGH_CONFIDENCE,
            "GUESSING": cls.LOW_CONFIDENCE,
        }
        return _map.get(value, cls(value))

    @property
    def customer_label(self) -> str:
        """Customer-facing label — never exposes 'GUESSING'."""
        _labels = {
            "VERIFIED": "Verified",
            "HIGH_CONFIDENCE": "High confidence",
            "MEDIUM_CONFIDENCE": "Moderate confidence",
            "LOW_CONFIDENCE": "Low confidence — requires verification",
            "UNVERIFIED": "Requires verification",
            "CERTAIN": "Verified",
            "LIKELY": "High confidence",
            "GUESSING": "Hypothesis — requires verification",
        }
        return _labels.get(self.value, self.value)

    @property
    def is_hypothesis(self) -> bool:
        """True if this finding belongs in the Hypotheses section, not Verified Findings."""
        return self in (
            RubricConfidence.GUESSING,
            RubricConfidence.LOW_CONFIDENCE,
            RubricConfidence.UNVERIFIED,
        )

    @property
    def affects_score(self) -> bool:
        """Only verified/high-confidence findings directly reduce category scores."""
        return self in (
            RubricConfidence.VERIFIED,
            RubricConfidence.HIGH_CONFIDENCE,
            RubricConfidence.CERTAIN,
            RubricConfidence.LIKELY,
        )


class Materiality(str, Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class EvidenceLevel(str, Enum):
    E0_NONE = "E0_NONE"                                 # No evidence
    E1_LLM_ASSERTION = "E1_LLM_ASSERTION"               # Pure model generation (insufficient alone)
    E2_DERIVED = "E2_DERIVED"                           # Derived from supplied evidence
    E3_DETERMINISTIC = "E3_DETERMINISTIC"               # Deterministic parser observation
    E4_FIRST_PARTY_DOM = "E4_FIRST_PARTY_DOM"           # First-party website DOM/HTTP evidence
    E5_AUTHORIZED_EXTERNAL = "E5_AUTHORIZED_EXTERNAL"   # Authorized external API source
    E6_CORROBORATED = "E6_CORROBORATED"                 # Independently corroborated external evidence


class ClaimState(str, Enum):
    CREATED = "CREATED"
    EVIDENCE_REQUIRED = "EVIDENCE_REQUIRED"
    EVIDENCE_ATTACHED = "EVIDENCE_ATTACHED"
    SOURCE_VALIDATED = "SOURCE_VALIDATED"
    CONTRADICTION_CHECK = "CONTRADICTION_CHECK"
    ADVERSARIAL_REVIEW = "ADVERSARIAL_REVIEW"
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    REJECTED = "REJECTED"
    CONFLICTED = "CONFLICTED"
    CONTESTED = "CONTESTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_MEASURED = "NOT_MEASURED"
    SINGLE_SOURCE_UNVERIFIED = "SINGLE_SOURCE_UNVERIFIED"


class ObservationType(str, Enum):
    OBSERVED = "OBSERVED"
    CALCULATED = "CALCULATED"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    HYPOTHESIS = "HYPOTHESIS"
    SIMULATION = "SIMULATION"
    UNKNOWN = "UNKNOWN"


class ClaimType(str, Enum):
    FACT = "fact"
    INFERENCE = "inference"
    RECOMMENDATION = "recommendation"


class ClaimSourceType(str, Enum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    MODEL_ANALYZED = "MODEL_ANALYZED"
    INFERRED = "INFERRED"
    RECOMMENDATION = "RECOMMENDATION"
    UNSUPPORTED = "UNSUPPORTED"


class BusinessIntent(str, Enum):
    LEAD_GENERATION = "lead_generation"
    SAAS = "saas"
    ECOMMERCE = "ecommerce"
    CONTENT_PUBLISHING = "content_publishing"
    PORTFOLIO = "portfolio"
    AGENCY = "agency"
    LOCAL_BUSINESS = "local_business"
    MARKETPLACE = "marketplace"
    EDUCATION = "education"
    MEDIA = "media"
    COMMUNITY = "community"
    DOCUMENTATION = "documentation"
    CORPORATE = "corporate"
    PERSONAL_BRAND = "personal_brand"
    NON_PROFIT = "non_profit"


class EvidenceConfidence(str, Enum):
    CONFIRMED = "Confirmed"       # 0.95–1.00 (deterministic proof)
    STRONG = "Strong Evidence"   # 0.85–0.94
    LIKELY = "Likely"             # 0.70–0.84
    POTENTIAL = "Potential"       # 0.50–0.69
    UNCERTAIN = "Uncertain"       # <0.50


class EvidenceState(str, Enum):
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    ESTIMATED = "ESTIMATED"
    UNAVAILABLE = "UNAVAILABLE"


class EvidenceClass(str, Enum):
    OBSERVED = "OBSERVED"                           # Directly measured
    EXTERNALLY_VERIFIED = "EXTERNALLY_VERIFIED"     # Confirmed via external source
    MODEL_INFERRED = "MODEL_INFERRED"               # LLM interpretation of evidence
    HYPOTHESIS = "HYPOTHESIS"                       # Requires validation
    RECOMMENDATION = "RECOMMENDATION"               # Proposed remediation


class EvidenceScope(str, Enum):
    """How far a finding was actually checked. Independent of evidence class."""
    PAGE_VERIFIED = "PAGE_VERIFIED"
    SAMPLE_VERIFIED = "SAMPLE_VERIFIED"
    ORIGIN_VERIFIED = "ORIGIN_VERIFIED"
    INDEX_OBSERVED = "INDEX_OBSERVED"
    SITE_INFERRED = "SITE_INFERRED"
    EXTERNAL_MEASURED = "EXTERNAL_MEASURED"
    PROVIDER_VERIFIED = "PROVIDER_VERIFIED"
    ACCOUNT_VERIFIED = "ACCOUNT_VERIFIED"
    DOMAIN_VERIFIED = "DOMAIN_VERIFIED"
    PERIOD_VERIFIED = "PERIOD_VERIFIED"
    EXTERNAL_INFERRED = "EXTERNAL_INFERRED"


class EvidenceSubtype(str, Enum):
    # OBSERVED subtypes
    DOM = "DOM"
    HTTP = "HTTP"
    AST = "AST"
    HEADERS = "HEADERS"
    SCREENSHOT = "SCREENSHOT"
    ACCESSIBILITY_TREE = "ACCESSIBILITY_TREE"
    SCHEMA = "SCHEMA"
    # EXTERNALLY_VERIFIED subtypes
    SEARCH = "SEARCH"
    BUSINESS_DIRECTORY = "BUSINESS_DIRECTORY"
    COMPANY_PROFILE = "COMPANY_PROFILE"
    CERTIFICATE_REGISTRY = "CERTIFICATE_REGISTRY"
    GSC = "GSC"
    ANALYTICS = "ANALYTICS"
    # MODEL_INFERRED subtypes
    LLM_INTERPRETATION = "LLM_INTERPRETATION"
    SEMANTIC_SYNTHESIS = "SEMANTIC_SYNTHESIS"
    COGNITIVE_REASONING = "COGNITIVE_REASONING"
    # HYPOTHESIS subtypes
    SINGLE_SOURCE_UNVERIFIED = "SINGLE_SOURCE_UNVERIFIED"
    WORKING_HYPOTHESIS = "WORKING_HYPOTHESIS"
    UNVERIFIED_ANOMALY = "UNVERIFIED_ANOMALY"
    # RECOMMENDATION subtypes
    CODE_PATCH = "CODE_PATCH"
    CONFIG_CHANGE = "CONFIG_CHANGE"
    CONTENT_REWRITE = "CONTENT_REWRITE"
    STRATEGIC_DIRECTIVE = "STRATEGIC_DIRECTIVE"


# ---------------------------------------------------------------------------
# FINDING LIFECYCLE STATE MACHINE
# OPEN → ACKNOWLEDGED → RECOMMENDED → PATCH_READY → APPROVED → APPLIED → VALIDATED
#                                                                         ↓
#                                                                      REGRESSED
#                                               ↓
#                                            BLOCKED
# ---------------------------------------------------------------------------
class FindingLifecycle(str, Enum):
    OPEN          = "OPEN"
    ACKNOWLEDGED  = "ACKNOWLEDGED"
    RECOMMENDED   = "RECOMMENDED"
    PATCH_READY   = "PATCH_READY"
    APPROVED      = "APPROVED"
    APPLIED       = "APPLIED"
    VALIDATED     = "VALIDATED"
    REGRESSED     = "REGRESSED"
    BLOCKED       = "BLOCKED"


# ---------------------------------------------------------------------------
# EVIDENCE SOURCE TYPE — what kind of signal produced this evidence?
# MODEL_INFERENCE is NOT equivalent to direct measurement.
# ---------------------------------------------------------------------------
class EvidenceSourceType(str, Enum):
    CRAWL           = "CRAWL"
    BROWSER         = "BROWSER"
    HTML            = "HTML"
    HTTP            = "HTTP"
    ROBOTS          = "ROBOTS"
    SITEMAP         = "SITEMAP"
    LIGHTHOUSE      = "LIGHTHOUSE"
    SCHEMA          = "SCHEMA"
    SEARCH_ENGINE   = "SEARCH_ENGINE"
    AI_ENGINE       = "AI_ENGINE"
    EXTERNAL_SOURCE = "EXTERNAL_SOURCE"
    USER_PROVIDED   = "USER_PROVIDED"
    CONNECTOR       = "CONNECTOR"
    MODEL_INFERENCE = "MODEL_INFERENCE"   # NOT equivalent to direct evidence


# ---------------------------------------------------------------------------
# QUERY CLASSES — for AI engine queries and simulations
# ---------------------------------------------------------------------------
class QueryClass(str, Enum):
    BRAND         = "BRAND"
    CATEGORY      = "CATEGORY"
    COMMERCIAL    = "COMMERCIAL"
    INFORMATIONAL = "INFORMATIONAL"
    PROBLEM       = "PROBLEM"
    COMPARISON    = "COMPARISON"
    ALTERNATIVE   = "ALTERNATIVE"
    BEST_OF       = "BEST_OF"
    LOCAL         = "LOCAL"
    TRANSACTIONAL = "TRANSACTIONAL"
    BUYER_INTENT  = "BUYER_INTENT"


# ---------------------------------------------------------------------------
# CONTRADICTION RESOLUTION STATUS
# ---------------------------------------------------------------------------
class ContradictionStatus(str, Enum):
    UNRESOLVED         = "UNRESOLVED"
    RESOLVED           = "RESOLVED"
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"
    STALE_EVIDENCE     = "STALE_EVIDENCE"
    SCOPE_DIFFERENCE   = "SCOPE_DIFFERENCE"


# ---------------------------------------------------------------------------
# AI VISIBILITY MEASUREMENT STATUS
# ---------------------------------------------------------------------------
class AiVisibilityStatus(str, Enum):
    MEASURED        = "MEASURED"        # Actually queried a live engine
    NOT_MEASURED    = "NOT_MEASURED"    # No live query was run
    SIMULATION_ONLY = "SIMULATION_ONLY" # Model-inferred — NOT a real engine result


# ---------------------------------------------------------------------------
# GEO DIMENSION KEYS — indexes into GeoReadinessReport.dimension_scores
# ---------------------------------------------------------------------------
class GeoDimensionKey(str, Enum):
    ENTITY_CLARITY          = "entity_clarity"
    ANSWERABILITY           = "answerability"
    CONTENT_EXTRACTABILITY  = "content_extractability"
    CITATION_READINESS      = "citation_readiness"
    RETRIEVAL_ACCESSIBILITY = "retrieval_accessibility"
    FACTUAL_GROUNDING       = "factual_grounding"
    EXTERNAL_AUTHORITY      = "external_authority"
    AI_ENGINE_VISIBILITY    = "ai_engine_visibility"


class AnalysisStage(str, Enum):
    QUEUED = "queued"
    INGESTING = "ingesting"
    DETERMINISTIC_ANALYSIS = "deterministic_analysis"
    PLANNING = "planning"
    SPECIALIST_EXECUTION = "specialist_execution"
    ADVERSARIAL_VERIFICATION = "adversarial_verification"
    SCORING = "scoring"
    EXECUTIVE_SYNTHESIS = "executive_synthesis"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    STOPPED = "stopped"


class ReleaseStatus(str, Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    AUTO_APPROVED = "AUTO_APPROVED"


class UserRole(str, Enum):
    SYSTEM_ADMIN = "system_admin"
    OWNER = "owner"
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"
    AUDITOR = "auditor"


class DataResidency(str, Enum):
    US = "us-east-1"
    EU = "eu-central-1"
    IN = "ap-south-1"
    GLOBAL = "global"


class PolicyDecisionType(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_HITL = "REQUIRE_HITL"


class PatchRiskLevel(str, Enum):
    SAFE_AUTO = "SAFE_AUTO"                     # Level 1: Meta tags, canonical, json-ld schema, robots.txt
    HUMAN_APPROVAL = "HUMAN_APPROVAL"           # Level 2: Titles, descriptions, hero headlines, FAQ copy
    DEVELOPER_REQUIRED = "DEVELOPER_REQUIRED"   # Level 3: App code, routing, security headers, layout.tsx


class PatchOperation(str, Enum):
    REPLACE = "REPLACE"
    INSERT_HEAD = "INSERT_HEAD"
    INSERT_BODY = "INSERT_BODY"
    UPDATE_JSONLD = "UPDATE_JSONLD"
    UPDATE_FILE = "UPDATE_FILE"
    APPEND_ROBOTS = "APPEND_ROBOTS"


class PatchApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"


class ConnectorType(str, Enum):
    WORDPRESS = "wordpress"
    GITHUB = "github"
    SHOPIFY = "shopify"
    WEBFLOW = "webflow"
    GOOGLE_SEARCH_CONSOLE = "google_search_console"
    GOOGLE_ANALYTICS_4 = "google_analytics_4"
    GOOGLE_ANALYTICS = "google_analytics"
    GOOGLE_BUSINESS_PROFILE = "google_business_profile"
    AHREFS = "ahrefs"
    SEMRUSH = "semrush"
    MAJESTIC = "majestic"
    BACKLINK_API = "backlink_api"
    BUSINESS_DIRECTORIES = "business_directories"
    REVIEW_PLATFORMS = "review_platforms"
    SOCIAL_ENTITY_SOURCES = "social_entity_sources"
    CRM = "crm"
    DATAFORSEO = "dataforseo"
    LIVE_AI_SEARCH = "live_ai_search"
    CRUX = "crux"
    GENERIC = "generic"
    # CMS / publishing providers
    FRAMER = "framer"
    WIX = "wix"
    SANITY = "sanity"
    # SEO data and AI search provider adapters
    OPENAI_SEARCH = "openai_search"
    PERPLEXITY = "perplexity"
    CLAUDE = "claude"
    GEMINI = "gemini"
    # Social distribution
    LINKEDIN = "linkedin"
    X = "x"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    # Messaging and approval channels
    WHATSAPP_BUSINESS = "whatsapp_business"
    TELEGRAM = "telegram"
    SLACK = "slack"
    # CRM and revenue
    HUBSPOT = "hubspot"
    SALESFORCE = "salesforce"
    STRIPE = "stripe"
    # Existing provider aliases remain available for backwards compatibility.


class ConnectorHealthStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    DEGRADED = "degraded"
    AUTH_REQUIRED = "auth_required"
    UNAVAILABLE = "unavailable"
    ERROR = "error"          # Legacy status retained for compatibility
    UNAUTHORIZED = "unauthorized"  # Legacy status retained for compatibility


class CapabilityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"
    NOT_CONNECTED = "NOT_CONNECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    PARTIAL = "PARTIAL"


class EvidenceOrigin(str, Enum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"


class MetricProvenanceState(str, Enum):
    MEASURED = "MEASURED"
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    SIMULATED = "SIMULATED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    NOT_CONNECTED = "NOT_CONNECTED"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"


class FindingClassification(str, Enum):
    VERIFIED_DEFECT = "VERIFIED_DEFECT"
    VERIFIED_OPPORTUNITY = "VERIFIED_OPPORTUNITY"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    AUDIT_SCOPE_LIMITATION = "AUDIT_SCOPE_LIMITATION"
    ANALYSIS_LIMITATION = "ANALYSIS_LIMITATION"


class ImpactLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class FindingStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    FIXED = "FIXED"               # Code deployed by developer
    VERIFIED = "VERIFIED"         # Confirmed resolved by re-crawl / automated retest
    VERIFIED_FIXED = "VERIFIED_FIXED"
    UNRESOLVED = "UNRESOLVED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_TESTED = "NOT_TESTED"
    UNAVAILABLE = "UNAVAILABLE"
    ACCEPTED_RISK = "ACCEPTED_RISK"


class DiagnosticStatus(str, Enum):
    """
    Controlled 6-state status model for audit checks and diagnostic inventory:
    - PASSED: The test ran and the condition was verified satisfied.
    - FAILED: The test ran and a defect was observed with evidence.
    - NOT_TESTED: No test was performed during this audit execution.
    - UNAVAILABLE: Required data, integration (GSC/GA4/PageSpeed), or access was unavailable.
    - INFERRED: A conclusion was inferred rather than directly measured.
    - SAMPLED: Only part of the relevant scope was inspected.
    """
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_TESTED = "NOT_TESTED"
    UNAVAILABLE = "UNAVAILABLE"
    INFERRED = "INFERRED"
    SAMPLED = "SAMPLED"



