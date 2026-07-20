"""Lokal, key'siz STT — faster-whisper (CUDA varsa GPU, yoksa CPU).

Env ayarlari:
  WATCH_CEVIZ_WHISPER_MODEL    (default: small)   ornek: small | medium | large-v3
  WATCH_CEVIZ_WHISPER_DEVICE   (default: auto)    auto | cuda | cpu
  WATCH_CEVIZ_WHISPER_COMPUTE  (default: otomatik) ornek: float16 | int8 | int8_float16
  WATCH_CEVIZ_WHISPER_LANGUAGE (default: tr)
"""
from __future__ import annotations

import os
import tempfile
import threading

_model = None
_model_key: tuple | None = None
_active_device = "none"
_lock = threading.Lock()


def is_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:
        return False


def active_device() -> str:
    return _active_device


def _load_model():
    global _model, _model_key, _active_device
    from faster_whisper import WhisperModel

    size = os.environ.get("WATCH_CEVIZ_WHISPER_MODEL", "small").strip() or "small"
    device = os.environ.get("WATCH_CEVIZ_WHISPER_DEVICE", "auto").strip().lower() or "auto"
    compute = os.environ.get("WATCH_CEVIZ_WHISPER_COMPUTE", "").strip()
    key = (size, device, compute)

    with _lock:
        if _model is not None and _model_key == key:
            return _model

        candidates: list[tuple[str, str]] = []
        if device in ("auto", "cuda"):
            candidates.append(("cuda", compute or "float16"))
        if device in ("auto", "cpu"):
            candidates.append(("cpu", compute or "int8"))

        import numpy as np

        last_err: Exception | None = None
        for dev, comp in candidates:
            try:
                model = WhisperModel(size, device=dev, compute_type=comp)
                # CUDA in/lib yuklemesi LAZY: encode'u zorlamak icin minik warmup.
                # Boylece libcublas eksikse burada patlar ve CPU'ya duseriz.
                segs, _ = model.transcribe(np.zeros(16000, dtype=np.float32), vad_filter=False, language="en")
                list(segs)
                _model = model
                _model_key = key
                _active_device = dev
                return model
            except Exception as exc:  # CUDA yok/lib eksik -> sonraki aday (CPU)
                last_err = exc
        raise RuntimeError(f"Whisper modeli yuklenemedi (model={size}): {last_err}")


def warmup() -> str:
    """Modeli onden yukle (boot'ta cagrilir) ki ilk komut yavas olmasin.
    Basarisizsa sessizce gec: ilk gercek istek yine lazy yukler."""
    try:
        _load_model()
    except Exception:
        pass
    return _active_device


def transcribe_bytes(audio_bytes: bytes, audio_format: str = "m4a", language: str | None = None) -> str:
    """Base64'ten cozulmus ses baytlarini metne cevir. Bos string = transkript yok."""
    model = _load_model()
    lang = (language or os.environ.get("WATCH_CEVIZ_WHISPER_LANGUAGE", "tr") or "tr").strip() or None
    suffix = "." + (audio_format or "m4a").lstrip(".")
    with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
        tmp.write(audio_bytes)
        tmp.flush()
        segments, _info = model.transcribe(tmp.name, language=lang, vad_filter=True)
        text = " ".join(seg.text.strip() for seg in segments if seg.text).strip()
    return text
