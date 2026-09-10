import React from 'react';
import ReactDOM from 'react-dom/client';
import ChatWidget from './ChatWidget';

const params = new URLSearchParams(window.location.search);
const clientKey = params.get('key') || 'demo';

ReactDOM.createRoot(document.getElementById('root')).render(
  <ChatWidget clientKey={clientKey} />
);
