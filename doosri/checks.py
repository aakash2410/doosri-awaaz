"""Deterministic checks on a pack. These run after Claude drafts a pack and
again before a reviewer can approve it. Errors block approval."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from .schema import Line, Pack

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
LETTER = re.compile(r"[^\W\d_]", re.UNICODE)
MAX_PROMPT_WORDS = 25
MIN_ITEMS, MAX_ITEMS = 3, 6


@dataclass
class Finding:
    level: str  # "error" | "warning"
    where: str
    message: str


def _devanagari_share(text: str) -> float:
    letters = LETTER.findall(text)
    if not letters:
        return 0.0
    return sum(1 for c in letters if DEVANAGARI.match(c)) / len(letters)


def _lines(pack: Pack):
    yield "intro", pack.intro
    if pack.story:
        yield "story", pack.story
    for it in pack.items:
        for field in ("prompt", "hint", "reveal", "praise"):
            yield f"{it.id}.{field}", getattr(it, field)
        for ch in it.choices:
            yield f"{it.id}.choice.{ch.colour}", ch.label
    for q in pack.faq:
        yield f"{q.id}.answer", q.answer
    yield "ask_teacher", pack.ask_teacher
    yield "closing", pack.closing


def check_pack(pack: Pack) -> List[Finding]:
    out: List[Finding] = []

    def err(where, msg):
        out.append(Finding("error", where, msg))

    def warn(where, msg):
        out.append(Finding("warning", where, msg))

    if not MIN_ITEMS <= len(pack.items) <= MAX_ITEMS:
        err("items", f"pack has {len(pack.items)} items; expected {MIN_ITEMS}-{MAX_ITEMS}")
    if len(pack.faq) < 2:
        warn("faq", "fewer than 2 FAQ entries; most child questions will go to the teacher")

    ids = [it.id for it in pack.items] + [q.id for q in pack.faq]
    if len(ids) != len(set(ids)):
        err("ids", "item and FAQ ids must be unique")

    for it in pack.items:
        colours = [c.colour for c in it.choices]
        if not 2 <= len(colours) <= 4:
            err(it.id, f"{len(colours)} choices; expected 2-4")
        if len(colours) != len(set(colours)):
            err(it.id, "a colour is used twice")
        if it.correct not in colours:
            err(it.id, f"correct colour '{it.correct}' is not one of the choices")
        if not [w for w in it.accepted_spoken if w.strip()]:
            err(it.id, "no accepted spoken answers; voice answers can never be marked right")
        for lang in ("home", "school"):
            n = len(getattr(it.prompt, lang).split())
            if n > MAX_PROMPT_WORDS:
                warn(f"{it.id}.prompt.{lang}", f"{n} words; Class 1-3 prompts should stay under {MAX_PROMPT_WORDS}")

    for where, line in _lines(pack):
        _check_line(where, line, err, warn)

    return out


def _check_line(where: str, line: Line, err, warn) -> None:
    for lang in ("home", "school"):
        text = getattr(line, lang).strip()
        if not text:
            err(f"{where}.{lang}", "empty line")
        elif _devanagari_share(text) < 0.8:
            err(f"{where}.{lang}", "line is not in Devanagari script")
    if line.home.strip() and line.home.strip() == line.school.strip():
        warn(where, "home and school lines are identical; check the home-language version")


def blocking(findings: List[Finding]) -> bool:
    return any(f.level == "error" for f in findings)
