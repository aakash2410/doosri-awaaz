"""Classroom I/O back ends for the session engine.

TextIO      scripted or typed answers; for tests and a terminal walk-through
LaptopIO    laptop speaker + microphone (Vosk), colour buttons on the keyboard
SunoSutraIO Suno Sutra device: speaker, microphone, trigger and NeoKey buttons
"""

from __future__ import annotations

import json
import logging
import os
import queue
import select
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Iterator, List, Optional

from .session import Heard

log = logging.getLogger(__name__)

KEY_COLOURS = {"r": "red", "b": "blue", "g": "green", "y": "yellow"}
VOSK_MODEL = "vosk-model-small-hi-0.22"
VOSK_DIR = Path(os.environ.get("DOOSRI_VOSK_DIR", Path.home() / ".cache" / "doosri" / "vosk"))


class AudioBank:
    """Finds the pre-rendered file for a line of text."""

    def __init__(self, pack_dir: Path):
        self.dir = pack_dir / "audio"
        manifest = self.dir / "manifest.json"
        self.manifest = json.loads(manifest.read_text()) if manifest.exists() else {}

    def path(self, lang: str, text: str) -> Optional[Path]:
        name = self.manifest.get(lang, {}).get(text)
        p = self.dir / name if name else None
        return p if p and p.exists() else None


def _player_cmd(path: Path) -> List[str]:
    if shutil.which("afplay"):
        return ["afplay", str(path)]
    if shutil.which("mpg123"):
        return ["mpg123", "-q", str(path)]
    return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)]


class TextIO:
    """Prints what the device says; answers come from a script or the keyboard.

    Script entries: 'r'/'b'/'g'/'y' for a button, 'say:<words>' for speech,
    'ask:<question>' for a question, '' for silence."""

    def __init__(self, script: Optional[Iterator[str]] = None, quiet: bool = False):
        self.script = script
        self.quiet = quiet
        self.spoken: List[tuple] = []

    def _next(self, prompt: str) -> str:
        if self.script is not None:
            return next(self.script, "")
        return input(prompt)

    def play(self, lang: str, text: str) -> None:
        self.spoken.append((lang, text))
        if not self.quiet:
            print(f"  [{lang}] {text}")

    def show(self, text: str) -> None:
        if not self.quiet:
            print(f"--- {text}")

    def listen_answer(self, words, seconds) -> Heard:
        s = self._next("answer (r/b/g/y, or say:<words>): ").strip()
        if s in KEY_COLOURS:
            return Heard("button", colour=KEY_COLOURS[s])
        if s.startswith("say:"):
            return Heard("voice", text=s[4:], confidence=1.0)
        return Heard("none")

    def listen_question(self, seconds) -> Optional[str]:
        s = self._next("question (ask:<text>, or Enter for none): ").strip()
        return s[4:] if s.startswith("ask:") else None


class _Recogniser:
    """Vosk speech recognition, optionally restricted to a word list."""

    def __init__(self, model_dir: Path = VOSK_DIR / VOSK_MODEL):
        from vosk import Model, SetLogLevel

        SetLogLevel(-1)
        if not model_dir.exists():
            raise SystemExit(f"Vosk model missing at {model_dir}. Run: python -m engine.fetch_models")
        self.model = Model(str(model_dir))

    def known(self, words: List[str]) -> List[str]:
        return [w for w in words if self.model.vosk_model_find_word(w) >= 0]

    def recognise(self, pcm16: bytes, rate: int, words: Optional[List[str]] = None) -> tuple:
        from vosk import KaldiRecognizer

        if words:
            rec = KaldiRecognizer(self.model, rate, json.dumps(self.known(words) + ["[unk]"], ensure_ascii=False))
        else:
            rec = KaldiRecognizer(self.model, rate)
        rec.SetWords(True)
        rec.AcceptWaveform(pcm16)
        res = json.loads(rec.FinalResult())
        parts = [w for w in res.get("result", []) if w.get("word") != "[unk]"]
        text = " ".join(w["word"] for w in parts)
        conf = sum(w["conf"] for w in parts) / len(parts) if parts else 0.0
        return text, conf


class LaptopIO:
    RATE = 16000

    def __init__(self, bank: AudioBank):
        self.bank = bank
        self.asr = _Recogniser()

    def play(self, lang: str, text: str) -> None:
        print(f"  [{lang}] {text}")
        p = self.bank.path(lang, text)
        if p:
            subprocess.run(_player_cmd(p), check=False)

    def show(self, text: str) -> None:
        print(f"--- {text}")

    def _record(self, seconds: float, stop: threading.Event) -> bytes:
        import sounddevice as sd

        frames: "queue.Queue[bytes]" = queue.Queue()
        with sd.RawInputStream(samplerate=self.RATE, channels=1, dtype="int16",
                               callback=lambda d, *_: frames.put(bytes(d))):
            stop.wait(seconds)
        return b"".join(frames.queue)

    def _listen(self, seconds: float, words: Optional[List[str]]) -> Heard:
        print(f"  (listening {seconds:.0f}s - speak, or type r/b/g/y + Enter for a button)")
        stop = threading.Event()
        result: dict = {}
        t = threading.Thread(target=lambda: result.update(pcm=self._record(seconds, stop)))
        t.start()
        ready, _, _ = select.select([sys.stdin], [], [], seconds)
        key = sys.stdin.readline().strip().lower() if ready else ""
        stop.set()
        t.join()
        if key in KEY_COLOURS:
            return Heard("button", colour=KEY_COLOURS[key])
        text, conf = self.asr.recognise(result.get("pcm", b""), self.RATE, words)
        print(f"  (heard: '{text}' conf={conf:.2f})")
        return Heard("voice", text=text, confidence=conf) if text else Heard("none")

    def listen_answer(self, words, seconds) -> Heard:
        return self._listen(seconds, words)

    def listen_question(self, seconds) -> Optional[str]:
        h = self._listen(seconds, None)
        return h.text or None


class SunoSutraIO:
    """Runs on the Suno Sutra device through its pocketinfer board object.

    NeoKey buttons A-D arrive from the IO expander as 'BA1'..'BD1' and map to
    red, blue, green, yellow. Questions are asked by holding the trigger button."""

    NEOKEY = {"BA1": "red", "BB1": "blue", "BC1": "green", "BD1": "yellow"}

    def __init__(self, board, bank: AudioBank):
        self.board, self.bank = board, bank
        self.asr = _Recogniser()
        self.presses: "queue.Queue[str]" = queue.Queue()
        board.ioexp.subscribe(self._on_msg)

    def _on_msg(self, msg: str) -> None:
        if msg in self.NEOKEY:
            self.presses.put(self.NEOKEY[msg])

    def play(self, lang: str, text: str) -> None:
        p = self.bank.path(lang, text)
        if p:
            subprocess.run(["ffmpeg", "-loglevel", "quiet", "-i", str(p), "-f", "alsa",
                            self.board.ALSA_PLAYBACK_DEVICE], check=False)

    def show(self, text: str) -> None:
        self.board.statusbar(text)

    def _pcm(self) -> tuple:
        data = self.board.audio.to_audio_data()
        return data.get_raw_data(convert_rate=16000, convert_width=2), 16000

    def listen_answer(self, words, seconds) -> Heard:
        while not self.presses.empty():
            self.presses.get_nowait()
        self.board.audio.start()
        try:
            colour = self.presses.get(timeout=seconds)
        except queue.Empty:
            colour = None
        self.board.audio.stop()
        if colour:
            return Heard("button", colour=colour)
        pcm, rate = self._pcm()
        text, conf = self.asr.recognise(pcm, rate, words)
        return Heard("voice", text=text, confidence=conf) if text else Heard("none")

    def listen_question(self, seconds) -> Optional[str]:
        self.board.statusbar("Hold button to ask")
        self.board.wait_for_trigger_button_down(timeout=seconds)
        if not self.board.trigger_button:
            return None
        self.board.audio.start()
        self.board.wait_for_trigger_button_up(timeout=15)
        self.board.audio.stop()
        pcm, rate = self._pcm()
        text, _ = self.asr.recognise(pcm, rate, None)
        return text or None
