# Hebra · Plataforma (MVP)

Hebra diu a una marca de moda **què es prova i no es ven, per què, i si el que hi canvia fa vendre més** (inclòs ensenyar l'origen de la peça), demostrat amb grup de control.

Aquest repositori és la primera versió de la plataforma per al **pilot de 8 setmanes**. Es basa en el document *Proposta MVP abans del pilot* (30-10-2026) i en les decisions posteriors:

- L'etiqueta de cada peça és **doble: RFID UHF + NFC**. L'UHF el llegeix el lector de la cabina (proves). L'NFC el toca el client amb el mòbil i obre la fitxa de la peça. Sense QR.
- L'**origen és una variable que es mesura**: uns dies la fitxa l'ensenya i uns altres no.
- **Cap dada personal.** Ni càmeres, ni galetes, ni comptes de client.

> Totes les dades del repositori són **inventades** (dades de prova). Cap xifra és d'una marca real.
>
> Funciona de dues maneres: amb el **simulador** (per provar-ho sense res) o amb **maquinari real** (lector Impinj R700 + Raspberry Pi + sensors de cabina). La instal·lació real és a [`docs/INSTAL-LACIO.md`](docs/INSTAL-LACIO.md).

## Què fa

| Part | On és | Què fa |
|---|---|---|
| Entrada de la passarel·la | `hebra/passarella.py`, `POST /api/v1/lots` | Rep lectures UHF agregades i esdeveniments de porta i presència de cada cabina. |
| Motor de proves | `hebra/proves.py` | Converteix lectures en **sessions de cabina** i **proves** (≥ 60 s, ≥ 5 lectures, RSSI per sobre del llindar, confiança alta, mitjana o ambigua). |
| Vendes | `hebra/vendes.py`, `/botiga/vendes` | Importa vendes en CSV i les **atribueix** a proves: mateix GTIN, mateixa botiga, entre l'inici de la prova i el tancament del dia. |
| Grup de control | `hebra/control.py` | Sorteja per dies si la fitxa ensenya l'origen («amb») o no («sense»), equilibrat per dia de la setmana. |
| Fitxa NFC | `hebra/fitxa.py`, `/p/{token}` | La pàgina que s'obre al mòbil: talles, composició, origen, cura, **demanar una altra talla** i **«per què no te l'emportes?»**. En català, castellà, francès i anglès. |
| Web del dependent | `/botiga/peticions` | Llista de talles demanades des de la fitxa, per portar-les a la cabina. |
| Informe setmanal | `hebra/informes.py`, `/botiga/informe` | «Provat, venut, convertit» per model, categoria i talla; efecte de l'origen amb i sense; demanda perduda; motius de no compra; una acció de la setmana. |
| Passarel·la real | `hebra_passarella/` | Programa de la Raspberry Pi: llegeix el lector R700 (API REST d'Impinj), els sensors de porta i presència pels GPIO, agrupa lectures cada 10 s i les envia; guarda 7 dies si cau la xarxa. |
| Administració | `hebra/admin.py` | Alta de botiga, cabines i antenes; catàleg de la marca en CSV; fitxa d'origen; etiquetes (EPC ↔ URL NFC amb codi aleatori); grup de control. |
| Simulador | `hebra/simulador.py` | Omple la base de dades amb una botiga de 3 cabines i setmanes de pilot simulades, per veure-ho tot funcionant sense maquinari. |
| Descodificador EPC | `hebra/epc.py` | SGTIN-96 (hex o URN) a GTIN-14 i número de sèrie (estàndard GS1). |

L'arquitectura i les regles en detall són a [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md). Les decisions obertes i el que falta són a [`docs/PENDENT.md`](docs/PENDENT.md).

## Posar-ho en marxa (local)

Cal Python 3.11 o més nou.

```bash
git clone https://github.com/infohebra-glitch/hebra-plataforma.git
cd hebra-plataforma
python3 -m venv .venv
source .venv/bin/activate            # a Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# 1. Omple la base de dades amb 2 setmanes de pilot simulat (crea hebra.db)
python -m hebra.simulador --setmanes 2 --inici 2026-11-16

# 2. Arrenca la web
uvicorn hebra.app:app --reload
```

Obre <http://localhost:8000>. Usuari i contrasenya de la zona de botiga per defecte: `botiga` / `hebra`.

- Fitxa NFC d'exemple: enllaç a la pàgina d'inici.
- Informe: <http://localhost:8000/botiga/informe?b=BCN-01&setmana=2026-11-16>
- Documentació de l'API: <http://localhost:8000/api/docs>

### Proves automàtiques

```bash
pytest
```

Cobreixen la descodificació d'EPC, la detecció de sessions i proves, la confiança amb cabines veïnes, l'atribució de vendes, el sorteig del grup de control i les pàgines web (incloent-hi que la fitxa no posa cap galeta).

## Configuració

Per variables d'entorn (vegeu [`.env.example`](.env.example)). Per carregar-les: `set -a; source .env; set +a`.

| Variable | Per defecte | Per a què serveix |
|---|---|---|
| `HEBRA_BD` | `hebra.db` | Fitxer de la base de dades SQLite. |
| `HEBRA_CLAU_PASSARELLA` | `canvia-aquesta-clau` | Clau que la passarel·la envia a la capçalera `X-Hebra-Clau`. |
| `HEBRA_USUARI_BOTIGA` / `HEBRA_CONTRASENYA_BOTIGA` | `botiga` / `hebra` | Accés a la web del dependent, vendes i informe. |
| `HEBRA_SAL_TIQUET` | `hebra-mvp` | Sal per xifrar l'id de tiquet de les vendes. |
| `HEBRA_PROVA_DURADA_S`, `HEBRA_PROVA_LECTURES`, `HEBRA_MARGE_*`, `HEBRA_TANCAMENT_SESSIO_S` | 60, 5, 6/3 dB, 10 s | Regla de prova. Es calibren a la setmana 0 del pilot. |

**Abans de fer-ho servir amb una botiga real cal canviar totes les claus i contrasenyes.**

## Maquinari real

Resum (detall a [`docs/INSTAL-LACIO.md`](docs/INSTAL-LACIO.md)):

1. **Servidor**: `uvicorn` + Caddy (HTTPS), amb els fitxers de `desplegament/`.
2. **Raspberry Pi**: `python3 -m hebra_passarella /etc/hebra/passarella.toml` (servei systemd inclòs).
3. **Dades**: `python -m hebra.admin botiga|cataleg|origen|etiquetes|control`.

## Com encaixa amb el maquinari

```
Etiqueta UHF+NFC ─► antena de cabina ─► lector Impinj R700 ─► passarel·la (Raspberry Pi 5)
                                                               │  filtra, agrega cada 5-10 s,
                                                               │  guarda 7 dies si cau la xarxa
Sensors de porta i presència (per cable) ──────────────────────┘
                                                               ▼
                                         POST /api/v1/lots  (aquesta plataforma, al núvol)
                                                               ▼
                         proves ─► + vendes CSV ─► atribució ─► informe setmanal
Mòbil del client ─(toc NFC)─► /p/{token}?b=BOTIGA ─► fitxa, petició de talla, motiu
```

La passarel·la real és a `hebra_passarella/`. **Encara no s'ha provat amb un R700 de veritat**: els camins de l'API són configurables i s'han de comprovar a la documentació del lector (vegeu PENDENT).

## Estructura

```
hebra/
  app.py           web i API (FastAPI)
  config.py        configuració i regla de prova
  schema.sql       model de dades (cap camp de persona)
  db.py            connexió a la base de dades
  epc.py           SGTIN-96 → GTIN
  cataleg.py       importació del catàleg i de l'origen (format hebra-origen/0.2)
  passarella.py    entrada de lectures i sensors
  proves.py        sessions i proves
  vendes.py        CSV de vendes i atribució
  control.py       grup de control per dies
  fitxa.py         lògica de la fitxa NFC
  informes.py      informe setmanal
  textos.py        textos de la fitxa en 4 idiomes
  admin.py         alta de botiga, catàleg, etiquetes i grup de control
  simulador.py     pilot simulat
  templates/       pàgines (Jinja2)
  static/          estil
hebra_passarella/         programa de la Raspberry Pi (lector, sensors, cua, enviament)
desplegament/             serveis systemd, Caddy i exemples de configuració
dades/origen-prova.json   4 peces de prova (inventades)
tests/                    proves automàtiques
docs/                     arquitectura i pendents
```
