"""
ICD-11 Full Chapter Ingestion Script

Ingests chapters 02, 05, 08, 11, 16, 18, 21 from the WHO ICD-11 API into icd11_codes.
Chapter 17 (HA* codes) is already ingested via ingest_icd11.py — do NOT touch it.

Smoke test:
  python -m ddx.ingest_icd11_full --chapters 11 --dry-run
  Expected: discovers ~400-600 codes in chapter 11, NO DB writes, runs in ~1-2 min.

Full run:
  python -m ddx.ingest_icd11_full --chapters 02,05,08,11,16,18,21
"""

import asyncio
import json
import logging
import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import AsyncGenerator

import httpx
import asyncpg
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
PROGRESS_FILE = DATA_DIR / "icd11_progress.json"       # no leading dot — avoids OneDrive locking issues
PROGRESS_TMP = DATA_DIR / "icd11_progress.json.tmp"

TARGET_CHAPTERS = ["02", "05", "08", "09", "11", "16", "18", "21"]

# Chapter root MMS entity IDs (verified against WHO API 2024-01 release)
CHAPTER_ROOT_IDS = {
    "02": "1630407678",   # Neoplasms
    "05": "21500692",     # Endocrine, nutritional or metabolic diseases
    "08": "1296093776",   # Diseases of the nervous system
    "09": "868865918",    # Diseases of the visual system
    "11": "426429380",    # Diseases of the circulatory system
    "16": "30659757",     # Diseases of the genitourinary system
    "18": "714000734",    # Pregnancy, childbirth or the puerperium
    "21": "1843895818",   # Symptoms, signs or clinical findings, not elsewhere classified
}


# ---------------------------------------------------------------------------
# OAuth2 token client
# ---------------------------------------------------------------------------

class WHOTokenClient:
    TOKEN_URL = "https://icdaccessmanagement.who.int/connect/token"
    SCOPE = "icdapi_access"

    def __init__(self, client_id: str, client_secret: str):
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._expires_at: float = 0.0

    async def get_token(self, http: httpx.AsyncClient) -> str:
        now = time.monotonic()
        if self._token and now < self._expires_at - 60:
            return self._token

        resp = await http.post(
            self.TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": self.SCOPE,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._expires_at = now + data.get("expires_in", 3600)
        return self._token


# ---------------------------------------------------------------------------
# WHO API client
# ---------------------------------------------------------------------------

class WHOAPIClient:
    BASE_URL = "https://id.who.int/icd/release/11"
    MAX_RETRIES = 5
    INITIAL_BACKOFF = 2.0
    MAX_BACKOFF = 60.0

    def __init__(self, token_client: WHOTokenClient, release_id: str,
                 linearization: str, language: str):
        self._token_client = token_client
        self._release_id = release_id
        self._linearization = linearization
        self._language = language
        self._semaphore = asyncio.Semaphore(8)  # max 8 concurrent requests
        self._last_request_time = 0.0

    def _base_headers(self, token: str) -> dict:
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "API-Version": "v2",
            "Accept-Language": self._language,
        }

    async def _get(self, http: httpx.AsyncClient, url: str) -> dict:
        backoff = self.INITIAL_BACKOFF
        for attempt in range(self.MAX_RETRIES + 1):
            async with self._semaphore:
                # Enforce ~8 req/sec: space requests at least 0.125s apart
                now = time.monotonic()
                gap = now - self._last_request_time
                if gap < 0.125:
                    await asyncio.sleep(0.125 - gap)
                self._last_request_time = time.monotonic()

                token = await self._token_client.get_token(http)
                resp = await http.get(url, headers=self._base_headers(token), follow_redirects=True)

            if resp.status_code == 429:
                if attempt >= self.MAX_RETRIES:
                    raise RuntimeError(f"WHO API rate-limit exceeded after {self.MAX_RETRIES} retries: {url}")
                wait = min(backoff, self.MAX_BACKOFF)
                logger.warning("429 rate-limit — waiting %.1fs (attempt %d/%d)", wait, attempt + 1, self.MAX_RETRIES)
                await asyncio.sleep(wait)
                backoff = min(backoff * 2, self.MAX_BACKOFF)
                continue

            if resp.status_code == 401:
                # Force token refresh and retry once
                self._token_client._token = None
                token = await self._token_client.get_token(http)
                async with self._semaphore:
                    resp = await http.get(url, headers=self._base_headers(token), follow_redirects=True)

            resp.raise_for_status()
            return resp.json()

        raise RuntimeError(f"Failed to GET {url} after {self.MAX_RETRIES} retries")

    async def get_entity_by_uri(self, http: httpx.AsyncClient, uri: str) -> dict:
        return await self._get(http, uri)

    async def get_chapter_root(self, http: httpx.AsyncClient, chapter: str) -> dict:
        entity_id = CHAPTER_ROOT_IDS[chapter]
        url = f"{self.BASE_URL}/{self._release_id}/{self._linearization}/{entity_id}"
        return await self._get(http, url)


# ---------------------------------------------------------------------------
# Code parser
# ---------------------------------------------------------------------------

def parse_entity(entity_json: dict, chapter: str, parent_code: str | None) -> dict | None:
    code = entity_json.get("code", "")
    if not code:
        return None

    title_obj = entity_json.get("title", {})
    if isinstance(title_obj, dict):
        title = title_obj.get("@value", "")
    else:
        title = str(title_obj)
    title = title[:255]

    definition_obj = entity_json.get("definition", {})
    if isinstance(definition_obj, dict):
        description = definition_obj.get("@value", "")
    else:
        description = ""

    inclusions = []
    for inc in entity_json.get("inclusion", []):
        try:
            val = inc.get("label", {}).get("@value", "")
            if val:
                inclusions.append(val)
        except (AttributeError, TypeError):
            pass

    exclusions = []
    for exc in entity_json.get("exclusion", []):
        try:
            # exclusions may have label or foundationReference
            label_obj = exc.get("label", {})
            if isinstance(label_obj, dict):
                val = label_obj.get("@value", "")
            else:
                val = ""
            if not val:
                val = exc.get("foundationReference", "")
            if val:
                exclusions.append(val)
        except (AttributeError, TypeError):
            pass

    return {
        "code": code,
        "title": title,
        "description": description,
        "inclusions": inclusions,
        "exclusions": exclusions,
        "parent_code": parent_code or "",
        "chapter": chapter,
    }


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def create_embedding_text(record: dict) -> str:
    parts = [record["title"]]
    if record["description"]:
        parts.append(record["description"])
    if record["inclusions"]:
        parts.append("Also known as: " + ", ".join(record["inclusions"]))
    return ". ".join(parts)


async def generate_embedding(text: str) -> list[float]:
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "openai").lower()

    if embedding_provider == "bedrock":
        import boto3

        bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
        model_id = os.getenv("EMBEDDING_MODEL", "amazon.titan-embed-text-v1")

        def _invoke():
            if "titan" in model_id:
                body = json.dumps({"inputText": text})
            elif "cohere" in model_id:
                body = json.dumps({"texts": [text], "input_type": "search_query"})
            else:
                raise ValueError(f"Unsupported Bedrock embedding model: {model_id}")

            response = bedrock_client.invoke_model(
                modelId=model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            result = json.loads(response["body"].read())
            if "titan" in model_id:
                return result["embedding"]  # native 1536-dim, no truncation
            return result["embeddings"][0]

        return await asyncio.to_thread(_invoke)

    # OpenAI-compatible fallback
    from agent.providers import get_embedding_client, get_embedding_model
    client = get_embedding_client()
    model_name = get_embedding_model()
    response = await client.embeddings.create(input=text, model=model_name)
    return response.data[0].embedding


# ---------------------------------------------------------------------------
# Chapter walker (async generator)
# ---------------------------------------------------------------------------

async def walk_chapter(
    api: WHOAPIClient,
    http: httpx.AsyncClient,
    chapter: str,
    visited: set[str],
    skip_codes: set[str],
    depth: int = 0,
    parent_code: str | None = None,
    entity_uri: str | None = None,
) -> AsyncGenerator[dict, None]:
    assert depth <= 10, f"Tree depth exceeded 10 levels in chapter {chapter}"

    if entity_uri is None:
        entity_json = await api.get_chapter_root(http, chapter)
    else:
        if entity_uri in visited:
            return
        visited.add(entity_uri)
        try:
            entity_json = await api.get_entity_by_uri(http, entity_uri)
        except Exception as e:
            logger.warning("Skipping entity %s: %s", entity_uri, e)
            return

    uri = entity_json.get("@id", entity_uri or "")
    if uri and uri not in visited:
        visited.add(uri)

    record = parse_entity(entity_json, chapter, parent_code)
    if record is not None:
        code = record["code"]
        if code not in skip_codes:
            yield record
        this_parent_code = code
    else:
        # Grouping node — propagate parent down
        this_parent_code = parent_code

    # Recurse into children
    for child_uri in entity_json.get("child", []):
        if isinstance(child_uri, dict):
            child_uri = child_uri.get("@id", "")
        if not child_uri:
            continue
        # Normalize http → https to avoid extra 301 round-trips
        child_uri = child_uri.replace("http://", "https://", 1)
        async for rec in walk_chapter(
            api, http, chapter, visited, skip_codes,
            depth=depth + 1,
            parent_code=this_parent_code,
            entity_uri=child_uri,
        ):
            yield rec


# ---------------------------------------------------------------------------
# Progress tracking
# ---------------------------------------------------------------------------

def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text())
        except Exception:
            pass
    return {
        "release_id": os.getenv("ICD11_API_RELEASE_ID", "2024-01"),
        "completed_chapters": [],
        "in_progress_chapter": None,
        "in_progress_entities_done": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "last_updated_at": datetime.now(timezone.utc).isoformat(),
    }


def save_progress(progress: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    progress["last_updated_at"] = datetime.now(timezone.utc).isoformat()
    PROGRESS_TMP.write_text(json.dumps(progress, indent=2))
    try:
        PROGRESS_TMP.replace(PROGRESS_FILE)
    except PermissionError:
        # Windows / OneDrive may hold a lock on the destination; fall back to
        # delete-then-rename which always works.
        if PROGRESS_FILE.exists():
            PROGRESS_FILE.unlink()
        PROGRESS_TMP.rename(PROGRESS_FILE)


# ---------------------------------------------------------------------------
# Database writer
# ---------------------------------------------------------------------------

UPSERT_SQL = """
INSERT INTO icd11_codes (code, title, description, inclusions, exclusions, parent_code, chapter, embedding)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
ON CONFLICT (code) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    inclusions = EXCLUDED.inclusions,
    exclusions = EXCLUDED.exclusions,
    parent_code = EXCLUDED.parent_code,
    chapter = EXCLUDED.chapter,
    embedding = EXCLUDED.embedding
"""


async def verify_embedding_dimension(conn: asyncpg.Connection) -> int:
    row = await conn.fetchrow(
        "SELECT atttypmod FROM pg_attribute "
        "WHERE attrelid = 'icd11_codes'::regclass AND attname = 'embedding'"
    )
    if row is None:
        raise RuntimeError("icd11_codes.embedding column not found")
    return row["atttypmod"]


# ---------------------------------------------------------------------------
# Main ingestion logic
# ---------------------------------------------------------------------------

async def ingest_chapters(
    chapters: list[str],
    dry_run: bool = False,
    resume: bool = False,
    force_refresh: bool = False,
) -> None:
    client_id = os.getenv("ICD11_API_CLIENT_ID", "")
    client_secret = os.getenv("ICD11_API_CLIENT_SECRET", "")
    release_id = os.getenv("ICD11_API_RELEASE_ID", "2024-01")
    linearization = os.getenv("ICD11_API_LINEARIZATION", "mms")
    language = os.getenv("ICD11_API_LANGUAGE", "en")

    if not client_id or not client_secret:
        raise RuntimeError("ICD11_API_CLIENT_ID and ICD11_API_CLIENT_SECRET must be set")

    token_client = WHOTokenClient(client_id, client_secret)
    api = WHOAPIClient(token_client, release_id, linearization, language)

    progress = load_progress() if resume else {
        "release_id": release_id,
        "completed_chapters": [],
        "in_progress_chapter": None,
        "in_progress_entities_done": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "last_updated_at": datetime.now(timezone.utc).isoformat(),
    }

    conn = None
    if not dry_run:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL not set")
        conn = await asyncpg.connect(database_url)
        dim = await verify_embedding_dimension(conn)
        if dim != 1536:
            await conn.close()
            raise RuntimeError(
                f"icd11_codes.embedding dimension is {dim}, expected 1536. "
                "Run migration 004 first."
            )
        logger.info("Embedding column confirmed: vector(1536)")

    total_start = time.monotonic()
    grand_total = 0
    grand_skipped = 0

    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            for chapter in chapters:
                if chapter not in CHAPTER_ROOT_IDS:
                    logger.error("Unknown chapter %s — skipping", chapter)
                    continue

                if not force_refresh and chapter in progress.get("completed_chapters", []):
                    logger.info("Chapter %s already complete (use --force-refresh to redo)", chapter)
                    continue

                logger.info("=== Chapter %s starting ===", chapter)
                ch_start = time.monotonic()
                progress["in_progress_chapter"] = chapter
                if not resume or chapter not in progress.get("in_progress_entities_done", []):
                    pass  # fresh start for this chapter

                skip_codes: set[str] = set()
                if resume and progress.get("in_progress_chapter") == chapter:
                    skip_codes = set(progress.get("in_progress_entities_done", []))
                    if skip_codes:
                        logger.info("Resuming chapter %s — skipping %d already-done codes", chapter, len(skip_codes))

                visited: set[str] = set()
                batch: list[dict] = []
                ch_count = 0
                ch_skipped = 0

                async for record in walk_chapter(api, http, chapter, visited, skip_codes):
                    if dry_run:
                        ch_count += 1
                        if ch_count % 50 == 0:
                            logger.info("[DRY-RUN] Chapter %s: discovered %d codes so far...", chapter, ch_count)
                        continue

                    embed_text = create_embedding_text(record)
                    try:
                        embedding = await generate_embedding(embed_text)
                    except Exception as e:
                        logger.warning("Embedding failed for %s: %s — skipping", record["code"], e)
                        ch_skipped += 1
                        continue

                    if len(embedding) != 1536:
                        logger.warning("Unexpected embedding dim %d for %s — skipping", len(embedding), record["code"])
                        ch_skipped += 1
                        continue

                    batch.append((
                        record["code"], record["title"], record["description"],
                        record["inclusions"], record["exclusions"],
                        record["parent_code"], record["chapter"],
                        str(embedding),
                    ))
                    ch_count += 1

                    if len(batch) >= 10:
                        await conn.executemany(UPSERT_SQL, batch)
                        for row in batch:
                            progress.setdefault("in_progress_entities_done", []).append(row[0])
                        save_progress(progress)
                        batch = []

                    if ch_count % 50 == 0:
                        logger.info("Chapter %s: %d codes ingested...", chapter, ch_count)

                # Flush remaining batch
                if not dry_run and batch:
                    await conn.executemany(UPSERT_SQL, batch)
                    for row in batch:
                        progress.setdefault("in_progress_entities_done", []).append(row[0])
                    save_progress(progress)

                elapsed = time.monotonic() - ch_start
                if dry_run:
                    logger.info("[DRY-RUN] Chapter %s: discovered %d codes in %.1fs", chapter, ch_count, elapsed)
                else:
                    logger.info("Chapter %s complete: %d ingested, %d skipped in %.1fs",
                                chapter, ch_count, ch_skipped, elapsed)

                if not dry_run:
                    if chapter not in progress["completed_chapters"]:
                        progress["completed_chapters"].append(chapter)
                    progress["in_progress_chapter"] = None
                    progress["in_progress_entities_done"] = []
                    save_progress(progress)

                grand_total += ch_count
                grand_skipped += ch_skipped

    finally:
        if conn:
            await conn.close()

    elapsed_total = time.monotonic() - total_start
    if dry_run:
        logger.info("[DRY-RUN] Total discovered: %d codes across %d chapters in %.1fs",
                    grand_total, len(chapters), elapsed_total)
    else:
        logger.info("=== Full run complete: %d ingested, %d skipped, %.1fs total ===",
                    grand_total, grand_skipped, elapsed_total)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest ICD-11 chapters from WHO API into icd11_codes table."
    )
    parser.add_argument(
        "--chapters",
        default=",".join(TARGET_CHAPTERS),
        help=f"Comma-separated chapter numbers (default: {','.join(TARGET_CHAPTERS)})",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Walk and parse only — no embeddings, no DB writes")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from progress file")
    parser.add_argument("--force-refresh", action="store_true",
                        help="Re-fetch even if progress shows chapter complete")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chapters = [c.strip().zfill(2) for c in args.chapters.split(",") if c.strip()]
    asyncio.run(ingest_chapters(
        chapters=chapters,
        dry_run=args.dry_run,
        resume=args.resume,
        force_refresh=args.force_refresh,
    ))


if __name__ == "__main__":
    main()
