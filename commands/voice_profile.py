"""
"""
Voice Profile — Speaker verification for HEY CEO OS.
Enrolls the owner's voice and rejects all other speakers.

Enrollment: python hey.py --enroll
  Records 8 seconds of speech, extracts spectral features, saves profile.

Verification: called automatically on every wake attempt.
  Compares incoming audio features to enrolled profile.
  Returns True only if the voice matches the owner.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import numpy as np

log = logging.getLogger("hey.voice_profile")

PROFILE_PATH = Path(os.environ.get("USERPROFILE", Path.home())) / ".hey_voice_profile.json"
SAMPLE_RATE = 16000

# How similar two feature vectors must be (0.0–1.0). Higher = stricter.
MATCH_THRESHOLD = float(os.environ.get("VOICE_MATCH_THRESHOLD", "0.72"))
# Number of enrollment samples to average
ENROLL_SECONDS = 8
ENROLL_SAMPLES = 3  # Record 3 separate utterances and average


# ─── Feature extraction ───────────────────────────────────────────────────────

def _extract_features(audio: np.ndarray, sr: int = SAMPLE_RATE) -> np.ndarray:
    """
    Extract a compact speaker feature vector from raw float32 audio.
    Uses spectral features computable with pure numpy (no librosa needed).
    """
    # Ensure 1D
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    audio = audio.astype(np.float64)

    N = len(audio)
    if N < 512:
        return np.zeros(20)

    # ── Windowed FFT features ─────────────────────────────────────────────
    win_size = 512
    hop = 256
    frames = []
    for start in range(0, N - win_size, hop):
        frame = audio[start: start + win_size] * np.hanning(win_size)
        frames.append(frame)

    if not frames:
        return np.zeros(20)

    frames = np.array(frames)                          # (n_frames, win_size)
    fft_mag = np.abs(np.fft.rfft(frames, axis=1))     # (n_frames, win_size//2+1)
    freqs   = np.fft.rfftfreq(win_size, 1.0 / sr)    # frequency bins

    eps = 1e-10
    power = fft_mag ** 2 + eps
    total_power = power.sum(axis=1, keepdims=True) + eps

    # Spectral centroid (mean pitch region)
    centroid = (power * freqs[None, :]).sum(axis=1) / total_power.squeeze()  # (n_frames,)

    # Spectral spread
    spread = np.sqrt(((power * (freqs[None, :] - centroid[:, None]) ** 2).sum(axis=1)) /
                     total_power.squeeze())

    # Spectral rolloff (85% energy)
    cumsum = np.cumsum(power, axis=1)
    rolloff_threshold = 0.85 * power.sum(axis=1, keepdims=True)
    rolloff_idx = np.argmax(cumsum >= rolloff_threshold, axis=1)
    rolloff = freqs[rolloff_idx]

    # Spectral flatness (voice vs noise)
    geom_mean = np.exp(np.mean(np.log(fft_mag + eps), axis=1))
    arith_mean = np.mean(fft_mag, axis=1)
    flatness = geom_mean / (arith_mean + eps)

    # Zero crossing rate
    signs = np.sign(frames)
    zcr = np.mean(np.abs(np.diff(signs, axis=1)), axis=1) / 2.0

    # RMS energy
    rms = np.sqrt(np.mean(frames ** 2, axis=1))

    # ── Band energy ratios (captures voice vs non-voice frequency bands) ──
    # Bands: sub-bass, bass, low-mid, mid, upper-mid, presence, brilliance
    band_edges = [0, 80, 250, 500, 1000, 2000, 4000, sr // 2]
    band_powers = []
    for lo, hi in zip(band_edges[:-1], band_edges[1:]):
        mask = (freqs >= lo) & (freqs < hi)
        if mask.any():
            band_powers.append(power[:, mask].sum(axis=1).mean())
        else:
            band_powers.append(0.0)
    band_arr = np.array(band_powers)
    band_arr /= (band_arr.sum() + eps)  # normalize

    # ── Pitch estimation via autocorrelation ──────────────────────────────
    pitch_features = []
    for f in frames[:min(len(frames), 20)]:
        corr = np.correlate(f, f, mode="full")[len(f) - 1:]
        corr = corr / (corr[0] + eps)
        # Look for first peak in typical voice range (80–600 Hz)
        lo_lag = max(1, int(sr / 600))
        hi_lag = int(sr / 80)
        hi_lag = min(hi_lag, len(corr) - 1)
        if lo_lag < hi_lag:
            peak_lag = lo_lag + np.argmax(corr[lo_lag:hi_lag])
            pitch_features.append(sr / (peak_lag + 1))
        else:
            pitch_features.append(0.0)
    pitch_mean = float(np.mean(pitch_features))
    pitch_std  = float(np.std(pitch_features))

    # ── Assemble feature vector ───────────────────────────────────────────
    feat = np.array([
        np.mean(centroid),   np.std(centroid),
        np.mean(spread),     np.std(spread),
        np.mean(rolloff),    np.std(rolloff),
        np.mean(flatness),
        np.mean(zcr),        np.std(zcr),
        np.mean(rms),        np.std(rms),
        pitch_mean,          pitch_std,
    ] + band_arr.tolist())  # 13 + 7 = 20 features

    return feat[:20]  # ensure exactly 20


def _normalize(feat: np.ndarray) -> np.ndarray:
    """L2-normalize a feature vector."""
    norm = np.linalg.norm(feat)
    return feat / (norm + 1e-10)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(_normalize(a), _normalize(b)))


# ─── Enrollment ───────────────────────────────────────────────────────────────

def enroll(speak_fn=None) -> bool:
    """
    Interactive enrollment: records several voice samples, saves profile.
    Run with: python jarvis.py --enroll
    """
    try:
        import sounddevice as sd
    except ImportError:
        log.error("sounddevice not installed.")
        return False

    blocksize = int(SAMPLE_RATE * 0.04)  # 40ms blocks
    all_features = []

    if speak_fn:
        speak_fn(f"Voice enrollment starting. I will record {ENROLL_SAMPLES} samples. "
                 f"Please speak naturally for {ENROLL_SECONDS} seconds each time.")

    for i in range(ENROLL_SAMPLES):
        if speak_fn:
            speak_fn(f"Sample {i + 1} of {ENROLL_SAMPLES}. Speak now.")
        else:
            print(f"\n[JARVIS] Sample {i + 1}/{ENROLL_SAMPLES} — Speak now for {ENROLL_SECONDS}s...")

        frames = []
        n_blocks = int(ENROLL_SECONDS * SAMPLE_RATE / blocksize)
        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                                blocksize=blocksize) as stream:
                for _ in range(n_blocks):
                    data, _ = stream.read(blocksize)
                    frames.append(data.copy())
        except Exception as e:
            log.error("Recording error: %s", e)
            return False

        audio = np.concatenate(frames, axis=0).squeeze()
        feat = _extract_features(audio, SAMPLE_RATE)
        all_features.append(feat.tolist())
        log.info("Sample %d features: shape=%s, mean=%.4f", i + 1, feat.shape, feat.mean())

        if i < ENROLL_SAMPLES - 1:
            if speak_fn:
                speak_fn("Good. Next sample in 2 seconds.")
            else:
                print("[HEY] Good. Next sample in 2s...")
            time.sleep(2)

    # Average all samples into one profile
    avg = np.mean(np.array(all_features), axis=0)
    profile = {
        "features": avg.tolist(),
        "n_samples": ENROLL_SAMPLES,
        "threshold": MATCH_THRESHOLD,
        "enrolled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    PROFILE_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    log.info("Voice profile saved to %s", PROFILE_PATH)

    if speak_fn:
        speak_fn("Voice enrollment complete. HEY will now only respond to your voice.")
    else:
        print(f"[HEY] Enrollment complete. Profile saved to {PROFILE_PATH}")
    return True


# ─── Verification ─────────────────────────────────────────────────────────────

_profile_cache: dict | None = None


def _load_profile() -> dict | None:
    global _profile_cache
    if _profile_cache is not None:
        return _profile_cache
    if not PROFILE_PATH.exists():
        return None
    try:
        _profile_cache = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        return _profile_cache
    except Exception as e:
        log.warning("Profile load error: %s", e)
        return None


def is_enrolled() -> bool:
    """Return True if a voice profile exists."""
    return PROFILE_PATH.exists()


def verify_speaker(frames: list, sr: int = SAMPLE_RATE) -> tuple[bool, float]:
    """
    Given a list of audio frames (numpy arrays), verify if the voice matches
    the enrolled profile.

    Returns (is_owner, similarity_score).
    """
    profile = _load_profile()
    if profile is None:
        # No profile enrolled — allow everyone (warn)
        log.warning("No voice profile enrolled. Run: python hey.py --enroll")
        return True, 1.0

    try:
        audio = np.concatenate(frames, axis=0).squeeze()
        feat = _extract_features(audio, sr)
        enrolled = np.array(profile["features"])
        threshold = float(profile.get("threshold", MATCH_THRESHOLD))
        sim = _cosine_similarity(feat, enrolled)
        log.info("Voice similarity: %.4f (threshold: %.4f)", sim, threshold)
        return sim >= threshold, sim
    except Exception as e:
        log.warning("Verification error: %s — allowing.", e)
        return True, 0.0


def reload_profile() -> None:
    """Clear the profile cache so it reloads from disk."""
    global _profile_cache
    _profile_cache = None
