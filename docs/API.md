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
