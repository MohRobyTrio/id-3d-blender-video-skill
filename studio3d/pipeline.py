"""End-to-end local rendering, contact-sheet preview, caption burning, and BT.709 H.264 MP4 encoding."""
from __future__ import annotations

import glob
import math
import os
import shutil
import subprocess
import sys
import time
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageStat

from .timeline import Timeline


def find_ffmpeg() -> str:
    """Resolve ffmpeg binary from FFMPEG_BIN / STUDIO3D_FFMPEG env, PATH, or standard system locations."""
    candidates = [
        os.environ.get("FFMPEG_BIN", ""),
        os.environ.get("STUDIO3D_FFMPEG", ""),
        shutil.which("ffmpeg") or "",
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/usr/bin/ffmpeg",
    ]
    for cand in candidates:
        if cand and os.path.exists(cand):
            return cand
    try:
        import imageio_ffmpeg  # type: ignore

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass
    raise FileNotFoundError("ffmpeg not found. Install ffmpeg on PATH or set FFMPEG_BIN.")


def find_caption_font() -> str:
    candidates = [
        os.environ.get("STUDIO3D_FONT", ""),
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/inter/Inter-SemiBold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    raise FileNotFoundError("No bold system font found. Set STUDIO3D_FONT=/path/to/font.ttf")


class CaptionCompositor:
    """Word-by-word progressive 2-4 word phrase burner with crisp drop shadow & outline."""

    def __init__(self, timeline: Timeline, font_px: int = 66, band_half_h: int = 110) -> None:
        self.timeline = timeline
        self.w = timeline.config.width
        self.h = timeline.config.height
        self.y_frac = timeline.config.caption_y_frac
        self.phrases = timeline.build_phrases()
        self.font = ImageFont.truetype(find_caption_font(), font_px)
        self.band_half_h = band_half_h
        self._cache: dict[tuple[int, int], Image.Image] = {}

    def _overlay_at(self, t_sec: float) -> Image.Image | None:
        for idx, ph in enumerate(self.phrases):
            if ph.start_sec <= t_sec < ph.end_sec:
                shown_n = sum(1 for s in ph.word_starts if s <= t_sec + 1e-6)
                key = (idx, shown_n)
                if key not in self._cache:
                    full_txt = " ".join(ph.words)
                    shown_txt = " ".join(ph.words[:shown_n])
                    x0 = (self.w - self.font.getlength(full_txt)) * 0.5
                    cy = self.band_half_h

                    layer = Image.new("RGBA", (self.w, 2 * self.band_half_h), (0, 0, 0, 0))
                    draw = ImageDraw.Draw(layer)
                    draw.text(
                        (x0, cy + 4),
                        shown_txt,
                        font=self.font,
                        fill=(0, 0, 0, 255),
                        anchor="lm",
                        stroke_width=4,
                        stroke_fill=(0, 0, 0, 255),
                    )
                    layer = layer.filter(ImageFilter.GaussianBlur(7))
                    layer.putalpha(layer.getchannel("A").point(lambda v: min(255, int(v * 1.35))))
                    draw = ImageDraw.Draw(layer)
                    draw.text(
                        (x0, cy),
                        shown_txt,
                        font=self.font,
                        fill=(255, 255, 255, 255),
                        anchor="lm",
                        stroke_width=2,
                        stroke_fill=(18, 18, 22, 235),
                    )
                    self._cache[key] = layer
                return self._cache[key]
        return None

    def burn_onto(self, frame: Image.Image, t_sec: float) -> Image.Image:
        ov = self._overlay_at(t_sec)
        if ov is None:
            return frame
        if frame.width != self.w:
            scale = frame.width / self.w
            ov = ov.resize((frame.width, max(2, int(round(ov.height * scale)))), Image.LANCZOS)
        y_top = int(frame.height * self.y_frac) - ov.height // 2
        frame.paste(ov, (0, y_top), ov)
        return frame


def build_contact_sheet(
    project_dir: str,
    stills_dir: str,
    out_png: str,
    cols: int = 3,
) -> str:
    """Burn captions & timestamps onto preview stills and arrange into a visual QA grid."""
    tl = Timeline(project_dir)
    comp = CaptionCompositor(tl)
    files = sorted(glob.glob(os.path.join(stills_dir, "t_*.*")))
    if not files:
        raise FileNotFoundError(f"No stills found in {stills_dir}")

    tiles = []
    for path in files:
        base = os.path.basename(path)
        t_sec = int(base[2:7]) / 100.0
        im = Image.open(path).convert("RGB")
        comp.burn_onto(im, t_sec)
        draw = ImageDraw.Draw(im)
        draw.rectangle([8, 8, 170, 44], fill=(0, 0, 0))
        draw.text((16, 14), f"t={t_sec:.2f}s", fill=(255, 230, 80))
        tiles.append(im.resize((360, 640), Image.LANCZOS))

    rows = math.ceil(len(tiles) / cols)
    sheet = Image.new("RGB", (cols * 360, rows * 640), (15, 15, 20))
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % cols) * 360, (i // cols) * 640))
    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    sheet.save(out_png)
    print(f"[SHEET] Wrote {out_png} ({sheet.size[0]}x{sheet.size[1]}, {len(tiles)} panels)", flush=True)
    return out_png


def render_parallel_frames(
    project_dir: str,
    scene_script: str,
    frames_dir: str,
    width: int = 1080,
    height: int = 1920,
    samples: int = 12,
    workers: int = 2,
    blender_python: str | None = None,
) -> None:
    """Cross-platform parallel local GPU/CPU Blender frame renderer with live ETA and integrity audit."""
    tl = Timeline(project_dir)
    total = tl.total_frames
    py_exe = blender_python or sys.executable
    os.makedirs(frames_dir, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("STUDIO3D_DEVICE", "GPU")
    env.setdefault("STUDIO3D_DENOISER", "OPTIX")
    env.setdefault("STUDIO3D_FMT", "JPEG")
    env.setdefault("STUDIO3D_PERSIST", "1")

    t0 = time.time()
    procs = []
    print(f"[RENDER] Launching {workers} worker(s) for {total} frames ({width}x{height} @ {samples} spp)...", flush=True)
    for idx in range(workers):
        log_f = open(os.path.join(project_dir, f"render_worker_{idx + 1}.log"), "w", encoding="utf-8")
        p = subprocess.Popen(
            [py_exe, scene_script, "frames", str(width), str(height), str(samples), frames_dir, str(idx + 1), str(total), str(workers)],
            cwd=project_dir,
            env=env,
            stdout=log_f,
            stderr=subprocess.STDOUT,
        )
        procs.append((p, log_f))

    while any(p.poll() is None for p, _ in procs):
        time.sleep(20)
        done = len(glob.glob(os.path.join(frames_dir, "f_*.*")))
        elapsed = time.time() - t0
        rate = done / elapsed if elapsed > 0 else 0.0
        eta = (total - done) / rate / 60.0 if rate > 0 else 0.0
        print(f"  PROGRESS: {done}/{total} ({100.0 * done / total:.1f}%) | {rate:.2f} fps | ETA {eta:.1f}m", flush=True)

    for p, log_f in procs:
        rc = p.wait()
        log_f.close()
        if rc != 0:
            raise RuntimeError(f"Render worker exited with code {rc}. Check render_worker_*.log")

    # Full integrity & brightness audit
    ext = "png" if os.path.exists(os.path.join(frames_dir, "f_00001.png")) else "jpg"
    missing, bad, sizes = [], [], []
    for f in range(1, total + 1):
        p = os.path.join(frames_dir, f"f_{f:05d}.{ext}")
        if not os.path.exists(p):
            missing.append(f)
            continue
        sz = os.path.getsize(p)
        sizes.append(sz)
        if sz < 5000:
            bad.append((f, "small", sz))
            continue
        if f % 10 == 1 or f in (1, total):
            im = Image.open(p).convert("RGB")
            if im.size != (width, height):
                bad.append((f, "size", im.size))
            mean = sum(ImageStat.Stat(im).mean) / 3.0
            if mean < 12.0:
                bad.append((f, "dark", round(mean, 1)))
    print(f"[AUDIT] frames={len(sizes)}/{total} min={min(sizes)//1024}KB max={max(sizes)//1024}KB missing={len(missing)} bad={len(bad)}", flush=True)
    if missing or bad:
        raise RuntimeError(f"Frame integrity audit failed: missing={missing[:10]}, bad={bad[:10]}")


def encode_bt709_mp4(
    project_dir: str,
    frames_dir: str,
    audio_wav: str,
    out_mp4: str,
    burn_captions: bool = True,
    crf: int = 17,
) -> str:
    """Pipe captioned RGB frames via image2pipe PNG into ffmpeg with explicit BT.709 color conversion."""
    tl = Timeline(project_dir)
    ffmpeg = find_ffmpeg()
    comp = CaptionCompositor(tl) if burn_captions else None
    os.makedirs(os.path.dirname(os.path.abspath(out_mp4)), exist_ok=True)
    part_mp4 = out_mp4[:-4] + ".part.mp4"

    ext = "png" if os.path.exists(os.path.join(frames_dir, "f_00001.png")) else "jpg"
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-f", "image2pipe", "-vcodec", "png", "-framerate", str(tl.config.fps), "-i", "-",
        "-i", audio_wav, "-map", "0:v", "-map", "1:a",
        "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{tl.total_duration:.3f}",
        "-movflags", "+faststart",
        part_mp4,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    for f in range(1, tl.total_frames + 1):
        im = Image.open(os.path.join(frames_dir, f"f_{f:05d}.{ext}")).convert("RGB")
        if comp is not None:
            comp.burn_onto(im, (f - 1) / tl.config.fps)
        im.save(proc.stdin, format="PNG", compress_level=1)
        if f % 300 == 0:
            print(f"[ENCODE] frame {f}/{tl.total_frames}", flush=True)
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg encoding failed")
    os.replace(part_mp4, out_mp4)
    print(f"[ENCODE] Wrote {out_mp4} ({os.path.getsize(out_mp4) / 1024 / 1024:.2f} MB)", flush=True)
    return out_mp4
