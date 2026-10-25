import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { ToastProvider } from './components/ui';
import { ThemeProvider } from './theme/ThemeProvider';
import './index.css';
import './styles/enterprise-ui.css';

// Handle stale chunk hash mismatches caused by server redeployments
window.addEventListener('vite:preloadError', (event) => {
  console.warn('Vite preload error detected (stale deployment chunk). Reloading page...', event);
  window.location.reload();
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <ToastProvider>
        <App />
      </ToastProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
