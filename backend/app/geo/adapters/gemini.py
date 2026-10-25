"""
Google Gemini Engine Adapter.
Queries Google's Gemini models with Search Grounding / knowledge graph capabilities.
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional
import httpx

from app.geo.adapters.base import BaseGeoEngineAdapter, EngineRawResponse

GEMINI_OPENAI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
DEFAULT_TIMEOUT_SECONDS = 14.0


class GeminiAdapter(BaseGeoEngineAdapter):
    engine_id = "gemini"
    display_name = "Google Gemini"
    default_model = "gemini-2.0-flash"

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
                error="Missing GEMINI_API_KEY. Configure in backend/.env to query Google Gemini.",
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
                    "content": "You are a commercial knowledge engine. Answer accurately with facts, companies, and authoritative sources."
                },
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 350,
        }

        async def _call(c: httpx.AsyncClient) -> EngineRawResponse:
            try:
                res = await c.post(GEMINI_OPENAI_URL, headers=headers, json=payload, timeout=DEFAULT_TIMEOUT_SECONDS)
                latency = round((time.perf_counter() - start_time) * 1000, 1)

                if res.status_code == 200:
                    data = res.json()
                    choices = data.get("choices", [])
                    content = choices[0].get("message", {}).get("content", "") if choices else ""

                    # Extract inline URL citations or sources
                    citations = re.findall(r"https?://[^\s\)\],>'\"]+", content)

                    return EngineRawResponse(
                        engine_id=self.engine_id,
                        engine_name=self.display_name,
                        model_version=self.model,
                        raw_content=content,
                        citations=citations,
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
                    error=f"Timeout after {DEFAULT_TIMEOUT_SECONDS}s contacting Gemini API.",
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
