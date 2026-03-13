import React from 'react';
import './src/index.css';

// Apply saved theme before React renders (avoids flash)
const savedTheme = localStorage.getItem('arcco_theme') || 'dark';
document.documentElement.setAttribute('data-theme', savedTheme);

import ReactDOM from 'react-dom/client';
import App from './App';
import { ToastProvider } from './components/Toast';

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error("Could not find root element to mount to");
}

const root = ReactDOM.createRoot(rootElement);
root.render(
  <React.StrictMode>
    <ToastProvider>
      <App />
    </ToastProvider>
  </React.StrictMode>
);