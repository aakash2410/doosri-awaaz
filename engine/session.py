"""The classroom session: plays an approved pack to a group, takes answers by
voice or colour button, and keeps a group-level log. Runs fully offline.

The log holds counts and timings per item plus the text of questions children
asked. It holds no names and no audio."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import List, Optional, Protocol

from doosri.phrases import COLOUR_WORDS, PHRASES, TEACHER_PHRASES, teacher_score
from doosri.schema import Item, Line, Pack

from .match import QuestionRouter, grammar_words, judge_button, judge_voice

MAX_TRIES = 2  # wrong answers before the device reveals the answer
MAX_UNCLEAR = 2  # re-prompts for unclear speech before moving on
LISTEN_SECONDS = 8
MAX_QUESTIONS = 3


@dataclass
class Heard:
    kind: str  # "button" | "voice" | "none"
    colour: Optional[str] = None
    text: str = ""
    confidence: float = 0.0


class ClassroomIO(Protocol):
    def play(self, lang: str, text: str) -> None: ...
    def listen_answer(self, words: List[str], seconds: float) -> Heard: ...
    def listen_question(self, seconds: float) -> Optional[str]: ...
    def show(self, text: str) -> None: ...


@dataclass
class ItemLog:
    id: str
    skill: str
    first_try_correct: bool = False
    correct: bool = False
    wrong_tries: int = 0
    unclear: int = 0
    answered_by: List[str] = field(default_factory=list)
    seconds: float = 0.0


@dataclass
class SessionLog:
    pack_id: str
    pack_title: str
    grade: int
    started_at: float
    ended_at: float = 0.0
    items: List[ItemLog] = field(default_factory=list)
    questions: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class Session:
    def __init__(self, pack: Pack, io: ClassroomIO, router: Optional[QuestionRouter] = None):
        if pack.status != "approved":
            raise ValueError("only approved packs can run in a classroom")
        self.pack, self.io = pack, io
        self.router = router or QuestionRouter(pack)
        self.home, self.school = pack.home_language, pack.school_language
        self.log = SessionLog(pack.id, pack.title, pack.grade, time.time())

    # --- speaking helpers ---
    def say(self, line: Line) -> None:
        self.io.play(self.home, line.home)
        self.io.play(self.school, line.school)

    def say_phrase(self, key: str) -> None:
        self.io.play(self.home, PHRASES[key][self.home])
        self.io.play(self.school, PHRASES[key][self.school])

    def say_choices(self, item: Item) -> None:
        for lang, side in ((self.home, "home"), (self.school, "school")):
            for ch in item.choices:
                self.io.play(lang, COLOUR_WORDS[ch.colour][lang])
                self.io.play(lang, getattr(ch.label, side))

    # --- flow ---
    def run(self, ask_questions: bool = True) -> SessionLog:
        p = self.pack
        self.io.show(p.title)
        self.say(p.intro)
        if p.story:
            self.say(p.story)
        for n, item in enumerate(p.items, 1):
            self.io.show(f"{n}/{len(p.items)}")
            self.log.items.append(self.run_item(item))
            if n < len(p.items):
                self.say_phrase("next")
        if ask_questions:
            self.run_questions()
        self.say(p.closing)
        self.log.ended_at = time.time()
        return self.log

    def run_item(self, item: Item) -> ItemLog:
        rec = ItemLog(item.id, item.skill)
        t0 = time.time()
        self.say(item.prompt)
        self.say_choices(item)
        self.say_phrase("answer_now")
        words = grammar_words(item)
        while True:
            heard = self.io.listen_answer(words, LISTEN_SECONDS)
            if heard.kind == "button" and heard.colour:
                verdict = judge_button(item, heard.colour)
            elif heard.kind == "voice":
                verdict = judge_voice(item, heard.text, heard.confidence)
            else:
                verdict = None
            if verdict is None or verdict.result == "unclear":
                rec.unclear += 1
                if rec.unclear > MAX_UNCLEAR:
                    self.say(item.reveal)
                    break
                self.say_phrase("not_heard")
                continue
            rec.answered_by.append(heard.kind)
            if verdict.result == "correct":
                rec.correct = True
                rec.first_try_correct = rec.wrong_tries == 0
                self.say(item.praise)
                break
            rec.wrong_tries += 1
            if rec.wrong_tries >= MAX_TRIES:
                self.say(item.reveal)
                break
            self.say(item.hint)
            self.say_phrase("try_again")
        rec.seconds = round(time.time() - t0, 1)
        return rec

    def run_questions(self) -> None:
        for _ in range(MAX_QUESTIONS):
            self.say_phrase("ask_prompt")
            q = self.io.listen_question(LISTEN_SECONDS)
            if not q:
                return
            route = self.router.route(q)
            self.log.questions.append({"text": q, "faq_id": route.faq_id, "gate": route.gate,
                                       "score": round(route.score, 2)})
            if route.faq_id:
                self.say(next(f.answer for f in self.pack.faq if f.id == route.faq_id))
            else:
                self.say(self.pack.ask_teacher)

    # --- debrief, spoken to the teacher in the school language ---
    def teacher_summary(self) -> List[str]:
        items = {it.id: it for it in self.pack.items}
        logs = self.log.items
        lines = [TEACHER_PHRASES["teacher_done"],
                 teacher_score(sum(r.first_try_correct for r in logs), len(self.pack.items))]
        hard = sorted((r for r in logs if not r.first_try_correct),
                      key=lambda r: (r.correct, -r.wrong_tries, -r.unclear))[:2]
        if hard:
            lines.append(TEACHER_PHRASES["teacher_hard"])
            lines += [items[r.id].skill_spoken for r in hard]
        else:
            lines.append(TEACHER_PHRASES["teacher_all_good"])
        if any(q["faq_id"] is None for q in self.log.questions):
            lines.append(TEACHER_PHRASES["teacher_questions"])
        return lines

    def debrief(self) -> None:
        for text in self.teacher_summary():
            self.io.play(self.school, text)
