"""Prepare stage (online, before class): Claude drafts an activity pack from the
week's lesson, then a second Claude call scores the draft against a rubric.
Nothing reaches a classroom until a person approves it (see review.py)."""

from __future__ import annotations

import json
import re
import uuid

from .checks import check_pack
from .claude import structured
from .schema import Pack, PackDraft, Rubric

LANGUAGES = {"mr": "Marathi", "hi": "Hindi", "bhb": "Bhili", "gon": "Gondi"}

DRAFT_SYSTEM = """You write audio activity packs for Doosri Awaaz, a small speaker device used in multigrade government primary classrooms in India. While the teacher teaches one grade, the device runs a 15-20 minute oral activity for the other grade: 20-30 children aged 6-9 sitting in a circle around it. There is no screen. Children answer together, aloud or by pressing one of four large colour buttons (red, blue, green, yellow).

Every line is spoken twice: first in the children's home language, then in the school language, so the home language carries the meaning and the school language is learnt alongside it. Many of these children are first-generation learners who do not yet follow the school language well.

How to write:
- Practise only what the source lesson teaches. Do not introduce new concepts.
- Short sentences a 6-year-old can follow when heard once. Everyday words from village life (rotis, goats, mangoes, the well, the bus), never city or brand references.
- The home-language line must be natural spoken home language, not a word-for-word translation of the school-language line. Use Devanagari script for both.
- Each item has exactly one correct answer, and every choice is read aloud with its colour so children who cannot read can still answer by button.
- accepted_spoken lists the short words children would actually shout for the correct answer: the home-language word, the school-language word, and digits if it is a number. Keep each entry to 1-2 words.
- hint nudges without giving the answer away. reveal states the answer and the reason in one sentence. praise is warm and short.
- faq covers 3-5 questions children are likely to ask about this lesson; answers use only the lesson. For each, near_misses are questions a child might ask that sound close but that this answer does not answer (e.g. 'what does a goat drink?' next to 'what does a goat eat?'); the device uses them to refuse rather than give a wrong answer. ask_teacher tells children kindly to keep their question for the teacher.
- Item ids are i1, i2, ...; FAQ ids are q1, q2, ...."""

SCORE_SYSTEM = """You review audio activity packs before a teacher or local speaker checks them. You did not write the pack. Score it strictly against the source lesson; a reviewer relies on your issues list to know what to fix.

Score each criterion from 1 (unusable) to 5 (ready):
- curriculum_alignment: every item practises something the source lesson teaches, at the stated grade.
- age_appropriateness: children aged 6-9 can follow each line when heard once; one idea per sentence.
- home_language_naturalness: the home-language lines read as natural speech, not as literal translations of the school-language lines. If you are unsure of a word, lower the score and quote the phrase in phrases_to_check.
- answer_unambiguity: each item has exactly one defensible correct answer; choices are clearly different when heard; accepted_spoken covers what children would say for the correct answer and nothing that would also fit a wrong choice.
- safety_and_culture: nothing frightening, shaming, or out of place for a rural Indian classroom; no gender, caste or religious stereotypes.

issues: concrete problems, each starting with the item id or section name. Leave empty if there are none; do not invent problems."""


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40] or "pack"


def draft_pack(
    source_text: str,
    *,
    grade: int,
    subject: str,
    source_ref: str,
    home_language: str = "mr",
    school_language: str = "hi",
    n_items: int = 5,
) -> Pack:
    home, school = LANGUAGES[home_language], LANGUAGES[school_language]
    prompt = (
        f"Write an activity pack for Class {grade} {subject}.\n"
        f"Home language: {home}. School language: {school}.\n"
        f"Number of items: {n_items}. Include a short story (4-6 sentences) that the items refer to "
        f"if the lesson suits one.\n"
        f"Source reference: {source_ref}\n\n"
        f"<source_lesson>\n{source_text.strip()}\n</source_lesson>"
    )
    draft = structured(system=DRAFT_SYSTEM, prompt=prompt, schema=PackDraft, effort="high")
    pack = Pack(
        id=f"{_slug(draft.title)}-{uuid.uuid4().hex[:6]}",
        home_language=home_language,
        school_language=school_language,
        **draft.model_dump(),
    )
    # Keep grade and subject as the teacher asked, whatever the draft says.
    pack.grade, pack.subject, pack.source_ref = grade, subject, source_ref
    return pack


def score_pack(pack: Pack, source_text: str) -> Rubric:
    body = pack.model_dump(exclude={"rubric", "review", "status"})
    prompt = (
        f"Home language: {LANGUAGES.get(pack.home_language, pack.home_language)}. "
        f"School language: {LANGUAGES.get(pack.school_language, pack.school_language)}.\n\n"
        f"<source_lesson>\n{source_text.strip()}\n</source_lesson>\n\n"
        f"<pack>\n{json.dumps(body, ensure_ascii=False, indent=1)}\n</pack>"
    )
    return structured(system=SCORE_SYSTEM, prompt=prompt, schema=Rubric, effort="high", max_tokens=16000)


def prepare(source_text: str, **kwargs) -> tuple[Pack, list]:
    """Draft, score and check a pack. Returns the draft pack and its check findings."""
    pack = draft_pack(source_text, **kwargs)
    pack.rubric = score_pack(pack, source_text)
    return pack, check_pack(pack)
