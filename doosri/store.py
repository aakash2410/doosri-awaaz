"""Packs live on disk as packs/<id>/pack.json plus packs/<id>/audio/*.mp3."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from .checks import blocking, check_pack
from .schema import Pack, Review

ROOT = Path(os.environ.get("DOOSRI_PACKS", Path(__file__).resolve().parent.parent / "packs"))
MIN_SCORE = 3


class ApprovalError(ValueError):
    pass


def pack_dir(pack_id: str) -> Path:
    if "/" in pack_id or ".." in pack_id:
        raise ValueError("bad pack id")
    return ROOT / pack_id


def save(pack: Pack) -> Path:
    d = pack_dir(pack.id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "pack.json").write_text(json.dumps(pack.model_dump(), ensure_ascii=False, indent=2))
    return d


def load(pack_id: str) -> Pack:
    return Pack.model_validate_json((pack_dir(pack_id) / "pack.json").read_text())


def list_packs() -> List[Pack]:
    if not ROOT.exists():
        return []
    return [load(p.name) for p in sorted(ROOT.iterdir()) if (p / "pack.json").exists()]


def approve(pack: Pack, *, reviewer: str, role: str, notes: str = "") -> Pack:
    """A person signs off a pack. Check errors always block; a low rubric score
    blocks unless the reviewer writes a note saying what they fixed or why it is fine."""
    if not reviewer.strip():
        raise ApprovalError("reviewer name is required")
    if blocking(check_pack(pack)):
        raise ApprovalError("fix the check errors before approving")
    if pack.rubric is None:
        raise ApprovalError("pack has not been scored")
    low = [k for k, v in pack.rubric.model_dump().items() if isinstance(v, int) and v < MIN_SCORE]
    if low and not notes.strip():
        raise ApprovalError(f"low rubric scores ({', '.join(low)}); add a note on what you fixed")
    pack.status = "approved"
    pack.review = Review(
        reviewer=reviewer.strip(),
        role=role.strip(),
        notes=notes.strip(),
        approved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    return pack
