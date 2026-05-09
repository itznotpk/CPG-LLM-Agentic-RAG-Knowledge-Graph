"""
Tests for ddx/ingest_icd11_full.py

All tests use mocking — no real WHO API calls, no real DB writes, no real embeddings.
"""

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import httpx

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from ddx.ingest_icd11_full import (
    WHOTokenClient,
    WHOAPIClient,
    parse_entity,
    create_embedding_text,
    walk_chapter,
    save_progress,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_http_response(status_code: int, body: dict, method: str = "GET") -> httpx.Response:
    req = httpx.Request(method, "https://example.com")
    return httpx.Response(status_code, json=body, request=req)


def make_token_response(expires_in: int = 3600) -> httpx.Response:
    return make_http_response(
        200,
        {"access_token": "test-token", "expires_in": expires_in},
        method="POST",
    )


# ---------------------------------------------------------------------------
# OAuth2 token tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_oauth_token_caches():
    """First call hits token endpoint; second call within TTL does not."""
    client = WHOTokenClient("id", "secret")
    mock_http = AsyncMock()
    mock_http.post = AsyncMock(return_value=make_token_response(3600))

    token1 = await client.get_token(mock_http)
    token2 = await client.get_token(mock_http)

    assert token1 == "test-token"
    assert token2 == "test-token"
    assert mock_http.post.call_count == 1  # only one network call


@pytest.mark.asyncio
async def test_oauth_token_refresh_on_expiry():
    """Token expires → next call hits the token endpoint again."""
    client = WHOTokenClient("id", "secret")
    mock_http = AsyncMock()
    mock_http.post = AsyncMock(return_value=make_token_response(expires_in=1))

    await client.get_token(mock_http)
    # Force expiry by backdating
    client._expires_at = time.monotonic() - 1.0

    await client.get_token(mock_http)
    assert mock_http.post.call_count == 2


@pytest.mark.asyncio
async def test_oauth_token_refresh_on_401():
    """First API call returns 401 → token re-fetched → request retried and succeeds."""
    client = WHOTokenClient("id", "secret")
    client._token = "stale-token"
    client._expires_at = time.monotonic() + 3600

    entity_data = {"@id": "http://id.who.int/icd/entity/123", "code": "BA00", "title": {"@value": "Title"}}

    call_count = 0

    async def fake_get(url, headers=None, **kwargs):
        nonlocal call_count
        call_count += 1
        req = httpx.Request("GET", url)
        if call_count == 1:
            return httpx.Response(401, json={"error": "unauthorized"}, request=req)
        return httpx.Response(200, json=entity_data, request=req)

    async def fake_post(url, data=None, headers=None, **kwargs):
        client._token = "fresh-token"
        client._expires_at = time.monotonic() + 3600
        return make_token_response()

    mock_http = AsyncMock()
    mock_http.get = fake_get
    mock_http.post = fake_post

    api = WHOAPIClient(client, "2024-01", "mms", "en")
    result = await api.get_entity_by_uri(mock_http, "http://id.who.int/icd/entity/123")
    assert result["code"] == "BA00"
    assert call_count == 2  # one 401, one success


# ---------------------------------------------------------------------------
# Rate-limit / retry tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_429_backoff_then_retry():
    """429 response → backoff → retry → succeed."""
    client = WHOTokenClient("id", "secret")
    client._token = "tok"
    client._expires_at = time.monotonic() + 3600

    entity_data = {"@id": "http://id.who.int/icd/entity/1", "code": "BA00", "title": {"@value": "T"}}
    call_count = 0

    async def fake_get(url, headers=None, **kwargs):
        nonlocal call_count
        req = httpx.Request("GET", url)
        call_count += 1
        if call_count == 1:
            return httpx.Response(429, text="too many requests", request=req)
        return httpx.Response(200, json=entity_data, request=req)

    mock_http = AsyncMock()
    mock_http.get = fake_get

    api = WHOAPIClient(client, "2024-01", "mms", "en")
    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await api._get(mock_http, "http://id.who.int/icd/entity/1")
    assert result["code"] == "BA00"
    assert call_count == 2


@pytest.mark.asyncio
async def test_429_backoff_max_retries():
    """429 forever → RuntimeError after MAX_RETRIES."""
    client = WHOTokenClient("id", "secret")
    client._token = "tok"
    client._expires_at = time.monotonic() + 3600

    async def always_429(url, headers=None, **kwargs):
        req = httpx.Request("GET", url)
        return httpx.Response(429, text="too many", request=req)

    mock_http = AsyncMock()
    mock_http.get = always_429

    api = WHOAPIClient(client, "2024-01", "mms", "en")
    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(RuntimeError, match="rate-limit exceeded"):
            await api._get(mock_http, "http://id.who.int/icd/entity/1")


# ---------------------------------------------------------------------------
# parse_entity tests
# ---------------------------------------------------------------------------

def test_parse_entity_minimal():
    entity = {
        "@id": "http://id.who.int/icd/entity/1",
        "code": "BA00",
        "title": {"@value": "Some condition"},
    }
    result = parse_entity(entity, "11", None)
    assert result is not None
    assert result["code"] == "BA00"
    assert result["title"] == "Some condition"
    assert result["description"] == ""
    assert result["inclusions"] == []
    assert result["exclusions"] == []
    assert result["parent_code"] == ""
    assert result["chapter"] == "11"


def test_parse_entity_full():
    entity = {
        "@id": "http://id.who.int/icd/entity/1",
        "code": "BA01",
        "title": {"@value": "Heart failure"},
        "definition": {"@value": "Inability of heart to pump sufficient blood"},
        "inclusion": [
            {"label": {"@value": "Cardiac failure"}},
            {"label": {"@value": "Myocardial failure"}},
        ],
        "exclusion": [
            {"label": {"@value": "Cardiac arrest (BA41)"}},
        ],
    }
    result = parse_entity(entity, "11", "BA00")
    assert result is not None
    assert result["description"] == "Inability of heart to pump sufficient blood"
    assert result["inclusions"] == ["Cardiac failure", "Myocardial failure"]
    assert result["exclusions"] == ["Cardiac arrest (BA41)"]
    assert result["parent_code"] == "BA00"


def test_parse_entity_skip_no_code():
    entity = {
        "@id": "http://id.who.int/icd/entity/1",
        "code": "",
        "title": {"@value": "Grouping node"},
    }
    result = parse_entity(entity, "11", None)
    assert result is None


def test_parse_entity_handles_inclusion_no_label():
    """Inclusion entry without label.@value is silently skipped."""
    entity = {
        "@id": "http://id.who.int/icd/entity/1",
        "code": "BA02",
        "title": {"@value": "Test"},
        "inclusion": [
            {"label": {"@value": "Valid"}},
            {"no_label_key": "oops"},   # malformed
            {"label": {}},              # empty label dict
        ],
    }
    result = parse_entity(entity, "11", None)
    assert result is not None
    assert result["inclusions"] == ["Valid"]


# ---------------------------------------------------------------------------
# Walker tests
# ---------------------------------------------------------------------------

def _make_entity(uri_id: str, code: str, title: str, children=None) -> dict:
    e = {
        "@id": f"http://id.who.int/icd/entity/{uri_id}",
        "code": code,
        "title": {"@value": title},
        "child": [f"http://id.who.int/icd/entity/{c}" for c in (children or [])],
    }
    return e


@pytest.mark.asyncio
async def test_walker_yields_all_descendants():
    """Synthetic 3-level tree → walker yields all nodes with real codes."""
    # Tree: root (grouping, no code) → A (BA00) → B (BA01), C (BA02)
    root = {"@id": "http://root", "code": "", "title": {"@value": "Root group"},
            "child": ["http://id.who.int/icd/entity/A"]}
    node_a = {"@id": "http://id.who.int/icd/entity/A", "code": "BA00", "title": {"@value": "A"},
               "child": ["http://id.who.int/icd/entity/B", "http://id.who.int/icd/entity/C"]}
    node_b = {"@id": "http://id.who.int/icd/entity/B", "code": "BA01", "title": {"@value": "B"}, "child": []}
    node_c = {"@id": "http://id.who.int/icd/entity/C", "code": "BA02", "title": {"@value": "C"}, "child": []}

    entity_map = {
        "http://id.who.int/icd/entity/A": node_a,
        "http://id.who.int/icd/entity/B": node_b,
        "http://id.who.int/icd/entity/C": node_c,
    }

    mock_api = MagicMock()
    mock_api.get_chapter_root = AsyncMock(return_value=root)
    mock_api.get_entity_by_uri = AsyncMock(side_effect=lambda http, uri: entity_map[uri])

    results = []
    async for rec in walk_chapter(mock_api, MagicMock(), "11", set(), set()):
        results.append(rec)

    codes = [r["code"] for r in results]
    assert sorted(codes) == ["BA00", "BA01", "BA02"]
    assert len(codes) == len(set(codes))  # no duplicates


@pytest.mark.asyncio
async def test_walker_records_parent_code():
    """Walker passes correct parent_code into each parsed entity."""
    root = {"@id": "http://root", "code": "BA00", "title": {"@value": "Root"},
            "child": ["http://id.who.int/icd/entity/child1"]}
    child = {"@id": "http://id.who.int/icd/entity/child1", "code": "BA01",
             "title": {"@value": "Child"}, "child": []}

    mock_api = MagicMock()
    mock_api.get_chapter_root = AsyncMock(return_value=root)
    mock_api.get_entity_by_uri = AsyncMock(return_value=child)

    results = []
    async for rec in walk_chapter(mock_api, MagicMock(), "11", set(), set()):
        results.append(rec)

    child_rec = next(r for r in results if r["code"] == "BA01")
    assert child_rec["parent_code"] == "BA00"


# ---------------------------------------------------------------------------
# Progress file tests
# ---------------------------------------------------------------------------

def test_progress_file_atomic_write(tmp_path, monkeypatch):
    """Atomic write: .tmp replaced by final; .tmp does not exist after success."""
    monkeypatch.setattr("ddx.ingest_icd11_full.DATA_DIR", tmp_path)
    monkeypatch.setattr("ddx.ingest_icd11_full.PROGRESS_FILE", tmp_path / ".icd11_progress.json")
    monkeypatch.setattr("ddx.ingest_icd11_full.PROGRESS_TMP", tmp_path / ".icd11_progress.json.tmp")

    progress = {"completed_chapters": ["08"], "in_progress_chapter": None}
    save_progress(progress)

    final = tmp_path / ".icd11_progress.json"
    tmp = tmp_path / ".icd11_progress.json.tmp"
    assert final.exists()
    assert not tmp.exists()
    data = json.loads(final.read_text())
    assert data["completed_chapters"] == ["08"]


# ---------------------------------------------------------------------------
# Resume tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resume_skips_completed_chapters():
    """Progress lists chapter 08 complete → walker not called for chapter 08."""
    with patch("ddx.ingest_icd11_full.load_progress") as mock_load, \
         patch("ddx.ingest_icd11_full.walk_chapter") as mock_walk, \
         patch("ddx.ingest_icd11_full.generate_embedding", new_callable=AsyncMock), \
         patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect, \
         patch("ddx.ingest_icd11_full.save_progress"):

        mock_load.return_value = {
            "release_id": "2024-01",
            "completed_chapters": ["08"],
            "in_progress_chapter": None,
            "in_progress_entities_done": [],
            "started_at": "2024-01-01T00:00:00+00:00",
            "last_updated_at": "2024-01-01T00:00:00+00:00",
        }

        async def empty_walk(*args, **kwargs):
            return
            yield  # make it an async generator

        mock_walk.side_effect = empty_walk

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"atttypmod": 1536})
        mock_connect.return_value = mock_conn

        from ddx.ingest_icd11_full import ingest_chapters
        await ingest_chapters(chapters=["08"], dry_run=False, resume=True, force_refresh=False)

    # walk_chapter should never have been called for chapter 08
    mock_walk.assert_not_called()


@pytest.mark.asyncio
async def test_resume_skips_completed_entities_within_chapter():
    """Progress lists BA00, BA01 → walk_chapter called with skip_codes containing those."""
    called_skip_codes = []

    async def capture_walk(api, http, chapter, visited, skip_codes, **kwargs):
        called_skip_codes.extend(skip_codes)
        return
        yield

    entity_data = {"@id": "http://root", "code": "", "title": {"@value": "G"}, "child": []}

    with patch("ddx.ingest_icd11_full.walk_chapter", side_effect=capture_walk), \
         patch("ddx.ingest_icd11_full.load_progress") as mock_load, \
         patch("ddx.ingest_icd11_full.save_progress"), \
         patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:

        mock_load.return_value = {
            "release_id": "2024-01",
            "completed_chapters": [],
            "in_progress_chapter": "11",
            "in_progress_entities_done": ["BA00", "BA01"],
            "started_at": "2024-01-01T00:00:00+00:00",
            "last_updated_at": "2024-01-01T00:00:00+00:00",
        }
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"atttypmod": 1536})
        mock_connect.return_value = mock_conn

        from ddx.ingest_icd11_full import ingest_chapters
        await ingest_chapters(chapters=["11"], dry_run=False, resume=True, force_refresh=False)

    assert "BA00" in called_skip_codes
    assert "BA01" in called_skip_codes


# ---------------------------------------------------------------------------
# Dry-run tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dry_run_makes_no_db_writes():
    """In dry-run mode, asyncpg.connect is never called."""
    async def fake_walk(api, http, chapter, visited, skip_codes, **kwargs):
        yield {"code": "BA00", "title": "T", "description": "", "inclusions": [],
               "exclusions": [], "parent_code": "", "chapter": "11"}

    with patch("ddx.ingest_icd11_full.walk_chapter", side_effect=fake_walk), \
         patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect, \
         patch("ddx.ingest_icd11_full.save_progress"):

        from ddx.ingest_icd11_full import ingest_chapters
        await ingest_chapters(chapters=["11"], dry_run=True)

    mock_connect.assert_not_called()


@pytest.mark.asyncio
async def test_dry_run_makes_no_embedding_calls():
    """In dry-run mode, generate_embedding is never called."""
    async def fake_walk(api, http, chapter, visited, skip_codes, **kwargs):
        yield {"code": "BA00", "title": "T", "description": "", "inclusions": [],
               "exclusions": [], "parent_code": "", "chapter": "11"}

    with patch("ddx.ingest_icd11_full.walk_chapter", side_effect=fake_walk), \
         patch("ddx.ingest_icd11_full.generate_embedding", new_callable=AsyncMock) as mock_embed, \
         patch("ddx.ingest_icd11_full.save_progress"):

        from ddx.ingest_icd11_full import ingest_chapters
        await ingest_chapters(chapters=["11"], dry_run=True)

    mock_embed.assert_not_called()


# ---------------------------------------------------------------------------
# Embedding text format tests
# ---------------------------------------------------------------------------

def test_embedding_text_format_title_only():
    record = {"title": "Heart failure", "description": "", "inclusions": []}
    assert create_embedding_text(record) == "Heart failure"


def test_embedding_text_format_full():
    record = {
        "title": "Heart failure",
        "description": "Inability of the heart to pump blood",
        "inclusions": ["Cardiac failure", "Myocardial failure"],
    }
    result = create_embedding_text(record)
    assert result == ("Heart failure. Inability of the heart to pump blood. "
                      "Also known as: Cardiac failure, Myocardial failure")
