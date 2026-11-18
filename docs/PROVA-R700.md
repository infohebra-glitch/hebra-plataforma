# Primera prova amb un lector R700 real

La passarel·la (`hebra_passarella/`) està provada amb un lector fals que imita l'API REST d'Impinj, **no amb un R700 real**. Aquesta guia és per al Xavier (o qui tingui el maquinari): en una tarda ha de quedar clar si el codi parla bé amb el lector i, si no, què cal canviar.

Material: lector Impinj R700 ETSI amb PoE, 1-3 antenes, Raspberry Pi 5 amb Raspberry Pi OS, un commutador o injector PoE, 5-20 etiquetes de la marca (o de prova SGTIN-96), un portàtil a la mateixa xarxa.

## 0. Abans (10 min)

- [ ] El lector té el firmware **8.2 o més nou** i la interfície **Impinj IoT Device Interface** activa (web del lector → *Settings → RFID interface*).
- [ ] S'ha canviat la contrasenya per defecte de l'usuari `root`.
- [ ] La Raspberry i el lector es veuen: `curl -k -u root:<contrasenya> https://<ip-lector>/api/v1/status`.
- [ ] Obriu el Swagger del lector (`https://<ip-lector>/api/v1/docs` o la documentació que porta) i apunteu els camins de: desar un preset, engegar-lo, aturar, i el flux d'esdeveniments.

## 1. Configuració (5 min)

A la Raspberry, amb el codi a `/opt/hebra-plataforma` (vegeu `docs/INSTAL-LACIO.md`, secció 2.3):

```bash
sudo cp desplegament/passarella.example.toml /etc/hebra/passarella.toml
sudo nano /etc/hebra/passarella.toml
#  [lector] url, contrasenya, ports (els que tingueu connectats)
#  Si al Swagger els camins no coincideixen, descomenteu i corregiu cami_preset, cami_inici, cami_aturada, cami_flux.
#  [plataforma] url i clau (HEBRA_CLAU_PASSARELLA del servidor, docs/ALLOTJAMENT.md). Si encara no hi ha servidor,
#  feu servir --sense-plataforma al pas 2.
```

## 2. Diagnosi automàtica (2 min)

```bash
cd /opt/hebra-plataforma
python3 -m hebra_passarella.diagnosi /etc/hebra/passarella.toml --segons 60
```

Mentre escolta, acosteu etiquetes a cada antena, una per una. L'ordre comprova la plataforma i la clau, l'estat del lector, desa el preset, l'engega, escolta el flux, l'atura i mostra una taula així:

```
  antena  etiqueta (EPC)              lectures  RSSI mitjà  mín / màx (dBm)
       1  3034257BF7194E4000001A85         412       -48.3  -61.0 / -41.5
       2  3034257BF7194E4000001A86         377       -51.0  -63.5 / -44.0
```

Desa totes les línies crues del flux a `diagnosi-<data>.jsonl`.

| Si surt... | Vol dir | Què fer |
|---|---|---|
| `no s'ha pogut desar el preset o engegar (HTTP 404)` | Camí diferent al firmware | Corregiu `cami_preset` / `cami_inici` amb el Swagger i torneu-hi |
| `HTTP 401` | Usuari o contrasenya | `usuari` i `contrasenya` a `[lector]` |
| `HTTP 400` / `422` al preset | El preset no compleix l'esquema del firmware | Envieu el missatge sencer: cal tocar `preset()` a `hebra_passarella/lector.py` |
| `el flux no ha enviat res` | Cap etiqueta a prop, o el camí del flux no és aquest | Acosteu etiquetes; reviseu `cami_flux` |
| `cap línia s'ha entès com a lectura` o `línies no són JSON` | El format de l'esdeveniment és diferent | Envieu el `.jsonl`: cal adaptar `interpreta()` |
| `rellotge del lector ... +95 s` (AVÍS) | El lector va desfasat | No passa res: per defecte es fan servir les hores de la Raspberry |
| `la plataforma no accepta la clau` | La clau no és la del servidor | Copieu `HEBRA_CLAU_PASSARELLA` de `/etc/hebra/plataforma.env` |

**Si alguna cosa falla, envieu el text de la diagnosi i el fitxer `.jsonl`** (no conté dades personals: només EPC, antena, RSSI i hora). Amb això es pot corregir el codi sense tenir el lector.

## 3. Passarel·la completa amb el servidor (15 min)

```bash
sudo -u hebra python3 -m hebra_passarella /etc/hebra/passarella.toml --sense-sensors
```

- [ ] Al registre surt `Lector engegat amb el preset hebra` i, cada 5 s, lots enviats sense errors.
- [ ] Al tauler, *Resum → Estat del sistema*: la cabina surt «Envia dades» i la passarel·la «vista fa < 1 min».
- [ ] Desconnecteu el cable de xarxa de la Raspberry 2 minuts i torneu-lo a connectar: les lectures d'aquells minuts arriben igualment (cua local).
- [ ] Desendolleu el lector (PoE) i torneu-lo a endollar: la passarel·la reconnecta sola (registre: `Connexió amb el lector perduda ... Reintent`).

## 4. Sensors de porta i presència (20 min)

Connecteu-los segons `docs/INSTAL-LACIO.md` (2.1) i engegueu-la sense `--sense-sensors`.

- [ ] Obrir i tancar la porta genera `porta_oberta` / `porta_tancada` (un sol esdeveniment per moviment, sense rebots).
- [ ] Entrar a la cabina genera `presencia_si`; sortir, `presencia_no` al cap d'uns segons. El radar **no** detecta algú que passa per fora de la cabina (ajusteu la distància màxima del LD2410C).
- [ ] Una prova de 2 minuts amb una peça a la cabina apareix al tauler com a prova (després del càlcul periòdic de 5 min, o amb `sudo hebra-admin processa --botiga <id>` al servidor).

## 5. Calibratge (la prova de laboratori de 20 peces)

Seguiu `docs/INSTAL-LACIO.md`, secció 4. La diagnosi del pas 2 ajuda a triar el llindar: l'RSSI d'una peça **dins** la cabina ha de quedar clarament per sobre del d'una peça a la cabina del costat (idealment ≥ 6 dB, el marge de confiança alta).

## Què cal tornar

- [ ] Text de la diagnosi (pas 2) i fitxer `.jsonl`.
- [ ] Els camins correctes del Swagger, si no eren els de l'exemple, i la versió del firmware.
- [ ] Potència i llindar RSSI per antena que funcionen, i la taxa d'error de la prova de laboratori.
