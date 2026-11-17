#!/usr/bin/env bash
# Instal·la (o reinstal·la) la plataforma Hebra en un servidor Ubuntu 22.04/24.04 net.
# Pensat per a una màquina gratuïta d'Oracle Cloud (Always Free), però val per a qualsevol Ubuntu.
# Es pot tornar a executar: no esborra dades ni canvia claus que ja existeixin.
#
#   sudo DOMINI=plataforma.hebraia.com BRANCA=mvp bash desplegament/instal-la-servidor.sh
#
# Variables:
#   DOMINI  domini públic (cal un registre A cap a la IP del servidor abans d'executar-ho)
#   BRANCA  branca del repositori a instal·lar (per defecte: main)
#   REPO    URL del repositori (per defecte el de GitHub; si és privat, feu servir una clau de desplegament)
set -euo pipefail

DOMINI="${DOMINI:-plataforma.hebraia.com}"
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
apt-get install -y -q python3-venv python3-dev git caddy sqlite3 rclone nodejs npm \
    libpango-1.0-0 libpangoft2-1.0-0 unattended-upgrades
apt-get install -y -q libharfbuzz-subset0 2>/dev/null || true   # WeasyPrint el farà servir en versions futures

# Les màquines petites (1 GB) necessiten memòria d'intercanvi per compilar el tauler
if [ "$(awk '/MemTotal/ {print $2}' /proc/meminfo)" -lt 2000000 ] && ! swapon --show | grep -q .; then
    pas "Memòria d'intercanvi de 2 GB"
    fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
    grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

pas "Usuari i carpetes"
id hebra >/dev/null 2>&1 || useradd --system --home-dir "$DADES" --shell /usr/sbin/nologin hebra
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

pas "HTTPS ($DOMINI)"
sed "s/^plataforma\.hebraia\.com {/$DOMINI {/" "$APP/desplegament/Caddyfile" > /etc/caddy/Caddyfile
systemctl enable -q caddy && systemctl reload-or-restart caddy

# Les imatges d'Ubuntu d'Oracle Cloud tanquen els ports amb iptables, a més de la llista de seguretat de la VCN
if [ -f /etc/iptables/rules.v4 ] && ! iptables -C INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null; then
    pas "Obrint els ports 80 i 443 (iptables d'Oracle)"
    iptables -I INPUT 5 -p tcp --dport 80 -m state --state NEW -j ACCEPT
    iptables -I INPUT 5 -p tcp --dport 443 -m state --state NEW -j ACCEPT
    netfilter-persistent save >/dev/null 2>&1 || iptables-save > /etc/iptables/rules.v4
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
  1. Obriu https://$DOMINI/salut (el certificat pot trigar un minut el primer cop).
  2. Creeu el primer usuari:
       sudo hebra-admin usuari --correu nom@hebraia.com --nom Nom --rol admin
  3. Configureu el destí remot de les còpies (secció «Còpies de seguretat»).
  4. Doneu d'alta un monitor gratuït a https://$DOMINI/salut.
EOF
