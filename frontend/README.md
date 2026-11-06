# Tauler de Hebra (frontend)

El tauler de la marca i la web del dependent. Vite + React 18 + TypeScript estricte,
`react-router-dom`, CSS escrit a mà (sense framework ni kit d'UI) i gràfics en SVG/HTML
propis (sense llibreria de gràfics). El contracte de dades és `../docs/API.md`.

El backend serveix `dist/` a **`/app`** (amb «SPA fallback»), i l'API és a `/api/v2`.

## Com s'arrenca

```bash
cd frontend
npm ci                 # instal·la les versions exactes de package-lock.json
npm run dev            # http://localhost:5173/app/  (proxy /api → http://localhost:8000)
```

Cal el backend engegat a `localhost:8000`. Sense sessió, qualsevol pàgina porta a `/app/entra`.

## Mode demostració (sense backend)

Dues maneres d'activar-lo:

- **En compilar**: `npm run dev:mock` (o `VITE_MOCK=1 npm run build`).
- **En temps d'execució**: afegeix `?mock=1` a qualsevol adreça (p. ex. `/app/?mock=1`).
  Es recorda durant la sessió del navegador; `?mock=0` el treu.

En mode demostració, `src/mock/` substitueix el transport del client HTTP i el flux SSE:
totes les rutes de `docs/API.md` es responen dins del navegador amb dades inventades
però coherents (3 botigues, 7 models, una sèrie diària per a qualsevol període, la prova
d'origen en curs amb la prova z real, una prova acabada, peticions que arriben cada ~25 s
a la web del dependent). La sessió comença oberta com a administradora; a `/app/entra`,
un correu que comenci per `botiga` entra amb el rol de botiga. El codi fals es carrega
amb `import()` dinàmic: no pesa al paquet normal.

## Compilar i comprovar

```bash
npm run build          # tsc --noEmit + vite build → dist/
npm run typecheck      # només TypeScript
npm test               # Vitest: formats, períodes i client de l'API
npm run preview        # serveix dist/ a http://localhost:4173/app/ (amb ?mock=1 per provar-lo sol)
```

## Estructura

```
src/
  api/          types.ts (mirall de docs/API.md), client.ts (fetch, galetes, 401 → /app/entra),
                endpoints.ts (una funció per ruta), flux.ts (EventSource amb reconnexió)
  mock/         servidor fals del mode demostració (dades.ts, servidor.ts, estadistica.ts)
  context/      Sessio (GET /jo, rols) i Filtre (botiga + període → botiga/des/fins a totes les crides)
  lib/          format.ts (Intl 'ca-ES'), periode.ts, etiquetes.ts (noms en català), useApi.ts, mode.ts
  components/   Shell (navegació), Rajola, Estat (esquelet/buit/error), Experiment, TaulaOrdenable...
    grafics/    SerieTemporal, Barres, MapaCalor, CorbaTalles, IntervalConfianca, Mesurador
  pages/        una per ruta (Resum, Peces, PecaDetall, Talles, PerQue, Origen, Servei, Estoc,
                Decisions, Valor, Informes, Informe, Dades, Dependent, Entra)
  styles/       tokens.css (colors de la marca, mode fosc), app.css, informe.css (impressió)
```

Rutes: `/app/entra`, `/app` (resum), `/app/peces`, `/app/peces/:model`, `/app/talles`,
`/app/per-que`, `/app/origen`, `/app/servei`, `/app/estoc`, `/app/decisions`, `/app/valor`,
`/app/informes`, `/app/informes/:tipus`, `/app/dades`, `/app/dependent`.

## Criteris que seguim

- **Honestedat**: cada percentatge porta el denominador a prop («143 de 403 proves»);
  un grup amb menys de 30 proves porta «Mostra petita»; tot import en euros diu «Estimació».
- **Gràfics**: una sola escala per gràfic; verd (proves, grup amb canvi) i coure (compres)
  són els colors de la marca ajustats i validats per a daltonisme i contrast en clar i fosc;
  cada gràfic té la taula de dades a sota («Veure les dades en una taula») i globus amb ratolí o teclat.
- **Accessibilitat**: etiquetes a tots els camps, focus visible, el focus va al títol en
  canviar de pàgina, objectius tàctils de 44 px al mòbil (56 px a la web del dependent).
- **Mode fosc**: segueix el sistema, o es tria al menú d'usuari (Clara / Fosca).
- **Informes**: «Desa en PDF» obre el diàleg d'impressió; el CSS d'impressió amaga la navegació.
