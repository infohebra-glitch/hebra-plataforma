# Especificació v0.3 (06-11-2026)

Canvis demanats per l'Iscle després de veure la demo (06-11), més alguns que hi afegim perquè ajuden la botiga sense fer la plataforma molt més complexa. **Aquest document és el contracte** entre backend i frontend per a la v0.3: les formes JSON d'aquí manen. Quan una part estigui feta, s'afegeix a `docs/API.md`.

Convencions: les de `docs/API.md` (base `/api/v2`, fraccions 0-1, dates ISO, errors `{"detail"}` en català, rols admin/marca/botiga, filtre comú `botiga`,`des`,`fins`).

Principis que no canvien: cap dada personal del client final (ni correus de clients, ni galetes a la fitxa), només proves de confiança alta i mitjana, "mostra petita" quan n'hi ha poques, el grup de control de l'origen continua manant sobre si la fitxa ensenya l'origen.

---

## A. Fitxa NFC configurable per la marca (i vinculada al tauler)

La marca decideix què veu el client quan toca l'etiqueta. Configuració a dos nivells: **general** (`botiga_id = '*'`) i **per botiga** (sobreescriu camps de la general). I contingut **per model**.

### A.1 Configuració de la fitxa

Taula `config_fitxa (botiga_id TEXT PRIMARY KEY, config_json TEXT NOT NULL, actualitzada TEXT NOT NULL)`.

```json
ConfigFitxa = {
  "seccions": {                       // què es mostra i en quin ordre (ordre de la llista)
    "ordre": ["talles", "composicio", "origen", "cura", "combina", "faq"],
    "visibles": {"talles": true, "composicio": true, "origen": true, "cura": true, "combina": true, "faq": true}
  },
  "accions": {                        // botons del client
    "demana_talla": true,
    "demana_assistencia": true,       // NOU: «Vull que m'atenguin» → avís a la web del dependent
    "per_que_no": true,               // «Per què no te l'emportes?»
    "mostra_estoc": "disponibilitat"  // "no" | "disponibilitat" (hi ha / no hi ha) | "unitats"
  },
  "idiomes": ["ca", "es", "fr", "en"],  // idiomes oferts; el primer és el per defecte
  "textos": {                          // textos propis de la marca (opcional, per idioma)
    "benvinguda": {"ca": "...", "es": "..."},
    "peu": {"ca": "..."}
  },
  "aparença": {"color_principal": "#214F46", "logo_data_url": null, "nom_marca": "Hebra"},
  "motius": ["talla", "preu", "tall", "qualitat", "color", "nomes_mirava"]   // opcions de «per què no»
}
```

- La fitxa (`/p/{token}`) aplica la configuració efectiva (`'*'` + botiga). L'origen només es mostra si està visible **i** el grup de control del dia ho permet.
- `logo_data_url`: imatge PNG/SVG en data URI, màxim 100 KB (validar-ho).
- Validacions: seccions i motius només dels valors coneguts; color `#RRGGBB`.

### A.2 Contingut per model

Taula `contingut_model (model TEXT, idioma TEXT, camps_json TEXT, actualitzat TEXT, PRIMARY KEY (model, idioma))`. Camps (tots opcionals; si no hi són, es fa servir el que ve del fitxer d'origen `origen_json`):

```json
ContingutModel = {"nom": "...", "descripcio": "...", "ajust": "...", "cura": ["..."],
                  "guia_talles": "...", "faq": [{"q": "...", "a": "..."}], "combina": ["MODEL-1", "MODEL-2"]}
```

### A.3 Rutes

| Ruta | Rol | Què fa |
|---|---|---|
| `GET /fitxa/config?botiga=` | marca+ | `{"general": ConfigFitxa, "botiga": ConfigFitxa parcial o null, "efectiva": ConfigFitxa}` |
| `PUT /fitxa/config?botiga=` | marca+ | desa la general (sense `botiga`) o la d'una botiga (parcial) → igual que GET |
| `GET /fitxa/models` | marca+ | `{"models": [{"model","nom","categoria","idiomes_amb_contingut": ["ca"], "te_origen": true}]}` |
| `GET /fitxa/models/{model}` | marca+ | `{"model", "contingut": {"ca": ContingutModel, ...}, "origen": {...origen_json...}}` |
| `PUT /fitxa/models/{model}/{idioma}` | marca+ | desa `ContingutModel` → `{"ok": true}` |
| `GET /fitxa/previsualitza?model=&botiga=&idioma=` | marca+ | HTML de la fitxa tal com la veuria el client (per a un iframe), **sense** registrar cap esdeveniment |

### A.4 Assistència des de la fitxa (NOU)

- La taula `peticio_talla` passa a tenir `tipus TEXT NOT NULL DEFAULT 'talla' CHECK (tipus IN ('talla','assistencia'))`. Una petició d'assistència té `gtin_demanat = gtin_origen` i `talla_demanada = ''`.
- Migració: com que SQLite no canvia CHECK, `db.inicialitza` fa `ALTER TABLE peticio_talla ADD COLUMN tipus ...` si la columna no hi és (idempotent).
- Fitxa: `POST /p/{token}/assistencia` (formulari, camp opcional `cabina`) → missatge «Ara ve algú a la cabina».
- `Peticio` (JSON de `/peticions` i del flux) guanya `"tipus": "talla" | "assistencia"`. La web del dependent les mostra a la mateixa llista, amb un distintiu «Assistència».
- Analítica: el servei compta les dues; `servei` afegeix `"peticions_assistencia": n`.

### A.5 Disponibilitat en altres botigues (NOU, petit)

Quan una talla demanada no hi és, `Peticio` porta `"altres_botigues": [{"botiga_id","nom","unitats"}]` (de la taula `estoc`), perquè el dependent pugui oferir-la.

---

## B. Provadors en directe

### B.1 Estat de cada cabina

`GET /provadors/directe?botiga=` (tots els rols; botiga només la seva):

```json
{"generat": "...", "cabines": [
  {"cabina_id": "BCN-01-C1", "nom": "Cabina 1", "botiga_id": "BCN-01",
   "estat": "ocupada" | "lliure" | "porta_oberta" | "sense_dades",
   "des_de": "2026-11-06T12:01:10+01:00",       // inici de l'estat actual
   "peces": [{"epc": "...", "model": "VV-26-VRD", "nom": "Vestit de viscosa", "talla": "38", "color": "Verd", "des_de": "..."}],
   "peticions_obertes": 1,
   "avui": {"sessions": 14, "proves": 31, "durada_mitjana_s": 312}}
], "resum": {"ocupades": 2, "lliures": 1, "sessions_avui": 40, "proves_avui": 88}}
```

- Estat a partir dels darrers `sensor_event` (porta/presència) i de les lectures dels darrers 60 s (peces dins: EPC llegits per les antenes de la cabina amb RSSI ≥ llindar en els darrers 60 s). `sense_dades` si no hi ha res en 2 h.
- Flux SSE `/flux`: nou tipus d'esdeveniment `cabina` amb el mateix objecte de cabina, publicat quan entra un lot de la passarel·la que afecta la cabina (com a molt un cop cada 5 s per cabina).

### B.2 On es veu

- Tauler: pantalla nova **Provadors en directe** (menú «Botiga»), targetes per cabina que s'actualitzen soles.
- Web del dependent: franja superior amb l'estat de les cabines (compacte).

---

## C. Sessions de provador: anàlisi nova

`GET /sessions` (filtre comú) → `analitica.sessions`:

```json
{"kpi": {"sessions": 252, "peces_per_sessio_mitjana": 2.3, "peces_per_sessio_mediana": 2,
         "durada_mitjana_s": 340, "pct_sessions_amb_compra": 0.41},
 "per_nombre_peces": [            // sessions amb 1, 2, 3, 4 i 5+ peces
   {"peces": "1", "sessions": 80, "amb_compra": 40, "conversio_sessio": 0.5, "unitats_comprades": 41},
   {"peces": "5+", ...}],
 "provades_juntes": [             // parells de models a la mateixa sessió (mínim 3 sessions)
   {"model_a","nom_a","model_b","nom_b","sessions": 18, "lift": 2.1, "conversio_conjunta": 0.33}],
 "mateix_model_diferent_talla": { // la mateixa peça en dues talles o més a la mateixa sessió
   "sessions": 37, "pct_sessions": 0.15,
   "parells_talla": [{"model","nom","talles": "XS+S","sessions": 9, "comprada": {"XS": 2, "S": 5, "cap": 2}}],
   "per_model": [{"model","nom","sessions_dubte": 12, "pct_sessions_model": 0.22, "talla_mes_comprada": "S"}]},
 "per_durada": [{"tram": "<2 min" | "2-5 min" | "5-10 min" | ">10 min", "sessions", "conversio_sessio"}],
 "per_hora": [{"hora": 11, "sessions", "conversio_sessio"}]}
```

Definicions:
- *Peces per sessió*: EPC diferents amb prova vàlida a la sessió.
- *Sessió amb compra*: alguna de les seves proves té venda atribuïda.
- *Lift* de dos models = P(A i B a la mateixa sessió) / (P(A)·P(B)).
- *Mateix model, diferent talla*: dos o més GTIN del mateix model i color, de talles diferents. «comprada» diu quina talla s'ha acabat comprant (o «cap»). Ens diu si el patró genera dubte de talla.
- `mostra_petita` (bool) a cada fila amb menys de 10 sessions.

Al tauler: pantalla nova **Sessions** (menú «Tauler»), amb gràfic de barres per nombre de peces (sessions i % amb compra), taula de peces provades juntes, i bloc «Dubte de talla» (mateix model en dues talles). A la fitxa de cada peça: bloc «Dubte de talla» d'aquell model.

---

## D. Estoc parat amb eines per a la botiga

`GET /estoc` amplia la resposta actual (es mantenen els camps que ja hi ha):

```json
"parat": [{"gtin","model","nom","color","talla","categoria","botiga_id","unitats","valor_eur",
           "dies_parat": 34, "darrera_prova": "..."|null, "darrera_venda": "..."|null,
           "proves_altres_botigues": 12, "vendes_altres_botigues": 3,
           "suggeriment": {"accio": "traspassar" | "moure_a_sala" | "promocio" | "retornar" | "revisar",
                           "text": "Traspassar 2 unitats a Girona: allà s'ha provat 12 vegades.",
                           "botiga_desti": "GIR-01" | null},
           "tasca": Tasca | null}],
"resum_parat": {"unitats": 41, "valor_eur": 2450.0, "per_categoria": [{"categoria","unitats","valor_eur"}]}
```

- Regles del suggeriment (simples i explicades): si una altra botiga el prova o el ven més → `traspassar`; si no s'ha provat mai a la botiga i hi ha unitats → `moure_a_sala` (probablement no és visible); si s'ha provat i no es ven (conversió baixa) → `promocio` o `revisar`; si fa > 60 dies i no es mou enlloc → `retornar`. Els llindars van a `parametre`.

### D.1 Tasques de botiga (NOU)

Taula `tasca (id, botiga_id, tipus TEXT, titol TEXT, detall TEXT, gtin TEXT, unitats INTEGER, botiga_desti TEXT, estat TEXT CHECK (estat IN ('pendent','feta','descartada')), creada TEXT, creada_per INTEGER, feta TEXT, feta_per INTEGER)`.

`Tasca = {"id","botiga_id","tipus","titol","detall","gtin","unitats","botiga_desti","estat","creada","feta"}`

| Ruta | Rol | |
|---|---|---|
| `GET /tasques?botiga=&estat=` | tots (botiga, la seva) | `{"tasques": [Tasca]}` |
| `POST /tasques` | marca+ i botiga (la seva) | crea (p. ex. des d'un suggeriment d'estoc parat) → Tasca |
| `PATCH /tasques/{id}` | idem | `{"estat": "feta"|"descartada"}` → Tasca |

- Tipus: `traspassar`, `moure_a_sala`, `promocio`, `retornar`, `recompte`, `altre`.
- La web del dependent mostra les tasques pendents de la seva botiga (secció «Tasques»), amb botó «Feta».
- Al tauler, pantalla Estoc: filtre per categoria, ordenació per valor o per dies, botó «Crea la tasca» a cada suggeriment, botó «Crea tasques per a tots els seleccionats», i **Descarrega CSV** (`GET /estoc/parat.csv`, mateix filtre).

---

## E. Informes: programats, lliurats, PDF i correu

### E.1 Model

- Els informes deixen de ser «tots els tipus junts». Hi ha **informes lliurats**: cada informe generat queda guardat (instantània JSON), amb data, tipus, període i destinataris.
- Taula `programacio_informe (id, botiga_id TEXT NULL, tipus TEXT, actiu INTEGER, dia_setmana INTEGER NULL, dia_mes INTEGER NULL, data TEXT NULL, hora TEXT, destinataris TEXT /*JSON llista de correus*/, creada TEXT)`.
  - `diari`: cada dia a `hora` (resum del dia anterior).
  - `setmanal`: `dia_setmana` (0 = dilluns) a `hora` (setmana anterior, dilluns-diumenge).
  - `mensual`: `dia_mes` (1-28) a `hora` (mes anterior).
  - `temporada`, `pilot`, `mango`: en una `data` concreta (una vegada).
- Taula `informe_lliurat (id, programacio_id NULL, botiga_id NULL, tipus, des, fins, generat TEXT, dades_json TEXT, enviat_a TEXT /*JSON*/, estat_enviament TEXT /*'no_enviat'|'enviat'|'error'*/, error TEXT NULL)`.
- El bucle de fons (com el de processament) mira cada minut si toca generar algun informe; si toca, el genera, el guarda i l'envia per correu (si hi ha SMTP configurat).

### E.2 Contingut més útil (cada informe porta gràfics)

Cada informe JSON (`GET /informes/...`) passa a tenir, a més dels blocs actuals, una llista de **gràfics** que el frontend i el PDF dibuixen igual:

```json
"grafics": [{"id": "conversio_setmanal", "titol": "Conversió de provador per setmana",
             "tipus": "linia" | "barres" | "barres_apilades" | "donut",
             "unitat": "pct" | "enter" | "eur" | "segons",
             "eix_x": ["S45", "S46"], "series": [{"nom": "Conversió", "valors": [0.31, 0.29]}],
             "nota": "..." }],
"xifres": [{"etiqueta": "Proves", "valor": 403, "unitat": "enter", "variacio": 0.04, "vs": "setmana anterior"}]
```

Mínim per tipus:
- **Diari** (encarregada, 5 línies + 3 xifres): proves, compres, peticions i temps de resposta, peces oblidades, talla més demanada sense estoc; gràfic de sessions per hora.
- **Setmanal**: xifres amb variació vs setmana anterior (proves, conversió, venut sense provar, demanda perduda en € estimats, temps de resposta); gràfics: proves i compres per dia, conversió per categoria, top 5 i cua 5 de models per conversió, peces per sessió; acció de la setmana.
- **Mensual d'accions**: decisions del mes i el seu resultat (abans/després), conversió per setmana del mes, estoc parat (unitats i €), valor estimat recuperat, demanda perduda per model.
- **Fi de temporada**: corba de talles provada vs comprada per categoria, models a repetir / a canviar (conversió i motius), dubte de talla per model, efecte de l'origen, recomanacions per a la propera comanda.
- **Pilot / gran marca**: com ara, amb gràfics de conversió setmanal amb/sense origen i KPI pactats.

### E.3 PDF i correu

- `GET /informes/lliurats/{id}.pdf` i `GET /informes/{tipus}.pdf?<filtre>`: PDF generat al servidor amb **WeasyPrint** a partir d'una plantilla HTML (`hebra/templates/informe_pdf.html`) amb gràfics SVG fets al servidor (`hebra/grafics_svg.py`, sense JS). A4, capçalera amb el nom de la marca i el període, peu «Dades de Hebra · pàgina X de Y».
- `POST /informes/lliurats/{id}/envia` `{"destinataris": ["a@marca.cat"]}` → envia el PDF adjunt per correu → `{"ok": true}` o 400 amb el motiu (sense SMTP configurat, correu no vàlid).
- `POST /informes/{tipus}/envia?<filtre>` igual però generant-lo al moment.
- Correu: `hebra/correu.py` amb `smtplib` (STARTTLS), variables `HEBRA_SMTP_HOST`, `HEBRA_SMTP_PORT` (587), `HEBRA_SMTP_USUARI`, `HEBRA_SMTP_CONTRASENYA`, `HEBRA_SMTP_REMITENT`. Sense configuració: el botó d'enviar respon 400 «El correu no està configurat».
- `requirements.txt` afegeix `weasyprint`; INSTAL-LACIO afegeix `apt install libpango-1.0-0 libpangoft2-1.0-0` (dependències de WeasyPrint).

### E.4 Rutes

| Ruta | Rol | |
|---|---|---|
| `GET /informes/programacio?botiga=` | marca+ (botiga veu les seves, només lectura) | `{"programacions": [Programacio]}` |
| `POST /informes/programacio` | marca+ | crea → Programacio |
| `PATCH /informes/programacio/{id}` | marca+ | canvia camps / `actiu` → Programacio |
| `DELETE /informes/programacio/{id}` | marca+ | → `{"ok": true}` |
| `GET /informes/lliurats?botiga=&tipus=` | tots (botiga, els seus) | `{"lliurats": [{"id","tipus","botiga_id","des","fins","generat","estat_enviament","enviat_a"}]}` (més nous primer) |
| `GET /informes/lliurats/{id}` | idem | l'informe JSON guardat (mateixa forma que `/informes/{tipus}`) |
| `POST /informes/lliurats` | marca+ | `{"tipus","botiga","des","fins"}` genera i guarda ara («Genera ara») → resum del lliurat |

`Programacio = {"id","botiga_id","tipus","actiu","dia_setmana","dia_mes","data","hora","destinataris","propera": "2026-11-09T08:00:00+01:00"}`

### E.5 Al tauler

Pantalla **Informes** reorganitzada:
1. **Lliurats**: llista per data (els diaris de la setmana, el setmanal, el mensual...), filtre per tipus; cada fila obre l'informe, amb **Descarrega PDF** i **Envia per correu**.
2. **Programació** (marca+): quins informes es generen, quan i a qui s'envien. Formulari senzill.
3. Un informe obert: xifres a dalt, gràfics, blocs, acció; els mateixos gràfics que al PDF.

El simulador crea programacions per defecte (diari 08:00, setmanal dilluns 08:00, mensual dia 1 08:00, temporada en una data) i genera els lliurats de les setmanes simulades, perquè la demo tingui una llista realista.

---

## F. Integracions: Shopify real, TPV, catàleg i estoc dins la plataforma

### F.1 Model

- Taula `integracio (id, botiga_id TEXT NULL /*NULL = tota la marca*/, proveidor TEXT CHECK (proveidor IN ('shopify','square','csv_url')), config_json TEXT, secret_xifrat TEXT, actiu INTEGER, abast TEXT /*JSON: ["cataleg","vendes","estoc"]*/, darrera_sync TEXT, estat TEXT /*'ok'|'error'|'mai'*/, missatge TEXT, creada TEXT)`.
- Taula `sync_registre (id, integracio_id, inici, fi, estat, resum_json, error)`.
- Els secrets (testimonis d'accés) es desen **xifrats** amb Fernet (llibreria `cryptography`) amb una clau derivada de `HEBRA_SECRET` (HKDF). Mai es tornen per l'API (només `"te_secret": true`). Les variables `HEBRA_SHOPIFY_TOKEN_<BOTIGA>` continuen funcionant per compatibilitat.

### F.2 Connectors (`hebra/integracions/`)

Cada connector implementa `prova(config, secret) -> dict`, `cataleg(...)`, `vendes(des, fins)`, `estoc()`, i tots fan servir les funcions existents per desar (`cataleg`, `vendes`, `estoc`) perquè la resta de la plataforma no canviï.

- **Shopify** (Admin REST API, versió fixada; app personalitzada amb testimoni `shpat_...`, permisos de només lectura `read_products`, `read_orders`, `read_inventory`, `read_locations`):
  - catàleg: productes i variants → `catalog_sku` (GTIN del codi de barres; model = `product_id` o SKU base configurable; talla i color de les opcions amb noms configurables, per defecte «Talla»/«Size» i «Color»; categoria = `product_type`; preu).
  - vendes: comandes de la ubicació de la botiga (POS i, si es vol, en línia), **incloent reemborsaments** com a línies negatives (`devolucio = 1`).
  - estoc: nivells d'inventari de la ubicació.
  - `prova`: crida `shop.json` i `locations.json` i retorna el nom de la botiga i les ubicacions (per triar-ne una al formulari).
- **Square** (API REST v2, testimoni d'accés): catàleg (`catalog/list` ITEM i ITEM_VARIATION, GTIN del camp `upc`/`sku`), vendes (`orders/search` per ubicació, devolucions com a negatives), estoc (`inventory/counts/batch-retrieve`).
- **CSV per URL** (per a TPV que exporten un fitxer, p. ex. Ágora, Revo, Lightspeed): una URL HTTPS per a vendes, una per a estoc i una per a catàleg (cada una opcional), amb capçalera d'autorització opcional; descarrega i importa amb els importadors existents.
- Tots els connectors tenen proves amb respostes falses (no cal xarxa).

### F.3 Sincronització

- Bucle de fons: cada integració activa es sincronitza cada `interval_min` (per defecte 60; mínim 15). Vendes: des de la darrera sincronització menys 2 dies (per agafar devolucions). Després de les vendes, `vendes.atribueix`.
- Rutes:

| Ruta | Rol | |
|---|---|---|
| `GET /integracions` | marca+ | `{"integracions": [Integracio]}` |
| `POST /integracions` | marca+ | `{"botiga_id","proveidor","config","secret","abast","interval_min"}` → Integracio |
| `PATCH /integracions/{id}` | marca+ | canvia config / secret / actiu |
| `DELETE /integracions/{id}` | marca+ | |
| `POST /integracions/prova` | marca+ | `{"proveidor","config","secret"}` → `{"ok": true, "detall": {...}}` o 400 amb el motiu |
| `POST /integracions/{id}/sincronitza` | marca+ | sincronitza ara → `{"resum": {"cataleg": n, "linies_venda": n, "devolucions": n, "estoc": n}}` |
| `GET /integracions/{id}/registre` | marca+ | `{"registre": [{"inici","fi","estat","resum","error"}]}` (darreres 20) |

`Integracio = {"id","botiga_id","proveidor","config","te_secret","actiu","abast","interval_min","darrera_sync","estat","missatge"}`

### F.4 Al tauler

La pantalla **Importa dades** passa a ser **Connexions i dades**: targetes per a Shopify, Square i CSV per URL (connectar, provar, triar ubicació, què sincronitzar, sincronitza ara, registre), i a sota la pujada manual de CSV que ja hi ha.

---

## G. Tema clar / fosc

- Només dues opcions: **Clar** (per defecte) i **Fosc**. Es treu la de «sistema». Es desa al navegador (`localStorage`, amb try/catch). El selector és al menú de l'usuari.

---

## H. Altres canvis petits que ajuden la botiga (decidits per Claude)

1. **Assistència des de la fitxa** (A.4) i **disponibilitat en altres botigues** (A.5).
2. **Tasques de botiga** a la web del dependent (D.1): una sola llista del que cal fer avui.
3. **Provadors en directe** a la web del dependent (B.2).
4. Resum diari per correu (E): tanca el forat del manual (capítol 13.2).

Fora d'abast d'aquesta versió: filtres per cabina/categoria a totes les pantalles, pantalla per entrar l'observació manual, etiquetes de recanvi des del tauler (es mantenen a `docs/PENDENT.md`).
