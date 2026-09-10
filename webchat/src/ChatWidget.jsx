import { useEffect, useRef, useState } from 'react';
import { createSession, fetchWidgetConfig, streamChat } from './api';
import './widget.css';

export default function ChatWidget({ clientKey, apiBase }) {
  const [config, setConfig] = useState(null);
  const [open, setOpen] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const bottomRef = useRef(null);

  useEffect(() => {
    if (!clientKey) return;
    fetchWidgetConfig(clientKey)
      .then((cfg) => {
        const host = window.location.hostname;
        if (cfg.allowed_domains?.length && !cfg.allowed_domains.includes(host) && !host.includes('localhost')) {
          return;
        }
        if (!cfg.enabled) return;
        setConfig(cfg);
        setMessages([{ role: 'assistant', content: cfg.welcome_message }]);
        return createSession(clientKey);
      })
      .then((sess) => {
        if (sess) setSessionId(sess.session_id);
      })
      .catch(() => setError('Widget unavailable'));
  }, [clientKey]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  async function send() {
    if (!input.trim() || !sessionId || loading) return;
    const userMsg = input.trim();
    setInput('');
    setMessages((m) => [...m, { role: 'user', content: userMsg }]);
    setLoading(true);
    setError('');
    let assistant = '';
    try {
      for await (const event of streamChat(clientKey, sessionId, userMsg, window.location.href)) {
        if (event.type === 'token') {
          assistant += event.content;
          setMessages((m) => {
            const copy = [...m];
            const last = copy[copy.length - 1];
            if (last?.role === 'assistant' && last.streaming) {
              copy[copy.length - 1] = { role: 'assistant', content: assistant, streaming: true };
            } else {
              copy.push({ role: 'assistant', content: assistant, streaming: true });
            }
            return copy;
          });
        } else if (event.type === 'error') {
          setError(event.message);
        }
      }
      setMessages((m) => {
        const copy = [...m];
        const idx = copy.findIndex((x) => x.streaming);
        if (idx >= 0) copy[idx] = { role: 'assistant', content: assistant };
        return copy;
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (!config) return null;
  const color = config.primary_color || '#4F46E5';

  return (
    <div className="cx-widget-root">
      {open && (
        <div className="cx-panel" style={{ '--cx-primary': color }}>
          <header className="cx-header">
            <span>{config.bot_name}</span>
            <button className="cx-close" onClick={() => setOpen(false)}>×</button>
          </header>
          <div className="cx-messages">
            {messages.map((m, i) => (
              <div key={i} className={`cx-msg cx-msg-${m.role}`}>{m.content}</div>
            ))}
            {loading && <div className="cx-typing">● ● ●</div>}
            {error && <div className="cx-error">{error}</div>}
            <div ref={bottomRef} />
          </div>
          <footer className="cx-footer">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && send()}
              placeholder="Type a message..."
            />
            <button onClick={send} disabled={loading}>Send</button>
          </footer>
          {config.show_branding && <div className="cx-branding">Powered by Trivighna CX</div>}
        </div>
      )}
      <button className="cx-bubble" style={{ background: color }} onClick={() => setOpen(!open)}>
        {open ? '×' : '💬'}
      </button>
    </div>
  );
}
