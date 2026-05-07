import { getToken, saveToken, apiPost, apiGet, streamSession } from './api.js';
import { PCMPlayer } from './audio.js';

let sessionId = null;
let player = null;

const btnMic = document.getElementById('btn-mic');
const btnText = document.getElementById('btn-text-send');
const inputText = document.getElementById('text-input');
const transcript = document.getElementById('transcript');
const statusEl = document.getElementById('status');

function setStatus(msg) { if (statusEl) statusEl.textContent = msg; }

function appendMessage(role, text) {
  if (!transcript || !text) return;
  const div = document.createElement('div');
  div.className = `msg msg-${role}`;
  div.innerHTML = `<b>${role === 'user' ? 'Вы' : 'Медсестра'}:</b> ${text}`;
  transcript.appendChild(div);
  transcript.scrollTop = transcript.scrollHeight;
}

async function ensureSession() {
  if (sessionId) return;
  setStatus('Подключение...');
  const res = await apiPost('/v1/session/start', { voice: 'Kore', language: 'ru-RU', source: 'web' });
  sessionId = res.session_id;
  player = new PCMPlayer();
  setStatus('Готово');
}

async function sendText(text) {
  if (!text.trim()) return;
  await ensureSession();
  appendMessage('user', text);
  setStatus('Медсестра отвечает...');
  let fullTranscript = '';
  try {
    for await (const chunk of streamSession(sessionId, text)) {
      if (chunk.type === 'audio_chunk' && chunk.audio_b64) {
        player.feed(chunk.audio_b64);
      } else if (chunk.type === 'turn_complete') {
        fullTranscript = chunk.transcript;
      }
    }
    appendMessage('model', fullTranscript);
    setStatus('Готово');
  } catch (e) {
    setStatus('Ошибка: ' + e.message);
  }
}

async function stopSession() {
  if (!sessionId) return;
  try {
    await apiPost(`/v1/session/${sessionId}/stop`, {});
  } catch (_) {}
  sessionId = null;
  player = null;
}

// Кнопка отправки текста
if (btnText) {
  btnText.onclick = () => {
    const text = inputText.value.trim();
    if (text) { inputText.value = ''; sendText(text); }
  };
}
if (inputText) {
  inputText.onkeydown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); btnText?.click(); }
  };
}

// Завершение сессии при закрытии страницы
window.addEventListener('beforeunload', stopSession);

// Проверка токена при загрузке
window.addEventListener('DOMContentLoaded', () => {
  const token = getToken();
  if (!token) {
    const t = prompt('Введите токен доступа:');
    if (t) saveToken(t);
    else location.href = '/';
  }
});
