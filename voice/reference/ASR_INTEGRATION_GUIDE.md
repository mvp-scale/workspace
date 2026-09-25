# Use Nemotron-3-Diarization with Streaming ASR

`nvidia/Nemotron-3-Diarization` answers **who spoke when**. To produce a
speaker-attributed transcript—**who said what**—pair it with a compatible ASR
model.

This guide shows two supported streaming ASR pairings:

- Diarization: [`nvidia/Nemotron-3-Diarization`](https://huggingface.co/nvidia/Nemotron-3-Diarization)
- ASR option 1: [`nvidia/multitalker-parakeet-streaming-0.6b-v1`](https://huggingface.co/nvidia/multitalker-parakeet-streaming-0.6b-v1)
- ASR option 2: [`nvidia/nemotron-3.5-asr-streaming-0.6b`](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b)
- Integration: NeMo Speech's [`speech_to_text_multitalker_streaming_infer.py`](https://github.com/NVIDIA-NeMo/Speech/blob/main/examples/asr/asr_cache_aware_streaming/speech_to_text_multitalker_streaming_infer.py)

This is a coupled streaming pipeline. Nemotron-3-Diarization produces
frame-level speaker activity, while the ASR stage maintains a separate
transcription stream for each detected speaker.

## 1. Install NeMo Speech

Use a recent checkout of NeMo Speech because the multi-talker streaming helper
is developed alongside the models.

```bash
apt-get update && apt-get install -y libsndfile1 ffmpeg git

git clone --branch main --single-branch https://github.com/NVIDIA-NeMo/Speech.git
cd Speech

curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --python 3.13 --extra asr --extra cu13 --no-dev
source .venv/bin/activate
```

Use `--extra cu12` instead of `--extra cu13` when your installed NVIDIA driver
and CUDA environment require CUDA 12.

If the Hugging Face repositories require authentication, provide a token that
has access to both models:

```bash
export HF_TOKEN="your-hugging-face-token"
```

Do not put the token in source code or commit it to a repository.

The NeMo example script accepts the Hugging Face repository ID directly:

```bash
diar_model=nvidia/Nemotron-3-Diarization
```

To keep a local copy of the checkpoint instead, download it with:

```bash
hf download nvidia/Nemotron-3-Diarization \
  --local-dir /path/to/Nemotron-3-Diarization
```

Then replace the repository ID in the commands below with
`/path/to/Nemotron-3-Diarization/Nemotron-3-Diarization.nemo`.

## 2. Prepare the audio

The paired models expect single-channel, 16 kHz audio. Convert other inputs
before inference:

```bash
ffmpeg -i input.mp3 -ac 1 -ar 16000 -c:a pcm_s16le conversation.wav
```

## 3. Choose the ASR model

Use one of the following ASR configurations with Nemotron-3-Diarization.

### Option 1: Multitalker Parakeet

[`nvidia/multitalker-parakeet-streaming-0.6b-v1`](https://huggingface.co/nvidia/multitalker-parakeet-streaming-0.6b-v1)
is a streaming ASR model fine-tuned for overlapping speech. It supports English
only and should be used with `masked_asr=false`.

From the NeMo Speech repository root, run:

```bash
python examples/asr/asr_cache_aware_streaming/speech_to_text_multitalker_streaming_infer.py \
  asr_model=nvidia/multitalker-parakeet-streaming-0.6b-v1 \
  diar_model=nvidia/Nemotron-3-Diarization \
  audio_file=/absolute/path/to/conversation.wav \
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
  output_path=./speaker_attributed_output.json
```

### Option 2: Nemotron 3.5 ASR

[`nvidia/nemotron-3.5-asr-streaming-0.6b`](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b)
is a regular single-speaker streaming ASR model. In this speaker-attributed
pipeline, it can use masked speaker activity to recognize overlapped speech to a
certain degree. It supports 32 language-locales out of the box; its tokenizer
supports eight additional adaptation-ready locales that require fine-tuning.
Use it with `masked_asr=true`.

Set `target_lang` to the input language-locale, or use `target_lang=auto` when
the model should infer the language prompt automatically.

```bash
python examples/asr/asr_cache_aware_streaming/speech_to_text_multitalker_streaming_infer.py \
  asr_model=nvidia/nemotron-3.5-asr-streaming-0.6b \
  diar_model=nvidia/Nemotron-3-Diarization \
  audio_file=/absolute/path/to/conversation.wav \
  max_num_of_spks=8 \
  single_speaker_mode=false \
  masked_asr=true \
  parallel_speaker_strategy=true \
  cache_gating=true \
  binary_diar_preds=true \
  att_context_size='[56,13]' \
  fifo_len=264 \
  spkcache_update_period=222 \
  target_lang=auto \
  generate_realtime_scripts=false \
  output_path=./speaker_attributed_output.json
```

The script writes the final result to `speaker_attributed_output.json` in
NeMo's SegLST format. Each finalized item contains its text, time range, and
anonymous speaker label. Set `generate_realtime_scripts=true` to also print
streaming hypotheses.

The important settings are:

| Setting | Meaning |
|---|---|
| `max_num_of_spks=8` | Maximum number of speaker streams maintained for the session. Lower this when the use case has fewer speakers to reduce compute. |
| `parallel_speaker_strategy=true` | Processes the speaker-specific ASR streams in parallel. |
| `masked_asr=false` | Use this with Multitalker Parakeet, which consumes speaker activity as conditioning. |
| `masked_asr=true` | Use this with Nemotron 3.5 ASR, which uses diarization activity to mask each speaker stream. |
| `att_context_size='[70,13]'` | Recommended context for Multitalker Parakeet. |
| `att_context_size='[56,13]'` | Recommended context for Nemotron 3.5 ASR. |
| `cache_gating=true` | Runs speaker-specific ASR only for speakers detected as active in the recent diarization window, reducing unnecessary ASR computation. |
| `fifo_len=264` | Maximum number of recent 80 ms diarization encoder frames retained in the FIFO queue. |
| `spkcache_update_period=222` | Number of the FIFO queue's oldest 80 ms frames transferred during each speaker-cache update; the effective value is constrained by the chunk and FIFO geometry. |

`max_num_of_spks` is an upper bound, not a promise that every configured speaker
will appear. The diarization model discovers active speaker identities from the
audio.

A typical rendered result looks like:

```text
Speaker 0: Welcome, everyone. Let us begin.
Speaker 1: I have the latest numbers.
Speaker 2: I agree, but there is one remaining issue.
```

Speaker numbers represent identities discovered during that stream. They do not
identify real-world names. If an application displays names, it must associate
those names separately—for example through an enrollment or application-level
mapping step.

## Real-time microphone or service integration

The `speech_to_text_multitalker_streaming_infer.py` example is best understood
as an offline streaming replay and evaluation driver. It exercises the streaming
model path chunk by chunk, but it reads from files or manifests that are already
available. A production web, microphone, or websocket service needs a persistent
session per client and must feed newly arriving PCM chunks into that session.

A live interface sends audio chunks to the server, which buffers them into the
model's required hop/cache geometry and passes each completed frame to NeMo
Speech's `SpeakerTaggedASR`. Gradio is one of many possible interface options;
alternatives include a custom web UI, a desktop or mobile application, an HTTP
API, or a raw websocket client.

The service structure is:

1. Load the ASR and diarization checkpoints once per worker process.
2. Create a new streaming session for each live client connection.
3. For each incoming mono PCM chunk, resample to 16 kHz if needed, append it to
   that client's pending audio buffer, and process every complete streaming
   frame.
4. Return the latest speaker-attributed transcript and, if desired, the latest
   diarization activity state to the client.
5. Reset the client's session when the recording stops or the websocket closes.

The illustrative streaming loop below is configured specifically for Option 1,
Multitalker Parakeet. Option 2 requires its corresponding model-specific
settings.

```python
import os

import numpy as np
import torch
from omegaconf import OmegaConf

import nemo.collections.asr as nemo_asr
from nemo.collections.asr.models.sortformer_diar_models import SortformerEncLabelModel
from nemo.collections.asr.parts.utils.multispk_transcribe_utils import (
    SpeakerTaggedASR,
    configure_diar_streaming,
    validate_feature_frame_strides,
)
from nemo.collections.asr.parts.utils.streaming_utils import CacheAwareStreamingAudioBuffer


def load_models(asr_model_path, diar_model_path, device="cuda"):
    if os.path.isfile(asr_model_path):
        asr_model = nemo_asr.models.ASRModel.restore_from(restore_path=asr_model_path)
    else:
        asr_model = nemo_asr.models.ASRModel.from_pretrained(asr_model_path)

    if os.path.isfile(diar_model_path):
        diar_model = SortformerEncLabelModel.restore_from(restore_path=diar_model_path, map_location=device)
    else:
        diar_model = SortformerEncLabelModel.from_pretrained(diar_model_path)

    asr_model.eval().to(device)
    diar_model.eval().to(device)
    asr_model.encoder.set_default_att_context_size([70, 13])

    validate_feature_frame_strides(asr_model=asr_model, diar_model=diar_model)
    return asr_model, diar_model


class LiveMultitalkerSession:
    def __init__(self, asr_model, diar_model, sample_rate=16000):
        self.cfg = OmegaConf.create(
            {
                "device": str(asr_model.device),
                "sample_rate": sample_rate,
                "deploy_mode": True,
                "streaming_mode": True,
                "max_num_of_spks": 8,
                "batch_size": 32,
                "parallel_speaker_strategy": True,
                "masked_asr": False,
                "mask_preencode": False,
                "single_speaker_mode": False,
                "cache_gating": True,
                "cache_gating_buffer_size": 2,
                "binary_diar_preds": True,
                "spkcache_len": None,
                "spkcache_update_period": 222,
                "fifo_len": 264,
                "diar_right_context": 0,
                "att_context_size": [70, 13],
                "use_amp": True,
                "precision": "bf16",
                "online_normalization": False,
                "pad_and_drop_preencoded": False,
                "feat_len_sec": 0.01,
                "discarded_frames": 8,
                "word_window": 50,
                "sent_break_sec": 1.0,
                "fix_prev_words_count": 5,
                "update_prev_words_sentence": 5,
                "left_frame_shift": -1,
                "right_frame_shift": 0,
                "min_sigmoid_val": 1e-2,
                "ignored_initial_frame_steps": 5,
                "generate_realtime_scripts": True,
                "print_sample_indices": [0],
                "colored_text": True,
                "verbose": False,
                "print_time": False,
                "log": False,
            }
        )
        self.asr_model = asr_model
        self.diar_model = diar_model

        streaming_cfg = asr_model.encoder.streaming_cfg
        diar_chunk_len = streaming_cfg.valid_out_len + streaming_cfg.cache_drop_size
        configure_diar_streaming(
            diar_model=diar_model,
            cfg=self.cfg,
            output_subsampling_factor=asr_model.encoder.subsampling_factor,
            diar_chunk_len=diar_chunk_len,
        )
        self.cfg.spkcache_len = int(diar_model.sortformer_modules.spkcache_len)

        self.streamer = SpeakerTaggedASR(self.cfg, asr_model, diar_model)
        self.audio_buffer = CacheAwareStreamingAudioBuffer(
            model=asr_model,
            online_normalization=self.cfg.online_normalization,
        )

        feature_stride = float(asr_model.cfg.preprocessor.window_stride)
        hop_feature_frames = streaming_cfg.valid_out_len * asr_model.encoder.subsampling_factor
        self.hop_samples = round(hop_feature_frames * feature_stride * sample_rate)

        cache_frames = streaming_cfg.pre_encode_cache_size
        if isinstance(cache_frames, (list, tuple)):
            cache_frames = cache_frames[-1]
        cache_samples = round(cache_frames * feature_stride * sample_rate)
        self.frame_samples = self.hop_samples + cache_samples
        self.pending_audio = np.zeros(cache_samples, dtype=np.float32)
        self.step_num = 0

    @torch.inference_mode()
    def accept_audio(self, pcm_chunk, sample_rate):
        """Accept one live mono PCM chunk and return the latest transcript text."""
        if pcm_chunk.dtype == np.int16:
            pcm_chunk = pcm_chunk.astype(np.float32) / 32768.0
        elif pcm_chunk.dtype == np.int32:
            pcm_chunk = pcm_chunk.astype(np.float32) / 2147483648.0
        else:
            pcm_chunk = pcm_chunk.astype(np.float32)

        # Resample here when sample_rate != self.cfg.sample_rate.
        self.pending_audio = np.concatenate([self.pending_audio, pcm_chunk])

        latest = None
        while len(self.pending_audio) >= self.frame_samples:
            frame = self.pending_audio[: self.frame_samples]
            self.pending_audio = self.pending_audio[self.hop_samples :]

            chunk_audio, chunk_lengths = self.audio_buffer.preprocess_audio(frame)
            chunk_audio = chunk_audio[:, :, : chunk_lengths[0]]
            drop_extra_pre_encoded = (
                0
                if self.step_num == 0
                else self.asr_model.encoder.streaming_cfg.drop_extra_pre_encoded
            )
            latest = self.streamer.perform_parallel_streaming_stt_spk(
                step_num=self.step_num,
                chunk_audio=chunk_audio,
                chunk_lengths=chunk_lengths,
                is_buffer_empty=False,
                drop_extra_pre_encoded=drop_extra_pre_encoded,
            )
            self.step_num += 1

        return "" if latest is None else latest[0]
```

Connect `accept_audio()` to the interface or transport used by your application.
For a network service, create the session when the client connects, call
`accept_audio()` for each decoded PCM message, and delete the session when the
client disconnects. Protect each session with a small lock if your server can
deliver overlapping callbacks for the same client.

Do not share the session object between clients: the speaker cache, ASR decoder
state, timestamps, pending audio buffer, and transcript history are all
session-specific.

Model weights may be shared across connections to save GPU memory, provided
each connection receives independent `SpeakerTaggedASR`, streaming-buffer, and
speaker-cache state.

## Choosing another ASR model

A conventional single-speaker ASR can be applied after diarization by cutting
the audio at each speaker segment and transcribing the cuts. That approach is
reasonable when speakers rarely overlap. It is not an equivalent replacement
for Multitalker Parakeet: an extracted time range still contains every voice
that overlaps it, so a conventional ASR may merge or select the wrong speaker's
words.

For overlap-aware speaker-attributed transcription, use an ASR model designed
to consume speaker activity and verify that its encoder frame geometry is
compatible with the diarization model.

## Troubleshooting

- **Only plain text appears:** Ensure you launched the multi-talker inference
  script with both `asr_model` and `diar_model`, rather than calling
  `asr_model.transcribe()` by itself.
- **A model cannot be downloaded:** Accept any required model terms and verify
  that `HF_TOKEN` can read both repositories.
- **Audio is rejected or results are poor:** Convert it to mono, 16-bit PCM at
  16 kHz.
- **CUDA out of memory:** Reduce `max_num_of_spks`. The multi-talker architecture
  maintains speaker-specific ASR state, so memory and compute grow with the
  number of simultaneous speaker streams.
- **Speaker labels change after reconnecting:** Labels are session-local and are
  not biometric identities.
- **Streaming parameters fail validation:** Start with the configuration above.
  The ASR and diarization chunk geometry must remain aligned; do not tune each
  model independently.
