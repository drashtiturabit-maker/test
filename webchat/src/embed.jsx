import React from 'react';
import ReactDOM from 'react-dom/client';
import ChatWidget from './ChatWidget';

(function () {
  const script = document.currentScript;
  const clientKey = script?.getAttribute('data-client-key');
  if (!clientKey) return;

  const host = document.createElement('div');
  host.id = 'cx-widget-host';
  document.body.appendChild(host);

  const shadow = host.attachShadow({ mode: 'open' });
  const mount = document.createElement('div');
  shadow.appendChild(mount);

  const style = document.createElement('style');
  style.textContent = `
    :host { all: initial; }
    * { box-sizing: border-box; }
  `;
  shadow.appendChild(style);

  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = new URL('/src/widget.css', import.meta.url).href;
  shadow.appendChild(link);

  ReactDOM.createRoot(mount).render(<ChatWidget clientKey={clientKey} />);
})();
