import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { esMock } from './lib/mode';
import { aplicaTema, llegeixTema } from './lib/tema';
import './styles/tokens.css';
import './styles/app.css';
import './styles/informe.css';

// Tema desat (Clar per defecte, o Fosc) abans del primer pintat, per evitar un parpelleig.
aplicaTema(llegeixTema());

async function inicia() {
  if (esMock()) {
    const { activaMock } = await import('./mock');
    activaMock();
  }
  createRoot(document.getElementById('arrel')!).render(<StrictMode><App /></StrictMode>);
}

void inicia();
