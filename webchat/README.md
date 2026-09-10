# Webchat Widget (React)

Embeddable chat widget for B2B client websites.

## Session Behavior

- **New page load = new session** (including browser refresh)
- Each visit calls `POST /api/chat/session` to get a fresh `session_id`
- Conversation history is scoped to that session only

## Development

```bash
cd webchat
npm install
npm run dev
```

Preview: http://localhost:5174?key=YOUR_CLIENT_KEY

## Embed on Client Website

```html
<script
  src="https://cdn.yourcxplatform.com/embed.js"
  data-client-key="ck_xxxxxxxx"
  async
></script>
```

## Build

```bash
npm run build
```

Deploy `dist/` to CDN. The embed script mounts a Shadow DOM-isolated React chat widget.

## Environment

```bash
VITE_API_URL=http://localhost:8000/api
```
