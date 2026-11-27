"""Free local Indonesian AI voice engine (F5-TTS-INDO-V2 Melodic, edge-tts fallback, or custom WAV),
studio biquad mastering, ambient synth BGM bed, and speech-envelope word alignment."""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import time
import numpy as np

from .pipeline import find_ffmpeg
from .timeline import Timeline, normalize_word

DEFAULT_MELODIC_REF_TEXT = (
    "Pernah kepikiran nggak, gimana cara kerja mesin raksasa ini?! "
    "Ternyata, rahasianya bukan sulap, melainkan kekuatan fisika yang luar biasa keren!"
)


def phoneticize_indonesian(text: str) -> str:
    """Convert common English loanwords to Indonesian phonetic spelling for F5-TTS ONLY
    (on-screen captions in script.txt stay in original standard spelling)."""
    replacements = [
        (r"\boutdoor\b", "autdor"),
        (r"\bindoor\b", "indor"),
        (r"\bblower\b", "blouwer"),
        (r"\bwireless\b", "wairles"),
        (r"\bsensor\b", "sensor"),
    ]
    out = text
    for pat, rep in replacements:
        out = re.sub(pat, rep, out, flags=re.IGNORECASE)
    return out


# --------------------------------------------------------- pure-Python/NumPy studio DSP
def _biquad(samples: np.ndarray, b0, b1, b2, a0, a1, a2) -> np.ndarray:
    nb0, nb1, nb2 = b0 / a0, b1 / a0, b2 / a0
    na1, na2 = a1 / a0, a2 / a0
    out = np.empty_like(samples)
    x1 = x2 = y1 = y2 = 0.0
    for i, x0 in enumerate(samples):
        y0 = nb0 * x0 + nb1 * x1 + nb2 * x2 - na1 * y1 - na2 * y2
        out[i] = y0
        x2, x1 = x1, x0
        y2, y1 = y1, y0
    return out


def _highpass(s: np.ndarray, sr: int, freq: float, q: float = 0.707) -> np.ndarray:
    w0 = 2.0 * math.pi * freq / sr
    cw, al = math.cos(w0), math.sin(w0) / (2.0 * q)
    return _biquad(s, (1 + cw) / 2, -(1 + cw), (1 + cw) / 2, 1 + al, -2 * cw, 1 - al)


def _low_shelf(s: np.ndarray, sr: int, freq: float, db: float, slope: float = 0.85) -> np.ndarray:
    a = 10.0 ** (db / 40.0)
    w0 = 2.0 * math.pi * freq / sr
    cw = math.cos(w0)
    al = math.sin(w0) * 0.5 * math.sqrt((a + 1.0 / a) * (1.0 / slope - 1.0) + 2.0)
    ts = 2.0 * math.sqrt(a) * al
    return _biquad(
        s,
        a * ((a + 1) - (a - 1) * cw + ts),
        2 * a * ((a - 1) - (a + 1) * cw),
        a * ((a + 1) - (a - 1) * cw - ts),
        (a + 1) + (a - 1) * cw + ts,
        -2 * ((a - 1) + (a + 1) * cw),
        (a + 1) + (a - 1) * cw - ts,
    )


def _peaking(s: np.ndarray, sr: int, freq: float, db: float, q: float = 1.0) -> np.ndarray:
    a = 10.0 ** (db / 40.0)
    w0 = 2.0 * math.pi * freq / sr
    al, cw = math.sin(w0) / (2.0 * q), math.cos(w0)
    return _biquad(s, 1 + al * a, -2 * cw, 1 - al * a, 1 + al / a, -2 * cw, 1 - al / a)


def _high_shelf(s: np.ndarray, sr: int, freq: float, db: float, slope: float = 0.85) -> np.ndarray:
    a = 10.0 ** (db / 40.0)
    w0 = 2.0 * math.pi * freq / sr
    cw = math.cos(w0)
    al = math.sin(w0) * 0.5 * math.sqrt((a + 1.0 / a) * (1.0 / slope - 1.0) + 2.0)
    ts = 2.0 * math.sqrt(a) * al
    return _biquad(
        s,
        a * ((a + 1) + (a - 1) * cw + ts),
        -2 * a * ((a - 1) + (a + 1) * cw),
        a * ((a + 1) + (a - 1) * cw - ts),
        (a + 1) - (a - 1) * cw + ts,
        2 * ((a - 1) - (a + 1) * cw),
        (a + 1) - (a - 1) * cw - ts,
    )


def clean_breath_trim(wav: np.ndarray, sr: int, gate_thresh: float = 0.012, tail_ms: int = 160) -> np.ndarray:
    """Soft RMS noise gate removing raw breath hiss while preserving full final consonants."""
    x = wav.astype(np.float32).copy()
    win = max(1, int(sr * 0.015))
    rms = np.sqrt(np.maximum(np.convolve(x * x, np.ones(win) / win, mode="same"), 0.0))
    gate = np.clip((rms - gate_thresh * 0.4) / (gate_thresh * 0.6), 0.0, 1.0)
    gwin = max(1, int(sr * 0.012))
    gate = np.convolve(gate, np.ones(gwin) / gwin, mode="same")
    x *= gate
    active = np.where(np.abs(x) > 0.006)[0]
    if len(active) == 0:
        return x
    s = max(0, int(active[0]) - int(sr * 0.03))
    e = min(len(x), int(active[-1]) + int(sr * tail_ms / 1000.0))
    return x[s:e]


def master_melodic_ai(audio: np.ndarray, sr: int) -> np.ndarray:
    """Sleek modern AI vocal mastering: crisp air sheen, scooped room mud, dynamic 2.6:1 leveling."""
    x = audio.astype(np.float64) - float(np.mean(audio))
    x = _highpass(x, sr, 90.0)
    x = _low_shelf(x, sr, 180.0, +2.0)
    x = _peaking(x, sr, 420.0, -1.8, 1.1)
    x = _peaking(x, sr, 3300.0, +3.0, 1.0)
    x = _high_shelf(x, sr, 6000.0, +2.2)

    env = 0.0
    atk = math.exp(-1.0 / (sr * 0.010))
    rel = math.exp(-1.0 / (sr * 0.130))
    out = np.empty_like(x)
    for i, sample in enumerate(x):
        mag = abs(sample)
        env = atk * env + (1.0 - atk) * mag if mag > env else rel * env + (1.0 - rel) * mag
        gain = (env / 0.16) ** (1.0 / 2.6 - 1.0) if env > 0.16 else 1.0
        y = sample * gain * 1.25
        out[i] = math.tanh(y * 1.12) / math.tanh(1.12)
    peak = max(1e-6, float(np.max(np.abs(out))))
    return np.clip(out * min(2.0, 0.90 / peak), -0.99, 0.99).astype(np.float32)


def synthesize_ambient_bed(num_samples: int, sr: int, level: float = 0.045) -> np.ndarray:
    """Generate a royalty-free subtle warm 4-chord ambient synth pad (-26 dB under narration)."""
    t = np.arange(num_samples, dtype=np.float64) / sr
    progression = [
        (130.81, 196.00, 246.94, 293.66),  # Cmaj9
        (110.00, 164.81, 196.00, 246.94),  # Am9
        (174.61, 220.00, 261.63, 329.63),  # Fmaj7
        (146.83, 196.00, 246.94, 329.63),  # G6
    ]
    bed = np.zeros(num_samples, dtype=np.float64)
    chord_len = int(4.0 * sr)
    for idx0 in range(0, num_samples, chord_len):
        idx1 = min(num_samples, idx0 + chord_len)
        seg_t = t[idx0:idx1] - t[idx0]
        freqs = progression[(idx0 // chord_len) % len(progression)]
        pad = np.zeros(idx1 - idx0, dtype=np.float64)
        for freq in freqs:
            pad += 0.25 * np.sin(2.0 * math.pi * freq * seg_t)
            pad += 0.06 * np.sin(2.0 * math.pi * (2.0 * freq) * seg_t)
        env = np.ones_like(seg_t)
        fade = min(int(0.45 * sr), len(env) // 3)
        if fade > 0:
            env[:fade] = np.linspace(0.0, 1.0, fade)
            env[-fade:] = np.linspace(1.0, 0.0, fade)
        pulse = 0.85 + 0.15 * np.sin(2.0 * math.pi * (105.0 / 60.0) * seg_t)
        bed[idx0:idx1] = pad * env * pulse
    fi = min(int(0.6 * sr), num_samples // 4)
    fo = min(int(1.2 * sr), num_samples // 4)
    bed[:fi] *= np.linspace(0.0, 1.0, fi)
    bed[-fo:] *= np.linspace(1.0, 0.0, fo)
    return (bed * level).astype(np.float32)


def resample_audio(wav: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return wav.astype(np.float32)
    n_out = int(round(len(wav) * sr_out / sr_in))
    xp = np.linspace(0.0, 1.0, len(wav), endpoint=False)
    xnew = np.linspace(0.0, 1.0, n_out, endpoint=False)
    return np.interp(xnew, xp, wav).astype(np.float32)


def align_words_to_waveform(
    sid: str,
    tokens: list[str],
    wav: np.ndarray,
    sr: int,
    t_offset: float,
) -> list[dict]:
    """Align spoken tokens onto the cumulative RMS speech-activity distribution of a sentence WAV."""
    dur = len(wav) / sr
    hop = max(1, int(sr * 0.010))
    n_bins = max(1, len(wav) // hop)
    rms = np.array([float(np.sqrt(np.mean(wav[i * hop : (i + 1) * hop] ** 2))) for i in range(n_bins)])
    activity = np.where(rms > 0.015, np.power(rms, 0.45) + 0.06, 0.015)
    cdf = np.cumsum(activity)
    cdf /= cdf[-1]

    weights = []
    for tok in tokens:
        clean = re.sub(r"[^a-zA-Z]", "", tok)
        vowels = len(re.findall(r"[aiueoAIUEO]", clean))
        syll_w = max(1.3, vowels * 1.35 + len(clean) * 0.18)
        pause_w = 1.6 if re.search(r"[.?!]+$", tok) else (0.75 if tok.endswith(",") else 0.0)
        weights.append((syll_w, pause_w))
    total_w = sum(w + p for w, p in weights)

    out = []
    acc = 0.0
    for tok, (w, p) in zip(tokens, weights):
        b0 = int(np.searchsorted(cdf, acc / total_w))
        b1 = int(np.searchsorted(cdf, (acc + w) / total_w))
        ws = t_offset + min(dur - 0.08, b0 * 0.010)
        we = t_offset + min(dur, max(ws - t_offset + 0.09, b1 * 0.010))
        out.append({"sid": sid, "word": re.sub(r"[.,:;…]", "", tok), "start": round(ws, 3), "end": round(we, 3)})
        acc += w + p
    return out


def ensure_melodic_reference(ref_wav_path: str) -> str:
    """Auto-generate a clean multi-pitch synthetic Indonesian male reference clip (zero third-party cloning)."""
    import soundfile as sf

    if os.path.exists(ref_wav_path):
        return ref_wav_path
    os.makedirs(os.path.dirname(os.path.abspath(ref_wav_path)), exist_ok=True)
    ffmpeg = find_ffmpeg()
    parts = [
        ("Pernah kepikiran nggak, gimana cara kerja mesin raksasa ini?!", "+10%", "+9Hz"),
        ("Ternyata, rahasianya bukan sulap,", "+2%", "-4Hz"),
        ("melainkan kekuatan fisika yang luar biasa keren!", "+12%", "+6Hz"),
    ]
    segs = []
    sr_out = 24000
    py_edge = os.environ.get("EDGE_TTS_PYTHON", sys.executable)
    for idx, (text, rate, pitch) in enumerate(parts):
        mp3 = f"{ref_wav_path}.p{idx}.mp3"
        wav_p = f"{ref_wav_path}.p{idx}.wav"
        subprocess.run(
            [
                py_edge,
                "-c",
                f"import asyncio, edge_tts; asyncio.run(edge_tts.Communicate({text!r}, 'id-ID-ArdiNeural', rate={rate!r}, pitch={pitch!r}).save({mp3!r}))",
            ],
            check=True,
        )
        subprocess.run([ffmpeg, "-y", "-v", "error", "-i", mp3, "-ac", "1", "-ar", "24000", wav_p], check=True)
        y, sr_out = sf.read(wav_p, dtype="float32")
        os.remove(mp3)
        os.remove(wav_p)
        active = np.where(np.abs(y) > 0.01)[0]
        if len(active) > 0:
            y = y[max(0, active[0] - int(sr_out * 0.02)) : min(len(y), active[-1] + int(sr_out * 0.05))]
        segs.append(y)
        if idx < len(parts) - 1:
            segs.append(np.zeros(int(sr_out * 0.14), dtype=np.float32))
    segs.append(np.zeros(int(sr_out * 0.16), dtype=np.float32))
    sf.write(ref_wav_path, np.concatenate(segs), sr_out)
    return ref_wav_path


def build_project_voice(
    project_dir: str,
    backend: str = "f5_indo",
    model_dir: str | None = None,
    ref_wav: str | None = None,
    ref_text: str = DEFAULT_MELODIC_REF_TEXT,
    speed: float = 0.93,
    cfg_strength: float = 1.95,
    pause_between: float = 0.26,
    only_sids: set[str] | None = None,
) -> dict:
    """Generate per-sentence narration, master studio audio + ambient BGM, and write timings.json."""
    import soundfile as sf

    tl = Timeline(project_dir)
    parts_dir = os.path.join(tl.project_dir, "vo_parts")
    os.makedirs(parts_dir, exist_ok=True)
    sr_gen = 24000
    sr_out = 48000

    tts = None
    if backend == "f5_indo":
        import torch
        from f5_tts.api import F5TTS

        m_dir = os.path.abspath(
            model_dir
            or os.environ.get(
                "F5_MODEL_DIR",
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "f5_indo_v2"),
            )
        )
        ckpt = os.path.join(m_dir, "f5_tts_indo_v2.pt")
        vocab = os.path.join(m_dir, "vocab.txt")
        if not os.path.exists(ckpt):
            raise FileNotFoundError(f"Missing F5-TTS checkpoint: {ckpt}. Run `python setup.py` first.")
        r_wav = ensure_melodic_reference(ref_wav or os.path.join(m_dir, "ref_melodic_male.wav"))
        device = "cuda" if torch.cuda.is_available() else "cpu"
        tts = F5TTS(model="F5TTS_v1_Base", ckpt_file=ckpt, vocab_file=vocab, device=device)
    else:
        r_wav = ""

    t0 = time.time()
    ffmpeg = find_ffmpeg()
    segs = []
    timed_words: list[dict] = []
    cursor = 0.0

    for idx, (sid, raw_text) in enumerate(tl.rows):
        part_path = os.path.join(parts_dir, f"{sid}.wav")
        tokens = [t for t in raw_text.split() if normalize_word(t)]
        spoken = re.sub(r"\s*/\s*", " ", raw_text).strip()

        need_gen = (only_sids is None and not os.path.exists(part_path)) or (only_sids is not None and sid in only_sids)
        if backend == "custom":
            if not os.path.exists(part_path):
                raise FileNotFoundError(f"Custom backend expects recorded file: {part_path}")
            wav, sr_gen = sf.read(part_path, dtype="float32")
            wav = clean_breath_trim(wav, sr_gen)
        elif need_gen:
            if backend == "f5_indo":
                ph_text = phoneticize_indonesian(spoken)
                wav_raw, sr_gen, _ = tts.infer(
                    ref_file=r_wav,
                    ref_text=ref_text,
                    gen_text=ph_text + "   ",
                    speed=speed,
                    nfe_step=32,
                    cfg_strength=cfg_strength,
                    cross_fade_duration=0.12,
                    seed=900 + idx,
                )
                wav = clean_breath_trim(np.asarray(wav_raw, dtype=np.float32), sr_gen)
            elif backend == "edge":
                mp3 = part_path + ".mp3"
                py_edge = os.environ.get("EDGE_TTS_PYTHON", sys.executable)
                subprocess.run(
                    [
                        py_edge,
                        "-c",
                        f"import asyncio, edge_tts; asyncio.run(edge_tts.Communicate({spoken!r}, 'id-ID-ArdiNeural', rate='+12%', pitch='-3Hz').save({mp3!r}))",
                    ],
                    check=True,
                )
                subprocess.run([ffmpeg, "-y", "-v", "error", "-i", mp3, "-ac", "1", "-ar", "24000", part_path], check=True)
                os.remove(mp3)
                wav, sr_gen = sf.read(part_path, dtype="float32")
                wav = clean_breath_trim(wav, sr_gen, gate_thresh=0.008)
            else:
                raise ValueError(f"Unknown voice backend: {backend}")
            sf.write(part_path, wav, sr_gen)
        else:
            wav, sr_gen = sf.read(part_path, dtype="float32")

        timed_words.extend(align_words_to_waveform(sid, tokens, wav, sr_gen, cursor))
        dur_s = len(wav) / sr_gen
        print(f"  [{sid}] {cursor:5.2f}s -> {cursor + dur_s:5.2f}s ({dur_s:.2f}s): {spoken}", flush=True)
        segs.append(wav)
        cursor += dur_s
        if idx < len(tl.rows) - 1 and pause_between > 0:
            segs.append(np.zeros(int(sr_gen * pause_between), dtype=np.float32))
            cursor += pause_between

    vo_proc = master_melodic_ai(np.concatenate(segs), sr_gen)
    vo_48 = resample_audio(vo_proc, sr_gen, sr_out)
    lead = np.zeros(int(round(tl.config.lead_in_sec * sr_out)), dtype=np.float32)
    tail = np.zeros(int(round(tl.config.tail_sec * sr_out)), dtype=np.float32)
    vo_final = np.concatenate([lead, vo_48, tail])
    vo_mix = np.clip(vo_final + synthesize_ambient_bed(len(vo_final), sr_out), -0.98, 0.98).astype(np.float32)

    sf.write(os.path.join(tl.project_dir, "vo_final.wav"), vo_final, sr_out)
    sf.write(os.path.join(tl.project_dir, "vo_mix.wav"), vo_mix, sr_out)

    voice_dur = round(len(vo_proc) / sr_gen, 3)
    payload = {"voice_duration": voice_dur, "backend": backend, "words": timed_words}
    with open(os.path.join(tl.project_dir, tl.config.timings_file), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    total_sec = round(tl.config.lead_in_sec + voice_dur + tl.config.tail_sec, 2)
    print(
        f"[VOICE] Built in {time.time() - t0:.1f}s | VO={voice_dur}s | Video={total_sec}s "
        f"({int(round(total_sec * tl.config.fps))} frames) | words={len(timed_words)}",
        flush=True,
    )
    return payload
