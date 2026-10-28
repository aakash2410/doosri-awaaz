# Doosri Awaaz

Offline, home-language guided practice for the grade a multigrade teacher is not teaching.

In 50-80% of Indian government primary schools one teacher teaches two or three grades in one room, so each grade gets half the teacher's time or less. Doosri Awaaz ("a second voice") is a small classroom device that runs 15-20 minutes of guided oral practice for the unattended grade: home language first, then Hindi. Children answer together, aloud or with four colour buttons. The teacher starts it in under a minute and gets a 20-second spoken summary afterwards.

Built for the ShikshaNext x Anthropic AI for Foundational Learning Hackathon (Challenge: classroom complexity). Team: Aakash Sangani, Honey Agarwal, Sanika Parasnis.

## How it works

| Stage | What happens | AI | Network |
|---|---|---|---|
| Prepare | Claude drafts an activity pack from the week's lesson; a second Claude call scores it; code checks it | Claude Opus 5.5 | needed |
| Approve | A teacher or local speaker edits any line and approves; every approved line is voiced to audio | none | needed |
| In class | The device plays the pack, recognises answers, routes children's questions, keeps a group-level log | Vosk speech recognition, multilingual MiniLM embeddings, on device | **none** |
| After school | The teacher's phone syncs the log; Claude writes a next-day note; code checks it against the log | Claude Opus 5.5 | optional |

Where Claude is called, in code:

- [`doosri/prepare.py`](doosri/prepare.py) `draft_pack`: lesson to activity pack, structured output validated against [`doosri/schema.py`](doosri/schema.py)
- [`doosri/prepare.py`](doosri/prepare.py) `score_pack`: independent rubric score of the draft
- [`doosri/report.py`](doosri/report.py) `write_note`: session log to next-day note, then `check_note` compares it with the log
- [`doosri/claude.py`](doosri/claude.py): the one wrapper all three use (model, structured output, refusal fallback, error handling)

The classroom loop ([`engine/`](engine/), and its browser port in [`web/js/engine.js`](web/js/engine.js)) imports none of these and makes no network calls.

## Guardrails

- Children only hear lines a person approved. Approval is blocked by check errors, and by rubric scores below 3 unless the reviewer writes a note ([`doosri/store.py`](doosri/store.py)). The engine refuses to run a draft pack.
- No text is generated in class. Answers are matched against the item's expected words; questions are matched to approved FAQ answers or sent to the teacher.
- Speech recognition is restricted to each item's expected words. Low confidence or an unknown word means "I didn't hear, say it again", never a wrong mark.
- Two gates for questions ([`engine/match.py`](engine/match.py)): close enough to a known phrasing (similarity >= 0.6), and closer to it than to Claude-written near-miss questions (margin >= 0.05).
- No child audio is stored or leaves the device. The log has counts, timings and question text, no names.
- The next-day note is checked by code: every count, item and question must match the log.

## Run it

Requires Python 3.10+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-device.txt pytest
python -m engine.fetch_models --web          # offline speech + embedding models (~170 MB, once)
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env   # only Prepare and the next-day note need it
uvicorn doosri.server:app --port 8000
```

Open http://localhost:8000. Approved packs open in the classroom simulator, which runs speech recognition and question matching in the browser. After the first load, turn off Wi-Fi or stop the server: the session still runs.

### Command line

```bash
python -m doosri.cli prepare content/class2-numbers-market.txt --grade 2 --subject Mathematics \
  --ref "NCERT Class 2 numbers up to 20" --home mr --id class2-market-numbers
python -m doosri.cli approve class2-market-numbers --reviewer "Name" --role "local speaker"
python -m engine.run --pack class2-market-numbers              # laptop speaker + mic, keys r/b/g/y
python -m engine.run --pack class2-market-numbers --io text    # type answers
python -m doosri.cli note class2-market-numbers logs/<session>.json
```

### On a Suno Sutra device

The engine runs on the [Suno Sutra](https://github.com/currentai-org/suno-sutra-sw) reference hardware (Jetson Orin Nano) through its `pocketinfer` board object, as an add-on: no base file changes.

```bash
pip install -r requirements-device.txt
python -m engine.fetch_models
python -m engine.run --pack class2-market-numbers --io sunosutra
```

The four NeoKey buttons (IO expander messages `BA1`..`BD1`) are red, blue, green and yellow; holding the trigger button asks a question. Audio plays through the board's ALSA device with ffmpeg.

## Tests and evaluations

```bash
pytest                                   # engine flow, matching, gates, approval, note check
python -m evals.asr_eval <pack-id>       # answer recognition on synthetic voices
```

Results so far (synthetic adult voices, so an upper bound for children in a noisy room):

- Answer recognition, test pack: 24 spoken answers in Marathi and Hindi, 22 judged right, 2 re-prompted, 0 marked wrongly.
- Question routing: 8 of 8 test questions handled correctly (4 answered, 4 refused, including near misses such as "what does a goat drink?" next to "what does a goat eat?"), same result in Python and in the browser.
- We first tried small on-device LLMs for question routing (qwen2.5 1.5B and 3B, gemma3 1B). Each got 4 of 8, so we replaced them with embeddings plus near-miss questions.

## Layout

```
doosri/      online stages: schema, Claude wrapper, prepare, checks, store/approval, audio, report, server, CLI
engine/      offline classroom engine: session, answer matching, question gates, laptop/device/text I/O
web/         web app: prepare, review, classroom simulator (offline, service worker), next-day note
content/     lesson sources
packs/       approved packs (pack.json + audio/)
evals/       evaluation scripts
docs/        teacher test kit, demo video script
tests/       pytest suite and fixture pack
```

## Limits we know about

- Recognition is tested on synthetic adult voices; children's voices and classroom noise need field testing, and adapting the model to children's speech is on the roadmap.
- Marathi is the first home language because it has voices for review and audio. Bhili and Gondi packs can be drafted but need community recordings in place of synthetic audio.
- The Hindi recogniser misses some Marathi words; the colour buttons cover them.

## Licence

MIT. Uses Vosk (Apache-2.0), vosk-browser (Apache-2.0), transformers.js (Apache-2.0), and the paraphrase-multilingual-MiniLM-L12-v2 model (Apache-2.0).
