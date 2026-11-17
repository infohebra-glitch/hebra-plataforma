# Allotjament gratuït i còpies de seguretat

Objectiu: tenir la plataforma en línia per al pilot **sense pagar res cada mes**, amb HTTPS al domini `hebraia.com` i una còpia diària de la base de dades fora del servidor.

Resum de la proposta:

| Peça | Servei | Cost |
|---|---|---|
| Servidor | Oracle Cloud **Always Free** (màquina virtual Ubuntu, regió UE: Madrid o Frankfurt) | 0 € |
| Domini | `plataforma.hebraia.com` (subdomini del que ja teniu a GoDaddy) | 0 € (ja pagat) |
| HTTPS | Caddy + Let's Encrypt (automàtic) | 0 € |
| Còpies fora del servidor | Oracle Object Storage (20 GB gratuïts) o Cloudflare R2 (10 GB gratuïts), xifrades amb `rclone` | 0 € |
| Avís si cau | UptimeRobot (pla gratuït, comprova `/salut` cada 5 min) | 0 € |

## Per què aquest i no un altre

La plataforma necessita **un procés que estigui sempre engegat** (les alertes en directe viuen a la memòria) i **un disc que no s'esborri** (la base de dades és un fitxer SQLite). Això descarta la majoria de plans gratuïts:

| Opció | Sempre engegat | Disc persistent | Dades a la UE | Veredicte |
|---|---|---|---|---|
| **Oracle Cloud Always Free** | Sí | Sí (fins a 200 GB) | Sí (Madrid, Frankfurt...) | **Recomanat** |
| Raspberry Pi de la botiga + Cloudflare Tunnel | Si la botiga té llum i xarxa | Targeta SD (cal còpia) | Sí | Pla B: si cau la botiga, cau el tauler |
| Google Cloud e2-micro (gratuït) | Sí | Sí (30 GB) | **No** (només regions dels EUA) | No, per les dades fora de la UE |
| Render, Railway, Koyeb, Vercel, Netlify (gratuïts) | No (s'adormen o no hi ha servidor) | No | Varia | No serveixen per a aquesta aplicació |
| Hetzner CX23 | Sí | Sí | Sí | El que hi havia previst, però és de pagament (≈4-5 €/mes) |

Coses a saber d'Oracle abans de començar (comproveu-les quan us doneu d'alta, les condicions poden canviar):

- **Demana una targeta** per verificar la identitat. Amb el compte gratuït no es cobra res: només es pot fer servir el que és «Always Free».
- La **regió principal no es pot canviar** després: trieu **Spain Central (Madrid)** o **Germany Central (Frankfurt)**.
- Oracle pot **recuperar màquines gratuïtes que estan inactives** durant 7 dies (CPU, xarxa i memòria molt baixes). Amb el pilot en marxa la màquina rep lectures contínuament i no hauria de passar, però per això també hi ha les còpies fora del servidor.
- A vegades no hi ha capacitat per a les màquines Ampere (ARM). Si passa, torneu-ho a provar més tard o feu servir la `VM.Standard.E2.1.Micro` (AMD, 1 GB): l'script hi afegeix memòria d'intercanvi i funciona per a una botiga.

## 1. Crear el servidor (una vegada, ≈30 min)

1. Doneu d'alta el compte a <https://www.oracle.com/cloud/free/> amb un correu `@hebraia.com` de l'empresa que puguin fer servir l'Iscle i el Xavier (no un de personal). Regió: **Madrid** o **Frankfurt**.
2. *Compute → Instances → Create instance*:
   - Imatge: **Canonical Ubuntu 24.04**.
   - Forma: **VM.Standard.A1.Flex** amb 2 OCPU i 12 GB (gratuït fins a 4 OCPU / 24 GB). Si no n'hi ha, `VM.Standard.E2.1.Micro`.
   - Xarxa: la VCN per defecte, amb **IP pública**.
   - Claus SSH: pugeu la vostra clau pública (o deixeu que Oracle en generi una i guardeu-la).
3. *Networking → Virtual Cloud Networks → (la VCN) → Security Lists → Default*: afegiu dues regles d'entrada **TCP 80** i **TCP 443** des de `0.0.0.0/0`. (El port 22 ja hi és.)
4. Apunteu la **IP pública** de la màquina.

## 2. Domini (GoDaddy, 5 min)

A GoDaddy → *Dominis → hebraia.com → DNS → Afegeix registre*:

| Tipus | Nom | Valor | TTL |
|---|---|---|---|
| A | `plataforma` | la IP pública d'Oracle | 1 hora |

Comproveu-ho amb `dig +short plataforma.hebraia.com` (ha de tornar la IP). Fins que no respon, Caddy no pot treure el certificat.

## 3. Instal·lar la plataforma (10-15 min)

```bash
ssh ubuntu@<IP>
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/infohebra-glitch/hebra-plataforma.git
# Mentre les PR no estiguin fusionades a main, indiqueu la branca:
sudo DOMINI=plataforma.hebraia.com BRANCA=mvp bash hebra-plataforma/desplegament/instal-la-servidor.sh
```

Si el repositori és privat, el servidor necessita permís de lectura: a GitHub, *Settings → Deploy keys → Add deploy key* (només lectura) amb la clau pública del servidor (`ssh-keygen -t ed25519` a la màquina), i feu servir `REPO=git@github.com:infohebra-glitch/hebra-plataforma.git`.

L'script ([`desplegament/instal-la-servidor.sh`](../desplegament/instal-la-servidor.sh)) es pot tornar a executar sense perdre res. Fa:

- Instal·la Python, Node.js (només per compilar el tauler), Caddy, SQLite, rclone i les llibreries dels PDF.
- Crea l'usuari `hebra`, la carpeta de dades `/var/lib/hebra` (base de dades i còpies) i `/etc/hebra/plataforma.env` amb **claus aleatòries noves** (`HEBRA_ENTORN=produccio`).
- Instal·la i engega els serveis `hebra-web` (un sol procés), `hebra-copia.timer` (còpia cada nit a les 3:30) i Caddy amb HTTPS.
- Obre els ports 80 i 443 a l'`iptables` que porten les imatges d'Ubuntu d'Oracle.
- Instal·la l'ordre `hebra-admin`, que executa `python -m hebra.admin` amb la mateixa configuració que el servei.

Després:

```bash
curl https://plataforma.hebraia.com/salut                 # {"estat":"ok",...}
sudo hebra-admin usuari --correu nom@hebraia.com --nom "Nom" --rol admin   # un per persona; demana la contrasenya
sudo grep HEBRA_CLAU_PASSARELLA /etc/hebra/plataforma.env  # per posar-la a passarella.toml de la Raspberry
```

Per actualitzar a una versió nova (fa una còpia abans i, si la web no respon, diu com tornar enrere):

```bash
sudo bash /opt/hebra-plataforma/desplegament/actualitza.sh
```

## 4. Còpies de seguretat

Cada nit el temporitzador `hebra-copia.timer` executa `hebra-admin copia`, que:

1. Fa una **còpia en calent** de la base de dades (no cal aturar la web), amb l'API de còpia de SQLite.
2. La **comprova** (`PRAGMA integrity_check`) abans de guardar-la: una còpia malmesa no substitueix mai les bones.
3. La comprimeix a `/var/lib/hebra/copies/hebra-<data>.db.gz` (permisos 600) amb la suma SHA-256 al costat.
4. Guarda les **14 últimes diàries i 8 setmanals** (`HEBRA_COPIES_DIARIES`, `HEBRA_COPIES_SETMANALS`) i esborra la resta.
5. Si hi ha `HEBRA_COPIES_DESTI`, l'**envia fora del servidor** amb rclone i hi esborra les de més de 60 dies.
6. Deixa el resultat a l'**Estat del sistema** del tauler (Resum): «Còpia de seguretat: ahir 3:31 (guardada fora del servidor)». Surt en vermell si fa més de 36 h que no se'n fa cap o si no s'ha pogut enviar fora.

### 4.1 Destí fora del servidor (una vegada, 10 min)

Una còpia que només és al mateix servidor no serveix si es perd el servidor. Opció recomanada, també gratuïta: **Oracle Object Storage** (20 GB inclosos al compte Always Free).

1. A Oracle: *Storage → Buckets → Create bucket* `hebra-copies` (privat, que és el valor per defecte).
2. *Perfil → Customer secret keys → Generate*: apunteu la clau d'accés i el secret (són compatibles amb S3).
3. Al servidor, configureu rclone com l'usuari `hebra` amb el fitxer de configuració del servei:

```bash
sudo -u hebra RCLONE_CONFIG=/etc/hebra/rclone.conf rclone config
#  n) New remote   name> oracle
#  Storage> s3     provider> Other
#  access_key_id> <clau>     secret_access_key> <secret>
#  endpoint> https://<namespace>.compat.objectstorage.eu-madrid-1.oraclecloud.com
#     (el <namespace> surt a la pàgina del bucket; canvieu la regió si no és Madrid)
#  region> eu-madrid-1
#
#  n) New remote   name> copies      (xifra les còpies abans d'enviar-les)
#  Storage> crypt   remote> oracle:hebra-copies
#  filename_encryption> standard    password> (genereu-la)   password2> (genereu-la)
```

**Guardeu les dues contrasenyes del remot `copies`** en un lloc segur fora del servidor (gestor de contrasenyes de l'Iscle i del Xavier): sense elles les còpies no es poden llegir.

4. Poseu el destí a la configuració i proveu-ho:

```bash
sudo sed -i 's|^HEBRA_COPIES_DESTI=.*|HEBRA_COPIES_DESTI=copies:|' /etc/hebra/plataforma.env
sudo hebra-admin copia                                                    # «Enviada a copies:»
sudo -u hebra RCLONE_CONFIG=/etc/hebra/rclone.conf rclone ls copies:     # s'hi veu el fitxer
systemctl list-timers hebra-copia.timer                                   # propera execució
```

Alternatives gratuïtes amb el mateix procediment (només canvia el primer remot): Cloudflare R2 (10 GB, `provider> Cloudflare`), Backblaze B2 (10 GB) o una carpeta de Google Drive de l'empresa (`Storage> drive`). Les còpies contenen els correus i els resums de contrasenya dels usuaris del tauler: feu servir sempre el remot xifrat (`crypt`).

### 4.2 Restaurar (i provar-ho una vegada abans del pilot)

```bash
sudo hebra-admin copies                                       # llista les còpies locals
# Si cal una còpia remota, primer baixeu-la:
sudo -u hebra RCLONE_CONFIG=/etc/hebra/rclone.conf rclone copy copies:hebra-2026-11-20T033012Z.db.gz /var/lib/hebra/copies/
sudo systemctl stop hebra-web
sudo hebra-admin restaura /var/lib/hebra/copies/hebra-2026-11-20T033012Z.db.gz
sudo systemctl start hebra-web
```

La restauració comprova la suma SHA-256 i la integritat abans de tocar res, i guarda la base de dades que hi havia com a `hebra.db.abans-de-restaurar-<hora>`.

**Proveu una restauració abans de començar el pilot** (per exemple en un portàtil amb `HEBRA_BD=prova.db python -m hebra.admin restaura ...`): una còpia que no s'ha provat mai de restaurar no és una còpia.

## 5. Avís si la plataforma cau

1. Compte gratuït a <https://uptimerobot.com>.
2. *New monitor → HTTP(s)* → `https://plataforma.hebraia.com/salut`, cada 5 minuts.
3. Avís per correu a l'Iscle i al Xavier.

`/salut` respon 503 si la base de dades no respon, i UptimeRobot avisa si no hi ha resposta. Les cabines sense dades i les còpies que fallen es veuen a l'**Estat del sistema** del tauler.

## 6. Pla B: el servidor a la Raspberry de la botiga

Si Oracle no deixa crear el compte o la màquina, la mateixa Raspberry Pi 5 de la botiga pot fer de servidor amb **Cloudflare Tunnel** (gratuït, sense obrir ports al router de la botiga). Inconvenients: si la botiga es queda sense llum o sense internet, la marca no veu el tauler; i cal moure els DNS de `hebraia.com` a Cloudflare (també gratuït). Les còpies fora del servidor són encara més importants en aquest cas (la targeta SD es pot espatllar). Si s'ha de fer, ho afegim a aquesta guia.
