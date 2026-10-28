"""Run an approved pack in class.

  python -m engine.run --pack <id>               laptop speaker + mic
  python -m engine.run --pack <id> --io text     type answers in the terminal
  python -m engine.run --pack <id> --io sunosutra  on the device

Writes the group-level session log to logs/<pack>-<time>.json.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

from doosri import store

from .io import AudioBank, LaptopIO, SunoSutraIO, TextIO
from .match import QuestionRouter
from .session import Session

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", required=True)
    ap.add_argument("--io", choices=["laptop", "text", "sunosutra"], default="laptop")
    ap.add_argument("--no-questions", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    pack = store.load(args.pack)
    bank = AudioBank(store.pack_dir(pack.id))
    if args.io == "text":
        io = TextIO()
    elif args.io == "laptop":
        io = LaptopIO(bank)
    else:
        from pocketinfer.boards.base import Board  # only present on the device

        io = SunoSutraIO(Board.get_board(), bank)

    session = Session(pack, io, QuestionRouter(pack))
    log = session.run(ask_questions=not args.no_questions)
    session.debrief()

    LOG_DIR.mkdir(exist_ok=True)
    out = LOG_DIR / f"{pack.id}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(log.to_dict(), ensure_ascii=False, indent=2))
    print(f"\nsession log: {out}")


if __name__ == "__main__":
    main()
