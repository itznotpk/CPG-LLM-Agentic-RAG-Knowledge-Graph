"""Neo4j Aura connectivity probe — distinguishes "Aura paused / unhealthy"
from "network/DNS blocked" without running the full pipeline.

Mirrors the runtime driver config in agent/graph_clinical.py::_get_neo4j_session
(same pool kwargs) so the result reflects what the pipeline actually sees.

Three layered checks, each timed:
  1. DNS + raw TCP reach to the Bolt host:port (is the socket even open?).
  2. Driver.verify_connectivity() (handshake + auth, no query).
  3. A trivial `RETURN 1` query through a session (full round-trip).

Run:  python scripts/probe_neo4j_connectivity.py
Exit: 0 = healthy, 2 = reachable-but-unhealthy, 3 = unreachable (network/DNS).
"""
from __future__ import annotations

import asyncio
import os
import socket
import sys
import time
from urllib.parse import urlparse

from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

URI = os.environ["NEO4J_URI"]
USER = os.environ["NEO4J_USER"]
PWD = os.environ["NEO4J_PASSWORD"]
DB = os.getenv("NEO4J_DATABASE") or None


def _ms(t0: float) -> str:
    return f"{(time.perf_counter() - t0) * 1000:.0f} ms"


def _tcp_check() -> bool:
    """DNS-resolve + open a raw TCP socket to the Bolt host:port."""
    parsed = urlparse(URI)
    host = parsed.hostname
    port = parsed.port or 7687
    print(f"1. TCP reach  -> {host}:{port}")
    t0 = time.perf_counter()
    try:
        ip = socket.gethostbyname(host)
        print(f"   DNS resolved {host} -> {ip} ({_ms(t0)})")
    except socket.gaierror as e:
        print(f"   DNS FAILED: {e} ({_ms(t0)})")
        return False
    t0 = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=10):
            print(f"   TCP connect OK ({_ms(t0)})")
        return True
    except (OSError, socket.timeout) as e:
        print(f"   TCP connect FAILED: {e} ({_ms(t0)})")
        return False


async def _driver_check() -> int:
    driver = AsyncGraphDatabase.driver(
        URI,
        auth=(USER, PWD),
        max_connection_lifetime=300,
        keep_alive=True,
        liveness_check_timeout=30,
        connection_acquisition_timeout=60,
    )
    try:
        print("2. Handshake  -> verify_connectivity()")
        t0 = time.perf_counter()
        try:
            await driver.verify_connectivity()
            print(f"   handshake + auth OK ({_ms(t0)})")
        except Exception as e:
            print(f"   handshake FAILED ({_ms(t0)}): {type(e).__name__}: {e}")
            return 2

        print("3. Round-trip -> RETURN 1")
        t0 = time.perf_counter()
        try:
            async with driver.session(database=DB) as sess:
                res = await sess.run("RETURN 1 AS ok")
                row = await res.single()
                print(f"   query returned {row['ok']} ({_ms(t0)})")
        except Exception as e:
            print(f"   query FAILED ({_ms(t0)}): {type(e).__name__}: {e}")
            return 2
        return 0
    finally:
        await driver.close()


async def main() -> int:
    print("=" * 70)
    print(f"Neo4j connectivity probe — {URI}")
    print("=" * 70)
    if not _tcp_check():
        print("\nVERDICT: UNREACHABLE — DNS/network/firewall, not Aura state.")
        return 3
    print()
    rc = await _driver_check()
    print()
    if rc == 0:
        print("VERDICT: HEALTHY — driver can query. KG flags should populate.")
    else:
        print("VERDICT: REACHABLE BUT UNHEALTHY — TCP opens but bolt handshake/")
        print("         query fails. Most likely Aura paused/resuming or auth.")
        print("         Check the Aura console: is the instance Running?")
    return rc


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
