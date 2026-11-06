# Arquitectura i regles

Document per revisar amb el Xavier. Les regles venen de la *Proposta MVP abans del pilot* (seccions 3.3 a 3.8). Tot el que porta **(proposta)** s'ha de validar o calibrar.

## Tecnologia

- **Python 3.11+, FastAPI, Jinja2, SQLite.** Pàgines fetes al servidor i sense JavaScript a la fitxa del client: carrega ràpid amb mala cobertura i no hi ha res a vigilar al navegador.
- **SQL escrit a mà** (`hebra/schema.sql`, `sqlite3` de la llibreria estàndard). Totes les consultes amb paràmetres. Per passar a PostgreSQL cal adaptar `hebra/db.py` (connexió i marcador `?` → `%s`) i els `AUTOINCREMENT` de l'esquema; la resta de l'SQL és estàndard.
- **Tauler web: React 18 + TypeScript + Vite** (`frontend/`), compilat a `frontend/dist` i servit pel mateix FastAPI a `/app/`. Gràfics en SVG propis, sense llibreries de gràfics. Només llegeix l'API v2: no calcula res, mostra el que dona el backend.
- **Una connexió SQLite per fil** (`db.ConnexioPerFil`): FastAPI executa els endpoints en paral·lel i una connexió compartida es trepitjava. Amb WAL, lectures i escriptures conviuen.
- **Allotjament previst:** un servidor petit (Hetzner CX23, ≈5,5 €/mes) amb `uvicorn` darrere d'un proxy amb HTTPS (Caddy o nginx).

## Hores

Tot es desa en **hora local de la botiga** amb desplaçament (`2026-11-16T12:00:00+01:00`), normalitzat a l'entrada (`hebra/temps.py`). Així el «dia» de la prova, de la venda i del grup de control és el mateix. Les comparacions de text entre dates funcionen perquè totes tenen el mateix format.

## Sessió de cabina

Una màquina d'estats per cabina (`proves.detecta_sessions`):

- **Comença** quan la porta és tancada **i** hi ha presència.
- **Acaba** quan la porta és oberta **i** no hi ha presència durant 10 s **(proposta)**. L'hora de fi és el moment en què ha quedat buida.
- Si la porta s'obre un moment (per demanar una talla) i torna a tancar, la sessió continua.
- Una sessió que no es tanca (tall de dades) no es compta.

Al nivell **Bàsic** (sense sensors per cabina) no hi ha sessions: cal una variant que compti entrades a zona. **No està feta** (vegeu PENDENT).

## Prova

Per a cada sessió i cada EPC llegit per les antenes de la cabina (`proves.processa_cabina`):

1. RSSI mitjà ponderat per lectures **≥ llindar de l'antena** (−60 dBm per defecte, **proposta**). Si no, és una peça de fora.
2. Temps entre la primera i l'última lectura **≥ 60 s** i **≥ 5 lectures** **(proposta)**. Si no, és un «pas».
3. Si una cabina veïna també la llegeix en la mateixa finestra, es compara l'RSSI mitjà:
   - marge ≥ 6 dB → **alta**; ≥ 3 dB → **mitjana**; entre −3 i 3 dB → **ambigua**; la veïna guanya per més de 3 dB → no és d'aquesta cabina.
4. L'EPC es tradueix a GTIN amb la taula `etiqueta` o, si no hi és, descodificant l'SGTIN.

Els informes només compten **alta i mitjana** i diuen quantes ambigües s'han descartat. El càlcul és **idempotent**: es pot repetir sobre les mateixes dades (esborra i recalcula les sessions de la cabina).

## Atribució de vendes

`vendes.atribueix`: Shopify i els TPV venen per **GTIN** (model + color + talla), no per peça física.

- Venda amb hora: s'aparella amb la prova **més antiga** del mateix GTIN, mateixa botiga i mateix dia, que hagi **començat abans** de la venda. Regla `mateix_gtin_hora`.
- Venda només amb data: qualsevol prova lliure del mateix GTIN i dia. Regla `mateix_gtin_dia`.
- Una venda ↔ una prova. Les devolucions (quantitat negativa) no s'atribueixen.
- **Venut sense provar** = unitats venudes − vendes atribuïdes.
- No s'atribueixen vendes en línia ni d'una altra botiga.

## Grup de control

`control.sorteja`: per a cada dia de la setmana, la meitat de les setmanes és «amb» i l'altra «sense», barrejat amb una llavor fixa (reproduïble i auditable). La fitxa consulta el grup del dia (`control.mostra_origen`) i amaga la secció d'origen els dies «sense». Cada sessió de cabina i cada esdeveniment NFC guarda el grup.

L'informe només dona la diferència si cada grup té **≥ 30 proves** **(proposta)**; si no, diu «mostra insuficient». Encara **no hi ha prova estadística** (vegeu PENDENT).

## Fitxa NFC i privacitat

- La URL gravada al xip NFC és `/p/{token}?b={botiga}`.
- **Sense galetes, sense JavaScript, sense fonts ni analítica de tercers** (`<meta name="referrer" content="no-referrer">`).
- La «sessió» és un id aleatori que viatja en camps ocults dels formularis, només mentre la pàgina és oberta. No es pot unir amb cap compra ni persona.
- Els tiquets de venda es desen com a hash SHA-256 amb sal, mai en clar.

## Model de dades

Vegeu `hebra/schema.sql`. Taules: `botiga`, `cabina`, `antena`, `catalog_sku`, `etiqueta`, `sensor_event`, `lectura_agregada`, `sessio`, `prova`, `venda_linia`, `atribucio`, `assignacio`, `esdeveniment_nfc`, `peticio_talla`; i des de la v0.2 `usuari`, `estoc`, `recompte_estoc`, `experiment`, `assignacio_model`, `decisio`, `peca_abandonada`, `pilot`, `observacio_manual`, `parametre`. **Cap camp de client** (els usuaris són el personal de la marca i de la botiga).

## Tauler, usuaris i API v2

- **Flux de les dades:** lectures → `proves.py` (sessions i proves) → `vendes.py` (atribució) → `hebra/analitica/` (insights) → `/api/v2/*` → tauler. Els informes i el tauler fan servir els mateixos càlculs.
- **Usuaris i rols:** `admin` (tot), `marca` (totes les botigues de la marca, decisions, experiments, importacions) i `botiga` (només la seva botiga: dependent, peticions, peces abandonades). Contrasenyes amb PBKDF2; sessió amb galeta `HttpOnly` signada (HMAC) i límit d'intents d'entrada.
- **En directe:** `/api/v2/flux` (Server-Sent Events) envia les peticions de talla i les peces abandonades al mòbil del dependent. El bus és en memòria: un sol procés.
- **Processament:** cada `HEBRA_PROCESSA_CADA_MIN` minuts es recalculen proves, atribucions i peces abandonades; cada dia s'esborren les dades en brut més antigues que `HEBRA_RETENCIO_DIES`.
- Contracte complet: [`API.md`](API.md). Pantalles i insights: [`ESPECIFICACIO.md`](ESPECIFICACIO.md).

## API de la passarel·la

Autenticació: capçalera `X-Hebra-Clau`.

- `POST /api/v1/lots` — lot de lectures agregades i sensors (format a `hebra/passarella.py`). Respon quantes n'ha desat i els errors per element.
- `POST /api/v1/processa?botiga=ID` — recalcula proves i atribucions. Al MVP es pot cridar cada nit amb cron.
