"""Audio-first script parser, word-level cue timeline, and phrase grouper."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from typing import Any


def normalize_word(token: str) -> str:
    """Keep ASCII letters lowercase for robust token matching across punctuation."""
    return re.sub(r"[^a-z]", "", token.lower())


@dataclass
class ProjectConfig:
    name: str = "explainer_id"
    scene_file: str = "scene.py"
    language: str = "id"
    fps: int = 30
    width: int = 1080
    height: int = 1920
    lead_in_sec: float = 0.25
    tail_sec: float = 1.35
    caption_style: str = "phrases"  # "phrases" | "cards"
    caption_y_frac: float = 0.675
    script_file: str = "script.txt"
    timings_file: str = "timings.json"
    keywords_file: str = "keywords.txt"

    @classmethod
    def load(cls, project_dir: str) -> "ProjectConfig":
        cfg = cls()
        json_path = os.path.join(project_dir, "project.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            for k, v in data.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
        return cfg


@dataclass
class TimedWord:
    sentence_id: str
    text: str
    start_sec: float
    end_sec: float


@dataclass
class CaptionPhrase:
    words: list[str]
    word_starts: list[float]
    start_sec: float
    end_sec: float


class Timeline:
    """Single source of truth synchronizing narration timing, 3D cues, and captions."""

    def __init__(self, project_dir: str) -> None:
        self.project_dir = os.path.abspath(project_dir)
        self.config = ProjectConfig.load(self.project_dir)
        self.rows: list[tuple[str, str]] = self._read_script()
        self.voice_duration: float = 0.0
        self.words: list[TimedWord] = []
        self._load_timings()

    def _read_script(self) -> list[tuple[str, str]]:
        path = os.path.join(self.project_dir, self.config.script_file)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Script file not found: {path}")
        rows: list[tuple[str, str]] = []
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                sid, body = line.split("|", 1)
                rows.append((sid.strip(), body.strip()))
        # Numbers must be written as spoken words so token counts match spoken syllables 1-to-1
        for sid, body in rows:
            for tok in body.split():
                if re.search(r"\d", tok):
                    raise ValueError(
                        f"script.txt ({sid}): write numbers as Indonesian words, not digits ('{tok}')"
                    )
        return rows

    def _load_timings(self) -> None:
        path = os.path.join(self.project_dir, self.config.timings_file)
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as fh:
            payload: dict[str, Any] = json.load(fh)
        self.voice_duration = float(payload.get("voice_duration", 0.0))
        self.words = [
            TimedWord(
                sentence_id=str(item["sid"]),
                text=str(item["word"]),
                start_sec=float(item["start"]),
                end_sec=float(item["end"]),
            )
            for item in payload.get("words", [])
        ]

    @property
    def total_duration(self) -> float:
        raw = self.config.lead_in_sec + self.voice_duration + self.config.tail_sec
        return round(raw, 2)

    @property
    def total_frames(self) -> int:
        return max(1, int(round(self.total_duration * self.config.fps)))

    def sec_to_frame(self, seconds: float) -> float:
        return seconds * self.config.fps + 1.0

    def cue(
        self,
        sentence_id: str,
        word: str | None = None,
        nth: int = 1,
        end: bool = False,
    ) -> float:
        """Return video-space timestamp (seconds) for a sentence or specific spoken word."""
        matches = [w for w in self.words if w.sentence_id == sentence_id]
        if not matches:
            raise KeyError(f"Sentence '{sentence_id}' not found in timings.json")
        if word is not None:
            target = normalize_word(word)
            word_hits = [w for w in matches if normalize_word(w.text) == target]
            if len(word_hits) < nth:
                raise KeyError(
                    f"Word '{word}' (nth={nth}) not found in sentence '{sentence_id}'"
                )
            chosen = word_hits[nth - 1]
            return (chosen.end_sec if end else chosen.start_sec) + self.config.lead_in_sec
        return (matches[-1].end_sec if end else matches[0].start_sec) + self.config.lead_in_sec

    def sentence_climax_times(self, ratio: float = 0.68) -> list[float]:
        """Return one representative timestamp per sentence (default 68% into each sentence)."""
        out: list[float] = []
        for sid, _ in self.rows:
            t0 = self.cue(sid, end=False)
            t1 = self.cue(sid, end=True)
            out.append(round(t0 * (1.0 - ratio) + t1 * ratio, 2))
        return out

    def build_phrases(self) -> list[CaptionPhrase]:
        """Build 2-4 word progressive caption phrases aligned 1-to-1 with script.txt '/' markers."""
        display_tokens: list[str] = []
        group_sizes: list[int] = []

        for _, body in self.rows:
            raw_parts = body.split()
            if "/" in raw_parts:
                count = 0
                for tok in raw_parts + ["/"]:
                    if tok == "/":
                        if count > 0:
                            group_sizes.append(count)
                            count = 0
                    elif normalize_word(tok):
                        display_tokens.append(tok)
                        count += 1
            else:
                # Auto-group 2-4 words breaking on punctuation with no orphan 1-word tail
                clean_toks = [t for t in raw_parts if normalize_word(t)]
                display_tokens.extend(clean_toks)
                buf = 0
                for idx, tok in enumerate(clean_toks):
                    buf += 1
                    is_break = idx == len(clean_toks) - 1 or bool(re.search(r"[.,:;!?…]$", tok))
                    if is_break:
                        while buf > 4:
                            take = 2 if buf == 5 else 3
                            group_sizes.append(take)
                            buf -= take
                        if buf > 0:
                            group_sizes.append(buf)
                            buf = 0

        if len(display_tokens) != len(self.words):
            raise AssertionError(
                f"Token mismatch: script.txt has {len(display_tokens)} words vs timings.json has {len(self.words)}"
            )
        for a, b in zip(display_tokens, self.words):
            if normalize_word(a) != normalize_word(b.text):
                raise AssertionError(f"Word mismatch: '{a}' != '{b.text}'")

        phrases: list[CaptionPhrase] = []
        cursor = 0
        offset = self.config.lead_in_sec
        for gsize in group_sizes:
            p_words = display_tokens[cursor : cursor + gsize]
            w_starts = [self.words[cursor + k].start_sec + offset for k in range(gsize)]
            w_end = self.words[cursor + gsize - 1].end_sec + offset
            phrases.append(
                CaptionPhrase(
                    words=p_words,
                    word_starts=w_starts,
                    start_sec=w_starts[0],
                    end_sec=w_end,
                )
            )
            cursor += gsize

        # Keep each phrase legible until the next phrase begins (capped at +0.5s across long gaps)
        for idx, ph in enumerate(phrases):
            if idx + 1 < len(phrases):
                ph.end_sec = min(phrases[idx + 1].start_sec, ph.end_sec + 0.5)
            else:
                ph.end_sec = ph.end_sec + 0.9
        return phrases
