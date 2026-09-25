"""Speaker-attributed live transcription, built the way NVIDIA specifies.

Source of truth (verbatim copies in ./reference, URLs + checksums in reference/SOURCES.md):
  https://huggingface.co/nvidia/Nemotron-3-Diarization/blob/main/ASR_INTEGRATION_GUIDE.md

Pipeline = Nemotron-3-Diarization (frame-level speaker activity, up to 8) coupled to
multitalker-parakeet-streaming-0.6b-v1 (one ASR stream per speaker, conditioned on that activity)
through NeMo's `SpeakerTaggedASR`. Words are attributed to speakers *inside* the model pipeline --
there is no separate "which speaker was active nearest this word" step, and no smoothing of our own.

LiveMultitalkerSession below is the guide's "illustrative streaming loop" (Option 1), unchanged in
its geometry/config. The guide is explicit that ASR and diarization geometry must stay aligned and
must not be tuned independently, so the only knob exposed is max_num_of_spks (which the guide
documents as the compute/memory lever).
"""
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

ASR_MODEL = "nvidia/multitalker-parakeet-streaming-0.6b-v1"
DIAR_MODEL = "nvidia/Nemotron-3-Diarization"
SAMPLE_RATE = 16000

# ---- Tunable settings, each tagged with where its production value comes from ------------------
# GUIDE = the value NVIDIA's ASR_INTEGRATION_GUIDE.md uses (reference/ASR_INTEGRATION_GUIDE.md).
# src "guide table"  : the guide's own settings table documents it.
# src "guide example": appears only in the guide's example config (value given, meaning not documented
#                      there); help text for these comes from the NeMo source/docstrings, not the guide.
# src "model card"   : documented in the multitalker model card (reference/multitalker-...README.md).
GUIDE = {
    "max_num_of_spks": 8, "att_right_context": 13, "fifo_len": 264, "spkcache_update_period": 222,
    "diar_right_context": 0, "masked_asr": False, "parallel_speaker_strategy": True, "cache_gating": True,
    "cache_gating_buffer_size": 2, "binary_diar_preds": True, "sent_break_sec": 1.0,
    "fix_prev_words_count": 5, "update_prev_words_sentence": 5, "word_window": 50,
    "min_sigmoid_val": 0.01, "ignored_initial_frame_steps": 5,
}
META = [
    # group, key, label, kind, extra, src, help
    ("Speaker capacity", "max_num_of_spks", "Max speakers", "range", dict(min=1, max=8, step=1), "guide table",
     "Upper bound on speaker streams kept for the session. Lower it when you know there are fewer people to cut compute. It is not a promise that many will appear."),
    ("Latency (change these together -- NVIDIA: ASR and diarization geometry must stay aligned)", "att_right_context", "ASR right context (frames of 80 ms)", "stops", dict(stops=[0, 1, 6, 13]), "model card",
     "att_context_size=[70, N]. Card: 0=0.08 s, 1=0.16 s, 6=0.56 s, 13=1.12 s output interval. The guide recommends [70,13]. Lower = faster output, but the card evaluates accuracy only at 13."),
    ("Latency (change these together -- NVIDIA: ASR and diarization geometry must stay aligned)", "fifo_len", "Diarizer FIFO length (frames)", "range", dict(min=0, max=264, step=4), "guide table",
     "Recent 80 ms diarization frames kept in the FIFO queue."),
    ("Latency (change these together -- NVIDIA: ASR and diarization geometry must stay aligned)", "spkcache_update_period", "Speaker-cache update period (frames)", "range", dict(min=40, max=300, step=2), "guide table",
     "Oldest FIFO frames moved into the speaker cache per update. Effective value is constrained by chunk and FIFO geometry (guide)."),
    ("Latency (change these together -- NVIDIA: ASR and diarization geometry must stay aligned)", "diar_right_context", "Diarizer right context (frames)", "range", dict(min=0, max=6, step=1), "guide example",
     "Future frames the diarizer sees before deciding. The guide's example uses 0."),
    ("How ASR is coupled to diarization", "parallel_speaker_strategy", "Parallel speaker streams", "toggle", {}, "guide table",
     "Runs the per-speaker ASR streams in parallel."),
    ("How ASR is coupled to diarization", "masked_asr", "Masked ASR", "toggle", {}, "guide table",
     "Guide: false for Multitalker Parakeet (it consumes speaker activity as conditioning); true is for Nemotron 3.5 ASR."),
    ("How ASR is coupled to diarization", "cache_gating", "Cache gating", "toggle", {}, "guide table",
     "Runs speaker-specific ASR only for speakers active in the recent diarization window, saving compute."),
    ("How ASR is coupled to diarization", "cache_gating_buffer_size", "Gating look-back (windows)", "range", dict(min=1, max=6, step=1), "guide example",
     "How many recent diarization windows the gating check looks back over (from NeMo source)."),
    ("How ASR is coupled to diarization", "binary_diar_preds", "Binary speaker activity", "toggle", {}, "guide example",
     "Speaker activity passed to ASR as on/off rather than soft probabilities (per the flag name; the guide gives the value only)."),
    ("How lines are formed (display, not accuracy)", "sent_break_sec", "New line after a pause of (s)", "range", dict(min=0.2, max=6, step=0.1), "guide example",
     "NeMo starts a new segment when the gap between words exceeds this (source docstring: 'minimum time gap between two sentences'). NVIDIA's script and guide both use 1.0 (5.0 is only a fallback inside the NeMo class)."),
    ("How lines are formed (display, not accuracy)", "fix_prev_words_count", "Re-check previous words", "range", dict(min=0, max=10, step=1), "guide example",
     "Number of previous words re-checked/corrected when new words arrive (source docstring)."),
    ("How lines are formed (display, not accuracy)", "update_prev_words_sentence", "Extra words re-rendered", "range", dict(min=0, max=10, step=1), "guide example",
     "Added to the above to set how much of the recent sentence is re-rendered each step (from NeMo source)."),
    ("How lines are formed (display, not accuracy)", "word_window", "Rolling word window", "range", dict(min=10, max=100, step=5), "guide example",
     "Length of the rolling word window kept per speaker (from NeMo source)."),
    ("How lines are formed (display, not accuracy)", "min_sigmoid_val", "Min speaker-activity floor", "range", dict(min=0.001, max=0.1, step=0.001), "guide example",
     "Floor applied to speaker-activity values (NeMo source: clamp(min=...))."),
    ("How lines are formed (display, not accuracy)", "ignored_initial_frame_steps", "Ignored initial steps", "range", dict(min=0, max=10, step=1), "guide example",
     "Initial frame steps ignored by the tagger (from the name and NeMo source)."),
]
TUNABLES = list(GUIDE)


def load_models(asr_model_path=ASR_MODEL, diar_model_path=DIAR_MODEL, device="cuda"):
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
    """One per client connection. Do not share between clients (speaker cache, ASR decoder state,
    timestamps, pending audio and transcript history are all session-specific -- guide)."""

    def __init__(self, asr_model, diar_model, sample_rate=SAMPLE_RATE, settings=None):
        st = {**GUIDE, **(settings or {})}
        self.settings = st
        self.cfg = OmegaConf.create(
            {
                "device": str(asr_model.device),
                "sample_rate": sample_rate,
                "deploy_mode": True,
                "streaming_mode": True,
                "max_num_of_spks": st["max_num_of_spks"],
                "batch_size": 32,
                "parallel_speaker_strategy": st["parallel_speaker_strategy"],
                "masked_asr": st["masked_asr"],
                "mask_preencode": False,
                "single_speaker_mode": False,
                "cache_gating": st["cache_gating"],
                "cache_gating_buffer_size": st["cache_gating_buffer_size"],
                "binary_diar_preds": st["binary_diar_preds"],
                "spkcache_len": None,
                "spkcache_update_period": st["spkcache_update_period"],
                "fifo_len": st["fifo_len"],
                "diar_right_context": st["diar_right_context"],
                "att_context_size": [70, int(st["att_right_context"])],
                "use_amp": True,
                "precision": "bf16",
                "online_normalization": False,
                "pad_and_drop_preencoded": False,
                "feat_len_sec": 0.01,
                "discarded_frames": 8,
                "word_window": st["word_window"],
                "sent_break_sec": st["sent_break_sec"],
                "fix_prev_words_count": st["fix_prev_words_count"],
                "update_prev_words_sentence": st["update_prev_words_sentence"],
                "left_frame_shift": -1,
                "right_frame_shift": 0,
                "min_sigmoid_val": st["min_sigmoid_val"],
                "ignored_initial_frame_steps": st["ignored_initial_frame_steps"],
                "generate_realtime_scripts": True,
                "print_sample_indices": [0],
                "colored_text": False,  # guide sets True for a terminal; we render our own UI
                "verbose": False,
                "print_time": False,
                "log": False,
            }
        )
        self.asr_model = asr_model
        self.diar_model = diar_model
        asr_model.encoder.set_default_att_context_size(list(self.cfg.att_context_size))

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
    def accept_audio(self, pcm_chunk, sample_rate=SAMPLE_RATE):
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

    def segments(self):
        """Current speaker-attributed segments (NeMo SegLST dicts) for this session -- read straight
        from the streamer's own state, exactly what print_sentences() renders in the guide's loop."""
        if self.step_num == 0:
            return []
        return list(self.streamer.instance_manager.batch_asr_states[0].seglsts)
