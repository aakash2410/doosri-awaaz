"""Fixed lines the session engine speaks in every pack. Written by the team;
a native speaker should confirm the home-language lines before field use.

Lines keyed 'teacher_*' are spoken to the teacher in the school language only.
"""

from __future__ import annotations

from typing import Dict

PHRASES: Dict[str, Dict[str, str]] = {
    "answer_now": {
        "mr": "आता उत्तर सांगा, किंवा रंगाचे बटण दाबा.",
        "hi": "अब जवाब बोलो, या रंग वाला बटन दबाओ।",
    },
    "not_heard": {
        "mr": "मला नीट ऐकू आले नाही. पुन्हा एकदा, सगळे मिळून.",
        "hi": "मुझे ठीक से सुनाई नहीं दिया। एक बार फिर, सब मिलकर।",
    },
    "try_again": {
        "mr": "अजून एकदा विचार करा.",
        "hi": "एक बार और सोचो।",
    },
    "ask_prompt": {
        "mr": "तुमचा प्रश्न विचारा.",
        "hi": "अपना सवाल पूछो।",
    },
    "next": {
        "mr": "चला, पुढचा प्रश्न.",
        "hi": "चलो, अगला सवाल।",
    },
}

COLOUR_WORDS: Dict[str, Dict[str, str]] = {
    "red": {"mr": "लाल", "hi": "लाल"},
    "blue": {"mr": "निळा", "hi": "नीला"},
    "green": {"mr": "हिरवा", "hi": "हरा"},
    "yellow": {"mr": "पिवळा", "hi": "पीला"},
}

TEACHER_PHRASES: Dict[str, str] = {
    "teacher_done": "कक्षा का अभ्यास पूरा हुआ।",
    "teacher_hard": "बच्चों को यह कठिन लगा:",
    "teacher_all_good": "सभी सवाल ठीक रहे।",
    "teacher_questions": "बच्चों ने कुछ सवाल पूछे, जो आपके लिए रखे हैं।",
}


def teacher_score(n: int, m: int) -> str:
    return f"{m} में से {n} सवाल पहली बार में सही हुए।"
