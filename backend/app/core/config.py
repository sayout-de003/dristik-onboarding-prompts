"""
Dristik AI Configuration
Loads settings from environment variables with validation.
"""
import os
from pathlib import Path
from typing import Any, Optional, List, Dict
# Attempt to import load_dotenv; if unavailable, define a no-op fallback
try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*args, **kwargs):
        """Fallback dummy load_dotenv when python-dotenv is not installed.
        This ensures the configuration module can be imported without
        raising an ImportError. Environment variables can still be set
        manually or via other means.
        """
        return None
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Ensure backend/.env variables are populated into os.environ for os.environ.get calls
_backend_root = Path(__file__).resolve().parent.parent.parent
for _candidate in (_backend_root / ".env", Path(".env").resolve(), Path("backend/.env").resolve()):
    if _candidate.is_file():
        load_dotenv(dotenv_path=_candidate, override=False)
        break

# Live Anthropic IDs (Claude 3 Haiku / 3.5 Sonnet were retired in 2026).
ANTHROPIC_DEFAULT_FAST = "claude-haiku-4-5-20251001"
ANTHROPIC_DEFAULT_REASONING = "claude-haiku-4-5-20251001"
ANTHROPIC_FALLBACK_MODEL = "claude-sonnet-4-6"
# Groq shut down llama-3.1-8b-instant and llama-3.3-70b-versatile for free/dev
# tiers on 2026-08-16. Live replacements are openai/gpt-oss-* and qwen/qwen3.6-27b.
GROQ_DEFAULT_FAST = "openai/gpt-oss-20b"
GROQ_DEFAULT_REASONING = "openai/gpt-oss-120b"
_GROQ_LIVE_PREFIXES = ("openai/gpt-oss-", "qwen/qwen")
_GROQ_RETIRED_MODELS = {
    "llama-3.1-8b-instant": GROQ_DEFAULT_FAST,
    "llama-3.3-70b-versatile": GROQ_DEFAULT_REASONING,
    "llama3-8b-8192": GROQ_DEFAULT_FAST,
    "llama3-70b-8192": GROQ_DEFAULT_REASONING,
    "gemma2-9b-it": GROQ_DEFAULT_FAST,
    "mixtral-8x7b-32768": GROQ_DEFAULT_REASONING,
    "qwen/qwen3-32b": GROQ_DEFAULT_REASONING,
    "qwen-qwq-32b": GROQ_DEFAULT_REASONING,
    "meta-llama/llama-4-scout-17b-16e-instruct": GROQ_DEFAULT_REASONING,
    "meta-llama/llama-4-maverick-17b-128e-instruct": GROQ_DEFAULT_REASONING,
}
_ANTHROPIC_RETIRED_MODELS = {
    "claude-3-haiku-20240307": ANTHROPIC_DEFAULT_FAST,
    "claude-3-haiku": ANTHROPIC_DEFAULT_FAST,
    "claude-3-5-haiku-20241022": ANTHROPIC_DEFAULT_FAST,
    "claude-3-5-haiku-latest": ANTHROPIC_DEFAULT_FAST,
    "claude-3-5-haiku": ANTHROPIC_DEFAULT_FAST,
    "claude-3-5-sonnet-20241022": ANTHROPIC_DEFAULT_REASONING,
    "claude-3-5-sonnet-20240620": ANTHROPIC_DEFAULT_REASONING,
    "claude-3-5-sonnet-latest": ANTHROPIC_DEFAULT_REASONING,
    "claude-3-5-sonnet": ANTHROPIC_DEFAULT_REASONING,
    "claude-3-7-sonnet-20250219": ANTHROPIC_DEFAULT_REASONING,
    "claude-3-7-sonnet-latest": ANTHROPIC_DEFAULT_REASONING,
    "claude-3-sonnet-20240229": ANTHROPIC_DEFAULT_REASONING,
    "claude-sonnet-4-20250514": ANTHROPIC_DEFAULT_REASONING,
    "claude-3-opus-20240229": "claude-opus-4-6",
    "claude-opus-4-20250514": "claude-opus-4-6",
}


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Dristik AI"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: str = "development"
    # Development/test convenience only; production startup validation rejects DEBUG=True.
    DEBUG: bool = True
    # Number of reverse proxies whose X-Forwarded-For hops may be trusted.
    # Zero means the socket address is the client. A browser cannot raise this.
    TRUSTED_PROXY_HOPS: int = Field(default=0, ge=0, le=5)
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    
    # Multi-Provider LLM Gateway Configuration
    # Supported providers: "auto" | "anthropic" | "gemini" | "groq" | "openrouter" | "together" | "nvidia"
    LLM_PROVIDER: str = Field(default="auto", description="Active LLM Provider: auto | anthropic | gemini | groq | openrouter | together | nvidia")
    
    # Provider-Specific API Keys
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, description="Anthropic API Key (Claude)")
    CLAUDE_API_KEY: Optional[str] = Field(default=None, description="Alternative alias for Anthropic API Key")
    GEMINI_API_KEY: Optional[str] = Field(default=None, description="Google Gemini API Key (AI Studio)")
    GOOGLE_API_KEY: Optional[str] = Field(default=None, description="Alternative alias for Gemini API Key")
    GROQ_API_KEY: Optional[str] = Field(default=None, description="Groq API Key (Free tier available)")
    OPENROUTER_API_KEY: Optional[str] = Field(default=None, description="OpenRouter API Key (Multi-model aggregator)")
    TOGETHER_API_KEY: Optional[str] = Field(default=None, description="Together AI API Key")
    NVIDIA_API_KEY: Optional[str] = Field(default=None, description="NVIDIA API Key (integrate.api.nvidia.com)")
    OPENAI_API_KEY: Optional[str] = Field(default=None, description="OpenAI API Key")
    DEEPSEEK_API_KEY: Optional[str] = Field(default=None, description="DeepSeek API Key")
    PERPLEXITY_API_KEY: Optional[str] = Field(default=None, description="Perplexity API Key")
    XAI_API_KEY: Optional[str] = Field(default=None, description="xAI Grok API Key")
    MOONSHOT_API_KEY: Optional[str] = Field(default=None, description="Moonshot Kimi API Key")
    
    # Generic Overrides (Optional)
    LLM_API_KEY: Optional[str] = Field(default=None, description="Generic LLM API Key override")
    LLM_BASE_URL: Optional[str] = Field(default=None, description="Generic LLM Base URL override")
    
    # Model Configuration (Set LLM_MODEL to apply one model to all tasks, or set FAST/REASONING individually)
    LLM_MODEL: Optional[str] = Field(default=None, description="Global model override for all tasks (e.g. llama-3.1-8b-instant, gemini-2.0-flash)")
    LLM_MODEL_FAST: Optional[str] = None
    LLM_MODEL_REASONING: Optional[str] = None
    LLM_MODEL_CRITIC: Optional[str] = None
    LLM_MODEL_SYNTHESIS: Optional[str] = None

    # Provider specific model overrides
    ANTHROPIC_MODEL: Optional[str] = None
    ANTHROPIC_MODEL_FAST: Optional[str] = None
    ANTHROPIC_MODEL_REASONING: Optional[str] = None
    GROQ_MODEL: Optional[str] = None
    GROQ_MODEL_FAST: Optional[str] = None
    GROQ_MODEL_REASONING: Optional[str] = None
    GEMINI_MODEL: Optional[str] = None
    OPENROUTER_MODEL: Optional[str] = None
    OPENROUTER_MODEL_FAST: Optional[str] = None
    OPENROUTER_MODEL_REASONING: Optional[str] = None
    OPENROUTER_SITE_URL: Optional[str] = Field(default="https://dristik.ai", description="HTTP-Referer header for OpenRouter rankings")
    OPENROUTER_SITE_NAME: Optional[str] = Field(default="Dristik AI", description="X-Title header for OpenRouter rankings")
    TOGETHER_MODEL: Optional[str] = None
    NVIDIA_BASE_URL: str = Field(default="https://integrate.api.nvidia.com/v1", description="NVIDIA NIM Base URL")
    NVIDIA_MODEL: Optional[str] = None
    NVIDIA_MODEL_FAST: Optional[str] = None
    NVIDIA_MODEL_REASONING: Optional[str] = None

    # AI Citation Tracker Engine Configuration
    AI_CITATION_PROVIDER: Optional[str] = Field(default=None, description="Default provider for AI citation engines (e.g. openrouter)")
    AI_CITATION_CROSS_PROVIDER: bool = Field(default=False, description="Enable multi-engine citation tracker fan-out across providers")
    AI_CITATION_CLAUDE_ACTIVE: Optional[bool] = None
    AI_CITATION_CLAUDE_PROVIDER: Optional[str] = None
    AI_CITATION_CLAUDE_API_KEY: Optional[str] = None
    AI_CITATION_CLAUDE_MODEL: Optional[str] = None

    AI_CITATION_LLAMA_ACTIVE: Optional[bool] = None
    AI_CITATION_LLAMA_PROVIDER: Optional[str] = None
    AI_CITATION_LLAMA_API_KEY: Optional[str] = None
    AI_CITATION_LLAMA_MODEL: Optional[str] = None

    AI_CITATION_GEMINI_ACTIVE: Optional[bool] = None
    AI_CITATION_GEMINI_PROVIDER: Optional[str] = None
    AI_CITATION_GEMINI_API_KEY: Optional[str] = None
    AI_CITATION_GEMINI_MODEL: Optional[str] = None

    AI_CITATION_CHATGPT_ACTIVE: Optional[bool] = None
    AI_CITATION_CHATGPT_PROVIDER: Optional[str] = None
    AI_CITATION_CHATGPT_API_KEY: Optional[str] = None
    AI_CITATION_CHATGPT_MODEL: Optional[str] = None

    AI_CITATION_PERPLEXITY_ACTIVE: Optional[bool] = None
    AI_CITATION_PERPLEXITY_PROVIDER: Optional[str] = None
    AI_CITATION_PERPLEXITY_API_KEY: Optional[str] = None
    AI_CITATION_PERPLEXITY_MODEL: Optional[str] = None

    AI_CITATION_DEEPSEEK_ACTIVE: Optional[bool] = None
    AI_CITATION_DEEPSEEK_PROVIDER: Optional[str] = None
    AI_CITATION_DEEPSEEK_API_KEY: Optional[str] = None
    AI_CITATION_DEEPSEEK_MODEL: Optional[str] = None

    AI_CITATION_QWEN_ACTIVE: Optional[bool] = None
    AI_CITATION_QWEN_PROVIDER: Optional[str] = None
    AI_CITATION_QWEN_API_KEY: Optional[str] = None
    AI_CITATION_QWEN_MODEL: Optional[str] = None

    AI_CITATION_GROK_ACTIVE: Optional[bool] = None
    AI_CITATION_GROK_PROVIDER: Optional[str] = None
    AI_CITATION_GROK_API_KEY: Optional[str] = None
    AI_CITATION_GROK_MODEL: Optional[str] = None

    AI_CITATION_KIMI_ACTIVE: Optional[bool] = None
    AI_CITATION_KIMI_PROVIDER: Optional[str] = None
    AI_CITATION_KIMI_API_KEY: Optional[str] = None
    AI_CITATION_KIMI_MODEL: Optional[str] = None

    AI_CITATION_NVIDIA_ACTIVE: Optional[bool] = None
    AI_CITATION_NVIDIA_PROVIDER: Optional[str] = None
    AI_CITATION_NVIDIA_API_KEY: Optional[str] = None
    AI_CITATION_NVIDIA_MODEL: Optional[str] = None

    # Legacy Together AI fields for backwards compatibility
    TOGETHER_BASE_URL: str = "https://api.together.xyz/v1"
    TOGETHER_MODEL_FAST: str = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
    TOGETHER_MODEL_REASONING: str = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    TOGETHER_MODEL_CRITIC: str = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    TOGETHER_MODEL_SYNTHESIS: str = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    
    # Inference Parameters
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 3000
    LLM_TIMEOUT_SECONDS: int = 60
    LLM_MAX_RETRIES: int = 3
    LLM_MAX_CONCURRENCY: int = Field(default=2, description="Max concurrent in-flight requests per LLM provider to eliminate 429 thundering herd")
    ANTHROPIC_RPM: int = Field(default=15, description="Requests per minute limit for Anthropic Messages API")
    ANTHROPIC_TPM: int = Field(default=40000, description="Tokens per minute limit for Anthropic Messages API")
    ENABLE_CROSS_PROVIDER_CASCADE: bool = Field(default=True, description="Cascade to secondary provider if primary provider is exhausted")
    ENABLE_LLM_RESPONSE_CACHE: bool = Field(default=True, description="Enable exact-match in-memory response cache for idempotent queries")
    LLM_CACHE_TTL_SECONDS: int = Field(default=3600, description="TTL in seconds for cached LLM responses")
    MAX_LLM_COPY_PAGES: int = Field(default=4, description="Max strategic high-priority pages to run deep LLM copywriting rewrites on")
    # Actual USD per 1M tokens you pay. Both must be set. They override the
    # published list price for every call the provider did not bill in-band.
    LLM_COST_INPUT_PER_MILLION: Optional[float] = None
    LLM_COST_OUTPUT_PER_MILLION: Optional[float] = None
    # JSON rates for specific models. A provider bill still wins.
    # {"groq/openai/gpt-oss-20b": {"input": 0.075, "output": 0.30}}
    LLM_MODEL_PRICES: Optional[str] = None
    
    # Legacy aliases
    TOGETHER_TEMPERATURE: float = 0.2
    TOGETHER_MAX_TOKENS: int = 3000
    TOGETHER_TIMEOUT_SECONDS: int = 60
    TOGETHER_MAX_RETRIES: int = 3
    
    # Embedding Configuration (HuggingFace local E5-Small & OpenRouter remote)
    EMBEDDING_PROVIDER: str = Field(default="huggingface", description="Embedding provider: huggingface (local) | openrouter")
    EMBEDDING_MODEL: str = Field(default="intfloat/e5-small-v2", description="Embedding model identifier (~130MB, 384-dim)")
    EMBEDDING_API_KEY: Optional[str] = Field(default=None, description="API key if using openrouter embedding provider")
    EMBEDDING_BASE_URL: str = Field(default="https://openrouter.ai/api/v1", description="API base URL for remote embeddings")
    EMBEDDING_DEVICE: str = Field(default="cpu", description="Embedding device for local huggingface: cpu | mps | cuda | auto")
    EMBEDDING_BATCH_SIZE: int = Field(default=32, description="Batch size for generating embeddings")
    HF_TOKEN: Optional[str] = Field(default=None, description="Hugging Face API token for authenticated Hub access and higher rate limits")
    HUGGINGFACE_TOKEN: Optional[str] = Field(default=None, description="Hugging Face API token alias")

    # Crawling & Ingestion
    FIRECRAWL_API_KEY: Optional[str] = None
    MAX_CRAWL_PAGES: Any = Field(default=5, description="Page limit or tier: quick (5) | standard (20) | expanded (50) | deep (500)")
    # Analyzed-URL budgets. These are plan caps, not a promise of an unlimited crawl.
    CRAWL_PAGE_CAP: int = 500
    CRAWL_TIERS: Dict[str, int] = Field(
        default_factory=lambda: {
            "quick": 5,
            "starter": 5,
            "standard": 20,
            "growth": 20,
            "expanded": 50,
            "professional": 50,
            "deep": 500,
            "enterprise": 500,
        }
    )
    CRAWL_TIMEOUT_SECONDS: int = Field(default=15, ge=1, le=120)
    CRAWL_CONCURRENCY: int = Field(default=3, ge=1, le=20)
    JS_RENDER_THIN_PAGES: bool = True
    FIRECRAWL_WAIT_MS: int = 3000
    PLAYWRIGHT_ENABLED: bool = True
    PLAYWRIGHT_TIMEOUT_MS: int = 15000
    PLAYWRIGHT_HEADLESS: bool = True
    USER_AGENT: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

    def get_max_crawl_pages(self, override: Optional[Any] = None) -> int:
        """
        Resolves the analyzed-URL budget.
        quick=5, standard=20, expanded=50, deep=500.
        'all', 'full', and '-1' stay on the deep cap (500). A positive integer
        is accepted up to CRAWL_PAGE_CAP (500). An unknown tier uses quick (5).
        """
        raw = override if override is not None else self.MAX_CRAWL_PAGES
        cap = int(self.CRAWL_PAGE_CAP or 500)
        if isinstance(raw, str):
            s = raw.strip().lower()
            if s in self.CRAWL_TIERS:
                return min(self.CRAWL_TIERS[s], cap)
            if s in ("all", "-1", "full", "max"):
                return min(self.CRAWL_TIERS.get("deep", 500), cap)
            try:
                requested = int(s)
            except ValueError:
                return self.CRAWL_TIERS.get("quick", 5)
            if requested <= 0:
                return min(self.CRAWL_TIERS.get("deep", 500), cap)
            return min(requested, cap)
        try:
            val = int(raw)
        except (ValueError, TypeError):
            return self.CRAWL_TIERS.get("quick", 5)
        if val <= 0:
            return min(self.CRAWL_TIERS.get("deep", 500), cap)
        return min(val, cap)
    
    # Security
    SSRF_PROTECTION_ENABLED: bool = True
    ALLOWED_SCHEMES: List[str] = ["http", "https"]
    AUTH_SECRET: str = Field(default="dristik-dev-secret-change-me", description="Secret used to bind session tokens")
    AUTH_DATABASE_PATH: str = Field(default="data/dristik.db")
    SESSION_DAYS: int = 14
    FRONTEND_URL: str = "http://localhost:5173"
    SYSTEM_ADMIN_EMAIL: str = "admin@dristik.ai"
    SYSTEM_ADMIN_PASSWORD: str = "DristikAdmin1!"
    SYSTEM_ADMIN_NAME: str = "Dristik Admin"
    
    # Budget & Cost Limits
    ANALYSIS_MAX_COST_USD: float = 0.05
    ANALYSIS_MAX_MODEL_CALLS: int = 25
    ANALYSIS_MAX_REASONING_CALLS: int = 6
    ANALYSIS_TIMEOUT_SECONDS: int = 180
    
    # Razorpay Payment Gateway Configuration
    RAZORPAY_KEY_ID: Optional[str] = Field(default=None, description="Razorpay Key ID (e.g. rzp_test_xxx or rzp_live_xxx)")
    RAZORPAY_KEY_SECRET: Optional[str] = Field(default=None, description="Razorpay Key Secret")
    RAZORPAY_WEBHOOK_SECRET: Optional[str] = Field(default=None, description="Razorpay Webhook Secret")
    RAZORPAY_CURRENCY: str = "INR"

    # Crawl resource safety. Enforced against decoded response bytes per URL.
    CRAWL_MAX_RESPONSE_BYTES: int = Field(default=5 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
    CRAWL_MAX_SITEMAP_BYTES: int = Field(default=2 * 1024 * 1024, ge=1024, le=10 * 1024 * 1024)

    # External ground truth. Absent keys stay NOT_CONFIGURED. Never invent the metric.
    CRUX_API_KEY: Optional[str] = Field(default=None, description="Chrome UX Report API key. Not a substitute for lab TTFB.")
    DATAFORSEO_LOGIN: Optional[str] = None
    DATAFORSEO_PASSWORD: Optional[str] = None
    CLEARBIT_API_KEY: Optional[str] = None
    BUILTWITH_API_KEY: Optional[str] = None
    CRUNCHBASE_API_KEY: Optional[str] = None
    G2_API_KEY: Optional[str] = None
    LINKEDIN_API_KEY: Optional[str] = None
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_OAUTH_REDIRECT_URI: Optional[str] = None
    OAUTH_REDIRECT_URI: Optional[str] = None
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    # Optional dedicated SSO client ID/secrets (falls back to GOOGLE_CLIENT_ID / GITHUB_CLIENT_ID if unset)
    GOOGLE_SSO_CLIENT_ID: Optional[str] = None
    GOOGLE_SSO_CLIENT_SECRET: Optional[str] = None
    GITHUB_SSO_CLIENT_ID: Optional[str] = None
    GITHUB_SSO_CLIENT_SECRET: Optional[str] = None
    SHOPIFY_CLIENT_ID: Optional[str] = None
    SHOPIFY_CLIENT_SECRET: Optional[str] = None
    WEBFLOW_CLIENT_ID: Optional[str] = None
    WEBFLOW_CLIENT_SECRET: Optional[str] = None
    HUBSPOT_CLIENT_ID: Optional[str] = None
    HUBSPOT_CLIENT_SECRET: Optional[str] = None
    SALESFORCE_CLIENT_ID: Optional[str] = None
    SALESFORCE_CLIENT_SECRET: Optional[str] = None
    STRIPE_CLIENT_ID: Optional[str] = None
    STRIPE_CLIENT_SECRET: Optional[str] = None
    LINKEDIN_CLIENT_ID: Optional[str] = None
    LINKEDIN_CLIENT_SECRET: Optional[str] = None
    SLACK_CLIENT_ID: Optional[str] = None
    SLACK_CLIENT_SECRET: Optional[str] = None
    INSTAGRAM_CLIENT_ID: Optional[str] = None
    INSTAGRAM_CLIENT_SECRET: Optional[str] = None
    WHATSAPP_BUSINESS_CLIENT_ID: Optional[str] = None
    WHATSAPP_BUSINESS_CLIENT_SECRET: Optional[str] = None
    SLACK_SIGNING_SECRET: Optional[str] = None
    META_APP_SECRET: Optional[str] = None
    META_WEBHOOK_VERIFY_TOKEN: Optional[str] = None
    WORDPRESS_CLIENT_ID: Optional[str] = None
    WORDPRESS_CLIENT_SECRET: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    GA4_PROPERTY_ID: Optional[str] = None

    # ------------------------------------------------------------------
    # External Authority & Entity Intelligence
    # Application credentials only. Customer OAuth tokens are encrypted
    # in the external-authority database and are never read from here.
    # ------------------------------------------------------------------
    GOOGLE_OAUTH_CLIENT_ID: Optional[str] = None
    GOOGLE_OAUTH_CLIENT_SECRET: Optional[str] = None
    GSC_ENABLED: bool = True
    GA4_ENABLED: bool = True
    GBP_ENABLED: bool = True
    GSC_URL_INSPECTION_ENABLED: bool = False
    EXTERNAL_GSC_ROW_LIMIT: int = 250

    BING_WEBMASTER_ENABLED: bool = True
    BING_OAUTH_CLIENT_ID: Optional[str] = None
    BING_OAUTH_CLIENT_SECRET: Optional[str] = None
    BING_OAUTH_REDIRECT_URI: Optional[str] = None
    BING_OAUTH_AUTHORIZE_URL: str = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    BING_OAUTH_TOKEN_URL: str = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    BING_OAUTH_SCOPE: str = "offline_access https://ssl.bing.com/webmaster/api/.default"

    AHREFS_ENABLED: bool = True
    AHREFS_CLIENT_ID: Optional[str] = None
    AHREFS_CLIENT_SECRET: Optional[str] = None
    AHREFS_REDIRECT_URI: Optional[str] = None
    AHREFS_API_KEY: Optional[str] = None
    AHREFS_AUTHORIZE_URL: str = "https://app.ahrefs.com/web/oauth/authorize"
    AHREFS_TOKEN_URL: str = "https://api.ahrefs.com/v3/oauth/token"

    SEMRUSH_ENABLED: bool = True
    SEMRUSH_CLIENT_ID: Optional[str] = None
    SEMRUSH_CLIENT_SECRET: Optional[str] = None
    SEMRUSH_REDIRECT_URI: Optional[str] = None
    SEMRUSH_API_KEY: Optional[str] = None
    SEMRUSH_AUTHORIZE_URL: str = "https://oauth.semrush.com/oauth2/authorize"
    SEMRUSH_TOKEN_URL: str = "https://oauth.semrush.com/oauth2/token"

    MAJESTIC_ENABLED: bool = True
    MAJESTIC_API_KEY: Optional[str] = None

    MOZ_ENABLED: bool = True
    MOZ_API_KEY: Optional[str] = None

    COMMONCRAWL_GRAPH_ENABLED: bool = True

    INDEXNOW_ENABLED: bool = True
    INDEXNOW_KEY: Optional[str] = None
    INDEXNOW_KEY_LOCATION: Optional[str] = None

    SEO_DATA_PROVIDER: Optional[str] = None
    DATAFORSEO_ENABLED: bool = False
    SERPAPI_ENABLED: bool = False
    SERPAPI_KEY: Optional[str] = None

    BRAND_MENTIONS_ENABLED: bool = False
    BRAND_MENTIONS_PROVIDER: Optional[str] = None
    BRAND_MENTIONS_API_KEY: Optional[str] = None
    BRAND_MENTIONS_BASE_URL: Optional[str] = None
    BRAND_MENTIONS_SENTIMENT_ENABLED: bool = False

    CITATIONS_ENABLED: bool = False
    CITATIONS_PROVIDER: Optional[str] = None
    CITATIONS_API_KEY: Optional[str] = None
    CITATIONS_BASE_URL: Optional[str] = None

    EXTERNAL_INTEGRATION_ENCRYPTION_KEY: Optional[str] = None
    OAUTH_STATE_TTL_SECONDS: int = 600
    OAUTH_TOKEN_REFRESH_ENABLED: bool = True
    # Hard-disabled in code. Tokens are never written to logs.
    OAUTH_DEBUG_LOG_TOKENS: bool = False

    EXTERNAL_AUTHORITY_DB_PATH: str = "data/external_authority.db"
    EXTERNAL_COLLECTION_PLAN: str = "STANDARD"
    EXTERNAL_SYNC_ON_AUDIT: bool = False
    EXTERNAL_SYNC_REFRESH_HOURS_FREE: int = 24
    EXTERNAL_SYNC_REFRESH_HOURS_STANDARD: int = 12
    EXTERNAL_SYNC_REFRESH_HOURS_ADVANCED: int = 168
    EXTERNAL_PROVIDER_TIMEOUT_SECONDS: float = 20.0
    EXTERNAL_OAUTH_REDIRECT_URI: Optional[str] = None

    def get_google_sso_client(self) -> tuple[Optional[str], Optional[str]]:
        cid = self.GOOGLE_SSO_CLIENT_ID or self.GOOGLE_CLIENT_ID
        sec = self.GOOGLE_SSO_CLIENT_SECRET or self.GOOGLE_CLIENT_SECRET
        return cid, sec

    def get_external_google_oauth(self) -> tuple[Optional[str], Optional[str]]:
        """Application OAuth client for Search Console, GA4, and Business Profile."""
        cid = self.GOOGLE_OAUTH_CLIENT_ID or self.GOOGLE_CLIENT_ID
        sec = self.GOOGLE_OAUTH_CLIENT_SECRET or self.GOOGLE_CLIENT_SECRET
        return cid, sec

    def external_oauth_redirect_uri(self) -> str:
        explicit = self.EXTERNAL_OAUTH_REDIRECT_URI or self.GOOGLE_OAUTH_REDIRECT_URI
        if explicit and "external-authority" in explicit:
            return explicit
        return "http://localhost:8000/api/v1/external-authority/oauth/callback"

    def registered_google_redirect_uri(self) -> Optional[str]:
        """Callback registered on the Google OAuth client, when one is configured.

        This deployment's client allows the external-authority callback only.
        Sign-in and the Google connectors must send that exact URI.
        """
        explicit = (self.EXTERNAL_OAUTH_REDIRECT_URI or self.GOOGLE_OAUTH_REDIRECT_URI or "").strip()
        if explicit and "external-authority" in explicit:
            return explicit
        return None

    def get_github_sso_client(self) -> tuple[Optional[str], Optional[str]]:
        cid = self.GITHUB_SSO_CLIENT_ID or self.GITHUB_CLIENT_ID
        sec = self.GITHUB_SSO_CLIENT_SECRET or self.GITHUB_CLIENT_SECRET
        return cid, sec

    # Notifications. Missing SMTP reports delivery_status=not_configured.
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    NOTIFY_EMAIL: Optional[str] = None

    # Data Integrity & Production Safety Guardrails
    PRODUCTION_DATA_INTEGRITY_MODE: bool = Field(
        default=True,
        description="Zero-Fake integrity mode: blocks mock payments, fake signatures, and ungrounded fallbacks"
    )
    ALLOW_PAYMENT_TEST_MOCKS: bool = Field(
        default=False,
        description="Strictly for isolated automated tests in non-production environments"
    )

    # Universal AI Connect & External AI Integration
    DRISTIK_CONNECT_FERNET_KEY: Optional[str] = Field(
        default=None,
        description="Fernet symmetric encryption key for secure tenant provider credential storage",
    )
    DRISTIK_MCP_PUBLIC_URL: Optional[str] = Field(
        default=None,
        description="Public internet-accessible HTTPS endpoint for external AI MCP connections",
    )
    DRISTIK_CONNECT_IDENTITY_DOMAIN: str = Field(
        default="connect.dristik.ai",
        description="Domain for issued AI connection identities",
    )
    
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env", "../backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @staticmethod
    def _coerce_groq_model(name: Optional[str], fallback: str) -> str:
        """Map retired Groq IDs to live ones. Keep Groq-hosted openai/ and qwen/ ids."""
        n = (name or "").strip()
        if not n:
            return fallback
        lowered = n.lower()
        if lowered in _GROQ_RETIRED_MODELS:
            return _GROQ_RETIRED_MODELS[lowered]
        if lowered.startswith(_GROQ_LIVE_PREFIXES):
            return n
        if "/" in n or lowered.endswith(":free"):
            return fallback
        return n

    @staticmethod
    def _coerce_anthropic_model(name: Optional[str], fallback: str) -> str:
        """Map retired Claude IDs and reject OpenRouter-style ids for the native Anthropic API."""
        n = (name or "").strip()
        if not n:
            return fallback
        lowered = n.lower()
        if "/" in n or lowered.endswith(":free"):
            return fallback
        return _ANTHROPIC_RETIRED_MODELS.get(lowered, n)

    def get_configured_providers(self) -> List[str]:
        """Returns list of providers with available API keys."""
        configured = []
        if self.ANTHROPIC_API_KEY or self.CLAUDE_API_KEY:
            configured.append("anthropic")
        if self.GEMINI_API_KEY or self.GOOGLE_API_KEY:
            configured.append("gemini")
        if self.GROQ_API_KEY:
            configured.append("groq")
        if self.OPENROUTER_API_KEY:
            configured.append("openrouter")
        if self.TOGETHER_API_KEY:
            configured.append("together")
        if self.NVIDIA_API_KEY:
            configured.append("nvidia")
        if self.LLM_API_KEY:
            configured.append("custom")
        return configured

    def get_active_provider(self) -> str:
        """Determines active provider based on LLM_PROVIDER setting or available keys."""
        prov = (self.LLM_PROVIDER or "auto").lower().strip()
        if prov in ("togetherapi", "together.ai"):
            prov = "together"
        elif prov in ("nvidia", "nvidiaapi", "nim", "integrate.api.nvidia.com"):
            prov = "nvidia"

        if prov != "auto" and prov != "":
            return prov
            
        # Auto-selection priority: anthropic -> gemini -> groq -> openrouter -> together -> nvidia -> custom
        if self.ANTHROPIC_API_KEY or self.CLAUDE_API_KEY:
            return "anthropic"
        if self.GEMINI_API_KEY or self.GOOGLE_API_KEY:
            return "gemini"
        if self.GROQ_API_KEY:
            return "groq"
        if self.OPENROUTER_API_KEY:
            return "openrouter"
        if self.TOGETHER_API_KEY:
            return "together"
        if self.NVIDIA_API_KEY:
            return "nvidia"
        if self.LLM_API_KEY:
            return "custom"
        return "none"

    def get_llm_credentials(self, provider_override: Optional[str] = None) -> dict:
        """
        Resolves (api_key, base_url, model_fast, model_reasoning, provider_name).
        """
        provider = (provider_override or self.get_active_provider()).lower().strip()
        if provider in ("togetherapi", "together.ai"):
            provider = "together"
        elif provider in ("nvidia", "nvidiaapi", "nim", "integrate.api.nvidia.com"):
            provider = "nvidia"
        
        # 0. Anthropic Claude
        if provider in ["anthropic", "claude"]:
            api_key = self.ANTHROPIC_API_KEY or self.CLAUDE_API_KEY or self.LLM_API_KEY
            base_url = self.LLM_BASE_URL or "https://api.anthropic.com/v1"
            # Provider-specific Anthropic models always win over the global LLM_MODEL
            # override (which may be an OpenRouter id like org/model:free).
            fast_model = self._coerce_anthropic_model(
                self.ANTHROPIC_MODEL_FAST or self.ANTHROPIC_MODEL or self.LLM_MODEL_FAST or self.LLM_MODEL,
                ANTHROPIC_DEFAULT_FAST,
            )
            reasoning_model = self._coerce_anthropic_model(
                self.ANTHROPIC_MODEL_REASONING or self.ANTHROPIC_MODEL or self.LLM_MODEL_REASONING or self.LLM_MODEL,
                ANTHROPIC_DEFAULT_REASONING,
            )
            return {
                "provider": "anthropic",
                "display_name": "Anthropic Claude",
                "api_key": api_key,
                "base_url": base_url,
                "model_fast": fast_model,
                "model_reasoning": reasoning_model,
                "extra_headers": {
                    "anthropic-version": "2023-06-01",
                    "x-api-key": api_key or ""
                }
            }
            
        # 1. Google Gemini
        elif provider in ["gemini", "google"]:
            api_key = self.GEMINI_API_KEY or self.GOOGLE_API_KEY or self.LLM_API_KEY
            base_url = self.LLM_BASE_URL or "https://generativelanguage.googleapis.com/v1beta/openai"
            model_override = self.LLM_MODEL or self.GEMINI_MODEL
            fast_model = self.LLM_MODEL_FAST or model_override or "gemini-2.0-flash"
            reasoning_model = self.LLM_MODEL_REASONING or model_override or "gemini-2.0-flash"
            return {
                "provider": "gemini",
                "display_name": "Google Gemini",
                "api_key": api_key,
                "base_url": base_url,
                "model_fast": fast_model,
                "model_reasoning": reasoning_model,
                "extra_headers": {}
            }
            
        # 2. Groq
        elif provider == "groq":
            api_key = self.GROQ_API_KEY or self.LLM_API_KEY
            base_url = self.LLM_BASE_URL or "https://api.groq.com/openai/v1"
            model_override = self.LLM_MODEL or self.GROQ_MODEL
            fast_model = self._coerce_groq_model(
                self.GROQ_MODEL_FAST or self.LLM_MODEL_FAST or model_override,
                GROQ_DEFAULT_FAST,
            )
            reasoning_model = self._coerce_groq_model(
                self.GROQ_MODEL_REASONING or self.LLM_MODEL_REASONING or model_override,
                GROQ_DEFAULT_REASONING,
            )
            return {
                "provider": "groq",
                "display_name": "Groq LPU",
                "api_key": api_key,
                "base_url": base_url,
                "model_fast": fast_model,
                "model_reasoning": reasoning_model,
                "extra_headers": {}
            }
            
        # 3. OpenRouter
        elif provider == "openrouter":
            api_key = self.OPENROUTER_API_KEY or self.LLM_API_KEY
            base_url = self.LLM_BASE_URL or "https://openrouter.ai/api/v1"
            model_override = self.LLM_MODEL or self.OPENROUTER_MODEL
            fast_model = self.OPENROUTER_MODEL_FAST or self.LLM_MODEL_FAST or model_override or "google/gemini-2.0-flash"
            reasoning_model = self.OPENROUTER_MODEL_REASONING or self.LLM_MODEL_REASONING or model_override or "openai/gpt-4o"
            site_url = self.OPENROUTER_SITE_URL or "https://dristik.ai"
            site_name = self.OPENROUTER_SITE_NAME or "Dristik AI"
            return {
                "provider": "openrouter",
                "display_name": "OpenRouter",
                "api_key": api_key,
                "base_url": base_url,
                "model_fast": fast_model,
                "model_reasoning": reasoning_model,
                "extra_headers": {
                    "HTTP-Referer": site_url,
                    "X-Title": site_name
                }
            }
            
        # 4. NVIDIA NIM
        elif provider in ["nvidia", "nvidiaapi", "nim"]:
            api_key = self.NVIDIA_API_KEY or self.LLM_API_KEY
            base_url = self.LLM_BASE_URL or self.NVIDIA_BASE_URL or "https://integrate.api.nvidia.com/v1"
            model_override = self.LLM_MODEL or self.NVIDIA_MODEL
            fast_model = self.NVIDIA_MODEL_FAST or self.LLM_MODEL_FAST or model_override or "nvidia/nemotron-3-super-120b-a12b"
            reasoning_model = self.NVIDIA_MODEL_REASONING or self.LLM_MODEL_REASONING or model_override or "nvidia/nemotron-3-super-120b-a12b"
            return {
                "provider": "nvidia",
                "display_name": "NVIDIA NIM",
                "api_key": api_key,
                "base_url": base_url,
                "model_fast": fast_model,
                "model_reasoning": reasoning_model,
                "extra_headers": {}
            }

        # 5. Together AI (or fallback default)
        else:
            api_key = self.TOGETHER_API_KEY or self.LLM_API_KEY
            base_url = self.LLM_BASE_URL or self.TOGETHER_BASE_URL or "https://api.together.xyz/v1"
            model_override = self.LLM_MODEL or self.TOGETHER_MODEL
            fast_model = self.LLM_MODEL_FAST or self.TOGETHER_MODEL_FAST or model_override or "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
            reasoning_model = self.LLM_MODEL_REASONING or self.TOGETHER_MODEL_REASONING or model_override or "meta-llama/Llama-3.3-70B-Instruct-Turbo"
            return {
                "provider": "together",
                "display_name": "Together AI",
                "api_key": api_key,
                "base_url": base_url,
                "model_fast": fast_model,
                "model_reasoning": reasoning_model,
                "extra_headers": {}
            }

    @property
    def has_active_llm_key(self) -> bool:
        creds = self.get_llm_credentials()
        return bool(creds.get("api_key") and creds["api_key"].strip())


def validate_production_configuration(settings_obj: Settings) -> None:
    """
    Production Startup Safety Check.
    Fails startup immediately if dangerous default secrets or mock configurations are active in production.
    """
    is_prod = settings_obj.ENVIRONMENT.lower() in ("production", "prod")

    if is_prod:
        if settings_obj.DEBUG:
            raise RuntimeError(
                "CRITICAL CONFIGURATION ERROR: DEBUG=True is forbidden in production. Set DEBUG=false."
            )
        if settings_obj.AUTH_SECRET == "dristik-dev-secret-change-me" or len(settings_obj.AUTH_SECRET) < 32:
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: Default or weak AUTH_SECRET detected in production. Set a cryptographically random secret of at least 32 characters."
            )
        if settings_obj.SYSTEM_ADMIN_PASSWORD == "DristikAdmin1!":
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: Default SYSTEM_ADMIN_PASSWORD detected in production. Set a secure password."
            )
        if not settings_obj.FRONTEND_URL.strip().lower().startswith("https://"):
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: FRONTEND_URL must use HTTPS in production."
            )
        if not settings_obj.SSRF_PROTECTION_ENABLED:
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: SSRF_PROTECTION_ENABLED must be True in production."
            )
        if settings_obj.CRAWL_CONCURRENCY < 1 or settings_obj.CRAWL_CONCURRENCY > 20:
            raise RuntimeError(
                "CRITICAL RESOURCE LIMIT ERROR: CRAWL_CONCURRENCY must be between 1 and 20."
            )
        if settings_obj.ALLOW_PAYMENT_TEST_MOCKS:
            raise RuntimeError(
                "CRITICAL DATA INTEGRITY ERROR: ALLOW_PAYMENT_TEST_MOCKS cannot be enabled in production."
            )
        if not settings_obj.PRODUCTION_DATA_INTEGRITY_MODE:
            raise RuntimeError(
                "CRITICAL DATA INTEGRITY ERROR: PRODUCTION_DATA_INTEGRITY_MODE must be True in production."
            )


settings = Settings()
