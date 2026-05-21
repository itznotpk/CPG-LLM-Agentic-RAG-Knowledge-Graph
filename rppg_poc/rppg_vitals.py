"""
rPPG Vital Signs POC - Standalone Proof of Concept
Captures webcam video, detects face, extracts heart rate using POS algorithm.
Runs as a standalone FastAPI server with its own UI.

Usage:
    pip install opencv-python numpy scipy mediapipe fastapi uvicorn
    python rppg_vitals.py
    Open http://127.0.0.1:8090 in browser
"""

import asyncio
import base64
import json
import os
import sys
import time
from collections import deque

import cv2
import numpy as np
from scipy import signal as scipy_signal
from scipy import sparse

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn

# ============================================================
# rPPG Signal Processing (adapted from rPPG-Toolbox)
# ============================================================

def detrend(input_signal, lambda_value=100):
    """Detrend PPG signal using regularized least squares."""
    signal_length = input_signal.shape[0]
    H = np.identity(signal_length)
    ones = np.ones(signal_length)
    minus_twos = -2 * np.ones(signal_length)
    diags_data = np.array([ones, minus_twos, ones])
    diags_index = np.array([0, 1, 2])
    D = sparse.spdiags(diags_data, diags_index,
                       (signal_length - 2), signal_length).toarray()
    filtered_signal = np.dot(
        (H - np.linalg.inv(H + (lambda_value ** 2) * np.dot(D.T, D))),
        input_signal)
    return filtered_signal


def pos_wang(rgb_signals, fs):
    """
    POS algorithm (Wang et al., 2017) for BVP extraction.
    rgb_signals: (N, 3) array of mean RGB values per frame
    fs: sampling rate (fps)
    Returns: BVP signal array
    """
    import math
    WinSec = 1.6
    N = rgb_signals.shape[0]
    H = np.zeros(N)
    l = math.ceil(WinSec * fs)

    for n in range(N):
        m = n - l
        if m >= 0:
            Cn = rgb_signals[m:n, :] / np.mean(rgb_signals[m:n, :], axis=0)
            Cn = Cn.T  # (3, window)
            S = np.array([[0, 1, -1], [-2, 1, 1]]) @ Cn  # (2, window)
            h = S[0, :] + (np.std(S[0, :]) / (np.std(S[1, :]) + 1e-10)) * S[1, :]
            h = h - np.mean(h)
            H[m:n] = H[m:n] + h

    # Detrend
    H = detrend(H, 100)

    # Bandpass filter: 0.75 Hz (45 BPM) to 3.0 Hz (180 BPM)
    nyq = fs / 2
    low = 0.75 / nyq
    high = 3.0 / nyq
    if low < 1 and high < 1:
        b, a = scipy_signal.butter(2, [low, high], btype='bandpass')
        H = scipy_signal.filtfilt(b, a, H.astype(np.double))

    return H


def calculate_hr_fft(bvp_signal, fs, low_pass=0.75, high_pass=2.5):
    """Calculate heart rate from BVP signal using FFT."""
    if len(bvp_signal) < 2:
        return 0.0

    N = 1 if len(bvp_signal) == 0 else 2 ** (len(bvp_signal) - 1).bit_length()
    f, pxx = scipy_signal.periodogram(bvp_signal, fs=fs, nfft=N, detrend=False)
    mask = np.argwhere((f >= low_pass) & (f <= high_pass))
    if len(mask) == 0:
        return 0.0
    masked_f = np.take(f, mask).flatten()
    masked_pxx = np.take(pxx, mask).flatten()
    hr = masked_f[np.argmax(masked_pxx)] * 60  # Convert Hz to BPM
    return float(hr)


def calculate_spo2(rgb_signals, fs):
    """
    Estimate SpO2 from RGB signals using red/blue channel ratio.
    Real pulse oximeters use red (660nm) + infrared (940nm).
    We approximate using red + blue channels as proxies.
    SpO2 ≈ 110 - 25 * R, where R = (AC_red/DC_red) / (AC_blue/DC_blue)
    NOTE: This is an ESTIMATE — not clinically accurate.
    """
    if len(rgb_signals) < fs * 5:
        return 0.0
    try:
        red = rgb_signals[:, 0].astype(np.float64)
        blue = rgb_signals[:, 2].astype(np.float64)

        # Bandpass filter to isolate pulsatile (AC) component
        nyq = fs / 2
        low = 0.75 / nyq
        high = 2.5 / nyq
        if low >= 1 or high >= 1:
            return 0.0
        b, a = scipy_signal.butter(2, [low, high], btype='bandpass')

        ac_red = scipy_signal.filtfilt(b, a, red)
        ac_blue = scipy_signal.filtfilt(b, a, blue)

        # DC component = mean
        dc_red = np.mean(red) + 1e-10
        dc_blue = np.mean(blue) + 1e-10

        # RMS of AC components
        rms_red = np.sqrt(np.mean(ac_red ** 2)) + 1e-10
        rms_blue = np.sqrt(np.mean(ac_blue ** 2)) + 1e-10

        # Ratio of ratios
        ratio = (rms_red / dc_red) / (rms_blue / dc_blue)

        # Empirical calibration: SpO2 = 110 - 25 * R
        spo2 = 110 - 25 * ratio

        # Clamp to realistic range
        spo2 = np.clip(spo2, 70, 100)
        return float(spo2)
    except Exception:
        return 0.0


def calculate_respiratory_rate(bvp_signal, fs):
    """Estimate respiratory rate from BVP amplitude modulation."""
    if len(bvp_signal) < fs * 5:
        return 0.0
    try:
        nyq = fs / 2
        b, a = scipy_signal.butter(2, [0.1 / nyq, 0.5 / nyq], btype='bandpass')
        resp_signal = scipy_signal.filtfilt(b, a, np.abs(bvp_signal))
        N = 2 ** (len(resp_signal) - 1).bit_length()
        f, pxx = scipy_signal.periodogram(resp_signal, fs=fs, nfft=N)
        mask = (f >= 0.1) & (f <= 0.5)
        if not np.any(mask):
            return 0.0
        rr = f[mask][np.argmax(pxx[mask])] * 60
        return float(rr)
    except Exception:
        return 0.0


def estimate_blood_pressure(bvp_signal, fs, hr):
    """
    Research-grade BP estimate from rPPG BVP waveform morphology.
    Uses normalised rise time and pulse width — features that correlate
    with arterial stiffness and therefore blood pressure.
    NOT clinically validated — label clearly as estimate.
    Returns: (sbp, dbp) in mmHg, or (0.0, 0.0) if insufficient data.
    """
    if len(bvp_signal) < fs * 5 or hr <= 0:
        return 0.0, 0.0
    try:
        bvp = np.array(bvp_signal, dtype=np.float64)
        rng = bvp.max() - bvp.min()
        if rng < 1e-6:
            return 0.0, 0.0
        bvp_norm = (bvp - bvp.min()) / rng

        min_dist = int(fs * 0.4)   # max ~150 BPM
        peaks, _ = scipy_signal.find_peaks(
            bvp_norm, distance=min_dist, height=0.5, prominence=0.25)
        if len(peaks) < 3:
            return 0.0, 0.0

        inv = 1.0 - bvp_norm
        troughs, _ = scipy_signal.find_peaks(inv, distance=min_dist)

        pulse_period = 60.0 / hr
        rise_times, pulse_widths = [], []

        for peak in peaks:
            before = troughs[troughs < peak]
            if len(before) == 0:
                continue
            trough = before[-1]
            rise_t = (peak - trough) / fs
            norm_rt = np.clip(rise_t / (pulse_period + 1e-10), 0.05, 0.6)
            rise_times.append(norm_rt)

            half = bvp_norm[trough] + 0.5 * (bvp_norm[peak] - bvp_norm[trough])
            seg = bvp_norm[trough:peak]
            cross = np.where(seg >= half)[0]
            if len(cross):
                pw = (peak - (trough + cross[0])) / fs
                pulse_widths.append(np.clip(pw / (pulse_period + 1e-10), 0.1, 0.6))

        if not rise_times:
            return 0.0, 0.0

        mrt = float(np.mean(rise_times))
        mpw = float(np.mean(pulse_widths)) if pulse_widths else 0.3

        # Empirical formulas — faster rise & narrower pulse → higher pressure
        sbp = 115 - 55 * mrt + 0.35 * hr + 12 * (1.0 - mpw)
        dbp =  72 - 18 * mrt + 0.15 * hr + 8  * mpw

        sbp = float(np.clip(sbp, 85, 185))
        dbp = float(np.clip(dbp, 55, 115))
        if dbp >= sbp - 15:
            dbp = sbp - 30

        return round(sbp, 1), round(dbp, 1)
    except Exception as e:
        print(f"[BP] Error: {e}")
        return 0.0, 0.0



# ============================================================
# EfficientPhys Deep Learning Processor (rPPG-Toolbox)
# ============================================================

_TOOLBOX_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'rPPG-Toolbox'))
_MODEL_PATH = os.path.join(_TOOLBOX_PATH, 'final_model_release', 'UBFC-rPPG_EfficientPhys.pth')

class DLProcessor:
    FRAME_DEPTH = 10
    IMG_SIZE    = 72
    BUFFER_SIZE = 101

    def __init__(self):
        self.frame_buffer = deque(maxlen=self.BUFFER_SIZE)
        self.model        = None
        self.last_hr      = 0.0
        self.last_rr      = 0.0
        self.last_spo2    = 0.0
        self.last_sbp     = 0.0
        self.last_dbp     = 0.0
        self._torch       = None
        self._load()

    def _load(self):
        try:
            if _TOOLBOX_PATH not in sys.path:
                sys.path.insert(0, _TOOLBOX_PATH)
            import torch
            from neural_methods.model.EfficientPhys import EfficientPhys
            self._torch = torch
            model = EfficientPhys(
                in_channels=3, nb_filters1=32, nb_filters2=64,
                kernel_size=3, dropout_rate1=0.25, dropout_rate2=0.5,
                pool_size=(2, 2), nb_dense=128,
                frame_depth=self.FRAME_DEPTH, img_size=self.IMG_SIZE
            )
            state = torch.load(_MODEL_PATH, map_location='cpu')
            if any(k.startswith('module.') for k in state):
                state = {k[7:]: v for k, v in state.items()}
            model.load_state_dict(state)
            model.eval()
            self.model = model
            print(f"[DL] EfficientPhys loaded OK ({_MODEL_PATH})")
        except Exception as e:
            print(f"[DL] EfficientPhys not loaded (optional): {e}")

    def reset(self):
        self.frame_buffer.clear()
        self.last_hr = self.last_rr = self.last_spo2 = self.last_sbp = self.last_dbp = 0.0

    @property
    def ready(self):
        return self.model is not None and len(self.frame_buffer) >= self.BUFFER_SIZE

    def add_frame(self, frame_bgr, roi):
        if self.model is None:
            return
        x, y, w, h = roi
        crop = frame_bgr[y:y+h, x:x+w]
        if crop.size == 0:
            return
        resized = cv2.resize(crop, (self.IMG_SIZE, self.IMG_SIZE))
        self.frame_buffer.append(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32))

    def _snapshot(self):
        return {
            'hr':   round(self.last_hr,   1),
            'rr':   round(self.last_rr,   1),
            'spo2': round(self.last_spo2, 1),
            'sbp':  round(self.last_sbp,  1),
            'dbp':  round(self.last_dbp,  1),
        }

    def compute_vitals(self, actual_fps):
        if not self.ready:
            return self._snapshot()
        try:
            torch  = self._torch
            frames = np.array(list(self.frame_buffer))
            rgb_means = frames.reshape(len(frames), -1, 3).mean(axis=1)
            frames_std = frames.copy()
            for c in range(3):
                ch = frames_std[:, :, :, c]
                frames_std[:, :, :, c] = (ch - ch.mean()) / (ch.std() + 1e-8)
            tensor = torch.FloatTensor(frames_std.transpose(0, 3, 1, 2))
            with torch.no_grad():
                bvp = self.model(tensor).squeeze().cpu().numpy()
            hr = calculate_hr_fft(bvp, actual_fps)
            if 40 <= hr <= 180:
                self.last_hr = hr
            rr = calculate_respiratory_rate(bvp, actual_fps)
            if 6 <= rr <= 30:
                self.last_rr = rr
            spo2 = calculate_spo2(rgb_means, actual_fps)
            if 80 <= spo2 <= 100:
                self.last_spo2 = spo2
            sbp, dbp = estimate_blood_pressure(bvp, actual_fps, self.last_hr)
            if sbp > 0 and dbp > 0:
                self.last_sbp = sbp
                self.last_dbp = dbp
            return self._snapshot()
        except Exception as e:
            print(f"[DL] Inference error: {e}")
            return self._snapshot()


# ============================================================
# Face Detection using OpenCV Haar Cascade
# ============================================================

class FaceDetector:
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    def detect(self, frame):
        """Returns (face_roi, rppg_roi) or (None, None).
        face_roi  — full bounding box, used by the DL model.
        rppg_roi  — forehead-only strip, used for POS signal extraction.
                    Avoids the eye/glasses region which causes specular glare.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5, minSize=(80, 80))
        if len(faces) == 0:
            return None, None
        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        x, y, w, h = faces[0]
        face_roi = (x, y, w, h)
        # Forehead strip: top 5–27% of face height, inset 10% on each side.
        # This sits above the eyebrow line and is completely clear of glasses.
        rppg_x = x + int(w * 0.10)
        rppg_y = y + int(h * 0.05)
        rppg_w = int(w * 0.80)
        rppg_h = int(h * 0.22)
        rppg_roi = (rppg_x, rppg_y, rppg_w, rppg_h)
        return face_roi, rppg_roi

    def extract_roi_rgb(self, frame, roi):
        """Extract mean RGB from ROI."""
        x, y, w, h = roi
        region = frame[y:y+h, x:x+w]
        if region.size == 0:
            return None
        mean_rgb = np.mean(region.reshape(-1, 3), axis=0)  # BGR
        return mean_rgb[[2, 1, 0]]  # Convert to RGB


# ============================================================
# rPPG Processor - manages the rolling window
# ============================================================

class RPPGProcessor:
    def __init__(self, buffer_seconds=15, fps=15):
        self.fps = fps
        self.buffer_size = buffer_seconds * fps
        self.rgb_buffer = deque(maxlen=self.buffer_size)
        self.timestamps = deque(maxlen=self.buffer_size)
        self.hr_history = deque(maxlen=20)  # Keep more readings for stability
        self.rr_history = deque(maxlen=10)
        self.spo2_history = deque(maxlen=15)
        self.last_hr = 0.0
        self.last_rr = 0.0
        self.last_spo2 = 0.0
        self.last_sbp = 0.0
        self.last_dbp = 0.0
        self.stable_hr = 0.0
        self.stable_rr = 0.0
        self.stable_spo2 = 0.0
        self.stable_sbp = 0.0
        self.stable_dbp = 0.0
        self.bp_history = deque(maxlen=10)
        self.signal_quality = 0.0
        self.is_locked = False
        self.lock_count = 0
        self.ema_alpha = 0.15

    def add_frame(self, mean_rgb):
        """Add a frame's mean RGB values to the buffer."""
        self.rgb_buffer.append(mean_rgb)
        self.timestamps.append(time.time())

    def _ema_update(self, current, new_val, alpha):
        """Exponential moving average update."""
        if current == 0.0:
            return new_val
        return current * (1 - alpha) + new_val * alpha

    def reset(self):
        """Clear all buffers — call between students so old data doesn't contaminate."""
        self.rgb_buffer.clear()
        self.timestamps.clear()
        self.hr_history.clear()
        self.rr_history.clear()
        self.spo2_history.clear()
        self.bp_history.clear()
        self.last_hr = self.last_rr = self.last_spo2 = 0.0
        self.last_sbp = self.last_dbp = 0.0
        self.stable_hr = self.stable_rr = self.stable_spo2 = 0.0
        self.stable_sbp = self.stable_dbp = 0.0
        self.signal_quality = 0.0
        self.is_locked = False
        self.lock_count = 0

    def compute_vitals(self):
        """Compute heart rate and respiratory rate from buffered RGB data."""
        min_frames = int(self.fps * 3)  # 3 seconds minimum for quick demo
        if len(self.rgb_buffer) < min_frames:
            return {
                "hr": 0.0,
                "rr": 0.0,
                "quality": 0.0,
                "buffer_pct": len(self.rgb_buffer) / min_frames * 100,
                "status": "buffering",
                "bvp": []
            }

        rgb_array = np.array(self.rgb_buffer)

        # Calculate actual FPS from timestamps
        ts = np.array(self.timestamps)
        actual_fps = len(ts) / (ts[-1] - ts[0] + 1e-10)

        # Run POS algorithm
        try:
            bvp = pos_wang(rgb_array, actual_fps)
            hr = calculate_hr_fft(bvp, actual_fps)
            rr = calculate_respiratory_rate(bvp, actual_fps)

            # Signal quality: true SNR — peak power in HR band vs noise floor outside it
            quality = 0.0
            if len(bvp) > 0:
                N = 2 ** (len(bvp) - 1).bit_length()
                f, pxx = scipy_signal.periodogram(bvp, fs=actual_fps, nfft=N)
                hr_band   = (f >= 0.75) & (f <= 2.5)
                noise_band = ((f >= 0.05) & (f < 0.75)) | ((f > 2.5) & (f <= 4.0))
                if np.any(hr_band) and np.any(noise_band):
                    peak_power  = np.max(pxx[hr_band])
                    noise_power = np.mean(pxx[noise_band]) + 1e-10
                    snr = peak_power / noise_power
                    # SNR 1 = noise floor, 40+ = clean signal → map to 0–1
                    quality = float(np.clip((snr - 1) / 39.0, 0.0, 1.0))

            # Smooth the quality itself
            self.signal_quality = self._ema_update(self.signal_quality, quality, 0.2)

            # Accept HR if in valid physiological range (quality gates smoothing speed)
            if 40 <= hr <= 180:
                self.hr_history.append(hr)

                if len(self.hr_history) >= 5:
                    sorted_hrs = sorted(self.hr_history)
                    trim = max(1, len(sorted_hrs) // 5)
                    trimmed = sorted_hrs[trim:-trim] if trim < len(sorted_hrs) // 2 else sorted_hrs
                    raw_hr = np.mean(trimmed)
                else:
                    raw_hr = np.median(self.hr_history)

                # High quality → fast lock; low quality → slow cautious update
                if quality > 0.2:
                    alpha = 0.08 if self.is_locked else self.ema_alpha
                    self.lock_count = min(self.lock_count + 1, 30)
                    if self.lock_count >= 10:
                        self.is_locked = True
                else:
                    alpha = 0.05   # slow update when signal is weak
                    self.lock_count = max(0, self.lock_count - 1)
                    if self.lock_count == 0:
                        self.is_locked = False

                self.stable_hr = self._ema_update(self.stable_hr, raw_hr, alpha)
                self.last_hr = self.stable_hr
            else:
                self.lock_count = max(0, self.lock_count - 1)
                if self.lock_count == 0:
                    self.is_locked = False

            # Respiratory rate — same stabilization
            if 6 <= rr <= 30:
                self.rr_history.append(rr)
                raw_rr = np.median(self.rr_history)
                self.stable_rr = self._ema_update(self.stable_rr, raw_rr, 0.1)
                self.last_rr = self.stable_rr

            # SpO2 estimation from red/blue ratio
            spo2 = calculate_spo2(rgb_array, actual_fps)
            if 80 <= spo2 <= 100:
                self.spo2_history.append(spo2)
                raw_spo2 = np.median(self.spo2_history)
                alpha_spo2 = 0.08 if quality > 0.2 else 0.03
                self.stable_spo2 = self._ema_update(self.stable_spo2, raw_spo2, alpha_spo2)
                self.last_spo2 = self.stable_spo2

            # Blood pressure estimate from BVP waveform morphology
            sbp, dbp = estimate_blood_pressure(bvp, actual_fps, self.last_hr)
            if sbp > 0 and dbp > 0:
                self.bp_history.append((sbp, dbp))
                raw_sbp = float(np.median([x[0] for x in self.bp_history]))
                raw_dbp = float(np.median([x[1] for x in self.bp_history]))
                alpha_bp = 0.06 if quality > 0.2 else 0.02
                self.stable_sbp = self._ema_update(self.stable_sbp, raw_sbp, alpha_bp)
                self.stable_dbp = self._ema_update(self.stable_dbp, raw_dbp, alpha_bp)
                self.last_sbp = self.stable_sbp
                self.last_dbp = self.stable_dbp

            # Downsample BVP for display (last 200 points)
            bvp_display = bvp[-200:].tolist() if len(bvp) > 0 else []

            return {
                "hr": round(self.last_hr, 1),
                "rr": round(self.last_rr, 1),
                "spo2": round(self.last_spo2, 1),
                "sbp": round(self.last_sbp, 1),
                "dbp": round(self.last_dbp, 1),
                "quality": round(self.signal_quality * 100, 1),
                "buffer_pct": 100.0,
                "status": "locked" if self.is_locked else "measuring",
                "fps": round(actual_fps, 1),
                "bvp": bvp_display
            }
        except Exception as e:
            return {
                "hr": self.last_hr,
                "rr": self.last_rr,
                "spo2": self.last_spo2,
                "quality": 0.0,
                "buffer_pct": 100.0,
                "status": f"error: {str(e)}",
                "bvp": []
            }


# ============================================================
# FastAPI App
# ============================================================

app = FastAPI(title="rPPG Vital Signs POC")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class HardwareSensorFilter:
    """Smooths MAX30100 HR + SpO2 — rejects out-of-range values and spikes."""
    HR_MIN,   HR_MAX    = 40,  140
    SPO2_MIN, SPO2_MAX  = 80,  100
    MAX_HR_JUMP   = 25  # BPM — ignore single-step spikes larger than this
    MAX_SPO2_JUMP = 10  # %   — reject implausible SpO2 jumps (outlier contact loss)
    ALPHA         = 0.30

    def __init__(self):
        self.hr   = 0.0
        self.spo2 = 0.0

    def process_hr(self, raw: float) -> float:
        if not (self.HR_MIN <= raw <= self.HR_MAX):
            return self.hr
        if self.hr > 0 and abs(raw - self.hr) > self.MAX_HR_JUMP:
            return self.hr
        self.hr = raw if self.hr == 0 else self.hr * (1 - self.ALPHA) + raw * self.ALPHA
        return round(self.hr, 1)

    def process_spo2(self, raw: float) -> float:
        if not (self.SPO2_MIN <= raw <= self.SPO2_MAX):
            return self.spo2
        if self.spo2 > 0 and abs(raw - self.spo2) > self.MAX_SPO2_JUMP:
            return self.spo2                        # contact-loss spike → ignore
        self.spo2 = raw if self.spo2 == 0 else self.spo2 * (1 - self.ALPHA) + raw * self.ALPHA
        return round(self.spo2, 1)

    def reset(self):
        self.hr   = 0.0
        self.spo2 = 0.0


# Global state
face_detector = FaceDetector()
processor = RPPGProcessor(buffer_seconds=30, fps=30)

# Store latest ESP32 hardware vitals
esp32_vitals = {"hr": 0, "spo2": 0, "temp": 0.0, "source": "esp32", "status": "disconnected"}

# Track all active WebSocket clients so ESP32 data can be pushed immediately
active_ws_clients: set = set()

# DL processor (shared across sessions — model loaded once at startup)
dl_processor          = DLProcessor()
_dl_inference_running = False

# Hardware sensor filter — smooths and validates MAX30100 readings
hw_filter = HardwareSensorFilter()


class ESP32Vitals(BaseModel):
    hr: float
    spo2: float
    temp: float = 0.0
    source: Optional[str] = "esp32"


@app.post("/api/vitals")
async def receive_esp32_vitals(data: ESP32Vitals):
    """Receive vitals from ESP32 MAX30100 sensor via HTTP POST."""
    global esp32_vitals
    no_contact = (data.hr == 0.0)
    filtered_hr   = hw_filter.process_hr(data.hr) if not no_contact else hw_filter.hr
    filtered_spo2 = hw_filter.process_spo2(data.spo2)
    esp32_vitals = {
        "hr":         filtered_hr,
        "spo2":       filtered_spo2,
        "temp":       round(data.temp, 2),
        "source":     "esp32",
        "type":       "esp32",
        "status":     "no_contact" if no_contact else "connected",
        "timestamp":  time.time()
    }
    if no_contact:
        print(f"[ESP32] No finger contact | SpO2: {filtered_spo2:.0f}% | Temp: {data.temp:.1f}°C")
    else:
        print(f"[ESP32] raw HR: {data.hr:.0f} → filtered: {filtered_hr:.0f} | SpO2: {filtered_spo2:.0f}% | Temp: {data.temp:.1f}°C")

    # Push immediately to all connected browser clients
    dead = set()
    for client in active_ws_clients:
        try:
            await client.send_text(json.dumps(esp32_vitals))
        except Exception:
            dead.add(client)
    active_ws_clients.difference_update(dead)

    return JSONResponse({"status": "ok"})


@app.get("/api/vitals")
async def get_esp32_vitals():
    """Get latest ESP32 vitals (for polling fallback)."""
    return JSONResponse(esp32_vitals)


student_count = 0

@app.post("/api/reset")
async def reset_session():
    """Reset all server-side buffers between students."""
    global _dl_inference_running, student_count, esp32_vitals
    dl_processor.reset()
    hw_filter.reset()
    _dl_inference_running = False
    student_count += 1
    esp32_vitals = {"hr": 0, "spo2": 0, "temp": 0.0, "source": "esp32", "status": "disconnected"}
    print(f"[RESET] Student #{student_count} — all buffers cleared")
    return JSONResponse({"status": "ok", "student": student_count})


async def _run_dl_inference(fps_est: float):
    global _dl_inference_running
    _dl_inference_running = True
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, dl_processor.compute_vitals, fps_est)
    finally:
        _dl_inference_running = False


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket endpoint: receives base64 video frames, returns vitals."""
    await ws.accept()

    # Clear stale clients and reset DL buffer for clean per-student session
    dead = {c for c in active_ws_clients}
    for c in dead:
        try:
            await c.send_text('{"type":"ping"}')
        except Exception:
            active_ws_clients.discard(c)
    active_ws_clients.add(ws)
    dl_processor.reset()

    proc = RPPGProcessor(buffer_seconds=10, fps=15)
    frame_count   = 0
    cached_face   = None   # full face bbox — for display
    cached_rppg   = None   # forehead strip — for POS signal extraction
    roi_miss      = 0
    detect_every  = 10

    # Send current ESP32 state only if fresh (< 10s old)
    if (esp32_vitals.get("status") == "connected" and
            time.time() - esp32_vitals.get("timestamp", 0) < 10):
        try:
            await ws.send_text(json.dumps(esp32_vitals))
        except Exception:
            pass

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "frame":
                # Decode base64 JPEG frame
                img_bytes = base64.b64decode(msg["data"])
                nparr = np.frombuffer(img_bytes, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                if frame is None:
                    continue

                # Re-run Haar Cascade every detect_every frames.
                # Only update on success — transient misses keep the old ROI.
                # After 3 consecutive misses the face is truly gone.
                if frame_count % detect_every == 0:
                    new_face, new_rppg = face_detector.detect(frame)
                    if new_face is not None:
                        cached_face = new_face
                        cached_rppg = new_rppg
                        roi_miss    = 0
                    else:
                        roi_miss += 1
                        if roi_miss >= 3:
                            cached_face = None
                            cached_rppg = None
                            roi_miss    = 0
                face_detected = cached_face is not None

                if face_detected:
                    # POS uses forehead-only ROI (above glasses/eyes)
                    mean_rgb = face_detector.extract_roi_rgb(frame, cached_rppg)
                    if mean_rgb is not None:
                        proc.add_frame(mean_rgb)
                    dl_processor.add_frame(frame, cached_face)

                frame_count += 1

                # Compute vitals every 8 frames (more stable, less jitter)
                if frame_count % 8 == 0:
                    vitals = proc.compute_vitals()
                    vitals["face_detected"] = face_detected
                    vitals["type"] = "camera"
                    if face_detected:
                        vitals["face_roi"]  = [int(v) for v in cached_face]
                        vitals["rppg_roi"]  = [int(v) for v in cached_rppg]
                    vitals["bvp"] = [float(v) for v in vitals.get("bvp", [])]
                    if frame_count % 24 == 0 and dl_processor.ready and not _dl_inference_running:
                        ts = list(proc.timestamps)
                        fps_est = len(ts) / (ts[-1] - ts[0] + 1e-10) if len(ts) > 1 else 15.0
                        asyncio.create_task(_run_dl_inference(fps_est))
                    dl = dl_processor._snapshot()
                    vitals["dl_hr"]   = dl['hr']
                    vitals["dl_rr"]   = dl['rr']
                    vitals["dl_spo2"] = dl['spo2']
                    vitals["dl_sbp"]  = dl['sbp']
                    vitals["dl_dbp"]  = dl['dbp']
                    vitals["dl_ready"] = dl_processor.ready
                    vitals["esp32"] = esp32_vitals
                    await ws.send_text(json.dumps(vitals))

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        active_ws_clients.discard(ws)


@app.get("/", response_class=HTMLResponse)
async def home():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/exceljs.min.js")
async def serve_exceljs():
    from fastapi.responses import FileResponse
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "exceljs.min.js"),
        media_type="application/javascript"
    )


@app.get("/download/slides")
async def download_slides():
    from fastapi.responses import FileResponse
    pptx_path = os.path.join(os.path.dirname(__file__), "rPPG_Presentation.pptx")
    return FileResponse(
        pptx_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename="rPPG_Presentation.pptx"
    )


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("=" * 50)
    print("rPPG Vital Signs POC")
    print("=" * 50)
    print("Open : http://127.0.0.1:8090")
    print("Camera : auto-starts in browser")
    print("ESP32  : POST to /api/vitals")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8090)
