import { lazy, Suspense, type ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Esquelet } from './components/Estat';
import { Shell } from './components/Shell';
import { ProveidorFiltre } from './context/Filtre';
import { ProveidorSessio, useSessio } from './context/Sessio';
import type { Rol } from './api/types';
import { Entra } from './pages/Entra';
import { Resum } from './pages/Resum';

// Les pàgines menys visitades es carreguen a part.
const Peces = lazy(() => import('./pages/Peces').then((m) => ({ default: m.Peces })));
const PecaDetall = lazy(() => import('./pages/PecaDetall').then((m) => ({ default: m.PecaDetall })));
const Talles = lazy(() => import('./pages/Talles').then((m) => ({ default: m.Talles })));
const PerQue = lazy(() => import('./pages/PerQue').then((m) => ({ default: m.PerQue })));
const Origen = lazy(() => import('./pages/Origen').then((m) => ({ default: m.Origen })));
const Servei = lazy(() => import('./pages/Servei').then((m) => ({ default: m.Servei })));
const Estoc = lazy(() => import('./pages/Estoc').then((m) => ({ default: m.Estoc })));
const Decisions = lazy(() => import('./pages/Decisions').then((m) => ({ default: m.Decisions })));
const Valor = lazy(() => import('./pages/Valor').then((m) => ({ default: m.Valor })));
const Informes = lazy(() => import('./pages/Informes').then((m) => ({ default: m.Informes })));
const Informe = lazy(() => import('./pages/Informe').then((m) => ({ default: m.Informe })));
const Dades = lazy(() => import('./pages/Dades').then((m) => ({ default: m.Dades })));
const Dependent = lazy(() => import('./pages/Dependent').then((m) => ({ default: m.Dependent })));

function NomesPer({ rols, children }: { rols: Rol[]; children: ReactNode }) {
  const { usuari } = useSessio();
  return rols.includes(usuari.rol) ? <>{children}</> : <Navigate to="/" replace />;
}

const MARCA: Rol[] = ['admin', 'marca'];
const espera = <Esquelet tipus="rajoles" />;

function AmbSessio({ children }: { children: ReactNode }) {
  return <ProveidorSessio><ProveidorFiltre><Suspense fallback={espera}>{children}</Suspense></ProveidorFiltre></ProveidorSessio>;
}

export function App() {
  return (
    <BrowserRouter basename="/app">
      <Routes>
        <Route path="/entra" element={<Entra />} />
        <Route path="/dependent" element={<AmbSessio><Dependent /></AmbSessio>} />
        <Route element={<AmbSessio><Shell /></AmbSessio>}>
          <Route index element={<Resum />} />
          <Route path="peces" element={<Suspense fallback={espera}><Peces /></Suspense>} />
          <Route path="peces/:model" element={<Suspense fallback={espera}><PecaDetall /></Suspense>} />
          <Route path="talles" element={<Suspense fallback={espera}><Talles /></Suspense>} />
          <Route path="per-que" element={<Suspense fallback={espera}><PerQue /></Suspense>} />
          <Route path="origen" element={<NomesPer rols={MARCA}><Suspense fallback={espera}><Origen /></Suspense></NomesPer>} />
          <Route path="servei" element={<Suspense fallback={espera}><Servei /></Suspense>} />
          <Route path="estoc" element={<Suspense fallback={espera}><Estoc /></Suspense>} />
          <Route path="decisions" element={<NomesPer rols={MARCA}><Suspense fallback={espera}><Decisions /></Suspense></NomesPer>} />
          <Route path="valor" element={<NomesPer rols={MARCA}><Suspense fallback={espera}><Valor /></Suspense></NomesPer>} />
          <Route path="informes" element={<Suspense fallback={espera}><Informes /></Suspense>} />
          <Route path="informes/:tipus" element={<Suspense fallback={espera}><Informe /></Suspense>} />
          <Route path="dades" element={<Suspense fallback={espera}><Dades /></Suspense>} />
          <Route path="*" element={<NoTrobada />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

function NoTrobada() {
  return <div className="buit"><h3>Aquesta pàgina no existeix</h3><p>Potser l’enllaç és antic. Torna al <a href="/app/">resum</a>.</p></div>;
}
