"""
Perplexity Pro / Sonar Engine Adapter.
Captures live web search citations and synthesized answers directly from Perplexity's API.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
import httpx

from app.geo.adapters.base import BaseGeoEngineAdapter, EngineRawResponse

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
DEFAULT_TIMEOUT_SECONDS = 12.0


class PerplexityAdapter(BaseGeoEngineAdapter):
    engine_id = "perplexity"
    display_name = "Perplexity Pro"
    default_model = "sonar"

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
                error="Missing PERPLEXITY_API_KEY. Configure in backend/.env to query Perplexity.",
                is_live=False,
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a web search answer engine. Answer accurately with facts and citations."
                },
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 400,
            "return_citations": True,
        }

        async def _call(c: httpx.AsyncClient) -> EngineRawResponse:
            try:
                res = await c.post(PERPLEXITY_API_URL, headers=headers, json=payload, timeout=DEFAULT_TIMEOUT_SECONDS)
                latency = round((time.perf_counter() - start_time) * 1000, 1)

                if res.status_code == 200:
                    data = res.json()
                    choices = data.get("choices", [])
                    content = choices[0].get("message", {}).get("content", "") if choices else ""
                    citations = data.get("citations", []) or []
                    return EngineRawResponse(
                        engine_id=self.engine_id,
                        engine_name=self.display_name,
                        model_version=self.model,
                        raw_content=content,
                        citations=[str(c) for c in citations],
                        status_code=200,
                        is_live=True,
                        latency_ms=latency,
                    )
                else:
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
                    error=f"Timeout after {DEFAULT_TIMEOUT_SECONDS}s contacting Perplexity API.",
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
