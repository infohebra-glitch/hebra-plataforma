import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { esMock } from './lib/mode';
import './styles/tokens.css';
import './styles/app.css';
import './styles/informe.css';

// Tema desat (clar/fosc) abans del primer pintat, per evitar un parpelleig.
try {
  const t = localStorage.getItem('hebra-tema');
  if (t === 'clar') document.documentElement.dataset.theme = 'light';
  if (t === 'fosc') document.documentElement.dataset.theme = 'dark';
} catch { /* sense emmagatzematge */ }

async function inicia() {
  if (esMock()) {
    const { activaMock } = await import('./mock');
    activaMock();
  }
  createRoot(document.getElementById('arrel')!).render(<StrictMode><App /></StrictMode>);
}

void inicia();
