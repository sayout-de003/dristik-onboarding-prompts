"""
Claude / Anthropic Engine Adapter.
Queries Anthropic's Messages API to evaluate brand retrieval and technical synthesis.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional
import httpx

from app.geo.adapters.base import BaseGeoEngineAdapter, EngineRawResponse

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_TIMEOUT_SECONDS = 14.0


class ClaudeAdapter(BaseGeoEngineAdapter):
    engine_id = "claude"
    display_name = "Claude (Anthropic)"
    default_model = "claude-3-5-haiku-20241022"

    async def execute_query(
        self,
        prompt: str,
        locale: str = "en-US",
        client: Optional[httpx.AsyncClient] = None
    ) -> EngineRawResponse:
        start_time = time.perf_counter()

        if not self.is_configured():
            return EngineRawResponse(
                engine_id=self.engine_id,
                engine_name=self.display_name,
                model_version=self.model,
                raw_content="",
                status_code=401,
                error="Missing ANTHROPIC_API_KEY. Configure in backend/.env to query Claude.",
                is_live=False,
            )

        headers = {
            "x-api-key": self.api_key.strip(),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": 350,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "system": "You are a commercial knowledge engine. Answer objectively and concisely with facts, naming companies and citing verified sources."
        }

        async def _call(c: httpx.AsyncClient) -> EngineRawResponse:
            try:
                res = await c.post(ANTHROPIC_API_URL, headers=headers, json=payload, timeout=DEFAULT_TIMEOUT_SECONDS)
                latency = round((time.perf_counter() - start_time) * 1000, 1)

                if res.status_code == 200:
                    data = res.json()
                    content_blocks = data.get("content", [])
                    raw_text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")

                    citations = re.findall(r"https?://[^\s\)\],>'\"]+", raw_text)

                    return EngineRawResponse(
                        engine_id=self.engine_id,
                        engine_name=self.display_name,
                        model_version=self.model,
                        raw_content=raw_text,
                        citations=citations,
                        status_code=200,
                        is_live=True,
                        latency_ms=latency,
                    )
                else:
                    logger.warning(
                        f"[ClaudeAdapter] HTTP {res.status_code} from Anthropic API (model: {self.model}): {res.text[:300]}"
                    )
                    return EngineRawResponse(
                        engine_id=self.engine_id,
                        engine_name=self.display_name,
                        model_version=self.model,
                        raw_content="",
                        status_code=res.status_code,
                        latency_ms=latency,
                        error=f"HTTP {res.status_code}: {res.text[:200]}",
                    )
            except httpx.TimeoutException:
                latency = round((time.perf_counter() - start_time) * 1000, 1)
                return EngineRawResponse(
                    engine_id=self.engine_id,
                    engine_name=self.display_name,
                    model_version=self.model,
                    raw_content="",
                    status_code=504,
                    latency_ms=latency,
                    error=f"Timeout after {DEFAULT_TIMEOUT_SECONDS}s contacting Claude API.",
                )
            except Exception as exc:
                latency = round((time.perf_counter() - start_time) * 1000, 1)
                return EngineRawResponse(
                    engine_id=self.engine_id,
                    engine_name=self.display_name,
                    model_version=self.model,
                    raw_content="",
                    status_code=500,
                    latency_ms=latency,
                    error=f"Request error: {exc}",
                )

        if client:
            return await _call(client)
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as local_client:
            return await _call(local_client)
