# Contracte de l'API del tauler (v2)

Aquest document és el **contracte** entre tres parts que es desenvolupen per separat:

- `hebra/analitica/` calcula les dades (funcions pures sobre la base de dades),
- `hebra/api/` les exposa (FastAPI, autenticació, permisos),
- `frontend/` les pinta (tauler de la marca i web del dependent).

Si una forma canvia, s'ha de canviar aquí primer.

## Convencions

- Base: `/api/v2`. JSON en UTF-8. Dates `AAAA-MM-DD`; hores ISO 8601 amb desplaçament.
- **Autenticació**: `POST /api/v2/sessio` amb `{"correu","contrasenya"}` posa una galeta `hebra_sessio` (HttpOnly, SameSite=Lax, Secure en producció, signada amb `HEBRA_SECRET`). Totes les altres rutes `/api/v2/*` la requereixen (401 si no). La fitxa NFC del client final **no** fa servir galetes; això és només per a l'equip de la marca.
- **Rols**: `admin` (tot), `marca` (totes les botigues de lectura + decisions/experiments), `botiga` (només la seva botiga: peticions, alertes, abandonades, vendes/estoc).
- **Filtre comú** (query): `botiga` (opcional; sense = totes les permeses), `des`, `fins` (per defecte: els darrers 7 dies amb dades). A Python: `hebra.analitica.Filtre(botiga_id, des, fins)`.
- Conversions i percentatges com a **fracció 0-1** (`0.34`), o `null` si no hi ha denominador. Diners en euros (`float`).
- Només compten proves de confiança `alta` i `mitjana`.
- Errors: `{"detail": "missatge en català"}` amb 400/401/403/404.

## Sessió

| Mètode i ruta | Cos / resposta |
|---|---|
| `POST /sessio` | `{"correu","contrasenya"}` → `{"usuari": Usuari}` + galeta |
| `DELETE /sessio` | esborra la galeta → `{"ok": true}` |
| `GET /jo` | `{"usuari": Usuari, "botigues": [{"id","nom","nivell"}]}` |

`Usuari = {"id","nom","correu","rol","botiga_id"}`

## Analítica (GET, totes accepten el filtre comú)

Cada ruta crida la funció homònima de `hebra.analitica` (`resum(con, f)`, `models(con, f)`, ...).

### `GET /resum` → `analitica.resum`
```json
{
  "periode": {"des": "2026-11-16", "fins": "2026-11-22", "dies": 7},
  "kpi": {
    "proves": 538, "compres_atribuides": 183, "conversio": 0.34,
    "conversio_periode_anterior": 0.31, "variacio_conversio": 0.03,
    "sessions": 340, "peces_per_sessio": 1.6,
    "unitats_venudes": 190, "venut_sense_provar": 7, "venut_sense_provar_pct": 0.037,
    "peticions_talla": 35, "temps_resposta_mediana_s": 92, "pct_resposta_sota_90s": 0.48,
    "peces_abandonades": 4, "demanda_perduda": 9,
    "respostes_motiu": 61, "taxa_resposta_motiu": 0.12,
    "proves_ambigues": 80
  },
  "serie_diaria": [{"data": "2026-11-16", "proves": 90, "compres": 30, "conversio": 0.33, "grup_origen": "amb"}],
  "accio": Accio | null,
  "alertes_obertes": 3
}
```
`Accio = {"text", "insight", "model", "responsable", "data_limit"}` (una sola, la més clara).

### `GET /models` → `analitica.models`
```json
{"models": [{
  "model": "VV-26-VRD", "nom": "Vestit de viscosa", "categoria": "vestit", "preu": 79.0,
  "proves": 116, "compres": 22, "conversio": 0.19,
  "conversio_categoria": 0.25, "quartil_categoria": 1,
  "molt_provat_poc_venut": true, "venut_sense_provar": 2,
  "estoc": 14, "motiu_principal": "talla", "demanda_perduda": 2
}]}
```
Regla «molt provat, poc venut» (insight 3): proves ≥ `N` al període (paràmetre `n_molt_provat`, per defecte 10 per setmana del període) i conversió al quartil inferior de la seva categoria (o < 60 % de la mitjana si la categoria té < 4 models).

### `GET /models/{model}` → `analitica.model_detall(con, f, model)`
```json
{
  "model": "CL-24-NAT", "nom": "Camisa de lli", "categoria": "camisa", "color": "Natural", "preu": 69.0,
  "kpi": {"proves": 146, "compres": 62, "conversio": 0.42, "venut_sense_provar": 3, "respostes_motiu": 20, "taxa_resposta_motiu": 0.14},
  "talles": [{"talla": "M", "gtin": "...", "proves": 48, "compres": 23, "conversio": 0.48,
              "pct_proves": 0.33, "pct_compres": 0.37, "estoc": 1, "demanda_perduda": 0, "canvis_de_talla": 2}],
  "motius": [{"motiu": "talla", "n": 8, "pct": 0.4}],
  "serie_setmanal": [{"setmana": "2026-11-16", "proves": 70, "compres": 30, "conversio": 0.43}],
  "provat_amb": [{"model": "TX-26-IND", "nom": "Texans", "sessions": 21}],
  "origen": {"etapes": [{"etapa","pais","regio"}], "composicio": [{"material","pct","pais"}]} | null,
  "efecte_origen": Experiment | null
}
```

### `GET /talles` → `analitica.talles`
```json
{
  "taula": [{"categoria": "texans", "talla": "38", "proves": 39, "compres": 11, "conversio": 0.28}],
  "no_quadra": [{"model": "TX-26-IND", "nom": "Texans", "talla": "38", "conversio": 0.12, "conversio_resta_talles": 0.33,
                 "text": "Els texans en 38 es venen a 1 de cada 8 proves; la resta de talles, a 1 de cada 3. Pot ser el patró de la 38."}],
  "corba": [{"model": "JM-24-GRF", "nom": "Jersei", "talles": [
             {"talla": "M", "pct_proves": 0.45, "pct_compres": 0.40, "pct_estoc": 0.30, "proposta_pct": 0.40}]}]
}
```
Corba proposada (insight 5): mitjana de `pct_compres` i `pct_proves` (pes 0,7 / 0,3), arrodonida a 5 punts.

### `GET /demanda-perduda` → `analitica.demanda_perduda`
```json
{"total": 9, "per_variant": [{"model","nom","color","talla","n","estoc"}], "text": "9 peticions de talles que no hi eren; 5 eren la camisa de lli en L."}
```

### `GET /motius` → `analitica.motius`
```json
{"respostes": 61, "sessions_fitxa": 500, "taxa_resposta": 0.12,
 "per_motiu": [{"motiu": "preu", "n": 14, "pct": 0.23}],
 "per_model": [{"model", "nom", "respostes", "motius": {"talla": 3, "preu": 1}}]}
```
Motius: `talla`, `tall`, `preu`, `color`, `qualitat`, `altre`.

### `GET /servei` → `analitica.servei`
```json
{
  "peticions": 35, "peticions_per_sessio": 0.10, "mediana_s": 92, "pct_sota_90s": 0.48,
  "per_estat": {"pendent": 1, "en_cami": 0, "lliurada": 30, "no_disponible": 4},
  "ocupacio": {
    "durada_mitjana_s": 340, "pct_temps_totes_plenes": 0.06,
    "mapa": [{"dia_setmana": 0, "hora": 12, "sessions": 9, "pct_totes_plenes": 0.2}]
  },
  "peces_per_sessio": [{"peces": 1, "sessions": 200, "pct_amb_compra": 0.3}]
}
```
`dia_setmana`: 0 = dilluns.

### `GET /estoc` → `analitica.estoc`
```json
{
  "parat": [{"gtin","model","nom","talla","unitats","dies_sense_activitat"}],
  "risc_rebaixa": [{"model","nom","unitats","cobertura_setmanes","conversio","quartil_categoria"}],
  "precisio": {"recomptes": 3, "error_mitja_pct": 0.04} | null
}
```
Estoc parat (insight 14): unitats > 0 amb 0 proves i 0 vendes en 21 dies (paràmetre `dies_estoc_parat`). Risc de rebaixa (15): cobertura (unitats ÷ vendes setmanals) > `setmanes_cobertura` (8) i conversió al quartil inferior.

### `GET /fitxa-nfc` → `analitica.fitxa_nfc`
```json
{"tocs": 520, "sessions_cabina": 340, "tocs_per_sessio": 1.5,
 "seccions": [{"seccio": "origen", "n": 120, "pct": 0.23}],
 "idiomes": [{"idioma": "ca", "n": 300, "pct": 0.58}]}
```
Seccions: `origen`, `talles`, `cura`, `preguntes`, `motiu`, `peticio_talla`.

### `GET /experiments` → `analitica.experiments`
```json
{"experiments": [Experiment]}
```
```json
Experiment = {
  "id": "origen-2026-11", "variable": "origen", "hipotesi": "...", "unitat": "dia",
  "inici": "2026-11-23", "fi": "2027-01-03", "estat": "actiu",
  "grups": {"amb": {"proves": 187, "compres": 72, "conversio": 0.385},
            "sense": {"proves": 351, "compres": 111, "conversio": 0.316}},
  "diferencia": 0.069, "ic95": [-0.016, 0.154], "p_valor": 0.11,
  "proves_minimes": 30, "mostra_suficient": true, "proves_necessaries": 820,
  "setmanes_restants": 4,
  "conclusio": "Encara no hi ha diferència demostrable (p = 0,11). Falten 4 setmanes."
}
```
Prova de dues proporcions (z) i IC del 95 % de la diferència; `proves_necessaries` per detectar la diferència observada amb potència 0,8.

### `GET /alertes` → `analitica.alertes`
```json
{"alertes": [{"id": "pt-12", "tipus": "peticio_talla", "text": "Cabina 2 demana el jersei de merino en M.",
              "botiga_id": "BCN-01", "cabina": "BCN-01-C2", "creada": "...", "estat": "pendent", "ref": 12}]}
```
Tipus: `peticio_talla`, `talla_esgotada` (≥ 3 peticions del mateix GTIN el mateix dia sense estoc), `peca_abandonada`, `molt_provat_poc_venut`.

### `GET /estat-sistema` → `analitica.estat_sistema`
```json
{"cabines": [{"cabina_id": "BCN-01-C1", "nom": "Cabina 1", "botiga_id": "BCN-01", "darrera_lectura": "...",
              "darrer_sensor": "...", "hores_sense_dades": 0.3, "alerta": false}],
 "darrera_venda": "...", "dies_sense_vendes": 1, "peces_llegides": 412, "peces_desconegudes": 3,
 "pct_desconegudes": 0.007, "hores_alerta": 24, "generat": "...", "periode": {"des": "...", "fins": "..."}}
```
`alerta`: la cabina fa més de `hores_alerta` hores que no envia lectures ni sensors. Les peces desconegudes són EPC llegits al període que no són a la taula `etiqueta`.

### `GET /valor` → `analitica.valor`
```json
{"parametres": {"marge_peca": 40, "quota_mensual": 350, "pvp_mitja": 69},
 "llindar_peces_mes": 9,
 "palanques": [{"palanca": "Menys talles esgotades", "insights": [7], "formula": "Peticions sense estoc × % reposat a temps × % que compra × marge", "valor_eur": 480.0, "detall": "60 × 50 % × 40 % × 40 €", "es_estimacio": true}]}
```

### Informes: `GET /informes/{tipus}` → `analitica.informe(con, f, tipus)`
`tipus`: `diari`, `setmanal`, `mensual`, `temporada`, `pilot`, `mango`.
```json
{"tipus": "setmanal", "titol": "Informe setmanal", "periode": {...},
 "blocs": [{"id": "xifres", "titol": "Tres xifres", "text": "...", "dades": {...}}],
 "accio": Accio | null,
 "avisos": ["Mostra petita: ...", "Vendes per CSV: ..."]}
```
Blocs per tipus (secció 5.2 de la Proposta): **diari** (resum d'ahir); **setmanal** (xifres, top 5 molt provat poc venut, talla que no quadra, demanda perduda, motius, servei, acció); **mensual** (registre de decisions amb resultat, conversió per categoria i talla amb tendència, corba de talles, estoc parat i risc de rebaixa, fitxa NFC i idiomes, prova en curs, valor estimat); **temporada** (rànquing per família i model, feedback de disseny per atribut, corba recomanada, efecte de l'origen, demanda perduda acumulada, unitats per país de fabricació); **pilot** (criteris d'èxit i compliment, qualitat de la dada, proves contra compra, decisions, precisió d'estoc, què no podem afirmar); **mango** (KPI del dossier i «últim metre de l'origen»).

### Historial d'una peça (insight 24): `GET /peces/{epc}/historial`
```json
{"epc","gtin","model","nom","talla","esdeveniments": [{"ts","tipus": "prova"|"venda"|"abandonada"|"nfc","detall"}]}
```

### Senyals de pèrdua (insight 25, només si el paràmetre `senyals_perdua` = `1`): `GET /perdues`
```json
{"actiu": true, "per_zona_hora": [{"cabina","hora","n"}], "total": 3}
```

## Operació

| Ruta | Rol | Cos / resposta |
|---|---|---|
| `GET /peticions?estat=pendent` | botiga+ | `{"peticions": [{"id","model","nom","color","talla","cabina","hora_peticio","estat","disponible","segons_espera"}]}` |
| `PATCH /peticions/{id}` | botiga+ | `{"estat": "en_cami"|"lliurada"|"no_disponible"}` → la petició |
| `GET /abandonades?obertes=1` | botiga+ | `{"abandonades": [{"id","epc","model","nom","talla","cabina","detectada","resolta"}]}` |
| `PATCH /abandonades/{id}` | botiga+ | `{"resolta": true}` |
| `GET /flux` | botiga+ | **Server-Sent Events**: `event: peticio` / `abandonada` / `alerta`, `data: <JSON>` en temps real |
| `GET /decisions` · `POST /decisions` · `PATCH /decisions/{id}` | marca+ | `Decisio = {"id","botiga_id","creada","titol","descripcio","insight","model","responsable","data_limit","estat","experiment_id","resultat"}` |
| `GET /experiments` · `POST /experiments` | marca+ | crear: `{"id","botiga_id","variable","hipotesi","unitat","inici","setmanes","proves_minimes"}`; fa el sorteig |
| `POST /importa/vendes` · `/importa/estoc` · `/importa/cataleg` | botiga+ / admin | fitxer CSV (multipart `fitxer`) → `{"importades","errors":[]}` |
| `POST /recomptes` | botiga+ | `{"botiga_id","data","gtin","manual","rfid"}` |
| `GET /parametres` · `PUT /parametres` | marca+ / admin | `{"botiga_id": "*", "valors": {"marge_peca": "40", ...}}` |
| `POST /shopify/sincronitza?botiga=` | admin | sincronitza comandes i estoc → `{"comandes","linies","estoc"}` |
| `GET /usuaris` · `POST /usuaris` | admin | gestió d'usuaris |

Paràmetres coneguts (`parametre`): `marge_peca`, `quota_mensual`, `n_molt_provat`, `dies_estoc_parat`, `setmanes_cobertura`, `minuts_abandonada` (30), `senyals_perdua` (0/1), `shopify_domini`, `shopify_ubicacio`.

## Integracions (v0.3 F)

Connexions amb Shopify, Square o fitxers CSV per URL (`hebra/integracions/`). Totes **marca+**. El secret (testimoni d'accés, o el valor de la capçalera d'autorització per al CSV) s'envia en crear o canviar i **no es torna mai**: només `"te_secret": true`. Es desa xifrat (Fernet, clau derivada de `HEBRA_SECRET` per HKDF): si es canvia `HEBRA_SECRET`, cal tornar a entrar els testimonis.

`Integracio = {"id","botiga_id","proveidor","config","te_secret","actiu","abast","interval_min","darrera_sync","estat","missatge"}`
(`botiga_id` null = tota la marca; `proveidor` `shopify`|`square`|`csv_url`; `abast` ⊆ `["cataleg","vendes","estoc"]`; `estat` `mai`|`ok`|`error`; `missatge` = resum o motiu de l'error de la darrera sincronització; `darrera_sync` = inici de la darrera bona, ISO UTC.)

| Ruta | Cos / resposta |
|---|---|
| `GET /integracions` | `{"integracions": [Integracio]}` |
| `POST /integracions` | `{"botiga_id","proveidor","config","secret","abast","interval_min","actiu"}` → Integracio. `abast` per defecte: tot (CSV: el que té URL). `interval_min` per defecte 60, mínim 15. `secret` obligatori per a Shopify i Square. |
| `PATCH /integracions/{id}` | qualsevol de `config`, `secret`, `actiu`, `abast`, `interval_min`, `botiga_id` → Integracio. `secret` absent o null = no canvia; `""` l'esborra (només CSV). `config` substitueix la configuració sencera. |
| `DELETE /integracions/{id}` | `{"ok": true}` (esborra també el registre) |
| `POST /integracions/prova` | `{"proveidor","config","secret","botiga_id"?,"id"?}` → `{"ok": true, "detall": {"botiga","ubicacions": [{"id","nom","activa"}], ...}}` o **400** amb el motiu en català (testimoni no vàlid, domini desconegut, falta un permís, xarxa...). Amb `id`, el que no s'enviï (secret, config) es pren de la integració desada. No cal la ubicació per provar (serveix per triar-la). |
| `POST /integracions/{id}/sincronitza` | sincronitza ara → `{"resum": {"cataleg","linies_venda","devolucions","estoc"}}` (+ `"errors": [...]` si alguna fila del CSV no s'ha pogut importar); **400** amb el motiu si falla; **409** si ja s'està sincronitzant |
| `GET /integracions/{id}/registre` | `{"registre": [{"inici","fi","estat": "en_curs"|"ok"|"error","resum","error"}]}` (les 20 darreres, la més nova primer) |

`config` per proveïdor:

* **shopify**: `{"domini": "marca.myshopify.com", "ubicacio": "<id de location>", "en_linia": false, "model": "producte"|"sku_base", "opcio_talla": ["Talla","Size"], "opcio_color": ["Color"], "sku_base_longitud"?: n}`. `detall` de la prova: `{"botiga","domini","moneda","ubicacions"}`; també comprova els permisos `read_products`, `read_orders`, `read_inventory`, `read_locations`.
* **square**: `{"ubicacio": "<location id>", "entorn": "produccio"|"sandbox", "model", "opcio_talla", "opcio_color"}`. `detall`: `{"botiga" (nom del comerç),"comerc","moneda","ubicacions"}`.
* **csv_url**: `{"url_vendes"?, "url_estoc"?, "url_cataleg"?, "capcalera"?: "Authorization"}` (HTTPS). Formats dels importadors de sempre; si la integració és d'una botiga i el fitxer no té la columna `botiga`, s'hi posa. `detall`: `{"botiga": null, "ubicacions": [], "fitxers": {"vendes": {"files","columnes"}, ...}}`.
* Integració de **tota la marca** (`botiga_id` null): `"ubicacions": {"<id d'ubicació>": "<botiga>"}` en lloc d'`ubicacio`, per repartir vendes i estoc entre botigues. Sense ubicacions, només es pot sincronitzar el catàleg.
* No s'accepten claus secretes dins `config` (`token`, `secret`, `authorization`...): 400.

Sincronització de fons: cada minut es mira quines integracions actives han passat `interval_min` des de l'intent anterior. Vendes des de la darrera sincronització bona menys 2 dies (la primera vegada, 30 dies); un tiquet ja importat no es duplica; les devolucions entren com a línies negatives (`devolucio = 1`); després, `vendes.atribueix`. Les botigues configurades a l'antiga (paràmetres `shopify_domini`/`shopify_ubicacio` i `HEBRA_SHOPIFY_TOKEN_<BOTIGA>`) es continuen sincronitzant cada hora si no tenen una integració Shopify activa; `POST /shopify/sincronitza` continua igual.

## v0.3 · Fitxa NFC configurable (A.1-A.3)

Lògica a `hebra/fitxa_config.py`; rutes a `hebra/api/fitxa.py`. Totes són **marca+**.

| Ruta | Cos / resposta |
|---|---|
| `GET /fitxa/config?botiga=` | `{"general": ConfigFitxa, "botiga": ConfigFitxa parcial \| null, "efectiva": ConfigFitxa}` |
| `PUT /fitxa/config?botiga=` | ConfigFitxa (parcial) → igual que GET. Sense `botiga`: la general (es completa amb els valors per defecte i es desa sencera). Amb `botiga`: es desa tal qual com a parcial; `{}` l'esborra (la botiga torna a la general). |
| `GET /fitxa/models` | `{"models": [{"model","nom","categoria","idiomes_amb_contingut": ["ca"],"te_origen": true}]}` |
| `GET /fitxa/models/{model}` | `{"model", "contingut": {"ca": ContingutModel, ...}, "origen": {...origen_json...} \| null}` (404 si no és al catàleg) |
| `PUT /fitxa/models/{model}/{idioma}` | ContingutModel → `{"ok": true}`. `{}` esborra el contingut d'aquell idioma. |
| `GET /fitxa/previsualitza?model=&botiga=&idioma=` | `text/html`: la fitxa de la primera variant del model amb la configuració efectiva. No registra res (sense script ni formularis actius). Es pot posar en un `<iframe>` del mateix origen (`frame-ancestors 'self'`, `X-Frame-Options: SAMEORIGIN`). Si avui el grup de control amaga l'origen, ho diu en un avís. |

```json
ConfigFitxa = {
  "seccions": {"ordre": ["talles","composicio","origen","cura","combina","faq"],
               "visibles": {"talles": true, "composicio": true, "origen": true, "cura": true, "combina": true, "faq": true}},
  "accions": {"demana_talla": true, "demana_assistencia": true, "per_que_no": true, "mostra_estoc": "disponibilitat"},
  "idiomes": ["ca","es","fr","en"],
  "textos": {"benvinguda": {"ca": "..."}, "peu": {"ca": "..."}},
  "aparença": {"color_principal": "#214F46", "logo_data_url": null, "nom_marca": "Hebra"},
  "motius": ["talla","tall","preu","color","qualitat","altre"]
}
ContingutModel = {"nom","descripcio","ajust","cura": ["..."],"guia_talles","faq": [{"q","a"}],"combina": ["MODEL"]}
```

- Fusió: per defecte ← general ← botiga. Els objectes es combinen camp a camp; les llistes (`ordre`, `idiomes`, `motius`) se substitueixen senceres. A l'efectiva, les seccions que no surten a `ordre` s'afegeixen al final.
- Validació (400 amb el motiu): seccions de `SECCIONS`; motius de `talla, tall, preu, color, qualitat, nomes_mirava, altre`; `mostra_estoc` ∈ `no | disponibilitat | unitats`; idiomes de `ca, es, fr, en` (llista no buida, el primer és el per defecte); color `#RRGGBB` (es desa en majúscules); logo `data:image/png;base64,...` o `data:image/svg+xml;base64,...` de 100 KB com a màxim; textos de 1000 caràcters com a màxim; camps desconeguts → 400.
- Fitxa (`/p/{token}`): aplica l'efectiva de `?b=`. L'idioma: `lang` si s'ofereix, si no el del navegador si s'ofereix, si no el primer. L'origen només surt si és visible **i** el grup de control del dia ho permet. Contingut de cada camp: el propi de la marca en l'idioma; si no, el fitxer d'origen; si no, el propi en un idioma de reserva. Una acció desactivada també es refusa per formulari (400). El color de la marca només s'aplica en mode clar.

## v0.3 · Assistència i altres botigues (A.4-A.5)

- `POST /p/{token}/assistencia` (formulari: `s`, `b`, `lang`, `cabina` opcional) → 303 a la fitxa amb `ok=assistencia` («Ara ve algú a la cabina»). Necessita `b`.
- `Peticio` (`GET /peticions`, `PATCH /peticions/{id}` i l'esdeveniment SSE `peticio`) guanya:
  - `"tipus": "talla" | "assistencia"`; en una d'assistència `talla` és `""` i `model`/`nom`/`color` són els de la peça que el client té a la mà.
  - `"altres_botigues": [{"botiga_id","nom","unitats"}]`: només a les de talla quan la talla no hi és (`disponible` = false o estat `no_disponible`); botigues amb unitats > 0 a la taula `estoc`, de més a menys. Sempre hi és (llista buida si no cal).
- `GET /servei` afegeix `"peticions_assistencia": n`; `peticions`, `per_estat` i el temps de resposta compten les dues. La resta de l'analítica (demanda perduda, peticions de talla del resum, talla esgotada, canvis de talla) només compta les de talla.
- Motiu nou de no compra: `nomes_mirava` («Només mirava»).

## v0.3 · Provadors en directe (B)

`GET /provadors/directe?botiga=` (tots els rols; un usuari de botiga, només la seva):

```json
{"generat": "...", "cabines": [Cabina], "resum": {"ocupades": 2, "lliures": 1, "sessions_avui": 40, "proves_avui": 88}}
Cabina = {"cabina_id","nom","botiga_id","estat": "ocupada"|"lliure"|"porta_oberta"|"sense_dades","des_de",
          "peces": [{"epc","model","nom","talla","color","des_de"}], "peticions_obertes": 1,
          "avui": {"sessions": 14, "proves": 31, "durada_mitjana_s": 312}}
```

- `ocupada` = porta tancada i presència; `porta_oberta` = presència amb la porta oberta; `lliure` = sense presència; `sense_dades` = res en 2 h. Sense sensors (Bàsic): `ocupada` si hi ha peces dins. `resum.ocupades` compta `ocupada` i `porta_oberta`.
- Peces: EPC llegits en els darrers 60 s amb RSSI ≥ llindar; si dues cabines la llegeixen, és de la que la llegeix més fort. `model`/`nom` són null si l'EPC no és a `etiqueta`.
- `peticions_obertes`: pendents o en camí amb `cabina` = l'id, el nom o el número de la cabina («2» ↔ «Cabina 2»).
- `avui` surt de les sessions ja processades (el càlcul periòdic): pot anar uns minuts endarrerit.
- SSE `/flux`: `event: cabina`, `data: Cabina`, quan entra un lot de la passarel·la que afecta la cabina (com a molt un cop cada 5 s per cabina).

## v0.3 · Sessions de provador (C)

`GET /sessions` (filtre comú) → `analitica.sessions` amb la forma de `docs/ESPECIFICACIO-v3.md` (C), més:

- `periode` i `kpi.mostra_petita`; `mostra_petita` a cada fila amb < 10 sessions (a `per_model`, sobre `sessions_dubte`).
- Població: sessions del període amb **almenys una prova vàlida**.
- `per_nombre_peces` i `per_durada` porten sempre tots els trams (amb 0 sessions i conversió null si cal).
- `provades_juntes`: parells amb ≥ 3 sessions, de més a menys sessions (màx. 20). `conversio_conjunta` = sessions on s'han comprat **tots dos** ÷ sessions on s'han provat junts; `conversio_alguna` = on se n'ha comprat almenys un.
- `mateix_model_diferent_talla.parells_talla[]` porta també `color`. «comprada» compta cada talla comprada (si se n'han comprat dues, totes dues) i `cap` quan no se n'ha comprat cap.

`GET /models/{model}` afegeix `"dubte_talla"` (null si el model no s'ha provat al període):

```json
{"sessions": 12, "sessions_model": 54, "pct_sessions_model": 0.22, "talla_mes_comprada": "S", "mostra_petita": false,
 "parells_talla": [{"color": "Natural", "talles": "XS+S", "sessions": 9, "comprada": {"XS": 2, "S": 5, "cap": 2}, "mostra_petita": true}]}
```

## v0.3 · Estoc parat amb eines per a la botiga (D)

`GET /estoc` (filtre comú) manté `parat`, `risc_rebaixa` i `precisio`, i amplia l'estoc parat:

```json
"parat": [{"gtin","model","nom","color","talla","categoria","botiga_id","unitats","valor_eur",
           "dies_parat": 34, "dies_sense_activitat": 34, "darrera_prova": "..."|null, "darrera_venda": "..."|null,
           "proves_altres_botigues": 12, "vendes_altres_botigues": 3,
           "suggeriment": {"accio": "traspassar"|"moure_a_sala"|"promocio"|"retornar"|"revisar",
                           "text": "Traspassar 2 unitats a Girona: allà s'ha provat 12 vegades en 21 dies.",
                           "botiga_desti": "GIR-01"|null},
           "tasca": Tasca|null}],
"resum_parat": {"unitats": 41, "valor_eur": 2450.0, "per_categoria": [{"categoria","unitats","valor_eur"}]}
```

- **Una fila per botiga i GTIN** (abans, amb totes les botigues, una per GTIN). `dies_sense_activitat` = `dies_parat` (es manté per compatibilitat). `valor_eur` = unitats × PVP del catàleg (null sense preu).
- `proves_altres_botigues` / `vendes_altres_botigues`: proves vàlides i unitats venudes del mateix GTIN a les altres botigues dins de la mateixa finestra de `dies_estoc_parat` dies.
- `tasca`: la tasca **pendent** més nova de la mateixa botiga i GTIN.
- Suggeriment, la primera regla que es compleixi (llindars a `parametre`, entre parèntesis el defecte):
  1. `traspassar` si una altra botiga l'ha provat ≥ `parat_min_proves_traspas` (3) vegades o n'ha venut ≥ `parat_min_vendes_traspas` (1) u.; destí, la que més el mou (proves + 3 × vendes); es proposen totes les unitats parades.
  2. `retornar` si fa més de `parat_dies_retornar` (60) dies que és parat i no s'ha provat ni venut enlloc a la finestra.
  3. `moure_a_sala` si no s'ha provat mai en aquesta botiga.
  4. `revisar` si s'ha provat ≥ `parat_min_proves_conversio` (5) vegades a la botiga amb conversió històrica < `parat_conversio_baixa` (0,15) i el motiu més citat no és el preu.
  5. `promocio` en la resta de casos (s'havia provat i ara no es mou, o el motiu és el preu).

`GET /estoc/parat.csv` (filtre comú i, opcional, `categoria`): CSV UTF-8 amb BOM, separador `;`, decimals amb coma. Columnes: `botiga_id;gtin;model;nom;color;talla;categoria;unitats;valor_eur;dies_parat;darrera_prova;darrera_venda;proves_altres_botigues;vendes_altres_botigues;suggeriment;botiga_desti;text_suggeriment;tasca_pendent`.

### Tasques de botiga (D.1)

`Tasca = {"id","botiga_id","tipus","titol","detall","gtin","unitats","botiga_desti","estat","creada","feta"}`

| Ruta | Rol | Cos / resposta |
|---|---|---|
| `GET /tasques?botiga=&estat=` | tots (botiga, la seva) | `{"tasques": [Tasca]}`: pendents primer, després les més noves (màx. 500) |
| `POST /tasques` | tots (botiga, la seva) | `{"botiga_id"?, "tipus", "titol"?, "detall"?, "gtin"?, "unitats"?, "botiga_desti"?}` → Tasca |
| `PATCH /tasques/{id}` | idem | `{"estat": "feta"|"descartada"|"pendent"}` → Tasca |

- Tipus: `traspassar`, `moure_a_sala`, `promocio`, `retornar`, **`revisar`** (perquè cada suggeriment es pugui convertir en tasca), `recompte`, `altre`.
- `botiga_id` és opcional per a un usuari de botiga (la seva). Sense `titol` se'n genera un («Traspassar 2 u. de Faldilla de llana (S) a Girona»). `traspassar` necessita `botiga_desti` (i només ell en pot tenir).
- Si ja hi ha una tasca **pendent** amb la mateixa botiga, tipus i GTIN, `POST` la retorna en lloc de crear-ne una altra (així «Crea tasques per a tots els seleccionats» es pot repetir).
- `feta` és l'hora en què s'ha tancat (feta o descartada); `PATCH` amb `pendent` la reobre.
- SSE `/flux`: `event: tasca`, `data: Tasca + {"accio": "nova"|"canvi"}`, a la botiga de la tasca.

## v0.3 · Informes programats, lliurats, PDF i correu (E)

Tots els informes (`GET /informes/{tipus}` i els lliurats) porten, a més dels blocs d'abans:

```json
"xifres": [{"etiqueta": "Proves", "valor": 403, "unitat": "enter", "variacio": 0.04, "vs": "setmana anterior"}],
"grafics": [{"id": "conversio_setmanal", "titol": "...", "tipus": "linia"|"barres"|"barres_apilades"|"donut",
             "unitat": "pct"|"enter"|"eur"|"segons", "eix_x": ["S47", "S48"],
             "series": [{"nom": "Conversió", "valors": [0.31, null]}], "nota": "..."|null}]
```

- `variacio`: si `unitat` és `pct`, **diferència en fracció** (0,03 = +3 punts); si no, **canvi relatiu** ((ara − abans) ÷ abans). `null` (i `vs` null) si no hi ha amb què comparar. `vs`: «setmana anterior», «el mateix dia de la setmana passada» (diari) o «període anterior».
- Al pilot, cada xifra és un criteri d'èxit i porta també `"objectiu"` i `"compleix"`.
- Un valor `null` dins de `valors` és «sense dada». Els donuts tenen una sola sèrie (les parts són `eix_x`).
- Gràfics per tipus: **diari** `sessions_hora`; **setmanal** `proves_compres_dia`, `conversio_categoria`, `top_models`, `cua_models`, `peces_per_sessio` (apilades: amb/sense compra), `motius` (donut); **mensual** `conversio_setmanal`, `decisions_abans_despres`, `estoc_parat_categoria` (donut, €), `demanda_perduda_model`; **temporada** `talles_<categoria>` (% proves vs % compres), `models_repetir`, `models_canviar`, `dubte_talla`, `efecte_origen`; **pilot** `conversio_origen`, `conversio_setmanal`, `proves_compres_setmana`; **mango** `conversio_origen`, `conversio_setmanal`, `motius`.
- Blocs nous: **diari** `cinc_linies` (primer bloc; `dades.linies` = 5 frases: proves, compres, peticions i temps de resposta, peces oblidades, talla més demanada sense estoc); **mensual** `decisions_resultat` (conversió del model 14 dies abans i després de cada decisió); **temporada** `dubte_talla` i `recomanacions_comanda`.
- Demanda perduda en euros (estimació): Σ PVP de les variants demanades que no hi eren × conversió del període.

`Programacio = {"id","botiga_id","tipus","actiu","dia_setmana","dia_mes","data","hora","destinataris","propera","darrera_execucio"}`

| Ruta | Rol | Cos / resposta |
|---|---|---|
| `GET /informes/programacio?botiga=` | tots (botiga, les seves, només lectura) | `{"programacions": [Programacio]}` |
| `POST /informes/programacio` | marca+ | `{"botiga_id"?, "tipus", "actiu"?, "dia_setmana"?, "dia_mes"?, "data"?, "hora", "destinataris"}` → Programacio |
| `PATCH /informes/programacio/{id}` | marca+ | qualsevol camp → Programacio |
| `DELETE /informes/programacio/{id}` | marca+ | `{"ok": true}` (els lliurats es queden) |
| `GET /informes/lliurats?botiga=&tipus=` | tots (botiga, els seus) | `{"lliurats": [{"id","tipus","botiga_id","des","fins","generat","estat_enviament","enviat_a","programacio_id","error"}]}`, per `generat` descendent (màx. 500) |
| `POST /informes/lliurats` | marca+ | `{"tipus","botiga","des","fins"}` → genera i desa ara (no l'envia) → fila de la llista |
| `GET /informes/lliurats/{id}` | tots (botiga, els seus) | l'informe JSON tal com es va generar |
| `GET /informes/lliurats/{id}.pdf` | idem | `application/pdf` |
| `POST /informes/lliurats/{id}/envia` | idem | `{"destinataris": ["a@marca.cat"]}` → `{"ok": true}`; desa `estat_enviament` i afegeix els correus a `enviat_a` |
| `GET /informes/{tipus}.pdf?<filtre>` | tots | PDF de l'informe calculat al moment |
| `POST /informes/{tipus}/envia?<filtre>` | tots | igual, generat al moment → `{"ok": true}` |

- `botiga_id` null = informe de totes les botigues; un usuari de botiga no el veu (només els de la seva botiga).
- Validacions (400): `setmanal` necessita `dia_setmana` (0 = dilluns), `mensual` `dia_mes` (1-28), `temporada`/`pilot`/`mango` `data`; `hora` `HH:MM`; correus vàlids (màx. 20). Els camps que no fa servir el tipus es desen a null.
- Enviament: 400 `{"detail": "El correu no està configurat"}` sense `HEBRA_SMTP_HOST`; 400 «Correu no vàlid: ...»; 400 «No s'ha pogut enviar el correu: ...» si el servidor falla. Els destinataris són sempre l'equip de la marca o de la botiga, mai clients.
- Calendari (hora local de la botiga, `botiga.zona_horaria`; Europe/Madrid per als informes de totes les botigues): diari → dia anterior; setmanal → setmana anterior completa (dilluns-diumenge); mensual → mes anterior; temporada → els 182 dies anteriors; pilot i mango → des de l'inici del pilot (taula `pilot`) o els 42 dies anteriors. `propera` és null si la programació és inactiva o ja s'ha fet (una vegada).
- El bucle de fons mira cada minut què toca: genera l'ocurrència més recent que encara no s'ha fet (posterior a la creació i a `darrera_execucio`), la desa i, si hi ha SMTP i destinataris, l'envia. Si el servidor ha estat aturat, en tornar no recupera tots els buits, només la darrera.
- PDF: WeasyPrint amb `hebra/templates/informe_pdf.html` i gràfics SVG fets al servidor (`hebra/grafics_svg.py`). El nom de la marca de la capçalera és el paràmetre `nom_marca`, o el de la configuració de la fitxa, o «Hebra».
