"""Thin wrapper around NeMo's bundled streaming diarization + ASR services.

Both `NeMoStreamingDiarService` and `NemoStreamingASRService` (nemo/agents/voice_agent/pipecat/
services/nemo/{streaming_diar,streaming_asr}.py) are pipecat service classes, but neither file
actually imports pipecat -- `.diarize(audio_bytes)` / `.transcribe(audio_bytes)` are plain,
stateful, synchronous methods that internally buffer whatever-sized chunk you hand them until
there's enough for a model step. That lets us drive them directly from a plain WebSocket loop
instead of pulling in the full pipecat Frame/Pipeline machinery.

Single-session only (module-level singletons): fine for a one-mic mockup, not for concurrent
callers. Audio in is mono 16kHz signed 16-bit PCM bytes, matching what both models expect.

Settings are live-reconfigurable via configure() -- see server.py's "configure" WS command and
mockup.html's Settings panel -- so wrong-guess parameters (there's real history of that: NeMo's
own published "very low latency" preset measurably degraded output in this pipeline vs the
smaller-buffer defaults below) can be tried and compared without restarting the process.
"""
import sys
import types

import numpy as np

# The package's own __init__.py eagerly imports ALL sibling services (diar, llm, stt, tts,
# turn_taking) -- pulling in unrelated OpenAI/TTS/vocoder deps we don't need just to reach
# streaming_diar/streaming_asr, which aren't even in that __init__'s export list. Stub the
# siblings out in sys.modules before the package initializes so Python skips executing them.
_PKG = "nemo.agents.voice_agent.pipecat.services.nemo"
for _mod, _attr in [("diar", "NemoDiarService"), ("llm", "HuggingFaceLLMService"), ("stt", "NemoSTTService"),
                     ("tts", "NeMoFastPitchHiFiGANTTSService"), ("turn_taking", "NeMoTurnTakingService")]:
    _name = f"{_PKG}.{_mod}"
    if _name not in sys.modules:
        _stub = types.ModuleType(_name)
        setattr(_stub, _attr, None)
        sys.modules[_name] = _stub

from nemo.agents.voice_agent.pipecat.services.nemo.streaming_diar import DiarizationConfig, NeMoStreamingDiarService
from nemo.agents.voice_agent.pipecat.services.nemo.streaming_asr import NemoStreamingASRService

DIAR_MODEL = "nvidia/Nemotron-3-Diarization"
ASR_MODEL = "nvidia/parakeet_realtime_eou_120m-v1"
MAX_SPEAKERS = 8
SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2  # s16le

# nvidia/Nemotron-3-Diarization's model card publishes four coordinated presets, all in 80ms
# frames (frame_len_in_secs): offline/30.4s, "low latency"/1.04s (chunk_len=9, right_context=4),
# "very low latency"/0.64s (chunk_len=6, right_context=2), "ultra low latency"/0.32s (chunk_len=3,
# right_context=1) -- fifo_len=264, spkcache_len=264, spkcache_update_period=222 across all three
# streaming presets. These are DEFAULT_SETTINGS's values (the 1.04s "low latency" a.k.a.
# "Balanced" preset): A/B tested here under real-time-paced audio and it decodes real speech
# correctly with smooth, well-paced timing throughout.
#
# The 0.64s "very low latency" a.k.a. "Fast" preset (chunk_len=6) was ALSO A/B tested here, under
# the same real-time pacing, and measurably failed -- word fragments disappeared entirely. The
# likely cause isn't the fifo/spkcache values themselves (Balanced uses the same ones and works
# fine); it's real-time compute budget: Fast's 640ms-per-chunk window may simply be tighter than
# this heavier config's actual per-chunk compute time on this hardware, so it falls behind and
# backlogs. Re-verify with real measurement (the Settings panel's Apply lets you A/B this
# yourself) before trusting Fast/Ultra for a live mic rather than assuming they're safe because
# NVIDIA publishes them.
DEFAULT_SETTINGS = {
    "diar_chunk_len": 9,               # frames (x frame_len_in_secs=0.08s) per diarize() call
    "diar_fifo_len": 264,
    "diar_spkcache_len": 264,
    "diar_chunk_right_context": 4,
    "diar_spkcache_update_period": 222,
    "asr_chunk_size_in_secs": 0.08,    # native ASR call stride; 0.08s = 1280 samples @16kHz
    "max_speakers": 8,
    # Not a model setting -- how quickly the DISPLAYED speaker label follows the diarizer (EMA
    # alpha over per-chunk speaker confidence). Low = sticky (one person keeps the same label
    # through noise, but a new person is slow to register, so two people get one label); high =
    # responsive (turn changes show quickly, but more flicker). Applied instantly, no reload.
    "speaker_smoothing": 0.5,
}
MODEL_KEYS = ("diar_chunk_len", "diar_fifo_len", "diar_spkcache_len", "diar_chunk_right_context",
              "diar_spkcache_update_period", "asr_chunk_size_in_secs", "max_speakers")

# Officially published presets (see comment above) plus the pipecat wrapper's own original
# defaults (smaller buffers, aimed at an older 4-speaker model) kept as a documented fallback --
# it's what this pipeline ran on before Balanced was verified, still fine if you want to compare.
PRESETS = {
    "balanced": {"diar_chunk_len": 9, "diar_chunk_right_context": 4, "diar_fifo_len": 264,
                 "diar_spkcache_len": 264, "diar_spkcache_update_period": 222},
    "fast": {"diar_chunk_len": 6, "diar_chunk_right_context": 2, "diar_fifo_len": 264,
             "diar_spkcache_len": 264, "diar_spkcache_update_period": 222},
    "ultra": {"diar_chunk_len": 3, "diar_chunk_right_context": 1, "diar_fifo_len": 264,
              "diar_spkcache_len": 264, "diar_spkcache_update_period": 222},
    "legacy_small_buffers": {"diar_chunk_len": 6, "diar_chunk_right_context": 7, "diar_fifo_len": 188,
                              "diar_spkcache_len": 264, "diar_spkcache_update_period": 144},
}

_settings = dict(DEFAULT_SETTINGS)
_diar = None
_asr = None
DIAR_CHUNK_SAMPLES = None
ASR_CHUNK_SAMPLES = None
_diar_carry = b""
_asr_carry = b""

# Per-chunk raw argmax speaker jitters -- a continuously-speaking person's dominant speaker index
# can flip between adjacent diar chunks even with no real speaker change (normal for real-time
# diarization; never actually exercised with a real multi-speaker conversation until now, since
# every test in this file's development used a single synthetic TTS voice). Smooth with an EMA
# over per-speaker frame-averaged probabilities so a switch requires sustained evidence across
# several chunks, not one noisy chunk, before the displayed speaker label actually changes.
_speaker_ema = None
SPEAKER_EMA_ALPHA = 0.3  # lower = more stable/slower to switch, higher = more responsive/jitterier


def _build(settings: dict):
    diar_kwargs = dict(
        model_path=DIAR_MODEL, max_num_speakers=settings.get("max_speakers", MAX_SPEAKERS),
        chunk_len=settings["diar_chunk_len"], fifo_len=settings["diar_fifo_len"],
        chunk_right_context=settings["diar_chunk_right_context"],
        spkcache_update_period=settings["diar_spkcache_update_period"],
    )
    # NOTE (verified, not just assumed): lowering max_num_speakers below the checkpoint's
    # trained 8 does NOT reduce diarization compute here -- it only resizes the wrapper's own
    # bookkeeping tensor (total_preds), which then mismatches the model's real 8-channel output
    # and makes diarize() return empty results every call (silently -- no exception), while ASR
    # keeps working normally since it doesn't depend on this at all. Confirmed by testing
    # max_speakers=2 directly: diar output went empty, texts kept decoding. Not exposed in the
    # UI for this reason; kept configurable here in case a future NeMo version fixes it.
    if settings.get("diar_spkcache_len") is not None:
        diar_kwargs["spkcache_len"] = settings["diar_spkcache_len"]
    diar = NeMoStreamingDiarService(DiarizationConfig(**diar_kwargs), model=DIAR_MODEL)

    asr = NemoStreamingASRService(model=ASR_MODEL, chunk_size_in_secs=settings["asr_chunk_size_in_secs"])
    # Real (non-blank) speech hits decoding token/duration shapes the greedy CUDA-graph decoder
    # hasn't captured yet, triggering a JIT compile that can stall the calling thread for many
    # seconds while holding the GIL -- long enough to starve an event loop or HTTP accept loop.
    # Disabling the graph decoder trades a little steady-state speed for no compile stalls.
    decoding_cfg = asr.asr_model.cfg.decoding
    decoding_cfg.greedy.use_cuda_graph_decoder = False
    asr.asr_model.change_decoding_strategy(decoding_cfg)
    return diar, asr


def load():
    global _diar, _asr, DIAR_CHUNK_SAMPLES, ASR_CHUNK_SAMPLES
    if _diar is None or _asr is None:
        _diar, _asr = _build(_settings)
        DIAR_CHUNK_SAMPLES = round(_diar.cfg.chunk_len * _diar.frame_len_in_secs * SAMPLE_RATE)
        ASR_CHUNK_SAMPLES = round(_asr.chunk_size_in_secs * SAMPLE_RATE)
        warmup()
    return _diar, _asr


def warmup():
    """Absorb the first-inference JIT/kernel-autotune cost (separate from weight loading --
    several seconds otherwise) once, up front, instead of on a live user's first real chunk."""
    diar, asr = _diar, _asr
    diar.diarize(b"\x00\x00" * DIAR_CHUNK_SAMPLES)
    asr.transcribe(b"\x00\x00" * ASR_CHUNK_SAMPLES)
    diar.reset_state()
    asr.reset_state()


def effective_settings() -> dict:
    sm = _diar.diarizer.sortformer_modules
    return {
        "diar_chunk_len": sm.chunk_len,
        "diar_fifo_len": sm.fifo_len,
        "diar_spkcache_len": sm.spkcache_len,
        "diar_chunk_right_context": sm.chunk_right_context,
        "diar_spkcache_update_period": sm.spkcache_update_period,
        "asr_chunk_size_in_secs": _asr.chunk_size_in_secs,
        "max_speakers": _settings.get("max_speakers", MAX_SPEAKERS),
        "speaker_smoothing": _settings.get("speaker_smoothing", DEFAULT_SETTINGS["speaker_smoothing"]),
        "diar_chunk_samples": DIAR_CHUNK_SAMPLES,
        "asr_chunk_samples": ASR_CHUNK_SAMPLES,
    }


def configure(new_settings: dict) -> dict:
    """Tear down and rebuild both models with updated settings (~seconds -- reloads from the
    local HF cache, does not re-download). Raises if NeMo's own _check_streaming_parameters()
    rejects the combination; callers should catch and report rather than let it crash the
    session, and the OLD models stay live until a new build fully succeeds (build-then-swap, not
    mutate-in-place) so a bad settings combo can't leave the pipeline half-broken."""
    global _diar, _asr, _settings, DIAR_CHUNK_SAMPLES, ASR_CHUNK_SAMPLES
    merged = {**_settings, **{k: v for k, v in new_settings.items() if v is not None}}
    if all(merged.get(k) == _settings.get(k) for k in MODEL_KEYS):
        _settings = merged  # only non-model settings (smoothing) changed: no reload, no reset
        return effective_settings()
    diar, asr = _build(merged)  # if this raises, the old _diar/_asr are untouched
    _diar, _asr = diar, asr
    _settings = merged
    DIAR_CHUNK_SAMPLES = round(_diar.cfg.chunk_len * _diar.frame_len_in_secs * SAMPLE_RATE)
    ASR_CHUNK_SAMPLES = round(_asr.chunk_size_in_secs * SAMPLE_RATE)
    warmup()
    reset()
    return effective_settings()


def reset():
    global _diar_carry, _asr_carry, _speaker_ema
    diar, asr = load()
    diar.reset_state()
    asr.reset_state()
    _diar_carry = b""
    _asr_carry = b""
    _speaker_ema = None


def feed(raw_bytes: bytes) -> list:
    """Accumulate arbitrary-sized incoming audio (e.g. a WebSocket message of whatever size the
    browser's audio callback produced) and run each model at its OWN native call stride --
    independently, since diar_chunk_samples and asr_chunk_samples need not be a clean multiple of
    each other once settings are adjustable. Emits one event per completed model step, in
    completion order: {"kind": "diar", ...} or {"kind": "asr", ...}.

    Both models' CacheFeatureBufferer advance their feature window by a FIXED stride set at
    init, no matter how much audio a single call actually contains -- feed anything other than
    exactly that many samples per call and the feature window silently desyncs from the real
    audio (no exception, just empty/garbled decoding). This is why calls are sliced to exactly
    DIAR_CHUNK_SAMPLES / ASR_CHUNK_SAMPLES, never an arbitrary sub-chunk size.
    """
    global _diar_carry, _asr_carry, _speaker_ema
    diar, asr = load()
    _diar_carry += raw_bytes
    _asr_carry += raw_bytes
    diar_step = DIAR_CHUNK_SAMPLES * BYTES_PER_SAMPLE
    asr_step = ASR_CHUNK_SAMPLES * BYTES_PER_SAMPLE
    results = []
    while len(_diar_carry) >= diar_step:
        chunk, _diar_carry = _diar_carry[:diar_step], _diar_carry[diar_step:]
        probs = diar.diarize(chunk)  # (frames, MAX_SPEAKERS)
        speakers = probs.argmax(axis=-1).tolist() if probs.size else []
        avg = probs.mean(axis=0) if probs.size else np.zeros(_diar.max_num_speakers)
        alpha = _settings.get("speaker_smoothing", SPEAKER_EMA_ALPHA)
        _speaker_ema = avg if _speaker_ema is None else alpha * avg + (1 - alpha) * _speaker_ema
        results.append({
            "kind": "diar", "speakers": speakers, "speaker_probs": np.round(probs, 3).tolist(),
            "smoothed_speaker": int(np.argmax(_speaker_ema)),
        })
    while len(_asr_carry) >= asr_step:
        chunk, _asr_carry = _asr_carry[:asr_step], _asr_carry[asr_step:]
        r = asr.transcribe(chunk)
        # The literal "<EOU>"/"<EOB>" marker can appear INSIDE the decoded text itself (that's
        # how the ASR service's own is_final flag gets set, by checking for that substring) --
        # it's control information, not transcript content, so strip it before it reaches the UI.
        # Only touch the string when a marker is actually present: every real word fragment
        # starts with a meaningful leading space (the tokenizer's word-boundary marker) that an
        # unconditional .strip() would destroy, gluing consecutive fragments together client-side.
        text = r.text
        if asr.eou_string in text or asr.eob_string in text:
            text = text.replace(asr.eou_string, "").replace(asr.eob_string, "").strip()
        results.append({"kind": "asr", "text": text, "is_final": r.is_final})
    return results


if __name__ == "__main__":
    import time

    load()
    print("models loaded ok", file=sys.stderr)
    chunk = (np.random.randint(-500, 500, DIAR_CHUNK_SAMPLES, dtype=np.int16)).tobytes()
    for i in range(20):
        t0 = time.time()
        out = feed(chunk)
        print(f"chunk {i}: {time.time()-t0:.3f}s -> {out}", file=sys.stderr)
