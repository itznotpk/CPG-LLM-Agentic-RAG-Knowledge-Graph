# Consultation STT → Summary Pipeline — Implementation Plan

**Status:** Ready to implement (revised 2026-05-29 — GCS upload step added)
**Author:** Planned 2026-05-29
**Implementer:** Claude Sonnet
**Scope:** Replace dictate-then-append in Clinical Notes with a full consultation recording flow.

> **REVISION NOTES (2026-05-29):**
>
> 1. **Inline audio duration limit.** Initial implementation hit `"Inline audio exceeds duration limit. Please use a GCS URI."` Google caps inline (base64) audio at ~1 minute for both `recognize` and `longrunningrecognize`. For 5–10 min consultations, audio MUST be uploaded to Google Cloud Storage and referenced by `gs://` URI. The GCS object is deleted immediately after transcription completes — no persistence.
>
> 2. **Speech → GCS auth propagation.** Second test hit `403 PERMISSION_DENIED: Anonymous caller does not have storage.objects.get access`. Cause: when calling Speech API with `?key=API_KEY`, the API key authenticates only the backend→Speech hop. The Speech→GCS hop uses Speech's **own** service agent. The bucket must grant `roles/storage.objectViewer` to `service-{PROJECT_NUMBER}@gcp-sa-speech.iam.gserviceaccount.com`. See §5b step 5 for the exact `gcloud` commands. **Running `gcloud auth application-default login` does NOT fix this — it's a Speech-service-agent IAM issue, not a user ADC issue.**
>
> 3. **IAM propagation delay.** Even after granting the binding correctly, the next two tests STILL returned the same `403 Anonymous caller` error. Root cause: the Speech service agent had **never been provisioned** in this project (project had only ever used Speech via API key, never via OAuth), so `gcloud beta services identity create` actually created it on the spot. IAM bindings for newly-provisioned service agents take **1–2 minutes** to propagate globally. The `gcloud` grant command returns success immediately but the binding isn't live yet. **The fix was to wait 2 minutes and retry — no further IAM changes needed.** §5b step 5c now bakes a `sleep 120` into the setup script so this can't happen again.

---

## Goal

Replace the existing dictate-then-append behavior in Clinical Notes with a full consultation recording flow: record doctor↔patient conversation → diarize via Google STT → summarize via Gemini Flash → append summary into Clinical Notes.

## Architecture

```
[Doctor clicks Dictate]
        ↓
Record full consultation (5–10 min, MediaRecorder, WEBM/Opus)
        ↓
[Doctor clicks Stop]
        ↓
Upload audio → Backend
        ↓
Backend uploads audio bytes to GCS bucket (random key, .webm)
        ↓
Google STT longrunningrecognize with gs:// URI (diarization, 2 speakers)
        ↓
Poll operation until done → Delete GCS object (finally block)
        ↓
Parse word-level speakerTag → group into turns
   Speaker 1 = Doctor (first to speak), Speaker 2 = Patient
        ↓
Pass labeled transcript → Gemini 2.5 Flash with consultation_summariser prompt
        ↓
Return { transcript: [...], summary: "..." } → Frontend
        ↓
Append summary into Clinical Notes (with separator)
Optional: "View Transcript" modal shows labeled turns before discard
```

---

## 1. Backend changes — `agent/api.py`

### 1a. New endpoint: `POST /clinical/consultation/process`

Located after the existing `/clinical/stt` endpoint (~line 1290).

**Inputs:** multipart form with `audio` field (same upload pattern as existing `/clinical/stt`).

**Logic:**
1. Validate `GOOGLE_CLOUD_STT_API_KEY` and `GCS_CONSULTATION_BUCKET` env vars.
2. Read audio bytes, determine encoding (reuse the existing mime→encoding map from `api.py:1201`).
3. **Upload audio to GCS** (see §1c for the helper):
   - Object key: `consultations/{uuid4()}.{ext}` (e.g. `.webm`)
   - Returns `gs://{bucket}/{object_key}`
   - Wrap entire downstream logic in `try/finally` so the blob is deleted even if STT or LLM fails.
4. **Call Google `longrunningrecognize`** with the GCS URI:
   - URL: `https://speech.googleapis.com/v1/speech:longrunningrecognize?key={api_key}`
   - Body:
     ```python
     {
         "config": {
             # ... existing config (encoding, sampleRateHertz, languageCode,
             # enableAutomaticPunctuation, model="latest_long", useEnhanced,
             # speechContexts with medical hints) ...
             "diarizationConfig": {
                 "enableSpeakerDiarization": True,
                 "minSpeakerCount": 2,
                 "maxSpeakerCount": 2,
             },
         },
         "audio": { "uri": gs_uri },  # ← NOT base64 content
     }
     ```
   - Returns `{ "name": "<operation-id>" }`
5. **Poll the operation** at `https://speech.googleapis.com/v1/operations/{name}?key={api_key}` every 3s until `done: true`. Hard timeout 10 min (10-min audio can take 60–120s to process, plus headroom).
6. **Parse diarized result:** the final `results[-1]` typically contains all words with `speakerTag`. Walk `words[]`, group consecutive words sharing the same `speakerTag` into utterance turns.
7. **Label speakers:** whichever `speakerTag` appears first → "Doctor"; the other → "Patient".
8. **Build labeled transcript** as both:
   - Structured list: `[{ "speaker": "Doctor", "text": "..." }, ...]`
   - Flat string for the LLM prompt: `"Doctor: ...\nPatient: ...\nDoctor: ..."`
9. **Call Gemini Flash** for summarization (see §1b).
10. **Finally block:** delete the GCS blob. Log a warning (don't fail the request) if deletion fails.
11. Return:
   ```json
   {
     "transcript": [ { "speaker": "Doctor", "text": "..." }, ... ],
     "summary": "<SOAP-style clinical summary>",
     "confidence": 0.92,
     "duration_seconds": 412
   }
   ```

**Errors:**
- Missing `GOOGLE_CLOUD_STT_API_KEY` or `GCS_CONSULTATION_BUCKET` → 500
- Audio too small (<100 bytes) → 400
- GCS upload failure → 502 with detail
- Google operation timeout (>10 min) → 504
- Google STT API error → 502
- LLM error → return transcript with `summary: null` and 200 (don't lose the transcription work)
- In all error paths, the `finally` block still attempts to delete the GCS blob.

### 1c. GCS upload/delete helpers

Add a small module (e.g. `agent/gcs_audio.py`) or inline helpers in `agent/api.py`:

```python
from google.cloud import storage
import uuid

_storage_client: Optional[storage.Client] = None

def _get_storage_client() -> storage.Client:
    global _storage_client
    if _storage_client is None:
        # Uses Application Default Credentials — same auth pattern
        # already used for Vertex in providers.py:get_vertex_token
        _storage_client = storage.Client()
    return _storage_client

def upload_consultation_audio(audio_bytes: bytes, ext: str = "webm") -> tuple[str, str]:
    """Upload audio to GCS. Returns (gs_uri, object_key)."""
    bucket_name = os.getenv("GCS_CONSULTATION_BUCKET")
    if not bucket_name:
        raise RuntimeError("GCS_CONSULTATION_BUCKET not configured")

    object_key = f"consultations/{uuid.uuid4()}.{ext}"
    bucket = _get_storage_client().bucket(bucket_name)
    blob = bucket.blob(object_key)
    blob.upload_from_string(audio_bytes, content_type=f"audio/{ext}")
    return f"gs://{bucket_name}/{object_key}", object_key

def delete_consultation_audio(object_key: str) -> None:
    """Delete the temporary audio object. Logs but does not raise on failure."""
    try:
        bucket_name = os.getenv("GCS_CONSULTATION_BUCKET")
        bucket = _get_storage_client().bucket(bucket_name)
        bucket.blob(object_key).delete()
    except Exception as e:
        logger.warning("Failed to delete GCS blob %s: %s", object_key, e)
```

**Auth:** uses Application Default Credentials. The project already runs `gcloud auth application-default login` for Vertex AI (see `providers.py:17-30`); the same credential needs `roles/storage.objectAdmin` on the consultation bucket. If using a service account, the JSON key path goes in `GOOGLE_APPLICATION_CREDENTIALS`.

**MIME → extension mapping** for the upload step:

| Browser MIME | ext to use |
|---|---|
| `audio/webm` (any) | `webm` |
| `audio/ogg` | `ogg` |
| `audio/wav` or `audio/x-wav` | `wav` |
| `audio/mp4` | `m4a` |
| `audio/mpeg` | `mp3` |

The extension only affects the GCS object name + `content_type` header; it does NOT change the STT `encoding` field (that still comes from the existing mime→encoding map).

### 1b. Gemini Flash invocation

**Use the direct OpenAI async client pattern, NOT pydantic-ai.**

Rationale: pydantic-ai is only used in `agent/agent.py:51` for the main RAG agent (which needs tool use). All single-shot prompt-to-text helpers in `agent/clinical_stages.py` use `_make_openai_client()` directly — see lines 501, 956, 1426, 1693, 1761, 1828. The Gemini Flash DDx re-rank at `clinical_stages.py:956` is the closest existing analog; follow that pattern.

Add a helper in `agent/clinical_stages.py`:

```python
async def summarise_consultation(labeled_transcript: str) -> str:
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    api_key = os.getenv("LLM_API_KEY", "")
    provider = os.getenv("LLM_PROVIDER", "openai")
    model_choice = os.getenv("CONSULTATION_SUMMARY_MODEL", "gemini-2.0-flash")

    client = _make_openai_client(base_url=base_url, api_key=api_key, provider=provider)
    system_prompt = load_prompt("consultation_summariser.txt")  # use whatever prompt loader exists

    resp = await client.chat.completions.create(
        model=model_choice,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": labeled_transcript},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()
```

Env var `CONSULTATION_SUMMARY_MODEL` defaults to `gemini-2.0-flash` so it's configurable without code changes. Match the exact provider/base_url/api_key resolution used by the existing Gemini Flash call at `clinical_stages.py:956` — copy that pattern verbatim if it differs from the snippet above.

---

## 2. New prompt file — `agent/prompts/consultation_summariser.txt`

Follows the conventions of existing prompts (terse, no markdown fences, hard length caps, no invention).

**Structure to include in the file:**

- **Role:** "You are a clinical scribe summarising a recorded doctor-patient consultation into structured clinical notes."
- **Input format spec:**
  ```
  You will receive a labeled transcript:
  Doctor: <utterance>
  Patient: <utterance>
  Doctor: <utterance>
  ...
  ```
- **Output format:** SOAP-style plain text, NOT JSON (since it goes into a free-text textarea):
  ```
  S (Subjective): <chief complaint, HPI, ROS in patient's own framing>
  O (Objective): <only items the doctor explicitly states — vitals, exam findings>
  A (Assessment): <working impression / suspected dx if doctor names one; else "Not stated">
  P (Plan): <investigations, medications, follow-up — only if stated>
  ```
- **Writing rules:**
  - Plain clinical prose, telegram style. No markdown headers, no bullets.
  - Only use information present in the transcript. Do NOT infer diagnoses or labs not stated.
  - If a section has nothing, write "Not discussed."
  - Prefer concrete (drug+dose, lab name+value, ICD if doctor states one) over vague.
  - Omit pleasantries, scheduling, off-topic chatter.
- **Length cap:** total output ≤ 1500 characters.
- **One example output** to anchor format (similar to how `prior_visit_summariser.txt` does).

---

## 3. Frontend changes — `Doctor UI/src/components/shared/VoiceInput.jsx`

### 3a. Add a `mode` prop to `VoiceInputButton`

```jsx
<VoiceInputButton mode="dictate" | "consultation" onTranscript={...} />
```

Default `mode="dictate"` keeps the existing short-clip behavior (no regression for other callers).

### 3b. New `consultation` mode states

| State | UI |
|-------|---|
| `idle` | Same "Dictate" button |
| `recording` | Live timer (mm:ss) + waveform + red "Stop" button |
| `processing` | Spinner + "Processing consultation… (this can take up to a minute)" |
| `done` (transient) | Brief checkmark, then back to idle |

Add a **"View Transcript"** secondary button that appears in `processing` and `done` states. Clicking opens a simple modal showing the labeled turns (Doctor / Patient color-coded). Closing the modal discards the transcript from local state (no persistence).

### 3c. API call change

In consultation mode, hit `POST /clinical/consultation/process` instead of `/clinical/stt`. Increase fetch timeout / no timeout on the fetch (since longrunning poll can take 30–90s). The endpoint response shape is `{ transcript: [...], summary: "..." }` — call `onTranscript(summary)` and stash `transcript` in local state for the optional viewer.

### 3d. Recording duration safety cap

Hard-stop recording at 12 min (visible warning at 10 min) to avoid runaway files.

---

## 4. Wire-in — `Doctor UI/src/components/sections/ClinicalNotes.jsx`

Change line 68 from:
```jsx
<VoiceInputButton onTranscript={handleVoiceTranscript} />
```
to:
```jsx
<VoiceInputButton mode="consultation" onTranscript={handleVoiceTranscript} />
```

`handleVoiceTranscript` already appends with a space separator (`ClinicalNotes.jsx:31-34`). Confirmed behavior: **append with separator**, no replace, no prompt.

Minor: use `\n\n` instead of `' '` as the separator since the summary will be multi-line SOAP text.

---

## 5. Environment

Add to `.env`:
```
CONSULTATION_SUMMARY_MODEL=gemini-2.0-flash
GCS_CONSULTATION_BUCKET=cpg-consultation-audio-temp
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json   # only if NOT using ADC
```

(Existing `GOOGLE_CLOUD_STT_API_KEY` already in place; Gemini access goes through the existing LLM provider config — confirm `LLM_PROVIDER` / `LLM_BASE_URL` is already wired for Gemini in the project before assuming.)

## 5b. One-time GCS setup (manual, before first run)

```bash
# 1. Pick the same GCP project as the STT API key
gcloud config set project <YOUR_GCP_PROJECT>

# 2. Create a private bucket in the closest region (e.g. asia-southeast1 for SG)
gcloud storage buckets create gs://cpg-consultation-audio-temp \
    --location=asia-southeast1 \
    --uniform-bucket-level-access \
    --public-access-prevention

# 3. Lifecycle rule — auto-delete any object older than 1 day as a safety net
#    (the app deletes immediately; this is belt-and-braces in case of crashes)
cat > /tmp/lifecycle.json <<'EOF'
{
  "lifecycle": {
    "rule": [
      { "action": {"type": "Delete"}, "condition": {"age": 1} }
    ]
  }
}
EOF
gcloud storage buckets update gs://cpg-consultation-audio-temp \
    --lifecycle-file=/tmp/lifecycle.json

# 4. Grant the ADC user (or service account) storage access for the upload step
#    Replace EMAIL with the result of: gcloud auth list --format="value(account)"
gcloud storage buckets add-iam-policy-binding gs://cpg-consultation-audio-temp \
    --member="user:<EMAIL>" \
    --role="roles/storage.objectAdmin"

# 5. CRITICAL — grant the Speech-to-Text service agent read access on the bucket.
#    Why: we call Speech API with ?key=API_KEY (no identity propagation).
#    When Speech fetches the gs:// object on our behalf, it uses its OWN
#    service agent — NOT the API key, NOT our ADC token.
#    Without this binding, GCS reads anonymous → PERMISSION_DENIED.
PROJECT_NUMBER=$(gcloud projects describe <YOUR_GCP_PROJECT> --format="value(projectNumber)")

# 5a. Make sure the Speech service agent exists (idempotent — safe to re-run).
gcloud beta services identity create \
    --service=speech.googleapis.com \
    --project=<YOUR_GCP_PROJECT>

# 5b. Grant it read on the consultation bucket.
gcloud storage buckets add-iam-policy-binding gs://cpg-consultation-audio-temp \
    --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-speech.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"

# 5c. WAIT 2 minutes before testing. IAM bindings propagate globally
#     across Google's systems on a 1–2 minute timescale. The binding
#     above will return success immediately but Speech may still see
#     "Anonymous caller" for up to ~2 min after step 5b.
#     If you test too early you will get a 403 with this misleading message:
#       "Anonymous caller does not have storage.objects.get access"
#     The fix is not more IAM — it's just to wait and retry.
sleep 120  # or just wait by the clock
```

**Why these choices:**
- `uniform-bucket-level-access` + `public-access-prevention`: PHI-safe defaults.
- 1-day lifecycle: cleanup safety net if the app crashes between upload and delete.
- `asia-southeast1`: minimizes latency for Singapore. Adjust for your deployment region.
- **Speech service agent binding (step 5):** mandatory because of how Speech-with-API-key + GCS-URI auth works. See the "Auth propagation note" below.

### Auth propagation note (DO NOT SKIP — root cause of the 403 hit on first try)

```
Backend → Speech API   :  authenticated via ?key=API_KEY
Speech API → GCS read  :  uses Speech's service agent
                          (service-{PROJECT_NUMBER}@gcp-sa-speech.iam.gserviceaccount.com)
```

- The API key authenticates **the backend → Speech** hop only. It does **not** flow downstream.
- The ADC token used for the GCS upload **also** doesn't flow downstream — it's only used by the backend's own GCS client, not by Speech.
- Therefore the Speech service agent **must** have `roles/storage.objectViewer` on the bucket, or the GCS read fails with `403 PERMISSION_DENIED: Anonymous caller`.
- Symptom `Anonymous caller does not have storage.objects.get access` ≠ stale token. Running `gcloud auth application-default login` will NOT fix it. The fix is the IAM binding in step 5b above.

**Alternative (Fix B, deferred):** switch the Speech call from API key to OAuth (Bearer token) using the existing `get_vertex_token()` pattern in `providers.py:17`. Then Speech inherits the caller's GCS permissions and the service-agent binding becomes unnecessary. Not adopted now to minimize code churn; revisit if we move off API keys for other reasons.

---

## 6. Out of scope (explicit)

- Real-time streaming STT (deferred — will be a follow-up project)
- Transcript persistence / storage (explicitly not wanted)
- Speaker re-assignment UI (we assume doctor speaks first, no override)
- Multi-language support (locked to en-US)
- Concurrent multi-speaker overlap handling (Google diarization does its best, not corrected)

---

## 7. Files touched

| File | Change |
|------|--------|
| `agent/api.py` | + new `/clinical/consultation/process` endpoint |
| `agent/clinical_stages.py` | + `summarise_consultation()` helper |
| `agent/gcs_audio.py` | **NEW** — GCS upload/delete helpers (or inline in api.py) |
| `agent/prompts/consultation_summariser.txt` | **NEW** |
| `requirements.txt` | + `google-cloud-storage` |
| `Doctor UI/src/components/shared/VoiceInput.jsx` | + `mode` prop, consultation states, transcript modal |
| `Doctor UI/src/components/sections/ClinicalNotes.jsx` | pass `mode="consultation"`, use `\n\n` separator |
| `.env` | + `CONSULTATION_SUMMARY_MODEL`, `GCS_CONSULTATION_BUCKET` |
| **GCS (one-time, manual)** | bucket create + IAM grant per §5b |

---

## 8. Test plan

- [ ] **Speech service agent IAM verified BEFORE first test run:**
      ```bash
      gcloud storage buckets get-iam-policy gs://cpg-consultation-audio-temp \
          --format=json | grep gcp-sa-speech
      ```
      Must show a binding for `service-{PROJECT_NUMBER}@gcp-sa-speech.iam.gserviceaccount.com` with `roles/storage.objectViewer`. If missing → see §5b step 5.
- [ ] **GCS round-trip:** record a 30s clip, confirm GCS bucket shows the object briefly during processing, and the object is gone within ~5s after the response returns.
- [ ] **Diarization smoke:** 30s clip with two distinct voices → confirm Doctor/Patient labels are sensible and Speaker 1 = Doctor.
- [ ] **Full consultation length:** 5–10 min mock consultation (use the pre-diagnostic script in this repo or read both voices yourself) → confirm `longrunningrecognize` completes within the 10-min poll cap and summary populates Clinical Notes.
- [ ] **Crash safety:** kill the backend mid-process → restart → confirm the GCS lifecycle rule (1-day) cleans up the orphaned object, even though the app couldn't delete it.
- [ ] **Click "View Transcript"** mid-processing → modal renders labeled turns once result arrives.
- [ ] **Stop button** cancels cleanly during recording (no orphaned mic stream, no GCS upload triggered).
- [ ] **Existing dictate callers** (if any beyond ClinicalNotes) still work in default `mode="dictate"` (unchanged inline `/clinical/stt` path).
- [ ] **Append separator** (`\n\n`) verified — summary doesn't smash into existing notes.
- [ ] **Error path:** backend down → frontend shows graceful error, no stuck spinner, no leftover GCS object.
- [ ] **No-PHI-in-logs check:** grep backend logs for snippets of transcript text → should find none beyond debug-level entries.
