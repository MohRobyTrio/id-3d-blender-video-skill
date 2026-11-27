# Changelog

All notable changes to **id-3d-blender-video-skill** are documented in this file.
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-27

### Added
- **Clean-room standalone `studio3d` Python package (MIT License):**
  - `studio3d/timeline.py` — Audio-first script parser (`script.txt`), strict numbers-as-words validation, word-level cue resolution (`Timeline.cue()`), and 2–4 word progressive phrase grouper.
  - `studio3d/scene.py` — Blender 5.3+ native OOP `DioramaStudio` & `CameraRig` (1.0 unit = 1 meter realistic scale, zero Blender 6.0 `use_nodes` deprecation warnings, procedural daylight cloud sky, stratified soil, striped turf, animated water shader, diegetic billboard callouts, Catmull-Rom particle flows, helical coils, and original `add_educator()` 3D presenter figure).
  - `studio3d/voice.py` — 100% free local Indonesian voice pipeline supporting **F5-TTS-INDO-FINETUNE-V2** (with auto-built multi-pitch melodic synthetic reference, zero third-party cloning), **edge-tts** fallback, and **custom WAV recordings**, plus pure-NumPy studio biquad EQ + dynamic compressor + ambient 4-chord synth BGM + RMS speech-envelope CDF word alignment.
  - `studio3d/pipeline.py` — Render-free scene QA audit, captioned preview contact-sheet generator, cross-platform multi-worker Cycles OptiX/CUDA/CPU frame renderer with brightness/size integrity audit, and lossless `image2pipe` PNG → explicit **BT.709** H.264/AAC MP4 encoder.
- **Unified CLI (`cli.py`)** supporting `voice`, `phrases`, `check`, `preview`, `render`, and `encode`.
- **Cross-platform bootstrap installer (`setup.py`)** with optional isolated CUDA Python 3.11 `.venv-tts` setup.
- **Complete realistic-scale example (`examples/ac_split_1pk/`)**: *Cara Kerja AC Split 1 PK* using everyday Indonesian terminology (*"freon"*) and true-to-life 1 PK indoor/outdoor wall-mounted proportions + macro cutaway zooms.
- **Multi-Agent Skill Specification (`SKILL.md`)** compatible with Antigravity, Claude Code, Cursor, and Gemini CLI.
- **Full Technical Documentation:** `README.md`, `docs/ARCHITECTURE.md`, and `docs/HARDWARE_SPECS.md`.
