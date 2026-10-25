"""
Base Engine Adapter Interface for Live AI Retrieval Benchmark (Layer 2).
Fails closed with zero fake data: records exact raw output, status codes, latency, and citations.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import httpx
from pydantic import BaseModel, Field


class EngineRawResponse(BaseModel):
    engine_id: str
    engine_name: str
    model_version: str
    raw_content: str
    citations: List[str] = Field(default_factory=list)
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    status_code: int = 0
    latency_ms: float = 0.0
    error: Optional[str] = None
    queried_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_live: bool = False


class BaseGeoEngineAdapter(ABC):
    """
    Standard interface for all AI answer engine adapters (ChatGPT, Perplexity, Gemini, Claude, Groq).
    """

    engine_id: str
    display_name: str
    default_model: str

    def __init__(self, api_key: str = "", model: str = ""):
        self.api_key = api_key
        self.model = model or self.default_model

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    @abstractmethod
    async def execute_query(
        self,
        prompt: str,
        locale: str = "en-US",
        client: Optional[httpx.AsyncClient] = None
    ) -> EngineRawResponse:
        """
        Executes a live query against the provider's API.
        Must return raw verbatim content, native citations, and accurate status.
        Never fakes or simulates outputs.
        """
        pass
