# Allotjament gratuït i còpies de seguretat

Objectiu: tenir la plataforma en línia per al pilot **sense pagar res**, amb HTTPS a `plataforma.hebraia.com` i una còpia diària de la base de dades fora de l'ordinador.

## La proposta

La plataforma funciona en un **ordinador nostre** (la Raspberry Pi 5 del pilot o qualsevol ordinador que estigui sempre engegat) i es publica a internet amb **Cloudflare Tunnel**, que és gratuït i no demana targeta.

| Peça | Servei | Cost |
|---|---|---|
| Ordinador | Raspberry Pi 5 del pilot (ja és al pressupost) o un ordinador vell amb Ubuntu | 0 € |
| Adreça i HTTPS | Cloudflare (pla gratuït) + Cloudflare Tunnel | 0 € |
| Domini | `plataforma.hebraia.com` (el domini ja és vostre, a GoDaddy) | 0 € |
| Còpies fora de l'ordinador | Google Drive de l'empresa (15 GB gratuïts), xifrades amb `rclone` | 0 € |
| Avís si cau | UptimeRobot (pla gratuït) | 0 € |

Per què així:

- La plataforma necessita **un programa sempre engegat** i **un disc que no s'esborri**. Els plans gratuïts de Render, Railway, Koyeb, Vercel o Netlify s'adormen o esborren el disc. Oracle Cloud gratuït es va descartar el 18-11-2026 perquè no tenia capacitat a Madrid. Google Cloud gratuït només funciona als EUA.
- Amb el túnel, **no cal obrir cap port del router** ni tenir IP fixa: l'ordinador obre una connexió cap a Cloudflare i Cloudflare hi porta les visites, amb HTTPS.
- Si la plataforma va a la **mateixa Raspberry de la botiga**, la passarel·la li envia les lectures sense passar per internet: encara que caigui la xarxa de la botiga, no es perd res.

Inconvenients (acceptables per al pilot):

- Si l'ordinador s'apaga o es queda sense internet, la marca no veu el tauler i la fitxa NFC no s'obre fins que torna. UptimeRobot us avisa al moment. Si teniu un lloc amb millor connexió que la botiga (oficina, casa), poseu-hi l'ordinador allà.
- La targeta SD de la Raspberry es pot espatllar: per això les còpies van cada nit a Google Drive. Millor encara: un disc SSD per USB.
- Cal **moure els DNS de `hebraia.com` a Cloudflare** (pas 2). El domini continua sent vostre i a GoDaddy. Només canvia qui respon les adreces. Cloudflare copia els registres que ja hi ha, també els del correu.

## Pas 1. Preparar l'ordinador (30 min)

Amb una **Raspberry Pi 5** (4 GB o més) i una targeta microSD de 32 GB o més:

1. A l'ordinador de casa, instal·leu **Raspberry Pi Imager** (<https://www.raspberrypi.com/software/>).
2. Trieu *Raspberry Pi 5* → *Raspberry Pi OS Lite (64-bit)* → la targeta.
3. Quan pregunti per la configuració, poseu:
   - nom de l'equip: `hebra`
   - un usuari i una contrasenya (apunteu-los)
   - la xarxa Wi-Fi, si no hi ha cable
   - a la pestanya *Serveis*: **activa SSH** amb contrasenya
4. Grava, posa la targeta a la Raspberry, connecta-la (millor amb cable de xarxa) i engega-la. Espera 2 minuts.
5. Des de l'ordinador de casa, obre el Terminal (Mac) o PowerShell (Windows) i escriu:
   ```
   ssh <usuari>@hebra.local
   ```
   Respon `yes` i posa la contrasenya. Ja ets dins de la Raspberry.

Amb un **ordinador vell**: instal·leu-hi Ubuntu Server 24.04, activeu SSH durant la instal·lació, i feu el mateix `ssh`.

## Pas 2. Passar el domini a Cloudflare (15 min, i esperar fins a unes hores)

1. Creeu un compte gratuït a <https://dash.cloudflare.com/sign-up> amb un correu `@hebraia.com` de l'empresa.
2. *Add a domain* → escriviu `hebraia.com` → trieu el pla **Free**.
3. Cloudflare llista els registres DNS que ha trobat. **Reviseu que hi siguin els del correu** (tipus `MX` i `TXT`) i els de la web. Si en falta algun, copieu-lo de GoDaddy (*Dominis → hebraia.com → DNS*).
4. Cloudflare us dona **dos noms de servidor** (per exemple `ada.ns.cloudflare.com` i `bob.ns.cloudflare.com`).
5. A GoDaddy: *Dominis → hebraia.com → DNS → Servidors de noms → Canvia → Faré servir els meus servidors de noms* i enganxeu-hi els dos de Cloudflare. Desa.
6. Espereu el correu de Cloudflare que diu que el domini és **Active** (normalment menys d'una hora; pot trigar fins a 24 h). Durant l'espera, comproveu que el correu `@hebraia.com` continua arribant.

## Pas 3. Instal·lar la plataforma i el túnel (20-30 min, gairebé tot sol)

Quan Cloudflare digui que el domini és **Active**, a la Raspberry (dins de l'`ssh` del pas 1) escriviu aquestes tres ordres, una per una:

```
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/infohebra-glitch/hebra-plataforma.git
sudo BRANCA=mvp bash hebra-plataforma/desplegament/instal-la-servidor.sh
```

A mitja instal·lació, la pantalla diu **«Ara sortirà un enllaç»** i en mostra un que comença per `https://dash.cloudflare.com/argotunnel?...`:

1. Copieu-lo i obriu-lo al navegador de l'ordinador de casa.
2. Entreu a Cloudflare (el compte del pas 2) i cliqueu el domini `hebraia.com` → *Authorize*.
3. Torneu al Terminal: continua sol. Crea el túnel `hebra-plataforma`, l'adreça `plataforma.hebraia.com` i ho deixa engegat.

Així no cal entrar al tauler de *Zero Trust* de Cloudflare ni donar cap targeta. (`BRANCA=mvp` fins que el codi es fusioni a `main`. Si el repositori és privat, abans cal donar permís de lectura a la Raspberry: *GitHub → Settings → Deploy keys*, amb una clau feta a la Raspberry amb `ssh-keygen -t ed25519`. Ho pot fer el Xavier o Claude amb vosaltres.)

L'script ([`desplegament/instal-la-servidor.sh`](../desplegament/instal-la-servidor.sh)) es pot tornar a executar sense perdre res. Fa:

- Instal·la Python, Node.js (només per compilar el tauler), SQLite, rclone, les llibreries dels PDF i `cloudflared` (el programa del túnel).
- Crea l'usuari `hebra`, la carpeta de dades `/var/lib/hebra` (base de dades i còpies) i `/etc/hebra/plataforma.env` amb **claus aleatòries noves** (`HEBRA_ENTORN=produccio`).
- Engega els serveis `hebra-web` (un sol procés), `hebra-copia.timer` (còpia cada nit a les 3:30) i el túnel.
- Instal·la l'ordre `hebra-admin`, que executa `python -m hebra.admin` amb la mateixa configuració que el servei.

Quan acabi:

1. Obriu <https://plataforma.hebraia.com/salut> al navegador. Ha de sortir `{"estat":"ok",...}`.
2. Creeu un usuari per persona (demana la contrasenya):
   ```
   sudo hebra-admin usuari --correu nom@hebraia.com --nom "Nom" --rol admin
   ```
3. Entreu a <https://plataforma.hebraia.com/app/>.
4. La clau per a la passarel·la és aquí: `sudo grep HEBRA_CLAU_PASSARELLA /etc/hebra/plataforma.env`. Si la passarel·la va a la mateixa Raspberry, a `passarella.toml` poseu `url = "http://127.0.0.1:8000"`.

Per actualitzar a una versió nova (fa una còpia abans i, si la web no respon, diu com tornar enrere):

```
sudo bash /opt/hebra-plataforma/desplegament/actualitza.sh
```

## Pas 4. Còpies de seguretat a Google Drive (15 min)

Cada nit el temporitzador `hebra-copia.timer` executa `hebra-admin copia`, que:

1. Fa una **còpia en calent** de la base de dades (no cal aturar la web).
2. La **comprova** (`PRAGMA integrity_check`) abans de guardar-la: una còpia malmesa no substitueix mai les bones.
3. La comprimeix a `/var/lib/hebra/copies/` amb la suma SHA-256 al costat.
4. Guarda les **14 últimes diàries i 8 setmanals** i esborra la resta.
5. Si hi ha `HEBRA_COPIES_DESTI`, l'**envia fora de l'ordinador** (xifrada) i hi esborra les de més de 60 dies.
6. Ho mostra a l'**Estat del sistema** del tauler (Resum). Surt en vermell si fa més de 36 h que no se'n fa cap o si no s'ha pogut enviar fora.

Per enviar-les a Google Drive (calen dos ordinadors: la Raspberry i el de casa, amb navegador):

1. A l'ordinador de casa, instal·leu rclone: <https://rclone.org/downloads/> (Mac: descarregueu el zip, o `brew install rclone` si teniu Homebrew).
2. A la Raspberry:
   ```
   sudo -u hebra RCLONE_CONFIG=/var/lib/hebra/rclone.conf rclone config
   ```
   Responeu així (prémer Retorn vol dir deixar el valor per defecte):
   - `n` (nou) → nom: `drive`
   - Storage: escriviu `drive`
   - client_id i client_secret: Retorn
   - scope: `1` (accés complet)
   - service_account_file: Retorn → Edit advanced config: `n`
   - **Use web browser to automatically authenticate?** `n`
   - Surt una ordre `rclone authorize "drive" "..."`. **Copieu-la, enganxeu-la al Terminal de l'ordinador de casa** i entreu amb el compte de Google de l'empresa. El Terminal de casa torna un text llarg: copieu-lo i enganxeu-lo a la Raspberry (`config_token>`).
   - Shared drive: `n` → `y` (desa)
   - Ara un segon remot, que xifra: `n` → nom: `copies` → Storage: `crypt` → remote: `drive:hebra-copies` → filename_encryption: `1` → directory_name_encryption: `1` → password: `g` (genera) i accepteu → password2: `g` i accepteu → `n` → `y` → `q`.
   - **Guardeu les dues contrasenyes que ha generat** al gestor de contrasenyes de l'Iscle i del Xavier. Sense elles les còpies no es poden llegir.
3. Activeu-ho i proveu-ho:
   ```
   sudo sed -i 's|^HEBRA_COPIES_DESTI=.*|HEBRA_COPIES_DESTI=copies:|' /etc/hebra/plataforma.env
   sudo hebra-admin copia
   ```
   Ha de dir «Enviada a copies:». A Google Drive apareix una carpeta `hebra-copies` amb fitxers de noms il·legibles (és normal: estan xifrats).

### Restaurar (i provar-ho una vegada abans del pilot)

```
sudo hebra-admin copies                       # llista les còpies que hi ha a l'ordinador
# Si l'ordinador s'ha perdut, primer baixeu-ne una de Drive a l'ordinador nou (amb el mateix rclone.conf):
sudo -u hebra RCLONE_CONFIG=/var/lib/hebra/rclone.conf rclone copy copies:hebra-2026-11-20T033012Z.db.gz /var/lib/hebra/copies/
sudo systemctl stop hebra-web
sudo hebra-admin restaura /var/lib/hebra/copies/hebra-2026-11-20T033012Z.db.gz
sudo systemctl start hebra-web
```

La restauració comprova la suma i la integritat abans de tocar res, i guarda la base de dades que hi havia com a `hebra.db.abans-de-restaurar-<hora>`. Guardeu també una còpia de `/etc/hebra/plataforma.env` i `/var/lib/hebra/rclone.conf` al gestor de contrasenyes: sense `HEBRA_SECRET` les connexions amb Shopify o Square s'han de tornar a entrar.

## Pas 5. Avís si la plataforma cau (5 min)

1. Compte gratuït a <https://uptimerobot.com>.
2. *New monitor → HTTP(s)* → `https://plataforma.hebraia.com/salut`, cada 5 minuts.
3. Avís per correu a l'Iscle i al Xavier.

## Altres maneres (si algun dia cal)

- **Servidor al núvol amb IP pública** (Hetzner, Oracle si torna a tenir capacitat...): el mateix script amb `ACCES=caddy` posa HTTPS amb Caddy. Cal un registre `A` cap a la IP i obrir els ports 80 i 443.
- **Túnel creat al tauler de Cloudflare** (*Zero Trust → Networks → Tunnels*): passeu-ne el testimoni a l'script amb `TUNNEL_TOKEN=eyJ...`.
- **Instal·lació a mà**, pas a pas: [`docs/INSTAL-LACIO.md`](INSTAL-LACIO.md).
