# Production Spec — 8-Speaker, 1h+ Speaker-Attributed Transcription with Voice ID

**Audience:** an implementing agent or engineer.
**Status:** research-backed design. Code blocks marked `GLUE — UNTESTED` were written for this spec and have not been executed. Every other fact cites a source in §1.
**Supersedes:** `speaker-attributed-asr-v1.md` and `speaker-attributed-asr-production-practices.md`.
**Research date:** 2026-09-24.
**Not legal advice:** §13 must be reviewed by counsel.

---

## 0. Rules for the implementing agent

| # | Rule |
|---|---|
| R1 | Treat every `[S#]` fact as verified against a primary source on the research date |
| R2 | Treat anything tagged `UNVERIFIED` as a hypothesis — test it before relying on it |
| R3 | Treat `GLUE — UNTESTED` code as a starting point, not working code |
| R4 | Never change a model setting away from a sourced value without a golden-set run (§14) |
| R5 | Pin every model and library to a commit before first production use (§15) |
| R6 | If a source changes after the research date, the source wins over this document |

---

## 1. Sources

Every citation below points back to this table.

| ID | Source | URL |
|---|---|---|
| S1 | NVIDIA blog: Nemotron 3 Diarization | https://huggingface.co/blog/nvidia/nemotron-diarization |
| S2 | Nemotron-3-Diarization model card | https://huggingface.co/nvidia/Nemotron-3-Diarization |
| S3 | Nemotron-3-Diarization ASR Integration Guide | https://huggingface.co/nvidia/Nemotron-3-Diarization/blob/main/ASR_INTEGRATION_GUIDE.md |
| S4 | Nemotron 3.5 ASR streaming model card | https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b |
| S5 | Multitalker Parakeet streaming model card | https://huggingface.co/nvidia/multitalker-parakeet-streaming-0.6b-v1 |
| S6 | Parakeet TDT 0.6B v3 model card | https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3 |
| S7 | Multitalker streaming script source | https://github.com/NVIDIA-NeMo/Speech/blob/main/examples/asr/asr_cache_aware_streaming/speech_to_text_multitalker_streaming_infer.py |
| S8 | TitaNet-Large model card | https://huggingface.co/nvidia/speakerverification_en_titanet_large |
| S9 | NeMo `label_models.py` source | https://github.com/NVIDIA-NeMo/NeMo/blob/main/nemo/collections/asr/models/label_models.py |
| S10 | NeMo-Speech.cpp README | https://github.com/NVIDIA/NeMo-Speech.cpp |
| S11 | NeMo-Speech.cpp CLI guide | https://github.com/NVIDIA/NeMo-Speech.cpp/blob/main/docs/cli.md |
| S12 | NeMo-Speech.cpp server guide | https://github.com/NVIDIA/NeMo-Speech.cpp/blob/main/docs/server.md |
| S13 | pyannote community-1 model card | https://huggingface.co/pyannote/speaker-diarization-community-1 |
| S14 | NeMo speaker diarization config docs | https://docs.nvidia.com/nemo/speech/nightly/asr/speaker_diarization/configs.html |
| S15 | NeMo speaker diarization intro docs | https://docs.nvidia.com/nemo/speech/latest/asr/speaker_diarization/intro.html |
| S16 | Riva ASR NIM support matrix | https://docs.nvidia.com/nim/riva/asr/latest/support-matrix.html |
| S17 | MeetEval toolkit | https://github.com/fgnt/meeteval |
| S18 | SciPy `linear_sum_assignment` | https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html |
| S19 | Massachusetts G.L. c.272 §99 | https://law.justia.com/codes/massachusetts/part-iv/title-i/chapter-272/section-99/ |
| S20 | Florida Statutes §934.03 | https://www.flsenate.gov/Laws/Statutes/2025/934.03 |
| S21 | Illinois BIPA, 740 ILCS 14 | https://law.justia.com/codes/illinois/chapter-740/act-740-ilcs-14/ |
| S22 | GDPR Article 9 | https://gdpr-info.eu/art-9-gdpr/ |

---

## 2. Glossary

| Term | Meaning |
|---|---|
| ASR | Automatic Speech Recognition — speech to text |
| Diarization | Who spoke when, using anonymous speaker labels |
| SA-ASR | Speaker-Attributed ASR — who said what |
| VAD | Voice Activity Detection — speech vs silence |
| Voiceprint / embedding | Numeric vector representing one person's voice |
| Enrollment | Capturing a consented voiceprint for a known person |
| Speaker identification | Matching an unknown voice against N enrolled people |
| DER | Diarization Error Rate — missed speech + false alarm + speaker confusion over total speech time [S1] |
| WER | Word Error Rate |
| cpWER | concatenated minimum-Permutation WER — standard multi-speaker transcript metric [S17] |
| tcpWER | time-constrained cpWER — also penalizes words at the wrong time [S17] |
| EER | Equal Error Rate — point where false accepts equal false rejects [S8] |
| RTFx | Real-Time Factor speedup — audio duration ÷ processing time [S2] |
| SegLST | Segment-wise Long-form Speech Transcription JSON format, used in CHiME challenges [S17] |
| RTTM | Rich Transcription Time Marked — diarization file format [S17] |
| AOSC | Arrival-Order Speaker Cache — the diarizer's streaming memory of earlier speakers [S1] |
| FIFO | First-In-First-Out queue of recent frames [S1] |
| Frame | 80 ms encoder step used by all streaming settings below [S2] |
| GGUF | Model file format used by the ggml C++ runtime [S10] |
| NIM | NVIDIA Inference Microservice |
| SLO | Service Level Objective |
| Pass A | Live streaming pass during the meeting |
| Pass B | Post-session pass on the archived audio; the transcript of record |

---

## 3. Requirements

| ID | Requirement |
|---|---|
| Q1 | Up to 8 speakers per session |
| Q2 | Sessions of 1 hour or longer |
| Q3 | Live streaming text during the session |
| Q4 | A clean final transcript after the session |
| Q5 | Map anonymous speakers to real people |
| Q6 | No single failure loses the session |
| Q7 | Self-hostable on owned NVIDIA GPUs |

---

## 4. Hard constraints

| Constraint | Source |
|---|---|
| Diarizer supports at most 8 speaker channels | S1 |
| More than 8 speakers → speech can be missed or assigned to the wrong channel | S1 |
| Input: 16 kHz, single-channel audio | S2 |
| No model-imposed maximum duration with chunked inference | S2 |
| Quality can degrade on unusually long recordings, noise, reverb, far-field capture, domain shift | S1 |
| Speaker labels are anonymous, not identities | S1 |
| Speaker labels are session-local and change after reconnect | S3 |
| Diarizer runs on Linux with Ampere, Ada, Hopper, or Blackwell GPUs; RTX 3090 and RTX 5090 are listed | S2 |
| Diarizer and ASR chunk geometry must stay aligned — do not tune them independently | S3 |
| GPU memory and compute grow with the number of speaker streams | S3 |
| Multitalker Parakeet needs one model instance per speaker | S5 |

---

## 5. Architecture

### 5.1 Layers

| # | Layer | Responsibility | Section |
|---|---|---|---|
| L1 | Capture | Mic or call audio, consent notice | §13 |
| L2 | Normalize | Convert to 16 kHz mono PCM16 | §9.1 |
| L3 | Archive | Write-once raw audio + SHA-256 | §9.2 |
| L4 | Pass A | Live SA-ASR over WebSocket | §9.3 |
| L5 | Pass B | Batch SA-ASR on archived audio | §9.4, §9.5 |
| L6 | Naming | Map anonymous labels to people | §9.7 |
| L7 | Store | Versioned SegLST with provenance | §9.8 |
| L8 | Evaluate | MeetEval scoring + regression gate | §9.9, §14 |

L3 is the recovery point. Every later layer can be rebuilt from it.

### 5.2 Why two passes

Same diarization model, live vs offline settings [S2]:

| Dataset | Speakers | DER live 1.04 s | DER offline 30.4 s | Speaker-count accuracy live | Speaker-count accuracy offline |
|---|---|---|---|---|---|
| NOTSOFAR1 single far mic | 3–7 | 12.77 | 11.00 | 60.62% | 78.12% |
| NOTSOFAR1 headset mix | 3–7 | 7.70 | 6.77 | 79.37% | 93.75% |
| DIHARD III | 5–9 | 28.65 | 27.58 | — | — |

Pass B also recovers from Pass A reconnects, which reset speaker labels [S3].

---

## 6. Options catalog

### 6.1 Diarization

| Option | Max speakers | Streaming | License | Runtime | Source |
|---|---|---|---|---|---|
| Nemotron-3-Diarization | 8 | Yes | OpenMDW-1.1 | NeMo, Transformers, NeMo-Speech.cpp | S2 |
| diar_streaming_sortformer_4spk-v2.1 | 4 | Yes | See card | NeMo | S1 |
| pyannote community-1 | Settable via `min_speakers` / `max_speakers` | No | CC-BY-4.0, gated | pyannote.audio | S13 |
| pyannote precision-2 | See vendor | No | Commercial API | pyannoteAI cloud | S13 |
| NeMo cascaded: VAD + TitaNet + clustering | Fewer restrictions on speaker count and length | No | See NeMo | NeMo | S15 |
| Riva ASR NIM with Sortformer profile | See NIM | Yes | NVIDIA NIM terms | NIM container | S16 |

Notes:
- The 4-speaker Sortformer is excluded by Q1.
- Which Sortformer checkpoint ships in the Riva NIM profile is `UNVERIFIED`.
- pyannote community-1 offers an *exclusive* diarization output, meant to make reconciling with ASR timestamps easier [S13].

### 6.2 ASR

| Option | Languages | Streaming | Overlap handling | Word timestamps | License | Source |
|---|---|---|---|---|---|---|
| Multitalker Parakeet streaming 0.6B v1 | English | Yes | Built for fully overlapped speech | Via SegLST segments | NVIDIA Open Model License | S5 |
| Nemotron 3.5 ASR streaming 0.6B | 32 locales ready | Yes | Partial, via diarization masking | Yes | OpenMDW-1.1 | S3, S4 |
| Parakeet TDT 0.6B v3 | 25 European languages | Chunked script | None | Yes | CC-BY-4.0 | S6 |

Notes:
- Nemotron 3.5's card recommends the English-only `nemotron-speech-streaming-en-0.6b` for English single-speaker use [S4].
- Multitalker Parakeet uses a different license from the Nemotron models — have it reviewed [S5].

### 6.3 Runtime

| Option | What it is | Production stance by vendor | Source |
|---|---|---|---|
| NeMo Speech, Python | Reference implementation; contains the multitalker integration | Requires recent `main` checkout | S3 |
| Hugging Face Transformers | Native diarizer support with streaming API | Install from source | S2 |
| NeMo-Speech.cpp | C++/ggml runtime; CLI, HTTP, WebSocket, Riva-compatible gRPC | Local use and direct integration; NIM is the supported production path | S12 |
| Riva ASR NIM | Containerized service with diarization profiles | Supported production path | S12, S16 |
| Managed: Baseten, DigitalOcean | Hosted inference for Nemotron-3-Diarization | Partner-listed | S1 |
| Argmax Pro SDK 3 | On-device diarization with pre-diarized transcription | Partner-listed | S1 |

### 6.4 Pass B strategies

| Option | Diarizer | ASR | Overlapped words | Speaker count quality |
|---|---|---|---|---|
| B1 — replay | Nemotron-3 with live geometry | Multitalker Parakeet via S3 script | Attributed per speaker | Live-grade |
| B2 — offline join | Nemotron-3, 30.4 s config | Parakeet TDT v3, local attention | Marked ambiguous | Offline-grade |
| B3 — alternate stack | pyannote community-1, exclusive output | Parakeet TDT v3 | Removed by exclusive diarization | Per S13 benchmarks |

No source compares B1, B2 and B3 end to end. Choose with §14.

### 6.5 Speaker naming

| Option | Stores biometrics | Effort | Source of accuracy |
|---|---|---|---|
| N1 — intro round, map by first-arrival order | No | Lowest | Channels are ordered by first arrival [S2] |
| N2 — human confirms in review UI | No | Low | Person |
| N3 — voiceprint identification | Yes | Highest | Embedding model + calibrated threshold |

### 6.6 Recommended default

| Component | Choice | Reason |
|---|---|---|
| Diarizer | Nemotron-3-Diarization | Only listed option meeting Q1 with streaming |
| Pass A ASR, English | Multitalker Parakeet | Overlap-aware [S5] |
| Pass A ASR, mixed language | Nemotron 3.5 ASR | 32 locales ready [S4] |
| Pass B | B1 and B2 both, pick after §14 | Unmeasured trade-off |
| Runtime | NeMo Speech, Python | Only runtime with the documented multitalker coupling [S3] |
| Naming | N1 + N2 in v1; N3 later | Avoid biometric liability until needed |

---

## 7. Reference configuration

### 7.1 Diarizer latency presets [S2]

All values in 80 ms frames. Input-buffer latency = (chunk + right context) × 80 ms, excluding compute.

| Preset | Input-buffer latency | spkcache_len | fifo_len | chunk_len | chunk_right_context | spkcache_update_period |
|---|---|---|---|---|---|---|
| Offline style | 30.4 s | 264 | 40 | 340 | 40 | 300 |
| Low latency | 1.04 s | 264 | 264 | 9 | 4 | 222 |
| Very low latency | 0.64 s | 264 | 264 | 6 | 2 | 222 |
| Ultra-low latency | 0.32 s | 264 | 264 | 3 | 1 | 222 |

0.32 s is the lowest recommended; 80 ms is technically possible [S2].

### 7.2 ASR latency presets

| Model | att_context_size | Chunk | Source |
|---|---|---|---|
| Multitalker Parakeet | [70,0] | 0.08 s | S5 |
| Multitalker Parakeet | [70,1] | 0.16 s | S5 |
| Multitalker Parakeet | [70,6] | 0.56 s | S5 |
| Multitalker Parakeet | [70,13] | 1.12 s | S5 |
| Nemotron 3.5 ASR | [56,0] | 0.08 s | S4 |
| Nemotron 3.5 ASR | [56,1] | 0.16 s | S4 |
| Nemotron 3.5 ASR | [56,3] | 0.32 s | S4 |
| Nemotron 3.5 ASR | [56,6] | 0.56 s | S4 |
| Nemotron 3.5 ASR | [56,13] | 1.12 s | S4 |

The integration guide recommends [70,13] for Multitalker Parakeet and [56,13] for Nemotron 3.5 [S3].

### 7.3 Multitalker pipeline settings [S3]

| Setting | Multitalker Parakeet | Nemotron 3.5 ASR | Meaning |
|---|---|---|---|
| max_num_of_spks | 8 | 8 | Upper bound on speaker streams |
| masked_asr | false | true | Conditioning vs masking mode |
| parallel_speaker_strategy | true | true | Run speaker streams in parallel |
| cache_gating | true | true | Run ASR only for recently active speakers |
| binary_diar_preds | true | true | Binarize diarizer output |
| att_context_size | [70,13] | [56,13] | ASR latency |
| fifo_len | 264 | 264 | Diarizer FIFO frames |
| spkcache_update_period | 222 | 222 | Frames moved into speaker cache per update |
| target_lang | — | auto or a locale | Language prompt |

---

## 8. Environment setup

Verbatim from S3:

```bash
apt-get update && apt-get install -y libsndfile1 ffmpeg git

git clone --branch main --single-branch https://github.com/NVIDIA-NeMo/Speech.git
cd Speech

curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --python 3.13 --extra asr --extra cu13 --no-dev
source .venv/bin/activate
```

- Use `--extra cu12` if the driver requires CUDA 12 [S3].
- Put `HF_TOKEN` in the environment, never in code [S3].
- For local weights: `hf download nvidia/Nemotron-3-Diarization --local-dir /path/to/Nemotron-3-Diarization` [S3].

Additional packages for this spec:

```bash
pip install meeteval scipy fastapi uvicorn soundfile
```

---

## 9. Implementation

### 9.1 Audio normalization [S3]

```bash
ffmpeg -i input.mp3 -ac 1 -ar 16000 -c:a pcm_s16le conversation.wav
```

### 9.2 Archive writer — GLUE — UNTESTED

Write raw PCM as it arrives, before any model sees it. Finalize to WAV and hash when the session ends.

```python
# archive.py — GLUE — UNTESTED
import hashlib, subprocess, pathlib

class SessionArchive:
    def __init__(self, root: str, session_id: str):
        self.dir = pathlib.Path(root) / session_id
        self.dir.mkdir(parents=True, exist_ok=False)   # write-once: fail if it exists
        self.raw_path = self.dir / "audio.s16le"
        self._f = open(self.raw_path, "ab", buffering=0)  # unbuffered: survive crashes

    def append(self, pcm16_bytes: bytes) -> None:
        self._f.write(pcm16_bytes)

    def finalize(self) -> dict:
        self._f.close()
        wav = self.dir / "audio.wav"
        subprocess.run(
            ["ffmpeg", "-f", "s16le", "-ar", "16000", "-ac", "1",
             "-i", str(self.raw_path), "-c:a", "pcm_s16le", str(wav)],
            check=True,
        )
        h = hashlib.sha256(wav.read_bytes()).hexdigest()
        (self.dir / "audio.wav.sha256").write_text(h)
        return {"wav": str(wav), "sha256": h}
```

Upload `audio.wav` and its hash to object storage with versioning or object lock enabled.

### 9.3 Pass A — live service

**Step 1.** Copy `load_models()` and `LiveMultitalkerSession` verbatim from S3 into `live_session.py`. Keep the source's settings, which include [S3]:

| Key in S3 live config | Value |
|---|---|
| max_num_of_spks | 8 |
| masked_asr | False |
| cache_gating | True |
| binary_diar_preds | True |
| spkcache_update_period | 222 |
| fifo_len | 264 |
| att_context_size | [70, 13] |
| precision | bf16 |
| sent_break_sec | 1.0 |

The S3 live example is configured for Multitalker Parakeet only; Nemotron 3.5 requires its own model-specific settings [S3].

**Step 2.** Wrap the session in a WebSocket server. Service rules from S3:
- Load weights once per worker process.
- One session per client connection.
- Never share a session between clients.
- Model weights may be shared across sessions.
- Add a per-session lock if callbacks can overlap.

```python
# live_server.py — GLUE — UNTESTED
import asyncio, uuid, numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from live_session import load_models, LiveMultitalkerSession   # copied from S3
from archive import SessionArchive

app = FastAPI()
ASR, DIAR = load_models("nvidia/multitalker-parakeet-streaming-0.6b-v1",
                        "nvidia/Nemotron-3-Diarization")      # once per process [S3]

@app.websocket("/v1/sessions")
async def session(ws: WebSocket):
    await ws.accept()
    sid = str(uuid.uuid4())
    archive = SessionArchive("/data/archive", sid)            # §9.2, archive first
    sess = LiveMultitalkerSession(ASR, DIAR, sample_rate=16000)  # never shared [S3]
    lock = asyncio.Lock()                                      # per-session lock [S3]
    await ws.send_json({"type": "session.started", "session_id": sid})
    try:
        while True:
            pcm = await ws.receive_bytes()                     # client sends 16 kHz PCM16 LE
            archive.append(pcm)                                # archive before inference
            async with lock:
                text = await asyncio.to_thread(
                    sess.accept_audio, np.frombuffer(pcm, dtype=np.int16), 16000)
            if text:
                await ws.send_json({"type": "transcript.partial", "text": text})
    except WebSocketDisconnect:
        pass
    finally:
        meta = archive.finalize()
        # enqueue Pass B job here with meta["wav"], meta["sha256"], sid
```

`accept_audio()` returns the latest rendered transcript string [S3]. Treat it as display text only. The record comes from Pass B.

### 9.4 Pass B1 — replay through the multitalker pipeline [S3]

```bash
python examples/asr/asr_cache_aware_streaming/speech_to_text_multitalker_streaming_infer.py \
  asr_model=nvidia/multitalker-parakeet-streaming-0.6b-v1 \
  diar_model=nvidia/Nemotron-3-Diarization \
  audio_file=/absolute/path/to/audio.wav \
  max_num_of_spks=8 \
  single_speaker_mode=false \
  masked_asr=false \
  parallel_speaker_strategy=true \
  cache_gating=true \
  binary_diar_preds=true \
  att_context_size='[70,13]' \
  fifo_len=264 \
  spkcache_update_period=222 \
  generate_realtime_scripts=false \
  output_path=./pass_b1.seglst.json
```

Output is SegLST: text, time range, anonymous speaker per item [S3].

Multilingual variant [S3]: swap the ASR model to `nvidia/nemotron-3.5-asr-streaming-0.6b`, and set `masked_asr=true`, `att_context_size='[56,13]'`, and `target_lang=auto`.

### 9.5 Pass B2 — offline diarizer + Parakeet TDT, joined by word midpoint

Sourced building blocks:

| Block | Source |
|---|---|
| Offline diarizer config and `diarize()` call | S1, S2 |
| Parakeet TDT word timestamps via `transcribe(..., timestamps=True)` | S6 |
| Long-form: `change_attention_model("rel_pos_local_attn", [256,256])` | S6 |
| Full attention handles up to 24 min on A100 80 GB; local attention up to 3 h | S6 |
| Word-to-speaker midpoint rule, marking overlap as ambiguous | S1 |

```python
# pass_b2.py — GLUE — UNTESTED (composes the sourced blocks above)
import json
from nemo.collections.asr.models import SortformerEncLabelModel, ASRModel

WAV = "/absolute/path/to/audio.wav"
SID = "session-id"

# 1. Diarize, offline preset [S2]
diar = SortformerEncLabelModel.from_pretrained("nvidia/Nemotron-3-Diarization").eval()
m = diar.sortformer_modules
m.spkcache_len, m.fifo_len, m.chunk_len = 264, 40, 340
m.chunk_right_context, m.spkcache_update_period = 40, 300
diar._check_streaming_parameters()
segments = diar.diarize(audio=[WAV], batch_size=1)[0]   # "start end speaker_N" strings [S1]
turns = [(float(s), float(e), spk) for s, e, spk in (x.split() for x in segments)]

# 2. Transcribe with word timestamps; local attention for >24 min audio [S6]
asr = ASRModel.from_pretrained(model_name="nvidia/parakeet-tdt-0.6b-v3")
asr.change_attention_model(self_attention_model="rel_pos_local_attn", att_context_size=[256, 256])
words = asr.transcribe([WAV], timestamps=True)[0].timestamp["word"]

# 3. Midpoint join [S1]
def speaker_at(t):
    active = sorted({spk for s, e, spk in turns if s <= t < e})
    if len(active) == 1:
        return active[0]
    return "overlap/ambiguous" if active else "unassigned"

# 4. Group consecutive same-speaker words into SegLST segments [S17 format]
seglst, cur = [], None
for w in words:
    spk = speaker_at((w["start"] + w["end"]) / 2)
    if cur and cur["speaker"] == spk and w["start"] - cur["end_time"] < 1.0:
        cur["words"] += " " + w["word"]
        cur["end_time"] = w["end"]
    else:
        cur = {"session_id": SID, "speaker": spk, "words": w["word"],
               "start_time": w["start"], "end_time": w["end"]}
        seglst.append(cur)

json.dump(seglst, open("pass_b2.seglst.json", "w"), indent=1)
```

- The 1.0 s gap for merging words into one segment is this spec's choice, not a sourced value.
- The midpoint rule does not separate overlapping voices [S1].

### 9.6 Alternative runtimes

**NeMo-Speech.cpp CLI** [S2, S11]:

```bash
nemo-speech diarize meeting.wav --model sortformer.gguf
nemo-speech diarize meeting.wav --format rttm --output meeting.rttm
nemo-speech transcribe meeting.wav --diarize --json
nemo-speech transcribe meeting.wav --vad-model silero.gguf --diar-model sortformer.gguf --json
nemo-speech transcribe recording.wav --device cuda:0
nemo-speech doctor
```

- Streaming geometry is the default; `--offline` gives full attention for *short* recordings [S11].
- The file CLI accepts mono or stereo WAV at 8–96 kHz and downmixes and resamples itself [S11].

**NeMo-Speech.cpp server** [S12]:

| Endpoint | Purpose |
|---|---|
| `GET /health`, `GET /ready` | Health and readiness, 503 until loaded |
| `POST /v1/audio/transcriptions` | OpenAI-compatible transcription |
| `POST /v1/audio/diarizations` | Speaker segments; `mode=streaming` or `offline` |
| WebSocket `/v1/realtime` | Live PCM16 transcription |

- Speaker labels over `/v1/realtime` are not documented in S12 — `UNVERIFIED`.

**Transformers streaming diarizer** [S2]:
- Call `processor.set_streaming_mode("low_latency" | "very_low_latency" | "ultra_low_latency")`.
- Pass `speaker_cache` from each forward call into the next.
- Mark the final chunk with `is_last_audio_chunk=True`.
- The full loop is in S2.

**pyannote community-1** [S13]:

```python
from pyannote.audio import Pipeline
import torch
pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-community-1", token="HF_TOKEN")
pipeline.to(torch.device("cuda"))
output = pipeline("audio.wav", min_speakers=2, max_speakers=8)
for turn, speaker in output.exclusive_speaker_diarization:
    print(speaker, turn.start, turn.end)
```

- Iterating `exclusive_speaker_diarization` the same way as `speaker_diarization` is `UNVERIFIED`. S13 shows the loop only for `speaker_diarization`.

### 9.7 Voice ID — naming speakers

#### 9.7.1 Sourced facts

| Fact | Source |
|---|---|
| Model `nvidia/speakerverification_en_titanet_large`, 23M parameters, English | S8 |
| Input 16 kHz mono | S8 |
| EER 0.66% on VoxCeleb1 cleaned trials | S8 |
| Fine-tune if your domain differs from training data | S8 |
| License CC-BY-4.0 | S8 |
| `get_embedding(path)` reads a file and resamples with librosa | S9 |
| `infer_segment(np_array)` returns `(emb, logits)` for in-memory audio | S9 |
| `verify_speakers` default `threshold=0.7` | S9 |
| That threshold applies to `(cosine + 1) / 2`, i.e. raw cosine ≥ 0.4 | S9 |
| NeMo computes EER with `sklearn.metrics.roc_curve` | S9 |
| `linear_sum_assignment(cost, maximize=True)` gives optimal one-to-one matching, rectangular allowed | S18 |

#### 9.7.2 Flow

| Step | Action |
|---|---|
| 1 | Enroll each consented person: 30–60 s clean speech → embedding → encrypted store |
| 2 | After Pass B, collect each anonymous speaker's single-speaker spans |
| 3 | Embed those spans; average the L2-normalized vectors |
| 4 | Score every speaker against every enrolled person |
| 5 | Solve one-to-one assignment |
| 6 | Accept a match only above the calibrated threshold; otherwise `unknown` |
| 7 | Write names as a separate mapping layer; never overwrite anonymous labels |

- The enrollment duration and the averaging method are this spec's design choices, not sourced values.

#### 9.7.3 Code — GLUE — UNTESTED

```python
# voice_id.py — GLUE — UNTESTED
import numpy as np, soundfile as sf, torch
from scipy.optimize import linear_sum_assignment
from nemo.collections.asr.models import EncDecSpeakerLabelModel

spk_model = EncDecSpeakerLabelModel.from_pretrained(
    "nvidia/speakerverification_en_titanet_large").eval().cuda()

def embed(audio_16k: np.ndarray) -> np.ndarray:
    emb, _ = spk_model.infer_segment(audio_16k.astype(np.float32))   # [S9]
    v = emb.squeeze().cpu().numpy()
    return v / np.linalg.norm(v)

def speaker_embeddings(wav_path, seglst, min_span_s=2.0):
    audio, sr = sf.read(wav_path)
    assert sr == 16000
    per_spk = {}
    for seg in seglst:
        spk = seg["speaker"]
        if spk in ("overlap/ambiguous", "unassigned"):
            continue
        if seg["end_time"] - seg["start_time"] < min_span_s:
            continue
        a = audio[int(seg["start_time"] * sr): int(seg["end_time"] * sr)]
        per_spk.setdefault(spk, []).append(embed(a))
    out = {}
    for spk, vs in per_spk.items():
        m = np.mean(vs, axis=0)
        out[spk] = m / np.linalg.norm(m)
    return out

def assign_names(spk_embs: dict, enrolled: dict, threshold_scaled: float):
    spks, people = list(spk_embs), list(enrolled)
    cos = np.array([[spk_embs[s] @ enrolled[p] for p in people] for s in spks])
    scaled = (cos + 1) / 2                              # same scale as NeMo [S9]
    rows, cols = linear_sum_assignment(scaled, maximize=True)   # [S18]
    mapping = {s: {"name": None, "score": None, "method": "voiceprint"} for s in spks}
    for r, c in zip(rows, cols):
        if scaled[r, c] >= threshold_scaled:
            mapping[spks[r]] = {"name": people[c], "score": float(scaled[r, c]),
                                "method": "voiceprint"}
    return mapping
```

`min_span_s=2.0` is this spec's choice, not a sourced value.

#### 9.7.4 Threshold calibration — GLUE — UNTESTED

```python
# calibrate.py — GLUE — UNTESTED; same EER method as NeMo [S9]
import numpy as np
from sklearn.metrics import roc_curve

def eer_threshold(scores, labels):   # labels: 1 = same person, 0 = different
    fpr, tpr, thr = roc_curve(labels, scores, pos_label=1)
    fnr = 1 - tpr
    i = np.nanargmin(np.abs(fnr - fpr))
    return float(thr[i]), float(fpr[i] * 100)   # threshold, EER %
```

Build same-person and different-person pairs from golden-set sessions (§14), scored on the `(cos+1)/2` scale. For naming, prefer a threshold above EER (fewer false names, more `unknown`).

### 9.8 Canonical record — SegLST plus provenance

SegLST requires `session_id` and `words`. It needs `speaker`, `start_time` and `end_time` for speaker- and time-aware metrics, and allows extra keys [S17].

| Field | Required by | Purpose |
|---|---|---|
| session_id | SegLST | Join key |
| words | SegLST | Text |
| speaker | cpWER | Anonymous label |
| start_time / end_time | tcpWER, DER | Timing |
| speaker_name | This spec | From §9.7 layer, nullable |
| name_method | This spec | intro, human, or voiceprint |
| name_score | This spec | Voiceprint score, nullable |
| pass | This spec | A, B1, B2, or B3 |
| audio_sha256 | This spec | Proves which audio produced it |
| diar_model_rev | This spec | Hugging Face commit |
| asr_model_rev | This spec | Hugging Face commit |
| nemo_commit | This spec | NeMo Speech git commit |
| config_hash | This spec | Hash of every setting in §7 used |
| version / edited_by | This spec | Human edits create new versions |

### 9.9 Evaluation commands [S17]

```bash
meeteval-wer cpwer  -r ref.seglst.json -h pass_b1.seglst.json
meeteval-wer tcpwer -r ref.seglst.json -h pass_b1.seglst.json --collar 5
meeteval-der md_eval_22 -r ref.seglst.json -h pass_b1.seglst.json --collar 0
meeteval-viz html --alignment tcp -r ref.seglst.json -h pass_b1.seglst.json -h pass_b2.seglst.json
```

- NVIDIA's DER numbers use a 0 s collar with overlap scored [S2]. Use the same when comparing.
- Converting files between formats is done with `meeteval-io` [S17].

---

## 10. Tips and traps

| # | Trap | Fix | Source |
|---|---|---|---|
| T1 | Multitalker script defaults `max_num_of_spks=4` | Always pass `max_num_of_spks=8` | S7 |
| T2 | Script defaults `spkcache_len=188`, `fifo_len=188` — the 4-speaker values | Pass `fifo_len=264`, `spkcache_update_period=222` as S3 does | S3, S7 |
| T3 | Script defaults `binary_diar_preds=False` | Pass `true` as S3 does | S3, S7 |
| T4 | Script default `sent_break_sec=30.0`; S3 live example uses `1.0` | Choose deliberately; affects segment breaks | S3, S7 |
| T5 | Multitalker Parakeet card example loads the **4-speaker** diarizer | Follow S3, not S5, for Nemotron-3 | S3, S5 |
| T6 | Tuning ASR and diarizer chunk sizes separately breaks validation | Change them together only | S3 |
| T7 | Quoted latency is input-buffer only | Measure end-to-end, including compute and network | S1 |
| T8 | Multitalker Parakeet runs one instance per speaker | Size GPUs for 8 streams; rely on `cache_gating` | S3, S5 |
| T9 | CUDA out of memory | Lower `max_num_of_spks` | S3 |
| T10 | Labels change after reconnect | Pass B is the record; show a visible gap in live UI | S3 |
| T11 | Sharing a session object across clients corrupts caches | One session per connection; share weights only | S3 |
| T12 | Cutting audio per speaker for a normal ASR merges overlapping voices | Use an overlap-aware ASR or mark overlap | S3 |
| T13 | Midpoint join cannot separate overlapped voices | Keep `overlap/ambiguous` label; don't guess | S1 |
| T14 | Parakeet TDT full attention tops out around 24 min on A100 80 GB | Switch to local attention for 1h+ | S6 |
| T15 | NumPy input without `sample_rate` gives wrong results | Always pass `sample_rate=16000` | S2 |
| T16 | Reproducing model-card DER requires post-processing; default is binarization only | Use NeMo post-processing YAML if comparing to cards | S14 |
| T17 | New diarizer is slightly worse on 2-speaker CALLHOME: 5.98 vs 5.68 DER | Expected; gains are at higher speaker counts | S1 |
| T18 | DIHARD "5–9 speakers" includes 9-speaker audio, beyond the limit | Don't read it as an 8-speaker score | S1 |
| T19 | NeMo `verify_speakers` 0.7 threshold is on `(cos+1)/2`, not raw cosine | Keep one score scale everywhere | S9 |
| T20 | `get_embedding` needs a file path | Use `infer_segment` for in-memory arrays | S9 |
| T21 | TitaNet is English-trained | Recalibrate and consider fine-tuning for other languages | S8 |
| T22 | NeMo-Speech.cpp server binds 127.0.0.1 by default | Remote access needs `--host`, TLS and `NEMO_SPEECH_HTTP_API_KEY` | S12 |
| T23 | `riva_server` uses plaintext gRPC | Terminate TLS in a trusted proxy | S12 |
| T24 | NeMo-Speech.cpp `--offline` diarization is for short recordings | Use streaming geometry for 1h+ | S11 |
| T25 | pyannote community-1 is gated | Accept terms; clone weights for offline use | S13 |
| T26 | Nemotron 3.5 with `target_lang=auto` appends a language tag | Set `strip_lang_tags` or strip before storing | S4 |
| T27 | Speaker labels are not identities | Naming is a separate, reversible layer | S1 |
| T28 | 0.32 s is the lowest *recommended* diarizer buffer | Don't go below without measurement | S2 |

---

## 11. Reliability

### 11.1 Failure modes

| Failure | Effect | Handling |
|---|---|---|
| WebSocket drop | Live labels reset | Reconnect; mark gap; Pass B recovers |
| GPU worker crash | Live text stops | Standby worker; Pass B recovers |
| Archive write fails | Nothing to recover from | Page on-call immediately — the only fatal failure |
| More than 8 voices | Missed or mislabeled speech | Warn at setup; flag low-confidence spans |
| Heavy overlap | Ambiguous attribution | Keep ambiguous labels |
| Late-session drift | Label confusion | Compare first vs last 10 min in §14 |
| Model repository changes | Silent behavior change | Pinned revisions and local mirror (§15) |

### 11.2 Starting SLOs

| SLO | Target |
|---|---|
| Archive completeness | 100% of session audio |
| Pass B completion | Within 1× meeting length |
| Live text availability | 99% of session time |

Revise targets after a month of data.

### 11.3 Capacity

| Fact | Source |
|---|---|
| Diarizer RTFx at batch 1, 1.04 s preset: 38 eager, 164 compiled, on RTX PRO 5000 | S2 |
| Diarizer RTFx at batch 1, 30.4 s preset: 1340 eager, 4385 compiled | S2 |
| Batched throughput is not single-stream end-to-end latency | S1 |
| Per-session GPU memory for 8-speaker multitalker | Not published — `UNVERIFIED`, measure |

---

## 12. Security

| Control | Implementation |
|---|---|
| Encryption at rest | Audio, transcripts, and voiceprints encrypted |
| Separate voiceprint store | Own storage and access role |
| Least privilege | Workers read audio, write transcripts; only the naming service reads voiceprints |
| Audit log | Every read of audio or voiceprints |
| Secrets | `HF_TOKEN`, API keys via environment or secret store only [S3, S12] |
| Network | No service bound publicly without TLS and auth [S12] |

---

## 13. Legal and consent gates

| Rule | Requirement | Source |
|---|---|---|
| Massachusetts | Secret recording without prior authority of all parties is interception | S19 |
| Florida | Interception is lawful when all parties give prior consent | S20 |
| Illinois BIPA | "Voiceprint" is a biometric identifier | S21 |
| Illinois BIPA §15(a) | Public written retention policy; destroy when purpose ends or within 3 years of last interaction, whichever is first | S21 |
| EU GDPR Art. 9 | Biometric data for uniquely identifying a person is a special category; explicit consent is one lawful basis | S22 |

Design consequences:

| Consequence | Implementation |
|---|---|
| Two consents | Recording consent per session; voiceprint consent once at enrollment |
| Consent is data | Store who, when, consent text, and version |
| Unknown speakers stay anonymous | Never create voiceprints for non-enrolled people |
| Deletion works end to end | Deleting a person removes voiceprint and all name mappings |
| Retention schedule enforced | Scheduled job destroys voiceprints per policy |

---

## 14. Acceptance and regression testing

| Step | Detail |
|---|---|
| 1 | Record 5–10 real sessions: all 8 people, 1h+, your actual rooms and mics |
| 2 | Hand-label a golden reference in SegLST; full sessions preferred, at least 10 min each |
| 3 | Run Pass A, B1, B2 and optionally B3 on every session |
| 4 | Score DER, cpWER and tcpWER with §9.9 commands |
| 5 | Compare first 10 min vs last 10 min for drift |
| 6 | Force a mid-session reconnect; confirm Pass B output is complete |
| 7 | If using N3, run §9.7.4 and set the threshold |
| 8 | Freeze the winning config and hash it into `config_hash` |
| 9 | Gate every model, config or library upgrade on no regression vs step 8 |

---

## 15. Model and dependency lifecycle

| Item | Pin by | Reason |
|---|---|---|
| Nemotron-3-Diarization | Hugging Face commit | Released 2026-09-23, still updating [S2] |
| Multitalker Parakeet | Hugging Face commit | Integration evolving with NeMo [S3] |
| Nemotron 3.5 ASR / Parakeet TDT | Hugging Face commit | Reproducibility |
| TitaNet-Large | Hugging Face commit | Voiceprints are only comparable within one model |
| NeMo Speech | Git commit | Multitalker helper is developed on `main` [S3] |
| NeMo-Speech.cpp, if used | Git commit | Young repository [S10] |
| Weights | Mirror to own storage | No dependency on external uptime |

Trap: changing the TitaNet revision invalidates all stored voiceprints. Re-enroll or re-embed from consented enrollment audio.

| Asset | License | Source |
|---|---|---|
| Nemotron-3-Diarization | OpenMDW-1.1 | S2 |
| Nemotron 3.5 ASR | OpenMDW-1.1 | S4 |
| Multitalker Parakeet | NVIDIA Open Model License | S5 |
| Parakeet TDT v3 | CC-BY-4.0 | S6 |
| TitaNet-Large | CC-BY-4.0 | S8 |
| pyannote community-1 | CC-BY-4.0, gated | S13 |
| NeMo-Speech.cpp code | Apache-2.0 | S10 |
| MeetEval | MIT | S17 |

---

## 16. Open questions

| # | Question | How to resolve |
|---|---|---|
| O1 | Capture: one room mic, or one channel per person? | If one channel per person, channel = person and diarization can be skipped |
| O2 | Languages spoken? | Picks Multitalker Parakeet vs Nemotron 3.5 |
| O3 | GPU memory per 8-speaker live session | Measure on target GPU |
| O4 | B1 vs B2 vs B3 quality | §14 |
| O5 | Does the Riva NIM diarization profile ship Nemotron-3? | Check NIM release notes |
| O6 | Does NeMo-Speech.cpp `/v1/realtime` emit speaker labels? | Test or read source |
| O7 | Jurisdictions of all participants | Counsel review of §13 |
