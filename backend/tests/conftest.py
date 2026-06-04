"""
Shared pytest fixtures for CPG LLM test suite.
"""

import pytest_asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()


@pytest_asyncio.fixture
async def db_conn():
    """Per-test asyncpg connection."""
    url = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(url)
    yield conn
    await conn.close()
