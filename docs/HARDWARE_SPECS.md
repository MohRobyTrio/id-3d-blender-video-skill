# Hardware, Software & Performance Specifications

## 1. Hardware Requirements

| Component | Minimum (CPU Fallback / Lightweight) | Recommended (Fast Local 1080p) | Optimal (Production Batching) |
| :--- | :--- | :--- | :--- |
| **GPU** | Any GPU (or CPU-only Cycles + `edge-tts`) | **NVIDIA RTX 3050 / RTX 4050 (6 GB VRAM)** with OptiX RT Cores | **NVIDIA RTX 3060 12 GB / RTX 4060 Ti / RTX 4070+ (12–16 GB VRAM)** |
| **VRAM** | 0 GB (CPU mode) / 4 GB (tight F5-TTS) | **6 GB VRAM** *(verified on RTX 4050 Laptop)* | **12 GB+ VRAM** |
| **CPU** | 4-core x86_64 / Apple Silicon | **6–8 core modern CPU** (Ryzen 5/7 or Intel Core i5/i7) | **8–16 core CPU** |
| **System RAM** | 8 GB | **16 GB** | **32 GB** |
| **Free Storage** | ~3 GB (`bpy` + `edge-tts` only) | **~12–15 GB** *(incl. PyTorch CUDA 5.6 GB + F5-TTS 1.3 GB + temp frames; ~9 GB after cache cleanup)* | **25 GB+ SSD/NVMe** |
| **OS** | Windows 10/11 (64-bit), macOS 13+, Linux (x86_64) | **Windows 11 / Ubuntu 22.04+ with NVIDIA Driver ≥ 535** | **Windows 11 / Linux with CUDA 12.4+** |

---

## 2. Software Dependencies

| Dependency | Version | Purpose | Required? |
| :--- | :--- | :--- | :--- |
| **Python (Blender runtime)** | **3.11 – 3.13** *(3.13 verified with `bpy 5.3.0`)* | Runs `bpy`, `cli.py`, `Pillow`, `numpy` | **Yes** |
| **Blender Python (`bpy`)** | **5.3.0+** *(4.2+ compatible)* | Headless Cycles 3D rendering engine | **Yes** |
| **FFmpeg** | **6.x / 7.x+** (with `libx264`, `aac`, `image2pipe`) | Final BT.709 MP4 encoding & audio decoding | **Yes** |
| **Python (TTS isolated venv)** | **3.11** *(recommended for `f5-tts` + `torch` wheels)* | Runs PyTorch CUDA + `f5-tts` + `soundfile` | Optional *(only for `f5_indo` backend)* |
| **PyTorch + torchaudio** | **2.6.0+cu124** | CUDA GPU inference for `F5-TTS-INDO-FINETUNE-V2` | Optional *(only for `f5_indo` backend)* |
| **edge-tts** | **7.x+** | Synthetic multi-pitch reference & commercial-safe TTS fallback | Recommended |

---

## 3. Verified Real-World Benchmarks (NVIDIA GeForce RTX 4050 Laptop — 6 GB VRAM)

Measured on Windows 11, 8-core laptop CPU, NVIDIA GeForce RTX 4050 Laptop (6 GB VRAM), `bpy 5.3.0`, Cycles **OptiX** + **OptiX Hardware AI Denoiser** (`RGB_ALBEDO_NORMAL`):

| Workload | Settings | Measured Speed | Typical Total Time (42s / 1,275 frames) |
| :--- | :--- | :--- | :--- |
| **Local F5-TTS Indonesian Voice** | `F5TTS_v1_Base`, `nfe=32`, CUDA FP32 | ~2.7 – 3.5 s / sentence | **~30 seconds** (9 sentences) |
| **Render-Free Scene QA (`check`)** | 255 objects, 30,000+ keyframes | Instant | **~8 seconds** |
| **Preview Contact Sheet (`preview`)** | 9 stills, `540×960` @ `12 spp` OptiX | **~1.0 s / still** | **~15 seconds** |
| **Full 1080p Render (`render`)** | `1080×1920` @ `12 spp` OptiX, 2 parallel workers, `PERSIST=1`, JPEG q97 | **~0.72 – 1.08 frames / sec** | **~20 – 28 minutes** |
| **Caption Burn + BT.709 MP4 Encode** | PIL RGBA overlay → `image2pipe` PNG → `libx264` CRF 17 | ~15 – 20 frames / sec | **~1.2 minutes** |
| **Total Monetary Cost** | 100% local execution | **Rp 0 / \$0.00** | **Unlimited videos** |

---

## 4. Storage Hygiene Guide

Because `pip` caches downloaded `.whl` installers (`torch` 2.5 GB + `bpy` 356 MB) and Blender writes ~350–400 KB per raw `1080×1920` JPEG frame (~500–750 MB per video):
- Run `pip cache purge` after initial setup to reclaim **~3–5 GB** immediately.
- Once your final `out/*.mp4` (~20–35 MB) is visually verified, you can safely delete `frames_1080/` to reclaim **~400–750 MB** per video while keeping all scripts, voiceover, and tools intact.
