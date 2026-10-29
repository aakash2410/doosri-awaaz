"""Export a pack's voiced lines as Calibrate (calibrate.artpark.ai) datasets.

Calibrate's speech-to-text evaluation takes audio with reference transcripts.
Uploading the audio children will hear, with the approved text as reference,
checks that each line is intelligible: if strong recognisers cannot transcribe
it, a child may not follow it either. Its text-to-speech evaluation takes text
only, to compare other voice providers on the same lines.

Writes, per language, to evals/calibrate/<pack-id>/:
  <pack-id>-<lang>-stt.zip   audios/*.wav + data.csv (audio_file, text)
  <pack-id>-<lang>-tts.csv   text

  python -m evals.calibrate_export <pack-id>
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from doosri import store

OUT = Path(__file__).resolve().parent / "calibrate"


def to_wav(mp3: Path, wav: Path) -> None:
    if sys.platform == "darwin":
        subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(mp3), str(wav)], check=True)
    else:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "quiet", "-i", str(mp3), "-ar", "16000", "-ac", "1", str(wav)], check=True)


def main() -> None:
    pack_id = sys.argv[1]
    pack = store.load(pack_id)
    if pack.status != "approved":
        sys.exit(f"{pack_id} is not approved; only approved packs have audio")
    audio = store.pack_dir(pack_id) / "audio"
    manifest = json.loads((audio / "manifest.json").read_text(encoding="utf-8"))
    out = OUT / pack_id
    out.mkdir(parents=True, exist_ok=True)

    for lang, lines in manifest.items():
        with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(out / f"{pack_id}-{lang}-stt.zip", "w") as z:
            rows = []
            for text, mp3 in lines.items():
                wav = Path(tmp) / Path(mp3).with_suffix(".wav").name
                to_wav(audio / mp3, wav)
                z.write(wav, f"audios/{wav.name}")
                rows.append((wav.name, text))
            data = Path(tmp) / "data.csv"
            with data.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerows([("audio_file", "text"), *rows])
            z.write(data, "data.csv")
        with (out / f"{pack_id}-{lang}-tts.csv").open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows([("text",), *((t,) for t in lines)])
        print(f"{lang}: {len(lines)} lines -> {out.relative_to(Path.cwd())}")


if __name__ == "__main__":
    main()
