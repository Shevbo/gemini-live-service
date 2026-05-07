const TOKEN_KEY = 'gls_token';

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || new URLSearchParams(location.search).get('token') || '';
}

export function saveToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function authHeaders() {
  return { 'Authorization': `Bearer ${getToken()}` };
}

export async function apiPost(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json();
}

export async function apiGet(path) {
  const res = await fetch(path, { headers: authHeaders() });
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json();
}

export async function* streamSession(sessionId, text) {
  const res = await fetch(`/v1/session/${sessionId}/send`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error('Send failed');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop();
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        yield JSON.parse(line.slice(6));
      }
    }
  }
}
