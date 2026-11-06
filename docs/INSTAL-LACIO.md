# Instal·lació real: servidor, Raspberry Pi i botiga

Aquesta guia porta la plataforma de les dades simulades a una botiga de veritat. Són tres parts:

1. **Servidor** (al núvol): la plataforma web, la fitxa NFC i l'informe.
2. **Raspberry Pi** (a la botiga): llegeix el lector RFID i els sensors i ho envia al servidor.
3. **Dades de la marca**: botiga i cabines, catàleg, etiquetes i grup de control.

> Abans de la primera botiga, feu la **prova de laboratori de 20 peces** (secció 4) per calibrar la potència i el llindar RSSI.

## 1. Servidor

Qualsevol servidor Linux petit serveix (previst: Hetzner CX23, Debian o Ubuntu). Cal un domini que apunti a la IP del servidor, p. ex. `plataforma.hebra.cat`.

```bash
sudo apt install -y python3-venv git caddy
sudo useradd --system --no-create-home hebra
sudo git clone https://github.com/infohebra-glitch/hebra-plataforma.git /opt/hebra-plataforma
sudo chown -R hebra /opt/hebra-plataforma
cd /opt/hebra-plataforma
sudo -u hebra python3 -m venv .venv
sudo -u hebra .venv/bin/pip install -r requirements.txt

# Tauler web (cal Node.js 18+ només per compilar-lo; també es pot compilar en un altre ordinador i copiar frontend/dist)
cd frontend && sudo -u hebra npm ci && sudo -u hebra npm run build && cd ..

# Configuració (secrets fora del repositori)
sudo mkdir -p /etc/hebra
sudo cp .env.example /etc/hebra/plataforma.env
sudo nano /etc/hebra/plataforma.env
#   HEBRA_BD=/opt/hebra-plataforma/hebra.db
#   HEBRA_CLAU_PASSARELLA=<genereu-la: python3 -c "import secrets; print(secrets.token_urlsafe(32))">
#   HEBRA_CONTRASENYA_BOTIGA=<una de forta>
#   HEBRA_SAL_TIQUET=<una altra de llarga>
#   HEBRA_ENTORN=produccio
#   HEBRA_SECRET=<python3 -c "import secrets; print(secrets.token_urlsafe(48))">
#   HEBRA_COOKIE_SECURE=1
sudo chmod 600 /etc/hebra/plataforma.env

# Servei i HTTPS
sudo cp desplegament/hebra-web.service /etc/systemd/system/
sudo systemctl enable --now hebra-web
sudo cp desplegament/Caddyfile /etc/caddy/Caddyfile   # canvieu-hi el domini
sudo systemctl reload caddy
```

Comprovació: `https://<domini>/salut` ha de respondre `{"estat":"ok",...}`, i `https://<domini>/app/` ha de mostrar la pantalla d'entrada del tauler.

El servei arrenca **un sol procés** `uvicorn`: les alertes en directe (peticions de talla a la web del dependent) viuen a la memòria del procés.

La plataforma recalcula proves i atribucions cada 5 minuts (`HEBRA_PROCESSA_CADA_MIN`).

**Còpia de seguretat**: la base de dades és un sol fitxer. Cada nit: `sqlite3 /opt/hebra-plataforma/hebra.db ".backup /opt/copies/hebra-$(date +%F).db"`.

## 2. Raspberry Pi de la botiga

Material (de la llista de components): Raspberry Pi 5 (4 GB) amb Raspberry Pi OS, lector Impinj R700 ETSI, una antena de camp proper per cabina, contacte magnètic de porta i radar HLK-LD2410C per cabina, cable.

### 2.1 Connexions

El lector i la Raspberry van a la mateixa xarxa local (cable). El lector s'alimenta per PoE.

Per cada cabina (pins en numeració BCM; els de l'exemple són a `desplegament/passarella.example.toml`):

| Element | Connexió a la Raspberry |
|---|---|
| Contacte de porta (reed) | un fil al pin de porta (p. ex. GPIO17), l'altre a GND. Porta tancada = contacte tancat. |
| Radar LD2410C | VCC a 5 V, GND a GND, **OUT** al pin de presència (p. ex. GPIO27). La sortida és de 3,3 V: es pot connectar directament. |

El radar es configura una vegada (sensibilitat i distància màxima, que no "vegi" fora la cabina). No fem servir el seu Bluetooth.

### 2.2 Lector R700

1. Entreu a la web del lector (`https://<ip-del-lector>`), canvieu la contrasenya per defecte.
2. A la configuració, la interfície RFID ha de ser **Impinj IoT Device Interface** (per defecte des del firmware 8.2).
3. Obriu la documentació de l'API que porta el lector i **comproveu els camins** de presets, inici, aturada i flux de dades. Si no són els de `passarella.example.toml`, poseu-hi els correctes.

### 2.3 Programa

```bash
sudo useradd --system --no-create-home --groups gpio hebra
sudo git clone https://github.com/infohebra-glitch/hebra-plataforma.git /opt/hebra-plataforma
sudo chown -R hebra /opt/hebra-plataforma
sudo mkdir -p /etc/hebra /var/lib/hebra && sudo chown hebra /var/lib/hebra
sudo cp /opt/hebra-plataforma/desplegament/passarella.example.toml /etc/hebra/passarella.toml
sudo nano /etc/hebra/passarella.toml     # URL i clau de la plataforma, IP i contrasenya del lector, pins
sudo chmod 640 /etc/hebra/passarella.toml && sudo chgrp hebra /etc/hebra/passarella.toml

# Primer, a mà, per veure que tot funciona:
cd /opt/hebra-plataforma && sudo -u hebra python3 -m hebra_passarella /etc/hebra/passarella.toml

# Després, com a servei (s'engega sol i es reinicia si cau):
sudo cp desplegament/hebra-passarella.service /etc/systemd/system/
sudo systemctl enable --now hebra-passarella
journalctl -u hebra-passarella -f        # registre en directe
```

No necessita cap paquet extra: només Python i `gpiozero`, que ja venen amb Raspberry Pi OS. Per provar només el lector, sense sensors: `--sense-sensors`.

Si cau internet, la Raspberry guarda tot el que llegeix fins a 7 dies (`/var/lib/hebra/cua.db`) i ho envia quan torna.

## 3. Dades de la marca i de la botiga

Al servidor, amb les variables de `/etc/hebra/plataforma.env` carregades (`set -a; . /etc/hebra/plataforma.env; set +a`) i des de `/opt/hebra-plataforma`:

```bash
# Botiga, cabines i antenes (l'id de l'antena és "<nom del lector>:<port>", com a passarella.toml)
.venv/bin/python -m hebra.admin botiga botiga.json            # model: desplegament/botiga.example.json

# Catàleg de la marca: una fila per variant (gtin;model;color;talla;categoria;preu)
.venv/bin/python -m hebra.admin cataleg cataleg.csv

# Fitxa d'origen dels models (format hebra-origen/0.2, com dades/origen-prova.json)
.venv/bin/python -m hebra.admin origen origen.json

# Etiquetes: EPC de cada peça (epc[;gtin]). Genera les URL per gravar als xips NFC.
.venv/bin/python -m hebra.admin etiquetes etiquetes.csv --botiga BCN-01 \
    --url https://plataforma.hebra.cat --sortida etiquetes-nfc.csv

# Grup de control de l'origen per a les 6 setmanes de mesura
.venv/bin/python -m hebra.admin control --botiga BCN-01 --inici 2026-11-23 --setmanes 6

# Usuaris del tauler: un per persona (la contrasenya es demana i no queda a l'historial)
.venv/bin/python -m hebra.admin usuari --correu anna@marca.cat --nom Anna --rol marca
.venv/bin/python -m hebra.admin usuari --correu bcn@marca.cat --nom "Botiga BCN" --rol botiga --botiga BCN-01

# Estoc inicial (botiga,gtin,unitats) o, si la botiga fa servir Shopify, sincronització de només lectura
.venv/bin/python -m hebra.admin estoc estoc.csv
.venv/bin/python -m hebra.admin shopify --botiga BCN-01     # cal HEBRA_SHOPIFY_TOKEN_BCN_01
```

`etiquetes-nfc.csv` és la llista que va a qui codifica les etiquetes (o a l'app del mòbil que les grava): cada EPC UHF amb la URL que ha de portar el seu xip NFC. Cada URL té un codi aleatori, i tornar a executar l'ordre no el canvia.

Les **vendes** (i l'estoc i el catàleg) es pugen des del tauler, a **Importa dades** (`https://<domini>/app/dades`), en CSV. La pàgina antiga `/botiga/vendes` continua funcionant.

El dependent obre `https://<domini>/app/dependent` al mòbil de la botiga (amb l'usuari de rol `botiga`) i hi rep les peticions de talla en directe.

## 4. Prova de laboratori (20 peces)

Objectiu: fixar la potència del lector i el llindar RSSI de cada antena abans d'anar a botiga.

1. Munteu 2 o 3 cabines (o simuleu-les amb mampares) amb les antenes al sostre.
2. Doneu d'alta la botiga de prova i les 20 etiquetes (secció 3). Engegueu la passarel·la.
3. Feu proves controlades i apunteu-les a mà: quina peça, quina cabina, quant temps. Incloeu-hi peces que passen pel costat sense entrar, i peces a la cabina del costat.
4. Mireu les lectures a la base de dades: `SELECT antena_id, epc, AVG(rssi_mitja), SUM(n_lectures) FROM lectura_agregada GROUP BY 1, 2;`
5. Ajusteu `potencia_cdbm` (passarella.toml) i `llindar_rssi` (botiga.json) fins que les proves detectades coincideixin amb les apuntades. Si cal, ajusteu també la regla de prova (`HEBRA_PROVA_*`).
6. Apunteu la taxa d'error: l'informe final del pilot l'ha de declarar.
