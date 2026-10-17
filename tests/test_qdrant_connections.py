"""Shared clients must survive operations and isolate connection settings."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from qdrant_client.http.exceptions import ResponseHandlingException

from src.pipeline import pipeline
from src.pipeline.settings import RagSettings


@pytest.fixture
def client_factory(monkeypatch):
    pipeline.close_qdrant_clients()
    factory = Mock(side_effect=lambda **kwargs: Mock())
    monkeypatch.setattr("qdrant_client.QdrantClient", factory)
    monkeypatch.setenv("OCI_QDRANT_URL", "http://127.0.0.1:6335")
    monkeypatch.setenv("OCI_QDRANT_API_KEY", "")
    yield factory
    pipeline.close_qdrant_clients()


def test_concurrent_queries_share_one_client_with_keepalive(client_factory):
    settings = RagSettings()
    with ThreadPoolExecutor(max_workers=8) as workers:
        clients = list(workers.map(lambda _: pipeline.get_qdrant_client(settings), range(24)))
    assert all(client is clients[0] for client in clients)
    client_factory.assert_called_once()
    kwargs = client_factory.call_args.kwargs
    assert kwargs["timeout"] == 30
    assert kwargs["limits"].max_keepalive_connections > 0
    assert kwargs["limits"].max_connections == 20
    clients[0].close.assert_not_called()
    pipeline.close_qdrant_clients()
    pipeline.close_qdrant_clients()
    clients[0].close.assert_called_once()
    assert pipeline.get_qdrant_client(settings) is not clients[0]


def test_provider_url_credentials_and_timeout_isolate_clients(client_factory, monkeypatch):
    settings = RagSettings()
    clients = [pipeline.get_qdrant_client(settings)]
    monkeypatch.setenv("OCI_QDRANT_API_KEY", "new-key")
    clients.append(pipeline.get_qdrant_client(settings))
    settings.qdrant.timeout_seconds = 45
    clients.append(pipeline.get_qdrant_client(settings))
    monkeypatch.setenv("OCI_QDRANT_URL", "http://127.0.0.1:6336")
    clients.append(pipeline.get_qdrant_client(settings))
    monkeypatch.setenv("QDRANT_URL", "https://remote.example.com")
    monkeypatch.setenv("QDRANT_API_KEY", "remote-key")
    settings.qdrant.provider = "remote"
    clients.append(pipeline.get_qdrant_client(settings))
    assert len({id(client) for client in clients}) == 5
    assert client_factory.call_args.kwargs["url"] == "https://remote.example.com"
    assert client_factory.call_args.kwargs["api_key"] == "remote-key"


def test_successful_query_retries_timeout_without_reembedding_or_closing(client_factory, monkeypatch):
    settings = RagSettings()
    client = pipeline.get_qdrant_client(settings)
    hit = SimpleNamespace(payload={"chunk_id": "one", "source": "policy", "text": "answer"}, score=1.0)
    client.query_points.side_effect = [
        ResponseHandlingException(httpx.ReadTimeout("timed out")),
        SimpleNamespace(points=[hit]),
    ]
    embed = Mock(return_value=[1.0, 0.0])
    monkeypatch.setattr(pipeline, "embed", embed)
    results = pipeline.retrieve_from_qdrant("question", rag_settings=settings)
    assert results[0]["chunk_id"] == "one"
    assert client.query_points.call_count == 2
    embed.assert_called_once()
    client.close.assert_not_called()


@pytest.mark.parametrize("failure,expected_calls", [
    (ResponseHandlingException(httpx.ReadTimeout("timed out")), 2),
    (ResponseHandlingException(ValueError("invalid response")), 1),
    (ValueError("bad configuration"), 1),
    (httpx.HTTPStatusError("unauthorized", request=httpx.Request("GET", "http://example.com"),
                           response=httpx.Response(401)), 1),
])
def test_read_retries_are_bounded_and_only_for_transport_failures(failure, expected_calls):
    client = Mock()
    client.query_points.side_effect = failure
    with pytest.raises(type(failure)) as caught:
        pipeline._qdrant_read(client, "query_points", retries=1, collection_name="policies")
    assert caught.value is failure
    assert client.query_points.call_count == expected_calls
    client.close.assert_not_called()


def test_ingestion_borrows_client_without_closing(client_factory, monkeypatch):
    settings = RagSettings()
    client = pipeline.get_qdrant_client(settings)
    publisher = Mock(return_value=1)
    monkeypatch.setattr(pipeline, "publish_snapshot", publisher)
    chunks = [pipeline.Chunk("one", "policy", "text", vector=[1.0, 0.0])]
    assert pipeline.persist_chunks_to_qdrant(chunks, collection_name="policies", rag_settings=settings) == 1
    assert publisher.call_args.args[0] is client
    client.close.assert_not_called()


def test_fastapi_shutdown_releases_clients(monkeypatch):
    import asyncio
    from api.main import app, lifespan

    close = Mock()
    monkeypatch.setattr("api.main.close_qdrant_clients", close)

    async def run():
        async with lifespan(app):
            close.assert_not_called()
        close.assert_called_once()

    asyncio.run(run())
