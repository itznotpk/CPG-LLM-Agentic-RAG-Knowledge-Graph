# rPPG Vital Signs — POC

Remote photoplethysmography (rPPG) system that measures vital signs from a **webcam** — no contact sensor required. Optionally integrates a hardware **ESP32 + MAX30100** sensor for clinical-grade HR and SpO2 readings.

---

## How it works

The browser streams webcam frames to a **FastAPI backend** over WebSocket. The backend detects the face, extracts the forehead region, and runs the **POS algorithm** (Wang et al., 2017) to isolate the blood volume pulse (BVP) signal hidden in subtle skin colour changes. Vitals are derived from that BVP signal and sent back to the browser in real time.

An optional **EfficientPhys deep learning model** (from rPPG-Toolbox) runs alongside POS to provide a second HR estimate.

```
Webcam frames (base64 JPEG)
        │
        ▼
┌─────────────────────────────┐
│   rppg_vitals.py            │
│   FastAPI  ws://0.0.0.0:8090│
│                             │
│  Face detection (Haar)      │
│    └─ Forehead ROI          │
│         │                   │
│         ▼                   │
│  POS Algorithm              │──► HR, SpO2, RR, BP
│  EfficientPhys (optional)   │
│                             │
│  ESP32 /api/vitals  ────────│──► filtered HR, SpO2, Temp
└─────────────────────────────┘
        │
        ▼
  index.html (served at /)
  Live charts + vitals display
```

---

## Vitals computed

| Vital | Method | Notes |
|---|---|---|
| Heart Rate | FFT on BVP signal | 40–180 BPM |
| SpO2 | Red / Blue channel ratio | Estimate only — not clinically validated |
| Respiratory Rate | BVP amplitude modulation | 6–30 breaths/min |
| Blood Pressure | BVP waveform morphology (rise time + pulse width) | Research-grade estimate only |

---

## Mode 1 — Standalone UI

Use this when you just want to measure vitals locally with no external dependencies.

### Install

```bash
pip install opencv-python numpy scipy mediapipe fastapi uvicorn
```

### Run

```bash
python rppg_vitals.py
```

Open **http://127.0.0.1:8090** in your browser. The webcam starts automatically.

### Optional: ESP32 hardware sensor

If you have an ESP32 + MAX30100 wired up, configure the device to POST to:

```
POST http://<your-machine-ip>:8090/api/vitals
Content-Type: application/json

{ "hr": 72.0, "spo2": 98.0, "temp": 36.5 }
```

Hardware readings override the webcam-derived values for HR and SpO2 (they are more accurate). Temperature is only available from the hardware sensor.

### Reset between patients

```
POST http://127.0.0.1:8090/api/reset
```

Clears all signal buffers so the previous patient's data does not bleed into the next session.

---

## Mode 2 — Doctor UI (Supabase integration)

Use this when you want live vitals streamed into the **Doctor UI** — a separate dashboard that doctors view. The `supabase_bridge.py` acts as the glue between the rPPG backend and Supabase.

### Architecture

```
┌──────────────┐        WebSocket         ┌──────────────────────┐
│ rppg_vitals  │ ──── ws://127.0.0.1:8090 ──► supabase_bridge.py  │
│  (backend)   │                          │                      │
└──────────────┘                          │  Quality filter      │
       │                                  │  (quality ≥ 50%)     │
       ▼                                  └──────────┬───────────┘
  index.html                                         │ HTTP POST
  (standalone UI)                                    ▼
                                          ┌──────────────────────┐
                                          │   Supabase           │
                                          │   live_vitals table  │
                                          └──────────────────────┘
                                                     │
                                                     ▼
                                            Doctor UI reads here
```

The bridge only forwards a reading when:
- A face is detected
- Signal quality is **≥ 50%**
- At least 3 seconds have passed since the last insert (configurable)

### Install bridge dependencies

```bash
pip install -r requirements_bridge.txt
```

### Configure environment

Create a `.env` file in `rppg_poc/`:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key

# Optional overrides
RPPG_WS_URL=ws://127.0.0.1:8090/ws
QUALITY_THRESHOLD=50
INSERT_INTERVAL=3.0
```

### Run both processes

Terminal 1 — backend:
```bash
python rppg_vitals.py
```

Terminal 2 — bridge (only needed for Doctor UI):
```bash
python supabase_bridge.py
```

The standalone `index.html` UI at **http://127.0.0.1:8090** keeps working as normal. The bridge just silently forwards validated vitals to Supabase in parallel so the Doctor UI can read them.

---

## Files in this folder

| File | Purpose |
|---|---|
| `rppg_vitals.py` | FastAPI backend — signal processing, face detection, WebSocket server |
| `index.html` | Standalone frontend — live vitals display + BVP waveform chart |
| `exceljs.min.js` | Excel export library used by the frontend |
| `supabase_bridge.py` | Forwards vitals to Supabase for the Doctor UI (Mode 2 only) |
| `requirements_bridge.txt` | Dependencies for `supabase_bridge.py` |
| `make_slides.py` | Utility to generate the rPPG presentation slides |
| `rPPG_Presentation.pptx` | Presentation deck |

---

## Disclaimers

- SpO2 and Blood Pressure estimates are **research-grade** and **not clinically validated**. Do not use for medical decisions.
- Heart Rate via webcam rPPG is affected by lighting conditions, movement, and skin tone. Hardware (MAX30100) is more reliable.
- The EfficientPhys model requires the `rPPG-Toolbox/` folder and its pretrained weights (`UBFC-rPPG_EfficientPhys.pth`) to be present. If missing, the system falls back to POS-only — this is handled gracefully.
