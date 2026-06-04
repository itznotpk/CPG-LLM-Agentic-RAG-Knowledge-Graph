"""
rPPG → Supabase Bridge
======================
Connects to the rPPG POC WebSocket (ws://127.0.0.1:8090/ws) and forwards
validated vitals to the Supabase `live_vitals` table.

Run this alongside the rPPG POC — do NOT modify rppg_vitals.py.

Usage:
    pip install -r requirements.txt
    copy .env.example .env          # then fill in your Supabase keys
    python supabase_bridge.py
"""

import asyncio
import json
import os
import time

import httpx
import websockets
from dotenv import load_dotenv

load_dotenv()

RPPG_WS_URL       = os.getenv("RPPG_WS_URL",        "ws://127.0.0.1:8090/ws")
SUPABASE_URL      = os.getenv("SUPABASE_URL",        "")
SUPABASE_KEY      = os.getenv("SUPABASE_ANON_KEY",   "")
QUALITY_THRESHOLD = float(os.getenv("QUALITY_THRESHOLD", "50"))
INSERT_INTERVAL   = float(os.getenv("INSERT_INTERVAL",   "3.0"))   # seconds between inserts

SUPABASE_ENDPOINT = f"{SUPABASE_URL}/rest/v1/live_vitals"


def _supabase_headers() -> dict:
    return {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "return=minimal",
    }


def build_record(data: dict) -> dict:
    """Map rPPG WebSocket JSON → live_vitals row."""
    esp32 = data.get("esp32") or {}

    # Prefer hardware (ESP32) values when present — they're more accurate
    hr   = esp32.get("hr")   or data.get("hr")
    spo2 = esp32.get("spo2") or data.get("spo2")
    temp = esp32.get("temp")             # only hardware has temp
    source = "esp32" if esp32.get("hr") else "rppg_webcam"

    def _round(val, digits=1):
        return round(float(val), digits) if val is not None else None

    return {
        "source":       source,
        "hr":           _round(hr),
        "spo2":         _round(spo2),
        "rr":           _round(data.get("rr")),
        "sbp":          _round(data.get("sbp")),
        "dbp":          _round(data.get("dbp")),
        # MAX30100 reports ambient temp; +3 °C converts to approximate body temp
        "temp":         _round(float(temp) + 3.0) if temp is not None else None,
        "quality":      _round(data.get("quality", 0)),
        "face_detected": bool(data.get("face_detected", False)),
        # Store everything except the large BVP array
        "raw_data":     {k: v for k, v in data.items() if k != "bvp"},
    }


async def insert(client: httpx.AsyncClient, record: dict) -> None:
    resp = await client.post(SUPABASE_ENDPOINT, json=record, headers=_supabase_headers())
    resp.raise_for_status()


async def run() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env")
        return

    print(f"Bridge starting — rPPG: {RPPG_WS_URL}  Supabase: {SUPABASE_URL}")

    async with httpx.AsyncClient(timeout=10.0) as http:
        while True:
            try:
                async with websockets.connect(RPPG_WS_URL) as ws:
                    print("Connected to rPPG WebSocket.")
                    last_insert = 0.0

                    async for raw in ws:
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        quality      = float(data.get("quality", 0))
                        face         = bool(data.get("face_detected", False))
                        now          = time.monotonic()
                        ready_enough = now - last_insert >= INSERT_INTERVAL

                        print(f"  recv: face={face} quality={quality:.1f} buffer={data.get('buffer_pct', 0):.0f}%", flush=True)

                        if face and quality >= QUALITY_THRESHOLD and ready_enough:
                            record = build_record(data)
                            try:
                                await insert(http, record)
                                last_insert = now
                                print(
                                    f"[{time.strftime('%H:%M:%S')}] "
                                    f"HR={record['hr']}  SpO2={record['spo2']}%  "
                                    f"RR={record['rr']}  BP={record['sbp']}/{record['dbp']}  "
                                    f"Q={record['quality']}%  src={record['source']}"
                                )
                            except httpx.HTTPStatusError as e:
                                print(f"Supabase error {e.response.status_code}: {e.response.text[:200]}")
                            except Exception as e:
                                print(f"Insert failed: {e}")

            except (websockets.exceptions.ConnectionClosed,
                    websockets.exceptions.WebSocketException,
                    OSError) as e:
                print(f"WebSocket disconnected ({e}). Retrying in 5 s...")
                await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(run())
