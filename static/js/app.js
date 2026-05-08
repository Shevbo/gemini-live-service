import { getToken, saveToken, apiPost, streamSession } from './api.js';
import { MicRecorder, PCMPlayer } from './audio.js';

// --- State ---
let textSessionId = null;
let textPlayer = null;

let ws = null;
let recorder = null;
let voicePlayer = null;
let voiceActive = false;

// --- DOM ---
const btnMic      = document.getElementById('btn-mic');
const btnSend     = document.getElementById('btn-text-send');
const inputText   = document.getElementById('text-input');
const transcript  = document.getElementById('transcript');
const statusEl    = document.getElementById('status');

// --- Helpers ---
function setStatus(msg) { if (statusEl) statusEl.textContent = msg; }

function appendMessage(role, text) {
  if (!transcript || !text) return;
  const div = document.createElement('div');
  div.className = `msg msg-${role}`;
  div.innerHTML = `<b>${role === 'user' ? 'Вы' : 'Медсестра'}:</b> ${escapeHtml(text)}`;
  transcript.appendChild(div);
  transcript.scrollTop = transcript.scrollHeight;
}

function escapeHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// --- Text mode (REST + SSE) ---
async function ensureTextSession() {
  if (textSessionId) return;
  setStatus('Подключение...');
  const res = await apiPost('/v1/session/start', { voice: 'Kore', language: 'ru-RU', source: 'web' });
  textSessionId = res.session_id;
  textPlayer = new PCMPlayer();
  setStatus('');
}

async function sendText(text) {
  if (!text.trim()) return;
  // Если в голосовом режиме — сначала выключить
  if (voiceActive) await stopVoice();
  await ensureTextSession();
  appendMessage('user', text);
  setStatus('Медсестра отвечает...');
  let fullTranscript = '';
  try {
    for await (const chunk of streamSession(textSessionId, text)) {
      if (chunk.type === 'audio_chunk' && chunk.audio_b64) {
        textPlayer.feed(chunk.audio_b64);
      } else if (chunk.type === 'turn_complete') {
        fullTranscript = chunk.transcript || '';
      }
    }
    appendMessage('model', fullTranscript);
    setStatus('');
  } catch (e) {
    setStatus('Ошибка: ' + e.message);
  }
}

// --- Voice mode (WebSocket) ---
async function startVoice() {
  const token = getToken();
  if (!token) { setStatus('Нет токена'); return; }

  btnMic.className = 'connecting';
  setStatus('Подключение...');

  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/ws/voice`);

  ws.onopen = () => {
    ws.send(JSON.stringify({ type: 'start', token, voice: 'Kore', language: 'ru-RU' }));
  };

  ws.onmessage = async (e) => {
    const msg = JSON.parse(e.data);

    if (msg.type === 'session_ready') {
      voicePlayer = new PCMPlayer();
      // Запускаем микрофон
      recorder = new MicRecorder((pcm) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          const b64 = btoa(String.fromCharCode(...new Uint8Array(pcm)));
          ws.send(JSON.stringify({ type: 'audio', data: b64 }));
        }
      });
      try {
        await recorder.start();
        voiceActive = true;
        btnMic.className = 'recording';
        setStatus('🎤 Говорите...');
      } catch (err) {
        setStatus('Ошибка микрофона: ' + err.message);
        stopVoice();
      }

    } else if (msg.type === 'audio' && msg.data) {
      voicePlayer?.feed(msg.data);

    } else if (msg.type === 'turn_complete') {
      if (msg.transcript) appendMessage('model', msg.transcript);

    } else if (msg.type === 'error') {
      setStatus('Ошибка: ' + msg.message);
      await stopVoice();
    }
  };

  ws.onclose = () => {
    if (voiceActive) stopVoice(false);
  };

  ws.onerror = () => {
    setStatus('WebSocket ошибка');
    stopVoice(false);
  };
}

async function stopVoice(sendStop = true) {
  voiceActive = false;
  btnMic.className = '';
  setStatus('');

  if (recorder) { recorder.stop(); recorder = null; }
  if (ws && ws.readyState === WebSocket.OPEN) {
    if (sendStop) ws.send(JSON.stringify({ type: 'stop' }));
    ws.close();
  }
  ws = null;
  voicePlayer = null;
}

// --- Mic button ---
btnMic.onclick = async () => {
  if (voiceActive) {
    await stopVoice();
  } else {
    // Сбрасываем текстовую сессию чтобы не было двух открытых
    textSessionId = null;
    textPlayer = null;
    await startVoice();
  }
};

// --- Text send button ---
btnSend.onclick = () => {
  const text = inputText.value.trim();
  if (text) { inputText.value = ''; sendText(text); }
};
inputText.onkeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); btnSend.click(); }
};

// --- Завершение при закрытии ---
window.addEventListener('beforeunload', () => {
  stopVoice(true);
  if (textSessionId) apiPost(`/v1/session/${textSessionId}/stop`, {}).catch(() => {});
});

// --- Проверка токена ---
window.addEventListener('DOMContentLoaded', () => {
  const token = getToken();
  if (!token) {
    const t = prompt('Введите токен доступа:');
    if (t) saveToken(t);
  }
});
