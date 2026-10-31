// Browser stand-ins for the device's speaker, microphone and buttons.
// Speech recognition (Vosk, WASM) and question matching (MiniLM, ONNX) run
// in this page; nothing is sent to a server during a session.

const VOSK_MODEL_URL = "/models/vosk-model-small-hi-0.22.tar.gz";
const EMBED_MODEL = "Xenova/paraphrase-multilingual-MiniLM-L12-v2";
const TRANSFORMERS = "https://cdn.jsdelivr.net/npm/@huggingface/transformers@4.2.0";

export async function loadEmbedder() {
  const {pipeline, env} = await import(TRANSFORMERS);
  env.localModelPath = "/models/";
  env.allowLocalModels = true;
  // The hosted demo does not serve the 118 MB model itself; it comes from the Hugging Face CDN
  // once and stays in the browser cache, so sessions still run offline afterwards.
  env.allowRemoteModels = true;
  const extract = await pipeline("feature-extraction", EMBED_MODEL, {dtype: "q8"});
  return async texts => (await extract(texts, {pooling: "mean", normalize: true})).tolist();
}

export async function loadRecogniser() {
  const model = await window.Vosk.createModel(new URL(VOSK_MODEL_URL, location.href).href);
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {echoCancellation: true, noiseSuppression: true, channelCount: 1}});
  const ctx = new AudioContext();
  const source = ctx.createMediaStreamSource(stream);
  const node = ctx.createScriptProcessor(4096, 1, 1);
  source.connect(node); node.connect(ctx.destination);
  let target = null;  // recogniser currently fed with audio
  node.onaudioprocess = e => { if (target) { try { target.acceptWaveform(e.inputBuffer); } catch {} } };

  // Records until stop() resolves; returns {text, confidence}.
  function listen(words) {
    const rec = words ? new model.KaldiRecognizer(ctx.sampleRate, JSON.stringify([...words, "[unk]"]))
                      : new model.KaldiRecognizer(ctx.sampleRate);
    rec.setWords(true);
    const results = [];
    rec.on("result", m => { if (m.result.result?.length) results.push(...m.result.result); });
    if (ctx.state === "suspended") ctx.resume();
    target = rec;
    return {
      stop: () => new Promise(resolve => {
        target = null;
        let done = false;
        const finish = () => {
          if (done) return; done = true;
          const parts = results.filter(w => w.word !== "[unk]");
          rec.remove();
          resolve({text: parts.map(w => w.word).join(" "),
                   confidence: parts.length ? parts.reduce((s, w) => s + w.conf, 0) / parts.length : 0});
        };
        rec.on("result", () => setTimeout(finish, 50));
        rec.retrieveFinalResult();
        setTimeout(finish, 1500);
      }),
    };
  }
  return {listen, ctx};
}

export class BrowserIO {
  constructor({pack, base, manifest, ui, recogniser}) {
    Object.assign(this, {pack, base, manifest, ui, recogniser});
    this.pending = null;   // resolves a listen early on a button press
    this.askHeld = null;
  }
  audioUrl(lang, text) {
    const name = this.manifest[lang]?.[text];
    return name ? `${this.base}/audio/${name}` : null;
  }
  play(lang, text) {
    this.ui.say(lang, text);
    const url = this.audioUrl(lang, text);
    if (!url) return new Promise(r => setTimeout(r, Math.max(800, text.length * 60)));
    return new Promise(resolve => {
      const a = new Audio(url);
      a.playbackRate = this.ui.rate();
      a.onended = a.onerror = () => resolve();
      a.play().catch(() => resolve());
    });
  }
  show(text) { this.ui.screen(text); }
  choices(colours) { this.ui.choices(colours); }
  highlight(colour) { this.ui.highlight(colour); }
  verdict(heard, v) { this.ui.verdict(heard, v); }
  routed(q, route) { this.ui.routed(q, route); }

  press(colour) { if (this.pending) this.pending({kind: "button", colour}); }

  async listenAnswer(words, seconds) {
    const rec = this.recogniser?.listen(words);
    this.ui.listening(true, seconds);
    const heard = await new Promise(resolve => {
      this.pending = resolve;
      setTimeout(() => resolve(null), seconds * 1000);
    });
    this.pending = null;
    this.ui.listening(false);
    const speech = rec ? await rec.stop() : {text: "", confidence: 0};
    if (heard) return heard;
    if (speech.text) return {kind: "voice", text: speech.text, confidence: speech.confidence};
    return {kind: "none"};
  }

  // A question is asked by holding the Ask button (or the space bar), as on the device's trigger.
  async listenQuestion(seconds) {
    this.ui.asking(true, seconds);
    const held = await new Promise(resolve => {
      this.askHeld = resolve;
      setTimeout(() => resolve(false), seconds * 1000);
    });
    this.askHeld = null;
    this.ui.asking(false);
    if (!held) return null;
    if (this.ui.typedQuestion) {  // no microphone: question typed instead
      const q = this.ui.typedQuestion(); return q || null;
    }
    const rec = this.recogniser.listen(null);
    this.ui.recordingQuestion(true);
    if (this.askIsDown) await new Promise(resolve => { this.askReleased = resolve; setTimeout(resolve, 15000); });
    this.askReleased = null;
    this.ui.recordingQuestion(false);
    const {text} = await rec.stop();
    return text || null;
  }
  askDown() { this.askIsDown = true; if (this.askHeld) this.askHeld(true); }
  askUp() { this.askIsDown = false; if (this.askReleased) this.askReleased(); }
}
