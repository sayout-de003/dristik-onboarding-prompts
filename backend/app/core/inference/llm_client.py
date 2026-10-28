"""
Dristik AI Multi-Provider LLM Gateway Client
Unified HTTP client for OpenAI-compatible LLM inference across:
- Google Gemini (gemini-2.0-flash / gemini-1.5-flash via OpenAI endpoint)
- Groq (Ultra-fast LPU inference: Llama 3.3 70B / 3.1 8B / Qwen)
- OpenRouter (Multi-model aggregator: DeepSeek, Gemini, Llama)
- Together AI (Llama 3.3 70B / 3.1 8B Turbo)
Anthropic Claude uses the official anthropic SDK (Messages API).

Includes:
- Asynchronous Token-Bucket Rate Limiter (enforces TPM & RPM constraints)
- Exponential backoff with randomized jitter (2s up to 30s) on HTTP 429 & 503
- Multi-provider cascade (Groq -> Together -> OpenRouter -> Deterministic Fallback)
"""
import asyncio
import copy
import hashlib
import logging
import random
import re
import time
from typing import Dict, Any, Optional, List, Tuple
import httpx
from app.core.config import settings, Settings, ANTHROPIC_DEFAULT_FAST
from app.core.inference.pricing import extract_provider_cost, provider_billed_usd

logger = logging.getLogger("dristik.llm_client")


class RateLimitException(Exception):
    def __init__(self, message: str, retry_after_seconds: float = 5.0):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class NonRetryableLLMError(Exception):
    """Errors that should NOT be retried (HTTP 400, 401, 403, 404, invalid auth, schema rejection)."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class TokenBucketRateLimiter:
    """
    Asynchronous token-bucket rate limiter that enforces both:
    - Requests Per Minute (RPM)
    - Tokens Per Minute (TPM)
    Prevents Groq/Together rate limit exhaustion during 105-agent parallel DAG executions.
    """
    def __init__(self, rpm: int = 30, tpm: int = 25000):
        self.rpm = rpm
        self.tpm = tpm
        self.request_timestamps: List[float] = []
        self.token_history: List[Tuple[float, int]] = []
        self._lock = asyncio.Lock()

    async def acquire(self, estimated_tokens: int = 1200) -> None:
        """
        Wait if necessary until enough RPM and TPM capacity is available in sliding 60s window.
        """
        while True:
            async with self._lock:
                now = time.time()
                window = 60.0

                # Prune records older than 60s
                self.request_timestamps = [t for t in self.request_timestamps if now - t < window]
                self.token_history = [(t, tok) for t, tok in self.token_history if now - t < window]

                # Check RPM
                wait_rpm = 0.0
                if len(self.request_timestamps) >= self.rpm:
                    oldest_req = self.request_timestamps[0]
                    wait_rpm = max(0.05, (oldest_req + window) - now)

                # Check TPM
                current_tokens = sum(tok for _, tok in self.token_history)
                wait_tpm = 0.0
                if current_tokens + estimated_tokens > self.tpm and self.token_history:
                    accum = 0
                    for t, tok in self.token_history:
                        accum += tok
                        if (current_tokens - accum) + estimated_tokens <= self.tpm:
                            wait_tpm = max(0.05, (t + window) - now)
                            break
                    if wait_tpm == 0.0:
                        wait_tpm = max(0.05, (self.token_history[0][0] + window) - now)

                wait_sec = max(wait_rpm, wait_tpm)
                if wait_sec <= 0.01:
                    # Capacity available, reserve and break out
                    self.request_timestamps.append(now)
                    self.token_history.append((now, estimated_tokens))
                    return

            # Wait outside lock with slight randomized jitter
            jitter = random.uniform(0.1, 0.4)
            sleep_duration = min(30.0, wait_sec + jitter)
            logger.debug(
                "[RateLimiter] Throttling request for %.2fs to respect RPM=%d, TPM=%d",
                sleep_duration, self.rpm, self.tpm
            )
            await asyncio.sleep(sleep_duration)


# Global rate limiters per provider to coordinate across concurrent agent tasks
_GLOBAL_RATE_LIMITERS: Dict[str, TokenBucketRateLimiter] = {
    # Groq on-demand / free tier enforces strict 8,000 TPM limit on openai/gpt-oss-* models.
    "groq": TokenBucketRateLimiter(rpm=30, tpm=7500),
    "together": TokenBucketRateLimiter(rpm=60, tpm=50000),
    "nvidia": TokenBucketRateLimiter(rpm=60, tpm=60000),
    "openrouter": TokenBucketRateLimiter(rpm=60, tpm=60000),
    "gemini": TokenBucketRateLimiter(rpm=60, tpm=100000),
    "anthropic": TokenBucketRateLimiter(rpm=getattr(settings, "ANTHROPIC_RPM", 15), tpm=getattr(settings, "ANTHROPIC_TPM", 40000)),
}

# Global in-flight concurrency semaphores to eliminate thundering herd against APIs
_PROVIDER_SEMAPHORES: Dict[str, asyncio.Semaphore] = {}


def get_provider_semaphore(provider: str) -> asyncio.Semaphore:
    """Returns or lazily creates an asyncio.Semaphore for the specified provider."""
    prov = (provider or "unknown").lower()
    if prov not in _PROVIDER_SEMAPHORES:
        concurrency = getattr(settings, "LLM_MAX_CONCURRENCY", 2)
        if prov == "groq":
            # Groq free/on-demand tier has a strict 8,000 TPM limit. Serializing requests prevents 429 storms.
            concurrency = 1
        elif prov in ("anthropic", "claude"):
            concurrency = max(1, getattr(settings, "LLM_MAX_CONCURRENCY", 2))
        else:
            concurrency = max(concurrency, 4)
        _PROVIDER_SEMAPHORES[prov] = asyncio.Semaphore(concurrency)
    return _PROVIDER_SEMAPHORES[prov]

# Global in-memory exact-match response cache for idempotent LLM completions
_RESPONSE_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_RESPONSE_CACHE_MAX_ENTRIES = 1000


def _get_cached_response(key: str) -> Optional[Dict[str, Any]]:
    ttl = float(getattr(settings, "LLM_CACHE_TTL_SECONDS", 3600))
    if key in _RESPONSE_CACHE:
        ts, data = _RESPONSE_CACHE[key]
        if time.time() - ts < ttl:
            res = copy.deepcopy(data)
            res["cached"] = True
            res["latency_ms"] = 0.0
            return res
        else:
            _RESPONSE_CACHE.pop(key, None)
    return None


def _put_cached_response(key: str, data: Dict[str, Any]) -> None:
    now = time.time()
    if len(_RESPONSE_CACHE) >= _RESPONSE_CACHE_MAX_ENTRIES:
        # Prune oldest 20%
        oldest_keys = sorted(_RESPONSE_CACHE.keys(), key=lambda k: _RESPONSE_CACHE[k][0])[:200]
        for k in oldest_keys:
            _RESPONSE_CACHE.pop(k, None)
    _RESPONSE_CACHE[key] = (now, copy.deepcopy(data))


class LLMClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        provider: Optional[str] = None
    ):
        prov = provider or settings.get_active_provider()
        creds = settings.get_llm_credentials(provider_override=prov)
        self.provider = creds.get("provider", "together")
        self.api_key = api_key or creds.get("api_key")
        self.base_url = (base_url or creds.get("base_url", "https://api.together.xyz/v1")).rstrip("/")
        self.timeout = timeout or settings.LLM_TIMEOUT_SECONDS
        self.extra_headers = creds.get("extra_headers", {})

    def _extract_retry_after(self, response: httpx.Response, err_msg: str) -> float:
        """Extracts seconds to wait from Retry-After header or error message text."""
        # 1. Header check
        retry_header = response.headers.get("Retry-After") or response.headers.get("retry-after")
        if retry_header:
            try:
                return float(retry_header)
            except ValueError:
                pass

        # 2. Regex check for 'try again in Xs' or 'in X.Xs'
        match = re.search(r"try again in ([\d\.]+)s", err_msg, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass

        match_ms = re.search(r"try again in ([\d\.]+)ms", err_msg, re.IGNORECASE)
        if match_ms:
            try:
                return float(match_ms.group(1)) / 1000.0
            except ValueError:
                pass

        return 5.0

    async def _generate_anthropic(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Native Anthropic Messages API via the official SDK."""
        import anthropic

        call_timeout = timeout or self.timeout
        # max_retries=0 disables SDK's internal sub-second retry storm so LLMClient coordinates retries with true backoff
        client = anthropic.AsyncAnthropic(
            api_key=self.api_key,
            timeout=float(call_timeout),
            max_retries=0,
        )
        kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": user_prompt or " "}],
        }
        if system_prompt and system_prompt.strip():
            kwargs["system"] = [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ]

        # Anthropic SDK 1.6.0+: 'temperature' is passed via extra_body
        if temperature is not None:
            kwargs["extra_body"] = {"temperature": float(temperature)}

        start_time = time.time()
        logger.info(
            "[LLMClient][anthropic] Sending request: model='%s', max_tokens=%d, prompt_chars=%d",
            model, max_tokens, len(user_prompt or "")
        )
        try:
            message = await client.messages.create(**kwargs)
        except anthropic.RateLimitError as e:
            err_msg = str(e)
            retry_sec = 5.0
            if getattr(e, "response", None) is not None:
                retry_sec = self._extract_retry_after(e.response, err_msg)
            logger.warning("[LLMClient][anthropic] HTTP 429 RateLimitError (retry_after=%.1fs): %s", retry_sec, err_msg)
            raise RateLimitException(
                f"LLM Provider 'anthropic' returned HTTP 429 (Rate Limit): {err_msg}",
                retry_after_seconds=retry_sec,
            )
        except (anthropic.BadRequestError, anthropic.AuthenticationError, anthropic.PermissionDeniedError, anthropic.NotFoundError) as e:
            status_code = getattr(e, "status_code", 400)
            err_msg = getattr(e, "message", None) or str(e)
            logger.error("[LLMClient][anthropic] HTTP %s non-retryable error for model '%s': %s", status_code, model, err_msg)
            raise NonRetryableLLMError(f"Anthropic returned non-retryable HTTP {status_code}: {err_msg}", status_code=status_code)
        except anthropic.APIStatusError as e:
            status_code = getattr(e, "status_code", 500)
            err_msg = getattr(e, "message", None) or str(e)
            if status_code in (500, 502, 503, 504, 529):
                logger.warning("[LLMClient][anthropic] Transient server error HTTP %s: %s", status_code, err_msg)
                raise RateLimitException(f"Anthropic server returned HTTP {status_code}: {err_msg}", retry_after_seconds=3.0)
            logger.error("[LLMClient][anthropic] HTTP %s error for model '%s': %s", status_code, model, err_msg)
            raise NonRetryableLLMError(f"Anthropic returned HTTP {status_code}: {err_msg}", status_code=status_code)
        except anthropic.APIConnectionError as e:
            logger.warning("[LLMClient][anthropic] Connection error: %s", str(e))
            raise RuntimeError(f"Connection failed to LLM endpoint (anthropic): {str(e)}")
        finally:
            await client.close()

        content = "".join(
            block.text for block in message.content if getattr(block, "type", None) == "text"
        )
        usage = message.usage
        latency_ms = (time.time() - start_time) * 1000
        logger.info(
            "[LLMClient][anthropic] Success: model='%s', latency=%.1fms, in_tokens=%d, out_tokens=%d",
            getattr(message, "model", None) or model,
            latency_ms,
            getattr(usage, "input_tokens", 0) or 0,
            getattr(usage, "output_tokens", 0) or 0,
        )
        return {
            "content": content,
            "input_tokens": getattr(usage, "input_tokens", 0) or 0,
            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
            "latency_ms": latency_ms,
            "model": getattr(message, "model", None) or model,
            "provider": self.provider,
            "stop_reason": getattr(message, "stop_reason", None),
            "provider_cost_usd": extract_provider_cost("anthropic", message),
        }

    async def _single_chat_completion(
        self,
        provider: str,
        base_url: str,
        api_key: str,
        extra_headers: Dict[str, str],
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 3000,
        response_format: Any = "DEFAULT",
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Executes a single HTTP chat completion against an OpenAI-compatible endpoint."""
        endpoint = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            **extra_headers
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if response_format == "DEFAULT":
            payload["response_format"] = {"type": "json_object"}
        elif response_format is not None:
            payload["response_format"] = response_format

        logger.info("[LLMClient] Calling %s endpoint (model: '%s')", provider, model)
        start_time = time.time()
        call_timeout = timeout or self.timeout

        async with httpx.AsyncClient(timeout=call_timeout) as client:
            try:
                response = await client.post(endpoint, json=payload, headers=headers)

                # HTTP 429 Rate Limit
                if response.status_code == 429:
                    err_text = response.text
                    try:
                        err_json = response.json()
                        err_msg = err_json.get("error", {}).get("message", err_text)
                    except Exception:
                        err_msg = err_text
                    retry_sec = self._extract_retry_after(response, err_msg)
                    raise RateLimitException(
                        f"LLM Provider '{provider}' returned HTTP 429 (Rate Limit): {err_msg}",
                        retry_after_seconds=retry_sec
                    )

                # HTTP 503 Service Unavailable / Overloaded
                if response.status_code == 503:
                    err_text = response.text
                    raise RateLimitException(
                        f"LLM Provider '{provider}' returned HTTP 503 (Overloaded): {err_text}",
                        retry_after_seconds=3.0
                    )

                # Handle response_format unsupported (400)
                if response.status_code == 400 and ("response_format" in response.text.lower() or "json_object" in response.text.lower()):
                    payload_no_format = dict(payload)
                    payload_no_format.pop("response_format", None)
                    response = await client.post(endpoint, json=payload_no_format, headers=headers)

                if response.status_code != 200:
                    err_text = response.text
                    try:
                        err_json = response.json()
                        err_msg = err_json.get("error", {}).get("message", err_text)
                    except Exception:
                        err_msg = err_text
                    logger.error(
                        "[LLMClient] Provider '%s' returned HTTP %d for model '%s': %s",
                        provider, response.status_code, model, err_msg
                    )
                    if response.status_code in (400, 401, 403, 404, 413):
                        raise NonRetryableLLMError(
                            f"LLM Provider '{provider}' returned non-retryable HTTP {response.status_code}: {err_msg}",
                            status_code=response.status_code,
                        )
                    if response.status_code in (429, 503, 529):
                        retry_sec = self._extract_retry_after(response, err_msg)
                        raise RateLimitException(
                            f"LLM Provider '{provider}' returned HTTP {response.status_code}: {err_msg}",
                            retry_after_seconds=retry_sec,
                        )
                    raise RuntimeError(
                        f"LLM Provider '{provider}' returned HTTP {response.status_code}: {err_msg}"
                    )
                data = response.json()
            except httpx.RequestError as e:
                raise RuntimeError(f"Connection failed to LLM endpoint ({provider}): {str(e)}")

        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {}) or {}
        content = msg.get("content", "") or ""
        reasoning = msg.get("reasoning_content", "") or ""
        if not content.strip() and reasoning:
            content = reasoning
        usage = data.get("usage", {}) or {}
        return {
            "content": content,
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "latency_ms": (time.time() - start_time) * 1000,
            "model": data.get("model") or model,
            "provider": provider,
            "stop_reason": choice.get("finish_reason"),
            "provider_cost_usd": extract_provider_cost(provider, data),
        }

    async def generate_chat_completion(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 3000,
        response_format: Any = "DEFAULT",
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Calls chat completion endpoint with token-bucket rate limiting, exponential backoff
        with randomized jitter on HTTP 429/503, and multi-provider cascade fallback:
        Primary (e.g. Groq) -> Fallback 1 (Anthropic/Together) -> Fallback 2 (OpenRouter).
        """
        # Check in-memory exact-match cache for idempotent completions (temperature <= 0.2)
        cache_key = None
        if temperature <= 0.2 and getattr(settings, "ENABLE_LLM_RESPONSE_CACHE", True):
            cache_payload = f"{model}:{system_prompt}:{user_prompt}:{temperature}:{str(response_format)}"
            cache_key = hashlib.sha256(cache_payload.encode("utf-8")).hexdigest()
            cached_resp = _get_cached_response(cache_key)
            if cached_resp is not None:
                logger.debug("[LLMClient] Response cache HIT for model '%s' (hash: %s...)", model, cache_key[:12])
                return cached_resp

        # Determine candidate provider sequence for cascade
        primary_prov = self.provider or "groq"
        cascade_chain: List[str] = [primary_prov]

        allow_cascade = getattr(settings, "ENABLE_CROSS_PROVIDER_CASCADE", True)
        if allow_cascade:
            if primary_prov == "groq":
                if (settings.ANTHROPIC_API_KEY or settings.CLAUDE_API_KEY) and "anthropic" not in cascade_chain:
                    cascade_chain.append("anthropic")
                if settings.TOGETHER_API_KEY and "together" not in cascade_chain:
                    cascade_chain.append("together")
                if settings.NVIDIA_API_KEY and "nvidia" not in cascade_chain:
                    cascade_chain.append("nvidia")
                if settings.OPENROUTER_API_KEY and "openrouter" not in cascade_chain:
                    cascade_chain.append("openrouter")
            elif primary_prov in ("nvidia", "nvidiaapi", "nim"):
                if (settings.ANTHROPIC_API_KEY or settings.CLAUDE_API_KEY) and "anthropic" not in cascade_chain:
                    cascade_chain.append("anthropic")
                if settings.OPENROUTER_API_KEY and "openrouter" not in cascade_chain:
                    cascade_chain.append("openrouter")
                if settings.TOGETHER_API_KEY and "together" not in cascade_chain:
                    cascade_chain.append("together")
            elif primary_prov == "together":
                if (settings.ANTHROPIC_API_KEY or settings.CLAUDE_API_KEY) and "anthropic" not in cascade_chain:
                    cascade_chain.append("anthropic")
                if settings.NVIDIA_API_KEY and "nvidia" not in cascade_chain:
                    cascade_chain.append("nvidia")
                if settings.OPENROUTER_API_KEY and "openrouter" not in cascade_chain:
                    cascade_chain.append("openrouter")
            elif primary_prov in ("anthropic", "claude"):
                if settings.OPENROUTER_API_KEY and "openrouter" not in cascade_chain:
                    cascade_chain.append("openrouter")
                if settings.NVIDIA_API_KEY and "nvidia" not in cascade_chain:
                    cascade_chain.append("nvidia")
                if settings.GROQ_API_KEY and "groq" not in cascade_chain:
                    cascade_chain.append("groq")

        last_error: Optional[Exception] = None

        for current_prov in cascade_chain:
            # Resolve credentials for current provider in cascade
            if current_prov == self.provider:
                curr_api_key = self.api_key
                curr_base_url = self.base_url
                curr_headers = self.extra_headers
                curr_model = model
            elif current_prov in ("anthropic", "claude"):
                curr_api_key = settings.ANTHROPIC_API_KEY or settings.CLAUDE_API_KEY
                curr_base_url = "https://api.anthropic.com/v1"
                curr_headers = {
                    "anthropic-version": "2023-06-01",
                    "x-api-key": curr_api_key or ""
                }
                curr_model = ANTHROPIC_DEFAULT_FAST
            elif current_prov in ("nvidia", "nvidiaapi", "nim"):
                curr_api_key = settings.NVIDIA_API_KEY
                curr_base_url = settings.NVIDIA_BASE_URL or "https://integrate.api.nvidia.com/v1"
                curr_headers = {}
                curr_model = settings.NVIDIA_MODEL or settings.NVIDIA_MODEL_REASONING or "meta/llama-3.2-11b-vision-instruct"
            elif current_prov == "together":
                curr_api_key = settings.TOGETHER_API_KEY
                curr_base_url = settings.TOGETHER_BASE_URL or "https://api.together.xyz/v1"
                curr_headers = {}
                curr_model = "meta-llama/Llama-3.3-70B-Instruct-Turbo" if "reason" in model.lower() or "120b" in model.lower() else "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
            elif current_prov == "openrouter":
                curr_api_key = settings.OPENROUTER_API_KEY
                curr_base_url = settings.LLM_BASE_URL or "https://openrouter.ai/api/v1"
                curr_headers = {
                    "HTTP-Referer": settings.OPENROUTER_SITE_URL or "https://dristik.ai",
                    "X-Title": settings.OPENROUTER_SITE_NAME or "Dristik AI"
                }
                curr_model = "deepseek/deepseek-chat" if "reason" not in model.lower() else "openai/gpt-4o"
            elif current_prov == "groq":
                curr_api_key = settings.GROQ_API_KEY
                curr_base_url = getattr(settings, "GROQ_BASE_URL", None) or "https://api.groq.com/openai/v1"
                curr_headers = {}
                curr_model = settings.GROQ_MODEL_FAST or "openai/gpt-oss-20b"
            else:
                curr_api_key = self.api_key
                curr_base_url = self.base_url
                curr_headers = self.extra_headers
                curr_model = model

            if not curr_api_key or not curr_api_key.strip():
                continue

            limiter = _GLOBAL_RATE_LIMITERS.get(current_prov)
            call_timeout = timeout or self.timeout

            # Groq-only token clamp to respect 8,000 TPM limit on free/on-demand tier
            effective_max_tokens = max_tokens
            if current_prov == "groq":
                est_prompt = int((len(system_prompt) + len(user_prompt)) / 3.8)
                if est_prompt + max_tokens > 7500:
                    effective_max_tokens = max(350, 7500 - est_prompt)
                    logger.info(
                        "[LLMClient][groq] Clamping max_tokens from %d to %d (prompt est: %d) to stay within 8,000 TPM limit",
                        max_tokens, effective_max_tokens, est_prompt
                    )

            # Max retries per provider with exponential backoff & randomized jitter (2s up to 30s)
            max_retries = max(settings.LLM_MAX_RETRIES, 3)
            sem = get_provider_semaphore(current_prov)

            for attempt in range(max_retries):
                try:
                    # 1. Enforce token-bucket TPM/RPM rate limits before dispatching
                    if limiter:
                        estimated_tokens = len(system_prompt.split()) + len(user_prompt.split()) + int(effective_max_tokens * 0.5)
                        await limiter.acquire(estimated_tokens=estimated_tokens)

                    # 2. Bounded Concurrency Semaphore: at most LLM_MAX_CONCURRENCY in flight
                    async with sem:
                        if current_prov in ["anthropic", "claude"]:
                            anthropic_model = Settings._coerce_anthropic_model(curr_model, ANTHROPIC_DEFAULT_FAST)
                            anthropic_system = system_prompt
                            wants_json = response_format == "DEFAULT" or (
                                isinstance(response_format, dict) and response_format.get("type") == "json_object"
                            )
                            if wants_json:
                                anthropic_system = (
                                    f"{system_prompt or ''}\n\n"
                                    "Respond with a single valid JSON object only. "
                                    "No markdown fences, no preamble, no trailing commentary."
                                    ).strip()
                            anthropic_res = await self._generate_anthropic(
                                model=anthropic_model,
                                system_prompt=anthropic_system,
                                user_prompt=user_prompt,
                                temperature=temperature,
                                max_tokens=max_tokens,
                                timeout=call_timeout,
                            )
                            if cache_key and anthropic_res:
                                _put_cached_response(cache_key, anthropic_res)
                            return anthropic_res

                        completion_res = await self._single_chat_completion(
                            provider=current_prov,
                            base_url=curr_base_url,
                            api_key=curr_api_key,
                            extra_headers=curr_headers,
                            model=curr_model,
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            temperature=temperature,
                            max_tokens=effective_max_tokens,
                            response_format=response_format,
                            timeout=call_timeout,
                        )
                        if cache_key and completion_res:
                            _put_cached_response(cache_key, completion_res)
                        return completion_res

                except RateLimitException as rle:
                    last_error = rle
                    base_delay = 2.0 * (2 ** attempt)
                    jitter = random.uniform(0.5, 2.0)
                    delay = min(30.0, max(2.0, max(rle.retry_after_seconds, base_delay) + jitter))
                    logger.warning(
                        "[LLMClient][%s] Rate limit (429/503/529) on attempt %d/%d. Backing off for %.2fs...",
                        current_prov, attempt + 1, max_retries, delay
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(delay)
                    else:
                        logger.warning("[LLMClient][%s] Exhausted %d retries on rate limits. Cascading.", current_prov, max_retries)
                except NonRetryableLLMError as nre:
                    last_error = nre
                    logger.error(
                        "[LLMClient][%s] Non-retryable error (status=%s): %s. Cascading to next provider.",
                        current_prov, nre.status_code, nre
                    )
                    break
                except Exception as e:
                    last_error = e
                    msg = str(e).lower()
                    if "404" in msg or "does not exist" in msg or "not found" in msg or "unauthorized" in msg or "invalid_api_key" in msg:
                        logger.error("[LLMClient][%s] Non-recoverable error detected: %s. Aborting provider.", current_prov, e)
                        break
                    base_delay = 2.0 * (attempt + 1)
                    jitter = random.uniform(0.2, 1.0)
                    delay = min(30.0, base_delay + jitter)
                    logger.warning(
                        "[LLMClient][%s] Attempt %d/%d failed: %s (%s). Retrying in %.2fs...",
                        current_prov, attempt + 1, max_retries, e, type(e).__name__, delay
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(delay)

        # If cascade exhausted, preserve specific exceptions for callers
        if isinstance(last_error, RateLimitException):
            raise last_error
        if isinstance(last_error, NonRetryableLLMError):
            raise last_error
        raise RuntimeError(f"All LLM providers in cascade failed. Last error: {last_error}")
