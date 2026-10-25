"""Bounded HTTP response reads for untrusted crawl targets.

The limit is enforced on decoded chunks, not just Content-Length, because the
header may be absent or dishonest and content can be compressed.
"""
from __future__ import annotations

from typing import Any


class ResponseTooLargeError(ValueError):
    """Raised when a response exceeds the configured decoded-byte budget."""


async def read_response_limited(response: Any, max_bytes: int) -> bytes:
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")

    declared = response.headers.get("content-length")
    if declared:
        try:
            if int(declared) > max_bytes:
                raise ResponseTooLargeError(
                    f"response exceeds configured {max_bytes}-byte limit"
                )
        except ValueError as exc:
            if isinstance(exc, ResponseTooLargeError):
                raise
            # Ignore malformed Content-Length; the streaming limit remains authoritative.

    body = bytearray()
    async for chunk in response.aiter_bytes():
        if not chunk:
            continue
        if len(body) + len(chunk) > max_bytes:
            raise ResponseTooLargeError(
                f"response exceeds configured {max_bytes}-byte limit"
            )
        body.extend(chunk)
    return bytes(body)
