"""Review stage (after school, optional sync): Claude turns a group-level
session log into a short next-day note for the teacher. A deterministic check
then confirms the note only names items and numbers that are in the log."""

from __future__ import annotations

import json
from typing import List

from pydantic import BaseModel, Field

from .claude import structured
from .schema import Pack


class HardItem(BaseModel):
    item_id: str
    what_happened: str = Field(description="One sentence citing the log, e.g. 'right only on the second try'")


class TeacherNote(BaseModel):
    headline: str = Field(description="One line, e.g. 'Class 2, story session: 4 of 5 right first time'")
    found_hard: List[HardItem] = Field(description="At most 2 items the group struggled with, worst first; empty if none")
    suggested_next: List[str] = Field(description="1-3 concrete things the teacher can do tomorrow in under 5 minutes each")
    questions_for_you: List[str] = Field(description="Children's questions the device could not answer, as asked")
    first_try_correct: int = Field(description="Count of items right on the first try, copied from the log")
    total_items: int


NOTE_SYSTEM = """You write a next-day note for a government primary school teacher who teaches two or three grades in one room. Yesterday, while the teacher taught one grade, a classroom audio device ran a short practice session for the other grade. You get the device's group-level log and the activity pack it ran.

The teacher reads this on a phone between classes. Write in simple {language}. Be specific and brief.
- Base every statement on the log. Do not guess at reasons the log does not show, and do not praise or blame individual children; the log has no names.
- An item is hard if the group was not right on the first try, needed re-prompts because the device could not hear an answer, or the device had to reveal the answer. Rank by how much trouble it caused.
- Suggestions use things a rural classroom has: stones, sticks, bead strings, fingers, the blackboard, a quick group game. Tie each suggestion to a hard item's skill. If nothing was hard, suggest moving on to the next lesson step.
- questions_for_you lists only questions whose faq_id is null, as the children asked them."""


def write_note(log: dict, pack: Pack, language: str = "Hindi") -> TeacherNote:
    items = [
        {"id": it.id, "skill": it.skill, "prompt": it.prompt.school,
         "correct_answer": next(c.label.school for c in it.choices if c.colour == it.correct)}
        for it in pack.items
    ]
    prompt = (
        f"Pack: {pack.title} (Class {pack.grade} {pack.subject}, {pack.source_ref})\n"
        f"<pack_items>\n{json.dumps(items, ensure_ascii=False, indent=1)}\n</pack_items>\n\n"
        f"<session_log>\n{json.dumps(log, ensure_ascii=False, indent=1)}\n</session_log>"
    )
    return structured(system=NOTE_SYSTEM.format(language=language), prompt=prompt,
                      schema=TeacherNote, effort="medium", max_tokens=8000)


def check_note(note: TeacherNote, log: dict) -> List[str]:
    """Problems where the note disagrees with the log. Empty means faithful."""
    problems = []
    logged = {it["id"]: it for it in log["items"]}
    ftc = sum(1 for it in log["items"] if it["first_try_correct"])
    if note.first_try_correct != ftc:
        problems.append(f"note says {note.first_try_correct} right first time; log says {ftc}")
    if note.total_items != len(log["items"]):
        problems.append(f"note says {note.total_items} items; log has {len(log['items'])}")
    for h in note.found_hard:
        if h.item_id not in logged:
            problems.append(f"note names item {h.item_id}, which is not in the log")
        elif logged[h.item_id]["first_try_correct"] and not logged[h.item_id]["unclear"]:
            problems.append(f"note calls {h.item_id} hard, but the log shows it right first time")
    unanswered = {q["text"] for q in log.get("questions", []) if q["faq_id"] is None}
    for q in note.questions_for_you:
        if q not in unanswered:
            problems.append(f"note lists a question the log does not have as unanswered: {q}")
    return problems
