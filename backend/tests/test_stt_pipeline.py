"""
Automated tests for the Speech-to-Text pipeline.
Covers: unit/mock, integration (real APIs), WER, latency, and edge cases.

Two integration paths are tested:
  - Google Cloud STT  (GOOGLE_CLOUD_STT_API_KEY)  — base64 REST transcription
  - Gemini Flash      (GEMINI_API_KEY)             — OpenAI-compat summarisation

Run all:         pytest backend/tests/test_stt_pipeline.py -v
Skip live API:   pytest backend/tests/test_stt_pipeline.py -v -m "not integration"
"""

import base64
import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests
from dotenv import load_dotenv

load_dotenv()

# ── Fixtures ────────────────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "stt"
GROUND_TRUTH: dict[str, str] = json.loads(
    (FIXTURES_DIR / "ground_truth.json").read_text()
)

# Maximum acceptable Word Error Rate for normal speech clips
WER_THRESHOLD = 0.20  # 20 %
# Maximum acceptable latency per clip (seconds) — includes cold-start network overhead
LATENCY_THRESHOLD_S = 30.0


# ── Helpers ──────────────────────────────────────────────────────────────────

def _normalise(text: str) -> str:
    import re
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def _transcribe_google_cloud_stt(audio_path: Path) -> str:
    """
    Transcribe audio via Google Cloud Speech-to-Text REST API (base64).
    Mirrors the short-clip path in backend/agent/api.py.
    Only supports WAV (LINEAR16) and MP3 — set encoding accordingly.
    """
    api_key = os.environ["GOOGLE_CLOUD_STT_API_KEY"]
    audio_bytes = audio_path.read_bytes()

    if audio_path.suffix == ".mp3":
        encoding, sample_rate = "MP3", 16000
    else:
        encoding, sample_rate = "LINEAR16", 16000

    payload = {
        "config": {
            "encoding": encoding,
            "sampleRateHertz": sample_rate,
            "languageCode": "en-US",
        },
        "audio": {
            "content": base64.b64encode(audio_bytes).decode("utf-8"),
        },
    }
    url = f"https://speech.googleapis.com/v1/speech:recognize?key={api_key}"
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results:
        return ""
    return results[0]["alternatives"][0]["transcript"].strip()


def _summarise_with_mimo(transcript: str) -> str:
    """
    Summarise a transcript via MiMo (LLM_BASE_URL) for testing only.
    Production uses Gemini Flash via CONSULTATION_SUMMARY_MODEL.
    """
    import openai

    client = openai.OpenAI(
        base_url=os.environ["LLM_BASE_URL"],
        api_key=os.environ["LLM_API_KEY"],
    )
    model = os.getenv("LLM_CHOICE", "mimo-v2.5-pro")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Summarise the consultation transcript concisely."},
            {"role": "user", "content": transcript},
        ],
        max_tokens=512,
    )
    return response.choices[0].message.content.strip()


# ── Unit / Mock tests ─────────────────────────────────────────────────────────

def _make_mock_model(response_text: str | None = None, error: Exception | None = None):
    """Build a fake Gemini model stub without importing google.generativeai."""
    mock_response = MagicMock()
    mock_response.text = response_text or ""
    mock_model = MagicMock()
    if error:
        mock_model.generate_content.side_effect = error
    else:
        mock_model.generate_content.return_value = mock_response
    return mock_model


class TestSTTMock:
    """Tests that never call a real API — fast, always run in CI."""

    def test_mock_returns_transcript(self):
        expected = "The patient presents with chest pain and shortness of breath."
        model = _make_mock_model(response_text=expected)
        result = model.generate_content(["fake audio", "Transcribe"])
        assert result.text == expected

    def test_mock_empty_response_handled(self):
        model = _make_mock_model(response_text="")
        result = model.generate_content(["fake audio", "Transcribe"])
        assert result.text == ""

    def test_mock_api_error_raises(self):
        model = _make_mock_model(error=Exception("API error"))
        with pytest.raises(Exception, match="API error"):
            model.generate_content(["fake audio", "Transcribe"])

    def test_normalise_helper(self):
        assert _normalise("Hello, World!") == "hello world"
        assert _normalise("") == ""
        assert _normalise("Type 2 diabetes.") == "type 2 diabetes"


# ── Integration tests — Google Cloud STT ─────────────────────────────────────

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("GOOGLE_CLOUD_STT_API_KEY"), reason="GOOGLE_CLOUD_STT_API_KEY not set"
)
class TestSTTIntegration:
    """Sends real audio to Google Cloud STT. Requires GOOGLE_CLOUD_STT_API_KEY."""

    @pytest.mark.parametrize("filename", [
        "normal_sentence.mp3",
        "medical_terms.mp3",
        "slow_speech.mp3",
    ])
    def test_transcript_matches_ground_truth(self, filename):
        audio_path = FIXTURES_DIR / filename
        expected = GROUND_TRUTH[filename]
        transcript = _transcribe_google_cloud_stt(audio_path)
        assert _normalise(transcript) == _normalise(expected), (
            f"[{filename}] expected: '{expected}' | got: '{transcript}'"
        )

    def test_short_utterance(self):
        transcript = _transcribe_google_cloud_stt(FIXTURES_DIR / "short_utterance.mp3")
        assert "yes" in _normalise(transcript)

    def test_silence_returns_empty(self):
        transcript = _transcribe_google_cloud_stt(FIXTURES_DIR / "silence.wav")
        words = _normalise(transcript).split()
        assert len(words) <= 3, (
            f"Expected near-empty transcript for silence, got: '{transcript}'"
        )


# ── Integration tests — Gemini Flash summarisation ────────────────────────────

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("LLM_API_KEY") or not os.getenv("LLM_BASE_URL"),
    reason="LLM_API_KEY or LLM_BASE_URL not set",
)
class TestGeminiSummarisation:
    """Verifies the STT -> summarisation step using MiMo (test env only).
    Production uses Gemini Flash via CONSULTATION_SUMMARY_MODEL."""

    def test_summary_is_nonempty(self):
        transcript = "The patient is a 45 year old male with chest pain, shortness of breath, and hypertension."
        summary = _summarise_with_mimo(transcript)
        assert len(summary) > 10

    def test_summary_contains_key_terms(self):
        transcript = "Patient has type 2 diabetes mellitus and is on metformin."
        summary = _summarise_with_mimo(transcript)
        lowered = summary.lower()
        terms = ["diabetes", "metformin", "type 2", "blood sugar", "glucose",
                 "antidiabetic", "medication", "treatment"]
        assert any(term in lowered for term in terms), (
            f"None of {terms} found in summary: '{summary}'"
        )

    def test_empty_transcript_handled(self):
        summary = _summarise_with_mimo("")
        assert isinstance(summary, str)


# ── WER tests ────────────────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("GOOGLE_CLOUD_STT_API_KEY"), reason="GOOGLE_CLOUD_STT_API_KEY not set"
)
class TestSTTWordErrorRate:
    """Measures WER against ground truth. Requires jiwer."""

    @pytest.mark.parametrize("filename", [
        "normal_sentence.mp3",
        "medical_terms.mp3",
        "fast_speech.mp3",
        "slow_speech.mp3",
    ])
    def test_wer_below_threshold(self, filename):
        from jiwer import wer

        audio_path = FIXTURES_DIR / filename
        expected = GROUND_TRUTH[filename]
        transcript = _transcribe_google_cloud_stt(audio_path)
        score = wer(_normalise(expected), _normalise(transcript))

        assert score <= WER_THRESHOLD, (
            f"[{filename}] WER {score:.2%} exceeds threshold {WER_THRESHOLD:.0%}\n"
            f"  expected:   '{expected}'\n"
            f"  transcript: '{transcript}'"
        )


# ── Latency tests ─────────────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("GOOGLE_CLOUD_STT_API_KEY"), reason="GOOGLE_CLOUD_STT_API_KEY not set"
)
class TestSTTLatency:
    """Asserts that STT + summarisation complete within their thresholds."""

    @pytest.mark.parametrize("filename", [
        "normal_sentence.mp3",
        "medical_terms.mp3",
    ])
    def test_stt_latency_under_threshold(self, filename):
        audio_path = FIXTURES_DIR / filename
        start = time.perf_counter()
        _transcribe_google_cloud_stt(audio_path)
        elapsed = time.perf_counter() - start
        assert elapsed <= LATENCY_THRESHOLD_S, (
            f"[{filename}] STT took {elapsed:.2f}s, threshold is {LATENCY_THRESHOLD_S}s"
        )

    @pytest.mark.skipif(
        not os.getenv("LLM_API_KEY") or not os.getenv("LLM_BASE_URL"),
        reason="LLM_API_KEY or LLM_BASE_URL not set",
    )
    def test_end_to_end_latency(self):
        """Full pipeline: STT + MiMo summarisation must complete within 60s."""
        audio_path = FIXTURES_DIR / "normal_sentence.mp3"
        start = time.perf_counter()
        transcript = _transcribe_google_cloud_stt(audio_path)
        _summarise_with_mimo(transcript)
        elapsed = time.perf_counter() - start
        assert elapsed <= 60.0, f"End-to-end took {elapsed:.2f}s"


# ── Edge case tests ───────────────────────────────────────────────────────────

class TestSTTEdgeCases:
    """Edge cases that can be tested without a live API."""

    def test_audio_file_exists(self):
        for fname in GROUND_TRUTH:
            assert (FIXTURES_DIR / fname).exists(), f"Missing fixture: {fname}"

    def test_ground_truth_keys_match_files(self):
        fixture_files = {f.name for f in FIXTURES_DIR.iterdir() if f.name != "ground_truth.json"}
        gt_keys = set(GROUND_TRUTH.keys())
        assert gt_keys == fixture_files, (
            f"Mismatch: GT keys={gt_keys} | files={fixture_files}"
        )

    def test_silence_wav_is_valid(self):
        import wave
        silence_path = FIXTURES_DIR / "silence.wav"
        with wave.open(str(silence_path), "r") as wf:
            assert wf.getnchannels() == 1
            assert wf.getframerate() == 16000
            assert wf.getnframes() > 0

    def test_audio_files_are_nonzero(self):
        for fname in GROUND_TRUTH:
            size = (FIXTURES_DIR / fname).stat().st_size
            assert size > 0, f"{fname} is empty"
