---
name: blender-3d-explainer-id
description: >-
  Creates 100% free, locally rendered 1080x1920 30fps Indonesian 3D engineering
  explainer videos (realistic cutaway diorama style) using the standalone
  clean-room `studio3d` Blender 5.3+ Cycles OptiX engine and melodic Indonesian
  male AI narration (F5-TTS-INDO-FINETUNE-V2 / edge-tts / custom WAV). Use
  whenever the user asks to create a 3D explainer video, "video 3D pakai style
  biasa", anatomy/how-it-works short, or TikTok/Reels educational 3D animation
  in Indonesian.
---

# Standalone Indonesian 3D Engineering Explainer Skill (`studio3d`)

100% free, local, standalone clean-room workflow (MIT License) for vertical `1080×1920`, 30 fps Indonesian 3D cutaway explainer videos — zero Higgsfield, zero ElevenLabs paid credits, zero cloud GPU charges.

## Repository & Engine Layout

Locate the cloned `id-3d-blender-video-skill` repo root (via the `STUDIO3D_HOME` environment variable, the active workspace, or wherever the repository was cloned):

- `studio3d/timeline.py` — Script parser, numbers-as-words validation, `Timeline.cue()`, and 2–4 word caption phrase grouper.
- `studio3d/scene.py` — Blender 5.3+ `DioramaStudio` & `CameraRig` (1.0 unit = 1 meter, zero deprecation warnings, OptiX hardware denoiser, original `add_educator()` figure, callouts, flow streams, helical coils).
- `studio3d/voice.py` — Local Indonesian TTS (`f5_indo` melodic expressive, `edge` commercial-safe fallback, or `custom` WAV), biquad studio mastering, ambient synth BGM, and RMS speech-envelope word alignment.
- `studio3d/pipeline.py` — Preview contact-sheet builder, cross-platform multi-worker GPU renderer, frame integrity audit, and BT.709 `image2pipe` H.264 encoder.
- `cli.py` — Unified CLI (`voice`, `phrases`, `check`, `preview`, `render`, `encode`).
- `examples/ac_split_1pk/` — Reference realistic-scale 1 PK Split AC example (`project.json`, `script.txt`, `scene.py`).

## Mandatory Style & Quality Standards

1. **Everyday Indonesian Language (Layman-Friendly):**
   - Keep total duration punchy (**~40–50 seconds**, 8–10 sentences `S01`..`S10`), ending with a clear CTA (`"Mau bedah apa lagi? Tulis di komentar ya!"`).
   - Use familiar everyday Indonesian vocabulary (e.g., **"freon"** instead of *"refrigeran"*).
   - Write **all numbers as Indonesian words** in `script.txt` and place ` / ` caption breaks every **2–4 words**.
   - Avoid short 2-letter acronyms (like `"AC"`) in F5-TTS spoken text — use natural Indonesian words (`"pendingin kamar"`, `"mesin pendingin"`) so neural TTS never mispronounces them.
2. **Melodic Expressive AI Male Voice (`--backend f5_indo`):**
   - Uses `Eempostor/F5-TTS-INDO-FINETUNE-V2` (local CUDA venv, non-commercial CC BY-NC 4.0) driven by the synthetic multi-pitch melodic reference (`ensure_melodic_reference()` — zero impersonation!) + `master_melodic_ai()` + subtle ambient synth BGM.
   - For commercial projects, switch cleanly to `--backend edge` or `--backend custom` (own voice recording).
   - **Mandatory Audio Audit:** Always listen to `vo_mix.wav` via `read_file` before rendering 3D frames. If a single sentence clips or stutters, fix only that line with `--only S0X`.
3. **Realistic 1:1 Scale & Macro Zoom Cinematography:**
   - Model every room, wall, furniture item, and mechanical unit at true real-world metric scale (`1.0 unit = 1 meter`) relative to the `1.72 m` `add_educator()` presenter figure. Mount equipment realistically (flush on walls, on L-brackets, connected via realistic wall sleeves/cables).
   - Use **smooth camera macro zoom (`distance = 1.8–2.8 m`)** to reveal internal components instead of unrealistically enlarging objects, and scale 3D callout text sizes proportionally to camera distance (`0.06–0.11` for macro shots vs `0.14–0.20` for wide shots).
   - Keep all 3D callouts cleanly clear of ceilings, walls, screen edges, and the caption band (`67.5%` screen height).

## Step-by-Step Execution Procedure

1. **Create a new project folder** (e.g. `projects/<topic>/`) with `project.json` and `script.txt` (following `examples/ac_split_1pk/`).
2. **Generate voice & timings:**
   - Run with the TTS Python venv: `<tts_python> cli.py voice <project_dir> --backend f5_indo --model-dir <model_dir> --ref-wav <ref_wav>`
   - Verify phrase timing splits: `python cli.py phrases <project_dir>`
   - **Listen to `<project_dir>/vo_mix.wav` via `read_file`**; fix any single flawed sentence using `--only S0X`.
3. **Write `<project_dir>/scene.py`** importing `DioramaStudio`, `Timeline`, and `catmull_rom` from `studio3d`.
4. **Run render-free QA:** `python cli.py check <project_dir>` (confirm zero unexpected single-frame jumps).
5. **Render & inspect visual preview contact sheet:**
   - `python cli.py preview <project_dir>` (540×960 @ 12 spp OptiX, ~15s).
   - **Inspect `<project_dir>/preview/contact_sheet.png` visually via `read_file`.** Fix any scale, framing, or label overlap issues and re-verify before final render.
6. **Render full `1080×1920` 30 fps MP4:**
   - `python cli.py render <project_dir> --samples 12 --workers 2` (runs parallel OptiX GPU render → full frame integrity/brightness audit → BT.709 H.264/AAC MP4 encode).
   - Extract and inspect 3–4 stills directly from the encoded MP4 via `read_file` before finishing.
7. **Post-render storage hygiene:** After verifying the final MP4, offer to remove raw `frames_1080/` to save ~400–750 MB per project.
