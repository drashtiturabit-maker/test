const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export async function fetchWidgetConfig(clientKey) {
  const res = await fetch(`${API_BASE}/widget/config?key=${encodeURIComponent(clientKey)}`);
  if (!res.ok) throw new Error('Widget config not found');
  return res.json();
}

export async function createSession(clientKey) {
  const res = await fetch(`${API_BASE}/chat/session?client_key=${encodeURIComponent(clientKey)}`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to create session');
  return res.json();
}

export async function* streamChat(clientKey, sessionId, message, pageUrl) {
  const res = await fetch(`${API_BASE}/chat/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ client_key: clientKey, session_id: sessionId, message, page_url: pageUrl }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Chat failed');
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          yield JSON.parse(line.slice(6));
        } catch { /* skip */ }
      }
    }
  }
}
