"""Unified cross-platform CLI for id-3d-blender-video-skill (studio3d)."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def cmd_voice(args) -> None:
    from studio3d.voice import build_project_voice

    only = set(args.only.split(",")) if args.only else None
    build_project_voice(
        project_dir=args.project,
        backend=args.backend,
        model_dir=args.model_dir,
        ref_wav=args.ref_wav,
        speed=args.speed,
        cfg_strength=args.cfg,
        only_sids=only,
    )


def cmd_phrases(args) -> None:
    from studio3d.timeline import Timeline

    tl = Timeline(args.project)
    phrases = tl.build_phrases()
    print(f"{len(phrases)} phrases | DUR={tl.total_duration}s | FRAMES={tl.total_frames}")
    for ph in phrases:
        print(f"  {ph.start_sec:6.2f}-{ph.end_sec:6.2f}  {' '.join(ph.words)}")


def cmd_check(args) -> None:
    from studio3d.timeline import Timeline

    tl = Timeline(args.project)
    scene_py = os.path.join(tl.project_dir, tl.config.scene_file)
    subprocess.run([sys.executable, scene_py, "check"], cwd=tl.project_dir, check=True)


def cmd_preview(args) -> None:
    from studio3d.pipeline import build_contact_sheet
    from studio3d.timeline import Timeline

    tl = Timeline(args.project)
    scene_py = os.path.join(tl.project_dir, tl.config.scene_file)
    stills_dir = os.path.join(tl.project_dir, "preview", "stills")
    times = [f"{t:.2f}" for t in tl.sentence_climax_times(args.ratio)]
    subprocess.run(
        [sys.executable, scene_py, "stills", str(args.width), str(args.height), str(args.samples), stills_dir, *times],
        cwd=tl.project_dir,
        check=True,
    )
    out_png = os.path.abspath(args.out or os.path.join(tl.project_dir, "preview", "contact_sheet.png"))
    build_contact_sheet(tl.project_dir, stills_dir, out_png, cols=args.cols)


def cmd_render(args) -> None:
    from studio3d.pipeline import encode_bt709_mp4, render_parallel_frames
    from studio3d.timeline import Timeline

    tl = Timeline(args.project)
    scene_py = os.path.join(tl.project_dir, tl.config.scene_file)
    frames_dir = os.path.abspath(args.frames_dir or os.path.join(tl.project_dir, "frames_1080"))
    render_parallel_frames(
        project_dir=tl.project_dir,
        scene_script=scene_py,
        frames_dir=frames_dir,
        width=tl.config.width,
        height=tl.config.height,
        samples=args.samples,
        workers=args.workers,
    )
    if not args.frames_only:
        out_mp4 = os.path.abspath(args.out or os.path.join(tl.project_dir, "out", f"{tl.config.name}.mp4"))
        audio = os.path.join(tl.project_dir, args.audio)
        encode_bt709_mp4(tl.project_dir, frames_dir, audio, out_mp4, burn_captions=not args.clean, crf=args.crf)


def cmd_encode(args) -> None:
    from studio3d.pipeline import encode_bt709_mp4
    from studio3d.timeline import Timeline

    tl = Timeline(args.project)
    frames_dir = os.path.abspath(args.frames_dir or os.path.join(tl.project_dir, "frames_1080"))
    out_mp4 = os.path.abspath(args.out or os.path.join(tl.project_dir, "out", f"{tl.config.name}.mp4"))
    audio = os.path.join(tl.project_dir, args.audio)
    encode_bt709_mp4(tl.project_dir, frames_dir, audio, out_mp4, burn_captions=not args.clean, crf=args.crf)


def main() -> None:
    ap = argparse.ArgumentParser(prog="studio3d", description="Local Free Indonesian 3D Engineering Explainer Pipeline")
    sub = ap.add_subparsers(dest="command", required=True)

    p_v = sub.add_parser("voice", help="Generate narration audio + timings.json")
    p_v.add_argument("project", help="Project folder containing script.txt & project.json")
    p_v.add_argument("--backend", choices=["f5_indo", "edge", "custom"], default="f5_indo")
    p_v.add_argument("--model-dir", default=None)
    p_v.add_argument("--ref-wav", default=None)
    p_v.add_argument("--speed", type=float, default=0.93)
    p_v.add_argument("--cfg", type=float, default=1.95)
    p_v.add_argument("--only", default=None, help="Comma-separated sentence IDs to regenerate (e.g. S02,S04)")
    p_v.set_defaults(func=cmd_voice)

    p_p = sub.add_parser("phrases", help="Inspect phrase timing splits")
    p_p.add_argument("project")
    p_p.set_defaults(func=cmd_phrases)

    p_c = sub.add_parser("check", help="Run render-free 3D scene QA audit")
    p_c.add_argument("project")
    p_c.set_defaults(func=cmd_check)

    p_pr = sub.add_parser("preview", help="Render captioned preview contact sheet")
    p_pr.add_argument("project")
    p_pr.add_argument("--width", type=int, default=540)
    p_pr.add_argument("--height", type=int, default=960)
    p_pr.add_argument("--samples", type=int, default=12)
    p_pr.add_argument("--cols", type=int, default=3)
    p_pr.add_argument("--ratio", type=float, default=0.68)
    p_pr.add_argument("--out", default=None)
    p_pr.set_defaults(func=cmd_preview)

    p_r = sub.add_parser("render", help="Render all 1080x1920 frames in parallel & encode BT.709 MP4")
    p_r.add_argument("project")
    p_r.add_argument("--samples", type=int, default=12)
    p_r.add_argument("--workers", type=int, default=2)
    p_r.add_argument("--frames-dir", default=None)
    p_r.add_argument("--audio", default="vo_mix.wav")
    p_r.add_argument("--out", default=None)
    p_r.add_argument("--crf", type=int, default=17)
    p_r.add_argument("--clean", action="store_true")
    p_r.add_argument("--frames-only", action="store_true")
    p_r.set_defaults(func=cmd_render)

    p_e = sub.add_parser("encode", help="Encode already-rendered frames + audio into BT.709 MP4")
    p_e.add_argument("project")
    p_e.add_argument("--frames-dir", default=None)
    p_e.add_argument("--audio", default="vo_mix.wav")
    p_e.add_argument("--out", default=None)
    p_e.add_argument("--crf", type=int, default=17)
    p_e.add_argument("--clean", action="store_true")
    p_e.set_defaults(func=cmd_encode)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
