// Browser port of engine/session.py and engine/match.py. Same flow, same
// thresholds, same log format, so the simulator behaves like the device.

export const MAX_TRIES = 2;
export const MAX_UNCLEAR = 2;
export const LISTEN_SECONDS = 8;
export const MAX_QUESTIONS = 3;
export const MIN_CONFIDENCE = 0.6;
export const SIMILARITY = 0.6;
export const MARGIN = 0.05;

const DEV_DIGITS = "०१२३४५६७८९";

export function normalize(text) {
  let t = (text || "").normalize("NFC").toLowerCase();
  t = t.replace(/[०-९]/g, d => String(DEV_DIGITS.indexOf(d)));
  t = t.replace(/[।॥.,!?;:"'()\-]/g, " ");
  return t.split(/\s+/).filter(Boolean).join(" ");
}
const tokens = t => normalize(t).split(" ").filter(Boolean);

export function judgeButton(item, colour) {
  return {result: colour === item.correct ? "correct" : "wrong", colour};
}

export function judgeVoice(item, text, confidence, colourWords) {
  const said = new Set(tokens(text));
  if (!said.size || confidence < MIN_CONFIDENCE) return {result: "unclear"};
  const accepted = item.accepted_spoken.map(normalize);
  const norm = normalize(text);
  if (accepted.some(a => said.has(a) || (a.includes(" ") && norm.includes(a)))) return {result: "correct", colour: item.correct};
  const right = item.choices.find(c => c.colour === item.correct);
  const rightWords = new Set([...accepted, ...tokens(right.label.home), ...tokens(right.label.school)]);
  for (const ch of item.choices) {
    if (ch.colour === item.correct) continue;
    const names = Object.values(colourWords[ch.colour]).map(normalize);
    const label = [...tokens(ch.label.home), ...tokens(ch.label.school)].filter(w => !rightWords.has(w));
    if (names.some(n => said.has(n)) || label.some(w => said.has(w))) return {result: "wrong", colour: ch.colour};
  }
  if (Object.values(colourWords[item.correct]).map(normalize).some(n => said.has(n))) return {result: "correct", colour: item.correct};
  return {result: "unclear"};
}

export function grammarWords(item, colourWords) {
  const w = new Set();
  item.accepted_spoken.forEach(a => tokens(a).forEach(t => w.add(t)));
  item.choices.forEach(c => {
    [...tokens(c.label.home), ...tokens(c.label.school)].forEach(t => w.add(t));
    Object.values(colourWords[c.colour]).forEach(t => w.add(t));
  });
  return [...w].sort();
}

// --- question routing: embeddings with two gates ---
const dot = (a, b) => a.reduce((s, x, i) => s + x * b[i], 0);

export class QuestionRouter {
  constructor(pack, embed) { this.pack = pack; this.embed = embed; this.faq = null; }
  async ready() {
    if (this.faq) return;
    this.faq = [];
    for (const q of this.pack.faq) {
      this.faq.push({id: q.id, pos: await this.embed(q.questions.map(normalize)),
                     neg: q.near_misses.length ? await this.embed(q.near_misses.map(normalize)) : []});
    }
  }
  async route(question) {
    await this.ready();
    const [v] = await this.embed([normalize(question)]);
    let best = {faq_id: null, score: 0, gate: "gate1"};
    for (const f of this.faq) {
      const ps = Math.max(...f.pos.map(p => dot(p, v)));
      const ns = f.neg.length ? Math.max(...f.neg.map(n => dot(n, v))) : 0;
      if (ps < SIMILARITY || ps <= best.score) continue;
      best = ps - ns >= MARGIN ? {faq_id: f.id, score: ps, gate: "answered"} : {faq_id: null, score: ps, gate: "gate2"};
    }
    return best;
  }
}

// --- the session ---
// io must provide: play(lang, text), listenAnswer(words, seconds) -> {kind, colour, text, confidence},
// listenQuestion(seconds) -> text|null, show(text), choices(colours|null)
export class Session {
  constructor(pack, phrases, io, router) {
    if (pack.status !== "approved") throw new Error("only approved packs can run in a classroom");
    Object.assign(this, {pack, ph: phrases, io, router});
    this.home = pack.home_language; this.school = pack.school_language;
    this.log = {pack_id: pack.id, pack_title: pack.title, grade: pack.grade,
                started_at: Date.now() / 1000, ended_at: 0, items: [], questions: []};
  }
  async say(line) { await this.io.play(this.home, line.home); await this.io.play(this.school, line.school); }
  async sayPhrase(key) { const p = this.ph.phrases[key]; await this.io.play(this.home, p[this.home]); await this.io.play(this.school, p[this.school]); }
  async sayChoices(item) {
    for (const [lang, side] of [[this.home, "home"], [this.school, "school"]])
      for (const ch of item.choices) {
        this.io.highlight?.(ch.colour);
        await this.io.play(lang, this.ph.colour_words[ch.colour][lang]);
        await this.io.play(lang, ch.label[side]);
      }
    this.io.highlight?.(null);
  }

  async run(askQuestions = true) {
    const p = this.pack;
    this.io.show(p.title);
    await this.say(p.intro);
    if (p.story) await this.say(p.story);
    for (let n = 0; n < p.items.length; n++) {
      this.io.show(`${n + 1}/${p.items.length}`);
      this.log.items.push(await this.runItem(p.items[n]));
      if (n < p.items.length - 1) await this.sayPhrase("next");
    }
    if (askQuestions) await this.runQuestions();
    await this.say(p.closing);
    this.log.ended_at = Date.now() / 1000;
    return this.log;
  }

  async runItem(item) {
    const rec = {id: item.id, skill: item.skill, first_try_correct: false, correct: false,
                 wrong_tries: 0, unclear: 0, answered_by: [], seconds: 0};
    const t0 = Date.now();
    await this.say(item.prompt);
    this.io.choices(item.choices.map(c => c.colour));
    await this.sayChoices(item);
    await this.sayPhrase("answer_now");
    const words = grammarWords(item, this.ph.colour_words);
    while (true) {
      const heard = await this.io.listenAnswer(words, LISTEN_SECONDS);
      let v = null;
      if (heard.kind === "button" && heard.colour) v = judgeButton(item, heard.colour);
      else if (heard.kind === "voice") v = judgeVoice(item, heard.text, heard.confidence, this.ph.colour_words);
      this.io.verdict?.(heard, v);
      if (!v || v.result === "unclear") {
        rec.unclear += 1;
        if (rec.unclear > MAX_UNCLEAR) { await this.say(item.reveal); break; }
        await this.sayPhrase("not_heard");
        continue;
      }
      rec.answered_by.push(heard.kind);
      if (v.result === "correct") {
        rec.correct = true; rec.first_try_correct = rec.wrong_tries === 0;
        await this.say(item.praise); break;
      }
      rec.wrong_tries += 1;
      if (rec.wrong_tries >= MAX_TRIES) { await this.say(item.reveal); break; }
      await this.say(item.hint);
      await this.sayPhrase("try_again");
    }
    this.io.choices(null);
    rec.seconds = Math.round((Date.now() - t0) / 100) / 10;
    return rec;
  }

  async runQuestions() {
    for (let i = 0; i < MAX_QUESTIONS; i++) {
      await this.sayPhrase("ask_prompt");
      const q = await this.io.listenQuestion(LISTEN_SECONDS);
      if (!q) return;
      const route = await this.router.route(q);
      this.log.questions.push({text: q, faq_id: route.faq_id, gate: route.gate, score: Math.round(route.score * 100) / 100});
      this.io.routed?.(q, route);
      if (route.faq_id) await this.say(this.pack.faq.find(f => f.id === route.faq_id).answer);
      else await this.say(this.pack.ask_teacher);
    }
  }

  teacherSummary() {
    const items = Object.fromEntries(this.pack.items.map(i => [i.id, i]));
    const logs = this.log.items;
    const lines = [this.ph.teacher.teacher_done, this.ph.teacher_score[logs.filter(r => r.first_try_correct).length]];
    const hard = logs.filter(r => !r.first_try_correct)
      .sort((a, b) => (a.correct - b.correct) || (b.wrong_tries - a.wrong_tries) || (b.unclear - a.unclear)).slice(0, 2);
    if (hard.length) { lines.push(this.ph.teacher.teacher_hard); hard.forEach(r => lines.push(items[r.id].skill_spoken)); }
    else lines.push(this.ph.teacher.teacher_all_good);
    if (this.log.questions.some(q => q.faq_id === null)) lines.push(this.ph.teacher.teacher_questions);
    return lines;
  }
  async debrief() { for (const t of this.teacherSummary()) await this.io.play(this.school, t); }
}
