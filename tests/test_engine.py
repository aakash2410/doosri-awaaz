import json
from pathlib import Path

import pytest

from doosri import store
from doosri.checks import blocking, check_pack
from doosri.report import HardItem, TeacherNote, check_note
from doosri.schema import Pack
from engine.io import TextIO
from engine.match import Embedder, QuestionRouter, judge_voice
from engine.session import Session

FIXTURE = Path(__file__).parent / "fixtures" / "pack.json"


@pytest.fixture
def pack() -> Pack:
    return Pack.model_validate_json(FIXTURE.read_text())


_EMBED = None


def embedder():
    global _EMBED
    _EMBED = _EMBED or Embedder()
    return _EMBED


def run(pack, script):
    io = TextIO(iter(script), quiet=True)
    s = Session(pack, io, QuestionRouter(pack, embedder()))
    return s, s.run(), io


def test_fixture_passes_checks(pack):
    assert not blocking(check_pack(pack))


def test_check_catches_bad_correct_colour(pack):
    pack.items[0].correct = "yellow"
    assert blocking(check_pack(pack))


def test_check_catches_latin_script(pack):
    pack.items[0].hint.home = "count on fingers"
    assert any("Devanagari" in f.message for f in check_pack(pack))


def test_draft_pack_cannot_run(pack):
    pack.status = "draft"
    with pytest.raises(ValueError):
        Session(pack, TextIO(iter([]), quiet=True))


def test_voice_matching_in_both_languages(pack):
    i1 = pack.items[0]
    assert judge_voice(i1, "पाच", 0.9).result == "correct"  # Marathi
    assert judge_voice(i1, "पाँच", 0.9).result == "correct"  # Hindi
    assert judge_voice(i1, "५", 0.9).result == "correct"  # Devanagari digit
    assert judge_voice(i1, "चार", 0.9).result == "wrong"
    assert judge_voice(i1, "लाल", 0.9).result == "wrong"  # colour of a wrong choice
    assert judge_voice(i1, "पाच", 0.3).result == "unclear"  # low confidence never marks wrong
    assert judge_voice(i1, "बकरी", 0.9).result == "unclear"
    i2 = pack.items[1]
    assert judge_voice(i2, "छह", 0.9).result == "wrong"  # one word of the wrong label "सहा / छह"


def test_full_session_log(pack):
    script = [
        "b",            # i1 right first try by button
        "r", "g",       # i2 wrong (red is not a choice -> still wrong colour), then right
        "say:कुछ", "say:सात",  # i3 unclear then right by voice
        "ask:बकरी क्या खाती है", "ask:आकाश नीला क्यों है", "",
    ]
    s, log, io = run(pack, script)
    i1, i2, i3 = log.items
    assert i1.first_try_correct and i1.answered_by == ["button"]
    assert i2.correct and not i2.first_try_correct and i2.wrong_tries == 1
    assert i3.first_try_correct and i3.unclear == 1 and i3.answered_by == ["voice"]
    assert [q["faq_id"] for q in log.questions] == ["q1", None]
    said = [t for _, t in io.spoken]
    assert pack.faq[0].answer.home in said and pack.ask_teacher.home in said
    summary = s.teacher_summary()
    assert "3 में से 2 सवाल पहली बार में सही हुए।" in summary
    assert pack.items[1].skill_spoken in summary
    assert json.dumps(log.to_dict(), ensure_ascii=False)  # serialisable, no audio


def test_reveal_after_two_wrong(pack):
    s, log, io = run(pack, ["r", "r", "g", "r", ""])
    assert not log.items[0].correct and log.items[0].wrong_tries == 2
    assert pack.items[0].reveal.school in [t for _, t in io.spoken]


def test_silence_moves_on_after_reprompts(pack):
    s, log, io = run(pack, ["", "", "", "g", "r", ""])
    assert log.items[0].unclear == 3 and not log.items[0].correct


def test_note_check(pack):
    _, log, _ = run(pack, ["b", "r", "g", "say:सात", "ask:आकाश नीला क्यों है", ""])
    log = log.to_dict()
    good = TeacherNote(headline="x", found_hard=[HardItem(item_id="i2", what_happened="second try")],
                       suggested_next=["x"], questions_for_you=["आकाश नीला क्यों है"],
                       first_try_correct=2, total_items=3)
    assert check_note(good, log) == []
    bad = good.model_copy(update={"first_try_correct": 3,
                                  "found_hard": [HardItem(item_id="i1", what_happened="x")],
                                  "questions_for_you": ["made up"]})
    assert len(check_note(bad, log)) == 3


def test_approval_gate(pack, tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path)
    pack.status, pack.review = "draft", None
    with pytest.raises(store.ApprovalError):
        store.approve(pack, reviewer="", role="teacher")
    pack.rubric.home_language_naturalness = 2
    with pytest.raises(store.ApprovalError):
        store.approve(pack, reviewer="Asha", role="local speaker")
    store.approve(pack, reviewer="Asha", role="local speaker", notes="fixed i1 hint wording")
    assert pack.status == "approved"
    store.save(pack)
    assert store.load(pack.id).review.reviewer == "Asha"


@pytest.mark.parametrize("question,expected", [
    ("बकरी क्या खाती है", "q1"),
    ("शेळी काय खाते", "q1"),
    ("बकरी को क्या पसंद है खाने में", "q1"),
    ("कुल का मतलब", "q2"),
    ("बकरी कहाँ सोती है", None),   # near a FAQ, not answered by it
    ("बकरी क्या पीती है", None),
    ("कुल कितनी बकरियाँ हैं", None),
    ("आकाश नीला क्यों है", None),   # unrelated
])
def test_question_gates(pack, question, expected):
    assert QuestionRouter(pack, embedder()).route(question).faq_id == expected
