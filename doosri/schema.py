"""Activity pack format shared by the prepare pipeline, the review app, the
browser classroom simulator and the device engine.

A pack is one 15-20 minute session for the grade the teacher is not teaching.
Every line a child hears exists in two languages: the home language (spoken
first) and the school language (spoken second, to bridge).
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Colour = Literal["red", "blue", "green", "yellow"]
COLOURS: tuple[str, ...] = ("red", "blue", "green", "yellow")


class Line(BaseModel):
    """One spoken line, home language first, then school language."""

    home: str = Field(description="Line in the child's home language, Devanagari script")
    school: str = Field(description="Same line in the school language (Hindi), Devanagari script")


class Choice(BaseModel):
    colour: Colour
    label: Line = Field(description="What this colour button stands for, spoken aloud")


class Item(BaseModel):
    id: str = Field(description="Short stable id, e.g. 'i1'")
    skill: str = Field(description="Skill practised, in plain English for the teacher, e.g. 'counting back from 20'")
    skill_spoken: str = Field(
        description="The same skill in the school language, 2-5 words, spoken to the teacher, e.g. '20 से उल्टी गिनती'"
    )
    prompt: Line = Field(description="Question or instruction the device speaks")
    choices: List[Choice] = Field(description="2 to 4 colour-button answers; each colour used at most once")
    correct: Colour = Field(description="Colour of the one correct choice")
    accepted_spoken: List[str] = Field(
        description="Words a child may say for the correct answer, in both languages and as digits, e.g. ['तीन', 'तीन', '3']"
    )
    hint: Line = Field(description="Re-prompt after a wrong or unclear answer; nudges without giving the answer")
    reveal: Line = Field(description="Says the correct answer and why, used after two tries")
    praise: Line = Field(description="Short praise for a correct answer")


class FAQ(BaseModel):
    id: str = Field(description="Short stable id, e.g. 'q1'")
    questions: List[str] = Field(description="3-5 ways a child might ask this, in both languages")
    near_misses: List[str] = Field(
        description="3-5 questions that sound similar but that this answer does NOT answer, in both languages"
    )
    answer: Line = Field(description="Answer, using only what the lesson teaches")


class Rubric(BaseModel):
    """Scores written by a second, independent Claude call."""

    curriculum_alignment: int = Field(ge=1, le=5)
    age_appropriateness: int = Field(ge=1, le=5)
    home_language_naturalness: int = Field(ge=1, le=5)
    answer_unambiguity: int = Field(ge=1, le=5)
    safety_and_culture: int = Field(ge=1, le=5)
    issues: List[str] = Field(description="Concrete problems a reviewer must fix, each naming the item id")
    phrases_to_check: List[str] = Field(
        description="Home-language phrases a native speaker should confirm, quoted exactly"
    )


class Review(BaseModel):
    reviewer: str
    role: str = Field(description="e.g. 'teacher', 'local speaker'")
    notes: str = ""
    approved_at: str


class Pack(BaseModel):
    id: str
    title: str
    grade: int = Field(ge=1, le=3)
    subject: str
    source_ref: str = Field(description="Lesson the pack is drawn from, e.g. 'NCERT Joyful Mathematics Class 2, Ch 5'")
    home_language: str = Field(description="BCP-47 code, e.g. 'mr'")
    school_language: str = Field(description="BCP-47 code, e.g. 'hi'")
    intro: Line
    story: Optional[Line] = Field(default=None, description="Optional short story (4-6 sentences) the items refer to")
    items: List[Item]
    faq: List[FAQ]
    ask_teacher: Line = Field(description="Said when a child's question is outside the pack: ask your teacher")
    closing: Line
    status: Literal["draft", "approved"] = "draft"
    rubric: Optional[Rubric] = None
    review: Optional[Review] = None


class PackDraft(BaseModel):
    """What Claude returns when drafting. id, status, rubric and review are set by code."""

    title: str
    grade: int
    subject: str
    source_ref: str
    intro: Line
    story: Optional[Line]
    items: List[Item]
    faq: List[FAQ]
    ask_teacher: Line
    closing: Line
