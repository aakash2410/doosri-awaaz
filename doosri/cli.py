"""Command line for the online stages.

  python -m doosri.cli prepare content/lesson.txt --grade 2 --subject Mathematics --ref "..." [--home mr]
  python -m doosri.cli show <pack>
  python -m doosri.cli approve <pack> --reviewer "Name" --role teacher [--notes "..."]
  python -m doosri.cli note <pack> logs/<session>.json [--language Hindi]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import store
from .audio import render_pack_audio
from .checks import check_pack
from .prepare import prepare
from .report import check_note, write_note


def _print_findings(pack) -> None:
    r = pack.rubric
    if r:
        scores = {k: v for k, v in r.model_dump().items() if isinstance(v, int)}
        print("rubric:", ", ".join(f"{k}={v}" for k, v in scores.items()))
        for i in r.issues:
            print("  issue:", i)
        for ph in r.phrases_to_check:
            print("  check phrase:", ph)
    for f in check_pack(pack):
        print(f"  {f.level}: {f.where}: {f.message}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="doosri")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("source", type=Path)
    p.add_argument("--grade", type=int, required=True)
    p.add_argument("--subject", required=True)
    p.add_argument("--ref", required=True)
    p.add_argument("--home", default="mr")
    p.add_argument("--items", type=int, default=5)
    p.add_argument("--id", help="pack id to use instead of a generated one")
    s = sub.add_parser("show")
    s.add_argument("pack")
    a = sub.add_parser("approve")
    a.add_argument("pack")
    a.add_argument("--reviewer", required=True)
    a.add_argument("--role", required=True)
    a.add_argument("--notes", default="")
    n = sub.add_parser("note")
    n.add_argument("pack")
    n.add_argument("log", type=Path)
    n.add_argument("--language", default="Hindi")
    args = ap.parse_args()

    if args.cmd == "prepare":
        text = args.source.read_text()
        pack, _ = prepare(text, grade=args.grade, subject=args.subject, source_ref=args.ref,
                          home_language=args.home, n_items=args.items)
        if args.id:
            pack.id = args.id
        d = store.save(pack)
        (d / "source.txt").write_text(text)
        print(f"draft pack: {pack.id}  ({d / 'pack.json'})")
        _print_findings(pack)
    elif args.cmd == "show":
        pack = store.load(args.pack)
        print(json.dumps(pack.model_dump(), ensure_ascii=False, indent=1))
        _print_findings(pack)
    elif args.cmd == "approve":
        pack = store.approve(store.load(args.pack), reviewer=args.reviewer, role=args.role, notes=args.notes)
        out = render_pack_audio(pack)
        store.save(pack)
        print(f"approved; audio in {out}")
    elif args.cmd == "note":
        pack, log = store.load(args.pack), json.loads(args.log.read_text())
        note = write_note(log, pack, args.language)
        print(json.dumps(note.model_dump(), ensure_ascii=False, indent=1))
        problems = check_note(note, log)
        print("faithfulness check:", "pass" if not problems else problems)


if __name__ == "__main__":
    main()
