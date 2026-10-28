"""How well does on-device answer recognition work for a pack?

For every item, synthesises each choice's spoken answer in both languages with
two voices per language, runs it through the same restricted-grammar Vosk
recogniser the device uses, and reports how often the verdict is right.

The voices are synthetic adult voices, so this is an upper bound; children in a
noisy room will do worse. What matters most is the last column: how often a
correct answer is marked wrong (should be 0).

  python -m evals.asr_eval <pack-id>
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import tempfile
import time
import wave
from collections import Counter
from pathlib import Path

import edge_tts

from doosri import store
from engine.io import _Recogniser
from engine.match import grammar_words, judge_voice

VOICES = {"mr": ["mr-IN-AarohiNeural", "mr-IN-ManoharNeural"], "hi": ["hi-IN-SwaraNeural", "hi-IN-MadhurNeural"]}


def pcm_for(text: str, voice: str, tmp: Path) -> bytes:
    mp3, wav = tmp / "a.mp3", tmp / "a.wav"
    for attempt in range(4):  # the TTS service occasionally drops a request
        try:
            asyncio.run(edge_tts.Communicate(text, voice).save(str(mp3)))
            break
        except edge_tts.exceptions.NoAudioReceived:
            time.sleep(1 + attempt)
    else:
        raise RuntimeError(f"no audio for {text!r} from {voice}")
    if sys.platform == "darwin":
        subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(mp3), str(wav)], check=True)
    else:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "quiet", "-i", str(mp3), "-ar", "16000", "-ac", "1", str(wav)], check=True)
    with wave.open(str(wav)) as w:
        return w.readframes(w.getnframes())


def main() -> None:
    pack = store.load(sys.argv[1])
    asr = _Recogniser()
    tally: Counter = Counter()
    rows = []
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        for item in pack.items:
            words = grammar_words(item)
            for ch in item.choices:
                for side, lang in (("home", pack.home_language), ("school", pack.school_language)):
                    said = getattr(ch.label, side)
                    for voice in VOICES[lang]:
                        text, conf = asr.recognise(pcm_for(said, voice, tmp), 16000, words)
                        result = judge_voice(item, text, conf).result
                        expected = "correct" if ch.colour == item.correct else "wrong"
                        outcome = "right" if result == expected else ("unclear" if result == "unclear" else "WRONG")
                        tally[(expected, outcome)] += 1
                        rows.append((item.id, lang, said, text, round(conf, 2), result, outcome))
            print(f"{item.id}: {len(asr.known(words))}/{len(words)} expected words in the recogniser's vocabulary")
    for r in rows:
        print("  ", *r, sep="\t")
    n = sum(tally.values())
    right = sum(v for (e, o), v in tally.items() if o == "right")
    unclear = sum(v for (e, o), v in tally.items() if o == "unclear")
    correct_marked_wrong = tally[("correct", "WRONG")]
    wrong_marked_correct = tally[("wrong", "WRONG")]
    print(f"\n{n} spoken answers: {right} judged right ({right / n:.0%}), {unclear} unclear -> re-prompt ({unclear / n:.0%})")
    print(f"correct answers marked wrong: {correct_marked_wrong}; wrong answers marked correct: {wrong_marked_correct}")


if __name__ == "__main__":
    main()
