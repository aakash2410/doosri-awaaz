# Teacher test kit

For 2-3 short tests between 29 and 31 October. Each test takes about 45 minutes. The build deck has a slide waiting for these results; the judges score "proof of testing and refinement based on user input" inside the 35% criterion, so honest small numbers are worth more than none.

## Who

- 2-3 teachers who teach two or more grades in one room (Class 1-3), ideally one Marathi-speaking.
- One Marathi speaker (can be the same teacher) to review the pack's home-language lines.
- If a classroom visit is not possible, run it over a video call: share the screen, the teacher listens and tells you which button to press or what children would say.

## Before

1. Run the app (`uvicorn doosri.server:app`) or open the deployed link. Open the approved pack in the classroom simulator once while online.
2. Print this page or copy the tally sheet into a notes app.
3. Ask permission to take notes. Do not record children. Do not write children's names.

## Part A: pack review (10 min, Marathi speaker)

Open the pack's Review page. Ask them to read every Marathi line aloud.

| Question | Their answer |
|---|---|
| Which lines sound unnatural or bookish? (note the exact words) | |
| Any word a Class 2 child at home would not use? | |
| Any question with more than one fair answer? | |
| Would you approve this pack? What would you change first? | |

Make their edits in the Review page and approve the pack in their name. Keep a copy of the before/after lines: this is direct evidence of refinement.

## Part B: session (15-20 min, teacher, with children if possible)

Teacher presses Start and goes back to teaching the other grade. You observe.

Tally sheet (one row per item):

| Item | On task? (most / some / few children) | Answered by (voice / button) | Device heard right? (yes / re-prompt / wrong) | Notes |
|---|---|---|---|---|
| i1 | | | | |
| i2 | | | | |
| i3 | | | | |
| i4 | | | | |
| i5 | | | | |

Also note:

- Minutes the teacher spent on the unattended grade during the session (target: under 1).
- Times children were stuck or the device misheard.
- Questions children asked, and what the device did.
- After the session: download the session log (shown on screen) and save it.

## Part C: debrief and survey (10 min, teacher)

Play the spoken summary, then show the next-day note.

1. How useful would this be for your class, 1 (not at all) to 5 (very)? ___
2. Could you start it on your own tomorrow without help? Yes / No / With help
3. Did the summary tell you something you would act on? Which item?
4. What is the one thing you would change?
5. Anything that worried you (children, language, data)?

Write down two or three sentences in the teacher's own words.

## After each test

Send the team (WhatsApp is fine):

- The filled tally sheet and survey.
- The session log JSON.
- The before/after lines from the pack review.
- The one change the teacher asked for.

We change one concrete thing from the feedback before submission and say so in the deck and video: "Teacher X said ... so we changed ...".
