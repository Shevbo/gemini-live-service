// MediaRecorder for mic capture + AudioContext for seamless PCM playback

const SILENCE_THRESHOLD = 0.008;
const SILENCE_FRAMES = 10; // 10 * 2048 / 16000 ≈ 1.3s of silence

export class MicRecorder {
  constructor(onChunk, onActivity) {
    this.onChunk = onChunk;
    this.onActivity = onActivity; // called when non-silent audio detected
    this.stream = null;
    this.audioCtx = null;
    this.processor = null;
    this._silenceCount = 0;
  }

  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: {
      channelCount: 1,
      sampleRate: 16000,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: false,
    }});

    this.audioCtx = new AudioContext({ sampleRate: 16000 });
    const source = this.audioCtx.createMediaStreamSource(this.stream);
    this.processor = this.audioCtx.createScriptProcessor(2048, 1, 1);

    this.processor.onaudioprocess = (e) => {
      const f32 = e.inputBuffer.getChannelData(0);

      let sum = 0;
      for (let i = 0; i < f32.length; i++) sum += f32[i] * f32[i];
      const rms = Math.sqrt(sum / f32.length);

      if (rms >= SILENCE_THRESHOLD) {
        this._silenceCount = 0;
        this.onActivity?.();
      } else {
        this._silenceCount++;
      }

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
    this.nextTime = 0;
    this._lastSrc = null;
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

    const src = this.audioCtx.createBufferSource();
    src.buffer = buf;
    src.connect(this.audioCtx.destination);

    // Schedule immediately after previous chunk — eliminates gaps
    const startAt = Math.max(this.audioCtx.currentTime, this.nextTime);
    src.start(startAt);
    this.nextTime = startAt + buf.duration;
    this._lastSrc = src;
  }

  // Returns ms remaining until all scheduled audio finishes
  remainingMs() {
    const remaining = this.nextTime - this.audioCtx.currentTime;
    return Math.max(0, remaining * 1000);
  }

  // Call after last chunk of a turn is fed; fires callback when audio is done
  onTurnEnd(callback) {
    const ms = this.remainingMs();
    if (ms <= 50) {
      callback();
    } else {
      setTimeout(callback, ms);
    }
  }

  reset() {
    this.nextTime = 0;
    this._lastSrc = null;
  }
}
