"""Keep real Blender RQ integration tests off the supervised production queue."""
import os
from urllib.parse import urlparse

import pytest


@pytest.fixture
def isolated_render_broker(monkeypatch):
    from redis import Redis
    from rq import Queue, Worker

    url = os.getenv("BLENDER_RENDER_TEST_REDIS_URL", "redis://127.0.0.1:6399/1")
    parsed = urlparse(url)
    if (parsed.scheme != "redis" or parsed.hostname not in ("127.0.0.1", "localhost")
            or parsed.port in (None, 6379) or parsed.path != "/1" or parsed.username
            or parsed.password or parsed.query or parsed.fragment):
        pytest.fail("Live RQ tests require isolated loopback DB 1, not production DB 0/port 6379")
    broker = Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
    assert broker.config_get("appendonly").get("appendonly") == "yes", "Test Redis requires AOF"
    assert not Worker.all(connection=broker), "Test Redis DB already has workers"
    assert not Queue("blender-mcp-render-v1", connection=broker).job_ids, "Test queue is not empty"
    monkeypatch.setenv("BLENDER_RENDER_REDIS_URL", url)
    return url
