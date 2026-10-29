# Teacher call guide

One 40-minute video call with a teacher who teaches two or more grades in one room (Class 1-3), ideally a Marathi speaker. You walk them through the web app, they react as if it were their classroom, and you write down what they say. The judges score "proof of testing and refinement based on user input", so their exact words and one change we make from them matter more than a polished demo.

## Before the call

1. Start the app (`uvicorn doosri.server:app --port 8000`) or use the deployed link. Open the pack `class2-market-numbers` in the classroom simulator once, so models and audio are loaded.
2. In the simulator, untick **Use microphone**: the teacher's voice over the call will not reach your mic reliably. You will press colour buttons for answers and type children's questions.
3. Share a **browser tab with audio** (Google Meet: "Share a tab" and "Also share tab audio"; Zoom: tick "Share sound"). Check the teacher can hear the Marathi lines.
4. At the start, ask permission to take notes and to quote them in the submission (name or anonymous, their choice). Do not record children or collect their names.

## Part 1: their day (8 min)

Ask, and write their answers in their words:

1. Which grades do you teach together, and how many children in each?
2. Which languages do the children speak at home? Which language do you teach in?
3. While you teach one grade, what does the other grade do? How long?
4. What goes wrong in that time?
5. What have you tried for it (worksheets, older children helping, phone videos)?
6. Is there a phone, speaker or device in the classroom? Electricity? Network?

## Part 2: walkthrough (20 min)

Say what each step is for in one sentence, then let them react.

| Step | Show | Ask |
|---|---|---|
| Prepare | Prepare page with this week's lesson (do not press Draft; show the pack already drafted) | Would you write or paste a lesson like this? How often? |
| Review | Review page: Claude's scores and flagged phrases, then the Marathi and Hindi lines | Read the Marathi lines aloud. Which sound unnatural or bookish? Any word a Class 2 child would not use? Any question with two fair answers? |
| Classroom | Start the session. Let items 1-2 play. Ask what children would say; press that colour. Get one wrong on purpose to show the hint | Would children follow this? Is the pace right? Is the mix of Marathi then Hindi right? |
| Questions | Hold "Hold to ask" and type one question from the pack (e.g. "एक जास्त म्हणजे काय?") and one it must not answer | Is "ask your teacher" the right response for the second? What would children actually ask? |
| Debrief | Let the session finish; play the spoken summary. Open Tomorrow's note | Would you act on this? What is missing? |

If they suggest edits to the Marathi lines, make them in the Review page during the call and re-approve. Write down each line before and after: this is the clearest evidence of refinement.

## Part 3: feedback (10 min)

1. How useful would this be for your class, 1 (not at all) to 5 (very)? ___
2. Could you start it on your own tomorrow without help? Yes / No / With help
3. What would stop you using it?
4. What is the one thing you would change first?
5. Anything that worries you (children, language, data, cost)?

Close by reading back the one change you heard, and check you understood it.

## After the call

Send the team:

- Part 1 answers and two or three sentences in the teacher's own words.
- Before/after lines from the Review page, if any.
- The survey answers.
- The one change they asked for.

We make that change before submission and say so in the deck and video: "A teacher of Class 1-3 told us ... so we changed ...".
