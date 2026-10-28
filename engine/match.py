"""Offline answer matching and question routing. No network calls.

Answers: speech recognition is restricted to the words a pack expects, then
matched here. Anything uncertain is "unclear" and triggers a re-prompt, so a
child is never marked wrong on a recognition error.

Questions: two gates before the device answers, both using a small
multilingual sentence-embedding model on the device.
  Gate 1: the question must be close to one of the ways the pack says children
          ask a FAQ (similarity >= SIMILARITY).
  Gate 2: it must be closer to those than to the FAQ's near-miss questions,
          which Claude writes at prep time, by at least MARGIN.
Otherwise the device says "ask your teacher". The model only selects a
reviewed answer; it never writes the words children hear."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional

from doosri.phrases import COLOUR_WORDS
from doosri.schema import Item, Pack

MIN_CONFIDENCE = 0.6

DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).translate(DIGITS).lower()
    text = re.sub(r"[।॥.,!?;:\"'()\-]", " ", text)
    return " ".join(text.split())


def tokens(text: str) -> List[str]:
    return normalize(text).split()


@dataclass
class Verdict:
    result: str  # "correct" | "wrong" | "unclear"
    colour: Optional[str] = None


def judge_button(item: Item, colour: str) -> Verdict:
    return Verdict("correct" if colour == item.correct else "wrong", colour)


def judge_voice(item: Item, text: str, confidence: float) -> Verdict:
    """Match a recognised utterance against the item. Wrong only when the
    child clearly said another choice; otherwise unclear."""
    said = set(tokens(text))
    if not said or confidence < MIN_CONFIDENCE:
        return Verdict("unclear")
    accepted = {normalize(w) for w in item.accepted_spoken}
    if said & accepted or any(a in normalize(text) for a in accepted if " " in a):
        return Verdict("correct", item.correct)
    right = next(c for c in item.choices if c.colour == item.correct)
    right_words = accepted | set(tokens(right.label.home)) | set(tokens(right.label.school))
    for ch in item.choices:
        if ch.colour == item.correct:
            continue
        names = {normalize(w) for w in COLOUR_WORDS[ch.colour].values()}
        label = set(tokens(ch.label.home)) | set(tokens(ch.label.school))
        if said & names or said & (label - right_words):
            return Verdict("wrong", ch.colour)
    # A colour name for the correct choice also counts.
    if said & {normalize(w) for w in COLOUR_WORDS[item.correct].values()}:
        return Verdict("correct", item.correct)
    return Verdict("unclear")


def grammar_words(item: Item) -> List[str]:
    """Words the recogniser may output for this item."""
    words = set()
    for w in item.accepted_spoken:
        words.update(tokens(w))
    for ch in item.choices:
        words.update(tokens(ch.label.home) + tokens(ch.label.school))
        words.update(COLOUR_WORDS[ch.colour].values())
    return sorted(words)


# ---------- question routing ----------

EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
SIMILARITY = 0.6
MARGIN = 0.05


@dataclass
class Route:
    faq_id: Optional[str]
    score: float  # similarity to the best matching FAQ phrasing
    gate: str  # "answered", "gate1" (nothing close), "gate2" (too close to a near miss)


class Embedder:
    def __init__(self, model: str = EMBED_MODEL):
        from fastembed import TextEmbedding

        self.model = TextEmbedding(model)

    def __call__(self, texts: List[str]):
        import numpy as np

        v = np.array(list(self.model.embed([normalize(t) for t in texts])))
        return v / np.linalg.norm(v, axis=-1, keepdims=True)


class QuestionRouter:
    def __init__(self, pack: Pack, embed: Optional[Embedder] = None):
        self.embed = embed or Embedder()
        self.faq = [(q.id, self.embed(q.questions), self.embed(q.near_misses) if q.near_misses else None)
                    for q in pack.faq]

    def route(self, question: str) -> Route:
        v = self.embed([question])[0]
        best = Route(None, 0.0, "gate1")
        for fid, pos, neg in self.faq:
            ps = float((pos @ v).max())
            ns = float((neg @ v).max()) if neg is not None else 0.0
            if ps < SIMILARITY or ps <= best.score:
                continue
            best = Route(fid, ps, "answered") if ps - ns >= MARGIN else Route(None, ps, "gate2")
        return best
