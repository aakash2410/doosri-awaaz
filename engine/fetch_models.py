"""Download the offline speech model once, while online.

  python -m engine.fetch_models            for the Python engine
  python -m engine.fetch_models --web      also pack it for the browser simulator
"""

from __future__ import annotations

import argparse
import io
import tarfile
import urllib.request
import zipfile
from pathlib import Path

from .io import VOSK_DIR, VOSK_MODEL

URL = f"https://alphacephei.com/vosk/models/{VOSK_MODEL}.zip"
WEB_MODELS = Path(__file__).resolve().parent.parent / "web" / "models"
WEB_OUT = WEB_MODELS / f"{VOSK_MODEL}.tar.gz"
# Same sentence-embedding model as the Python engine, exported for transformers.js.
WEB_EMBED = "Xenova/paraphrase-multilingual-MiniLM-L12-v2"
WEB_EMBED_FILES = ["config.json", "tokenizer.json", "tokenizer_config.json",
                   "special_tokens_map.json", "onnx/model_quantized.onnx"]


def fetch() -> Path:
    target = VOSK_DIR / VOSK_MODEL
    if target.exists():
        return target
    VOSK_DIR.mkdir(parents=True, exist_ok=True)
    print(f"downloading {URL}")
    with urllib.request.urlopen(URL) as r:
        zipfile.ZipFile(io.BytesIO(r.read())).extractall(VOSK_DIR)
    return target


def pack_for_web(model_dir: Path) -> None:
    """vosk-browser loads a .tar.gz whose top folder is named 'model'."""
    WEB_OUT.parent.mkdir(parents=True, exist_ok=True)
    if not WEB_OUT.exists():
        with tarfile.open(WEB_OUT, "w:gz") as tar:
            tar.add(model_dir, arcname="model")
    print(f"wrote {WEB_OUT} ({WEB_OUT.stat().st_size // 1_000_000} MB)")
    for name in WEB_EMBED_FILES:
        out = WEB_MODELS / WEB_EMBED / name
        if out.exists():
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(f"https://huggingface.co/{WEB_EMBED}/resolve/main/{name}", out)
        print(f"wrote {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", action="store_true")
    args = ap.parse_args()
    model_dir = fetch()
    print(f"model at {model_dir}")
    if args.web:
        pack_for_web(model_dir)


if __name__ == "__main__":
    main()
