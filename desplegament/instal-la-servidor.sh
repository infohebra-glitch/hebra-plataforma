#!/usr/bin/env bash
# Instal·la (o reinstal·la) la plataforma Hebra en un ordinador amb Linux:
# Raspberry Pi OS (64 bits, Bookworm o posterior), Debian 12+ o Ubuntu 24.04+ (cal Node.js 18+ dels paquets). Vegeu docs/ALLOTJAMENT.md.
# Es pot tornar a executar: no esborra dades ni canvia claus que ja existeixin.
#
# Camí recomanat (gratuït, sense obrir ports): Cloudflare Tunnel. El domini ha de ser ja a Cloudflare.
#   sudo BRANCA=mvp bash desplegament/instal-la-servidor.sh
#   (demana obrir un enllaç al navegador per autoritzar el domini; o passeu TUNNEL_TOKEN=eyJ... si heu
#    creat el túnel des del tauler de Cloudflare)
# Servidor amb IP pública (HTTPS amb Caddy; cal un registre A cap a la IP i els ports 80/443 oberts):
#   sudo ACCES=caddy BRANCA=mvp bash desplegament/instal-la-servidor.sh
#
# Variables:
#   ACCES         tunel (per defecte) o caddy
#   TUNNEL_TOKEN  opcional: testimoni d'un túnel creat al tauler de Cloudflare
#   DOMINI        domini públic (per defecte plataforma.hebraia.com)
#   BRANCA        branca del repositori a instal·lar (per defecte: main)
#   REPO          URL del repositori (si és privat, feu servir una clau de desplegament)
set -euo pipefail

DOMINI="${DOMINI:-plataforma.hebraia.com}"
TUNNEL_TOKEN="${TUNNEL_TOKEN:-}"
ACCES="${ACCES:-tunel}"
case "$ACCES" in tunel|caddy) ;; *) echo "ACCES ha de ser tunel o caddy"; exit 1 ;; esac
BRANCA="${BRANCA:-main}"
REPO="${REPO:-https://github.com/infohebra-glitch/hebra-plataforma.git}"
APP=/opt/hebra-plataforma
DADES=/var/lib/hebra
ENVF=/etc/hebra/plataforma.env

[ "$(id -u)" = 0 ] || { echo "Executeu-ho amb sudo"; exit 1; }
pas() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

pas "Paquets del sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q python3-venv python3-dev git curl sqlite3 rclone nodejs npm \
    libpango-1.0-0 libpangoft2-1.0-0 unattended-upgrades
apt-get install -y -q libharfbuzz-subset0 2>/dev/null || true   # WeasyPrint el farà servir en versions futures
[ "$(node -p 'process.versions.node.split(".")[0]')" -ge 18 ] || { echo "Cal Node.js 18 o més nou (sistema massa antic)"; exit 1; }

# Les màquines petites (1 GB) necessiten memòria d'intercanvi per compilar el tauler
if [ "$(awk '/MemTotal/ {print $2}' /proc/meminfo)" -lt 2000000 ] && ! swapon --show | grep -q .; then
    pas "Memòria d'intercanvi de 2 GB"
    fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
    grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

pas "Usuari i carpetes"
id hebra >/dev/null 2>&1 || useradd --system --home-dir "$DADES" --shell /usr/sbin/nologin hebra
# A la Raspberry de la botiga el mateix usuari fa servir els sensors (passarel·la)
getent group gpio >/dev/null && usermod -aG gpio hebra
install -d -o hebra -g hebra -m 700 "$DADES" "$DADES/copies"
install -d -m 755 /etc/hebra

pas "Codi ($BRANCA)"
if [ -d "$APP/.git" ]; then
    sudo -u hebra git -C "$APP" fetch -q origin "$BRANCA"
    sudo -u hebra git -C "$APP" checkout -q -B "$BRANCA" "origin/$BRANCA"
else
    git clone -q --branch "$BRANCA" "$REPO" "$APP"
    chown -R hebra:hebra "$APP"
fi
sudo -u hebra python3 -m venv "$APP/.venv"
sudo -u hebra "$APP/.venv/bin/pip" install -q --upgrade pip
sudo -u hebra "$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"

pas "Tauler web (compilació)"
( cd "$APP/frontend" && sudo -u hebra HOME="$DADES" npm ci --no-audit --no-fund --loglevel=error \
    && sudo -u hebra HOME="$DADES" npm run build --silent )

pas "Configuració ($ENVF)"
if [ ! -f "$ENVF" ]; then
    aleatori() { python3 -c "import secrets; print(secrets.token_urlsafe($1))"; }
    cat > "$ENVF" <<EOF
# Generat per instal-la-servidor.sh el $(date -I). No el pugeu mai al repositori.
HEBRA_ENTORN=produccio
HEBRA_BD=$DADES/hebra.db
HEBRA_SECRET=$(aleatori 48)
HEBRA_CLAU_PASSARELLA=$(aleatori 32)
HEBRA_SAL_TIQUET=$(aleatori 32)
HEBRA_COOKIE_SECURE=1
# Pàgines antigues /botiga/* desactivades (usuari compartit). Feu servir el tauler (/app/).
HEBRA_CONTRASENYA_BOTIGA=
HEBRA_RETENCIO_DIES=90
HEBRA_PROCESSA_CADA_MIN=5
# Còpies de seguretat (docs/ALLOTJAMENT.md). Sense destí, només es guarden al servidor.
HEBRA_COPIES_CARPETA=$DADES/copies
HEBRA_COPIES_DIARIES=14
HEBRA_COPIES_SETMANALS=8
HEBRA_COPIES_DESTI=
HEBRA_COPIES_REMOT_DIES=60
# Correu dels informes programats (opcional)
# HEBRA_SMTP_HOST=
# HEBRA_SMTP_PORT=587
# HEBRA_SMTP_USUARI=
# HEBRA_SMTP_CONTRASENYA=
# HEBRA_SMTP_REMITENT=Hebra <informes@hebraia.com>
EOF
    echo "Claus noves generades."
else
    echo "Ja existeix: no es toca."
fi
chown root:hebra "$ENVF" && chmod 640 "$ENVF"
[ -f /etc/hebra/rclone.conf ] || install -o hebra -g hebra -m 600 /dev/null /etc/hebra/rclone.conf

pas "Serveis"
install -m 644 "$APP/desplegament/hebra-web.service" "$APP/desplegament/hebra-copia.service" \
    "$APP/desplegament/hebra-copia.timer" /etc/systemd/system/
install -m 755 "$APP/desplegament/hebra-admin" /usr/local/bin/hebra-admin
systemctl daemon-reload
systemctl enable -q --now hebra-web hebra-copia.timer
systemctl restart hebra-web

if [ "$ACCES" = tunel ]; then
    pas "Cloudflare Tunnel (HTTPS sense obrir ports)"
    if ! command -v cloudflared >/dev/null; then
        install -d -m 755 /usr/share/keyrings
        curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg -o /usr/share/keyrings/cloudflare-main.gpg
        echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' \
            > /etc/apt/sources.list.d/cloudflared.list
        apt-get update -q && apt-get install -y -q cloudflared
    fi
    if systemctl is-enabled -q cloudflared 2>/dev/null; then
        echo "El túnel ja estava instal·lat: no es toca."
    elif [ -n "$TUNNEL_TOKEN" ]; then
        cloudflared service install "$TUNNEL_TOKEN"
    else
        # Túnel gestionat des d'aquí: no cal el tauler de Zero Trust de Cloudflare.
        CF=/etc/cloudflared
        install -d -m 700 "$CF"
        if [ ! -f /root/.cloudflared/cert.pem ]; then
            echo
            echo ">>> Ara sortirà un enllaç. Obriu-lo al navegador, entreu a Cloudflare i trieu el domini ${DOMINI#*.}."
            echo ">>> Quan el navegador digui que ja està, aquí continuarà sol."
            cloudflared tunnel login
        fi
        [ -f "$CF/hebra.json" ] || cloudflared tunnel create --credentials-file "$CF/hebra.json" hebra-plataforma
        ID="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['TunnelID'])" "$CF/hebra.json")"
        printf 'tunnel: %s\ncredentials-file: %s/hebra.json\ningress:\n  - hostname: %s\n    service: http://localhost:8000\n  - service: http_status:404\n' \
            "$ID" "$CF" "$DOMINI" > "$CF/config.yml"
        cloudflared tunnel route dns --overwrite-dns "$ID" "$DOMINI"
        cloudflared --config "$CF/config.yml" service install
    fi
    systemctl enable -q --now cloudflared
elif [ "$ACCES" = caddy ]; then
    pas "HTTPS amb Caddy ($DOMINI)"
    apt-get install -y -q caddy
    sed "s/^plataforma\.hebraia\.com {/$DOMINI {/" "$APP/desplegament/Caddyfile" > /etc/caddy/Caddyfile
    systemctl enable -q caddy && systemctl reload-or-restart caddy
fi

pas "Comprovació"
for i in $(seq 1 20); do
    curl -fsS http://127.0.0.1:8000/salut >/dev/null 2>&1 && break
    sleep 1
done
curl -fsS http://127.0.0.1:8000/salut && echo
hebra-admin copia || true

cat <<EOF

Fet. Passos que queden (docs/ALLOTJAMENT.md):
  1. Obriu https://$DOMINI/salut (pot trigar un o dos minuts el primer cop).
  2. Creeu el primer usuari:
       sudo hebra-admin usuari --correu nom@hebraia.com --nom Nom --rol admin
  3. Configureu el destí remot de les còpies (secció «Còpies de seguretat»).
  4. Doneu d'alta un monitor gratuït a https://$DOMINI/salut.
EOF
