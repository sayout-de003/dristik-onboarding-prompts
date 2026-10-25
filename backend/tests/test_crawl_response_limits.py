from types import SimpleNamespace

import pytest

from app.crawl.response_limits import ResponseTooLargeError, read_response_limited


class FakeStreamResponse:
    def __init__(self, chunks, content_length=None):
        self.chunks = chunks
        self.headers = {}
        if content_length is not None:
            self.headers["content-length"] = str(content_length)

    async def aiter_bytes(self):
        for chunk in self.chunks:
            yield chunk


@pytest.mark.asyncio
async def test_response_limit_accepts_body_at_limit():
    response = FakeStreamResponse([b"abc", b"de"])
    assert await read_response_limited(response, 5) == b"abcde"


@pytest.mark.asyncio
async def test_response_limit_rejects_oversized_stream_even_without_length():
    response = FakeStreamResponse([b"abc", b"def"])
    with pytest.raises(ResponseTooLargeError, match="configured 5-byte limit"):
        await read_response_limited(response, 5)


@pytest.mark.asyncio
async def test_response_limit_rejects_declared_oversize_before_reading():
    response = FakeStreamResponse([], content_length=100)
    with pytest.raises(ResponseTooLargeError, match="configured 5-byte limit"):
        await read_response_limited(response, 5)


@pytest.mark.asyncio
async def test_response_limit_rejects_non_positive_limit():
    with pytest.raises(ValueError, match="must be positive"):
        await read_response_limited(FakeStreamResponse([]), 0)
