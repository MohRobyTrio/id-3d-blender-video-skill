"""Cross-platform one-command environment bootstrap for id-3d-blender-video-skill.

Usage:
  python setup.py                  # Install Blender bpy + core deps + check GPU/FFmpeg
  python setup.py --with-f5-tts    # Also create isolated Python 3.11 CUDA venv + download F5-TTS-INDO-FINETUNE-V2
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def run(cmd: list[str]) -> None:
    print(">>", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def check_system() -> None:
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    ff = shutil.which("ffmpeg")
    print(f"FFmpeg: {ff or 'NOT IN PATH (install ffmpeg or set FFMPEG_BIN)'}")
    nv = shutil.which("nvidia-smi")
    if nv:
        subprocess.run([nv, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"])
    else:
        print("GPU: nvidia-smi not found (Cycles will fall back to CPU/Metal).")


def install_blender_deps() -> None:
    print("\n=== Installing Blender bpy + core Python dependencies ===")
    run([sys.executable, "-m", "pip", "install", "--upgrade", "bpy", "pillow", "numpy", "soundfile", "edge-tts"])
    run(
        [
            sys.executable,
            "-c",
            "import bpy; print('Blender bpy:', bpy.app.version_string); "
            "prefs = bpy.context.preferences.addons['cycles'].preferences; "
            "prefs.compute_device_type = 'OPTIX'; prefs.get_devices(); "
            "print('Detected devices:', [(d.name, d.type) for d in prefs.devices])",
        ]
    )


def install_f5_tts(py311: str | None) -> None:
    print("\n=== Installing isolated F5-TTS Indonesian CUDA environment ===")
    venv_dir = os.path.join(ROOT, ".venv-tts")
    base_py = py311 or sys.executable
    if not os.path.exists(venv_dir):
        run([base_py, "-m", "venv", venv_dir])
    is_win = os.name == "nt"
    v_py = os.path.join(venv_dir, "Scripts" if is_win else "bin", "python.exe" if is_win else "python")
    v_pip = os.path.join(venv_dir, "Scripts" if is_win else "bin", "pip.exe" if is_win else "pip")
    run([v_py, "-m", "pip", "install", "--upgrade", "pip"])
    run([v_pip, "install", "torch", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cu124"])
    run([v_pip, "install", "f5-tts", "soundfile", "huggingface_hub", "edge-tts"])

    model_dir = os.path.join(ROOT, "models", "f5_indo_v2")
    os.makedirs(model_dir, exist_ok=True)
    print("\n=== Downloading Eempostor/F5-TTS-INDO-FINETUNE-V2 (~1.3 GB, CC BY-NC 4.0) ===")
    run(
        [
            v_py,
            "-c",
            "from huggingface_hub import hf_hub_download; "
            f"hf_hub_download('Eempostor/F5-TTS-INDO-FINETUNE-V2', 'f5_tts_indo_v2.pt', local_dir={model_dir!r}); "
            f"hf_hub_download('Eempostor/F5-TTS-INDO-FINETUNE-V2', 'vocab.txt', local_dir={model_dir!r}); "
            "print('Model downloaded cleanly!')",
        ]
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Bootstrap id-3d-blender-video-skill dependencies")
    ap.add_argument("--with-f5-tts", action="store_true", help="Install isolated CUDA PyTorch + F5-TTS Indonesian model")
    ap.add_argument("--py311", default=None, help="Path to Python 3.11 executable for F5-TTS venv")
    args = ap.parse_args()

    check_system()
    install_blender_deps()
    if args.with_f5_tts:
        install_f5_tts(args.py311)
    print("\nSetup complete! See README.md for Quick Start commands.")


if __name__ == "__main__":
    main()
