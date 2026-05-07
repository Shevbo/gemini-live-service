// MediaRecorder для захвата голоса + AudioContext для воспроизведения PCM

export class MicRecorder {
  constructor(onChunk) {
    this.onChunk = onChunk;
    this.stream = null;
    this.recorder = null;
    this.audioCtx = null;
    this.processor = null;
  }

  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: {
      channelCount: 1,
      sampleRate: 16000,
      echoCancellation: true,
      noiseSuppression: true,
    }});

    this.audioCtx = new AudioContext({ sampleRate: 16000 });
    const source = this.audioCtx.createMediaStreamSource(this.stream);
    this.processor = this.audioCtx.createScriptProcessor(4096, 1, 1);

    this.processor.onaudioprocess = (e) => {
      const f32 = e.inputBuffer.getChannelData(0);
      // Float32 → Int16 PCM
      const i16 = new Int16Array(f32.length);
      for (let i = 0; i < f32.length; i++) {
        i16[i] = Math.max(-32768, Math.min(32767, f32[i] * 32768));
      }
      this.onChunk(i16.buffer);
    };

    source.connect(this.processor);
    this.processor.connect(this.audioCtx.destination);
  }

  stop() {
    if (this.processor) { this.processor.disconnect(); this.processor = null; }
    if (this.audioCtx) { this.audioCtx.close(); this.audioCtx = null; }
    if (this.stream) { this.stream.getTracks().forEach(t => t.stop()); this.stream = null; }
  }
}

export class PCMPlayer {
  constructor() {
    this.audioCtx = new AudioContext({ sampleRate: 24000 });
    this.queue = [];
    this.playing = false;
  }

  feed(pcmBase64) {
    const binary = atob(pcmBase64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const i16 = new Int16Array(bytes.buffer);
    const f32 = new Float32Array(i16.length);
    for (let i = 0; i < i16.length; i++) f32[i] = i16[i] / 32768;

    const buf = this.audioCtx.createBuffer(1, f32.length, 24000);
    buf.copyToChannel(f32, 0);
    this.queue.push(buf);
    if (!this.playing) this._play();
  }

  _play() {
    if (!this.queue.length) { this.playing = false; return; }
    this.playing = true;
    const buf = this.queue.shift();
    const src = this.audioCtx.createBufferSource();
    src.buffer = buf;
    src.connect(this.audioCtx.destination);
    src.onended = () => this._play();
    src.start();
  }
}
