"""Load Audio Batch From Dir  --  audio version of "Load Image Batch From Dir (Inspire)".

Same inputs and behaviour as the Inspire node, for audio files:
  directory       folder to read
  audio_load_cap  load at most this many files (0 = no limit)           [image_load_cap]
  start_index     skip this many files first (-1 = the last file)       [start_index]
  load_always     re-run every time instead of only when inputs change  [load_always]
  sort_method     None / Alphabetical / Numerical / Datetime, ASC or DESC

Outputs: AUDIO and INT (number of files loaded), like IMAGE / MASK / INT.
An image batch stacks frames, but audio files have different lengths, so the files are joined one after another
into a single AUDIO. Files are converted to the first file's sample rate and channel count so they can be joined.

Adapted from ComfyUI-Inspire-Pack (image_util.py) by ltdrdata, GPL-3.0.
Drop this file into ComfyUI/custom_nodes/ and restart ComfyUI.
"""
import os
import re

import torch

AUDIO_EXTENSIONS = (".wav", ".mp3", ".flac", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".wma", ".aiff", ".aif", ".mka")

SORT_METHODS = [
    "None",
    "Alphabetical (ASC)",
    "Alphabetical (DESC)",
    "Numerical (ASC)",
    "Numerical (DESC)",
    "Datetime (ASC)",
    "Datetime (DESC)",
]


def _first_number(s):
    m = re.search(r"\d+", s)
    return int(m.group()) if m else float("inf")


def _sort_by(items, base_path=".", method=None):
    def full(x):
        return os.path.join(base_path, x)

    def stamp(path):
        try:
            return os.path.getmtime(path)
        except OSError:
            return float("-inf")

    if method == "Alphabetical (ASC)":
        return sorted(items)
    if method == "Alphabetical (DESC)":
        return sorted(items, reverse=True)
    if method == "Numerical (ASC)":
        return sorted(items, key=lambda x: _first_number(os.path.splitext(x)[0]))
    if method == "Numerical (DESC)":
        return sorted(items, key=lambda x: _first_number(os.path.splitext(x)[0]), reverse=True)
    if method == "Datetime (ASC)":
        return sorted(items, key=lambda x: stamp(full(x)))
    if method == "Datetime (DESC)":
        return sorted(items, key=lambda x: stamp(full(x)), reverse=True)
    return items


def _read_audio(path):
    """-> (waveform [C, T] float32, sample_rate)."""
    try:
        import torchaudio
        wav, sr = torchaudio.load(path)
        return wav.float(), int(sr)
    except Exception:
        pass
    import av
    import numpy as np
    with av.open(path) as container:
        stream = next(s for s in container.streams if s.type == "audio")
        sr = int(stream.codec_context.sample_rate)
        chunks = []
        for frame in container.decode(stream):
            a = frame.to_ndarray()                      # [channels, n] (planar) or [1, n*channels] (packed)
            if a.dtype.kind in "iu":
                a = a.astype(np.float32) / float(np.iinfo(a.dtype).max + 1)
            else:
                a = a.astype(np.float32)
            ch = max(len(frame.layout.channels), 1)
            if a.shape[0] == 1 and ch > 1:
                a = a.reshape(-1, ch).T
            chunks.append(a)
    if not chunks:
        raise RuntimeError(f"No audio could be read from '{path}'.")
    return torch.from_numpy(np.concatenate(chunks, axis=1)).float(), sr


def _match_channels(wav, channels):
    c = wav.shape[0]
    if c == channels:
        return wav
    if channels == 1:
        return wav.mean(0, keepdim=True)
    if c == 1:
        return wav.repeat(channels, 1)
    if c > channels:
        return wav[:channels]
    return torch.cat([wav, wav[-1:].repeat(channels - c, 1)], 0)


def _resample(wav, sr_from, sr_to):
    if sr_from == sr_to:
        return wav
    try:
        import torchaudio
        return torchaudio.functional.resample(wav, sr_from, sr_to)
    except Exception:
        n = max(int(round(wav.shape[1] * sr_to / float(sr_from))), 1)
        return torch.nn.functional.interpolate(wav[None], size=n, mode="linear", align_corners=False)[0]


class LoadAudioBatchFromDir:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "directory": ("STRING", {"default": ""}),
            },
            "optional": {
                "audio_load_cap": ("INT", {"default": 0, "min": 0, "step": 1}),
                "start_index": ("INT", {"default": 0, "min": -1, "max": 0xffffffffffffffff, "step": 1}),
                "load_always": ("BOOLEAN", {"default": False, "label_on": "enabled", "label_off": "disabled"}),
                "sort_method": (SORT_METHODS,),
            },
        }

    RETURN_TYPES = ("AUDIO", "INT")
    RETURN_NAMES = ("audio", "count")
    FUNCTION = "load_audio"
    CATEGORY = "audio"

    @classmethod
    def IS_CHANGED(cls, directory="", audio_load_cap=0, start_index=0, load_always=False, sort_method=None, **kwargs):
        if load_always:
            return float("NaN")
        stamp = []
        try:
            for f in sorted(os.listdir(directory)):
                p = os.path.join(directory, f)
                if f.lower().endswith(AUDIO_EXTENSIONS):
                    stamp.append((f, os.path.getmtime(p)))
        except OSError:
            pass
        return hash((directory, audio_load_cap, start_index, sort_method, tuple(stamp)))

    def load_audio(self, directory: str, audio_load_cap: int = 0, start_index: int = 0, load_always=False, sort_method=None):
        if not os.path.isdir(directory):
            raise FileNotFoundError(f"Directory '{directory}' cannot be found.")
        files = os.listdir(directory)
        if len(files) == 0:
            raise FileNotFoundError(f"No files in directory '{directory}'.")

        files = [f for f in files if f.lower().endswith(AUDIO_EXTENSIONS) and os.path.isfile(os.path.join(directory, f))]
        files = _sort_by(files, directory, sort_method)
        files = [os.path.join(directory, f) for f in files]
        files = files[start_index:]
        if audio_load_cap > 0:
            files = files[:audio_load_cap]
        if len(files) == 0:
            raise FileNotFoundError(f"No audio files to load in '{directory}' (check start_index and the file types).")

        waves = []
        sr0 = None
        ch0 = None
        for path in files:
            wav, sr = _read_audio(path)
            if sr0 is None:
                sr0, ch0 = sr, wav.shape[0]
            wav = _match_channels(_resample(wav, sr, sr0), ch0)
            waves.append(wav)

        out = waves[0] if len(waves) == 1 else torch.cat(waves, dim=1)
        return ({"waveform": out.unsqueeze(0).contiguous(), "sample_rate": int(sr0)}, len(waves))


NODE_CLASS_MAPPINGS = {"LoadAudioBatchFromDir": LoadAudioBatchFromDir}
NODE_DISPLAY_NAME_MAPPINGS = {"LoadAudioBatchFromDir": "Load Audio Batch From Dir"}
