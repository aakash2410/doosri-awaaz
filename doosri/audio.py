"""Renders every line a pack can speak to audio files during Prepare (online),
so the classroom device only plays files and needs no text-to-speech model.

Where a home language has no synthetic voice, a local speaker's recording can
be dropped in under the same file name (see manifest.json)."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Dict, Iterable, Tuple

import edge_tts

from .checks import _lines
from .phrases import COLOUR_WORDS, PHRASES, TEACHER_PHRASES, teacher_score
from .schema import Pack
from .store import pack_dir

VOICES = {"mr": "mr-IN-AarohiNeural", "hi": "hi-IN-SwaraNeural"}
RATE = "-10%"  # a little slower for young listeners


def audio_name(lang: str, text: str) -> str:
    return hashlib.sha1(f"{lang}|{text}".encode()).hexdigest()[:16] + ".mp3"


def spoken_texts(pack: Pack) -> Iterable[Tuple[str, str]]:
    """Every (language, text) pair the engine may play for this pack."""
    home, school = pack.home_language, pack.school_language
    for _, line in _lines(pack):
        yield home, line.home
        yield school, line.school
    for p in list(PHRASES.values()) + list(COLOUR_WORDS.values()):
        yield home, p[home]
        yield school, p[school]
    for text in TEACHER_PHRASES.values():
        yield school, text
    m = len(pack.items)
    for n in range(m + 1):
        yield school, teacher_score(n, m)
    for it in pack.items:
        yield school, it.skill_spoken


async def _render_one(lang: str, text: str, path: Path) -> None:
    for attempt in range(4):  # the TTS service occasionally drops a request
        try:
            await edge_tts.Communicate(text, VOICES[lang], rate=RATE).save(str(path))
            return
        except edge_tts.exceptions.NoAudioReceived:
            await asyncio.sleep(1 + attempt)
    raise RuntimeError(f"no audio received for {text!r}")


async def _render(pack: Pack, out: Path, force: bool) -> Dict[str, Dict[str, str]]:
    out.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, Dict[str, str]] = {}
    todo = []
    for lang, text in dict.fromkeys(spoken_texts(pack)):
        name = audio_name(lang, text)
        manifest.setdefault(lang, {})[text] = name
        if force or not (out / name).exists():
            todo.append(_render_one(lang, text, out / name))
    sem = asyncio.Semaphore(6)

    async def bounded(c):
        async with sem:
            await c

    await asyncio.gather(*(bounded(c) for c in todo))
    return manifest


def render_pack_audio(pack: Pack, force: bool = False) -> Path:
    out = pack_dir(pack.id) / "audio"
    manifest = asyncio.run(_render(pack, out, force))
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    # Fixed lines for the browser simulator, so it speaks exactly what the Python engine does.
    m = len(pack.items)
    phrases = {"phrases": PHRASES, "colour_words": COLOUR_WORDS, "teacher": TEACHER_PHRASES,
               "teacher_score": {n: teacher_score(n, m) for n in range(m + 1)}}
    (out / "phrases.json").write_text(json.dumps(phrases, ensure_ascii=False, indent=1))
    return out
