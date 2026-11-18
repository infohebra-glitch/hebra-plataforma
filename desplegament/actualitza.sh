#!/usr/bin/env bash
# Actualitza la plataforma a l'última versió de la branca instal·lada, amb una còpia abans.
#   sudo bash /opt/hebra-plataforma/desplegament/actualitza.sh
set -euo pipefail
APP=/opt/hebra-plataforma
[ "$(id -u)" = 0 ] || { echo "Executeu-ho amb sudo"; exit 1; }
BRANCA="$(sudo -u hebra git -C "$APP" rev-parse --abbrev-ref HEAD)"
ABANS="$(sudo -u hebra git -C "$APP" rev-parse --short HEAD)"

echo "== Còpia de seguretat abans d'actualitzar"
# 0 = feta; 2 = feta al servidor però no enviada fora (es continua); 1 = no s'ha pogut fer
rc=0; hebra-admin copia || rc=$?
if [ "$rc" -eq 1 ]; then echo "La còpia ha fallat: no actualitzo"; exit 1; fi

echo "== Codi ($BRANCA)"
sudo -u hebra git -C "$APP" fetch -q origin "$BRANCA"
sudo -u hebra git -C "$APP" reset -q --hard "origin/$BRANCA"
sudo -u hebra "$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"
( cd "$APP/frontend" && sudo -u hebra HOME=/var/lib/hebra npm ci --no-audit --no-fund --loglevel=error \
    && sudo -u hebra HOME=/var/lib/hebra npm run build --silent )
install -m 644 "$APP/desplegament/hebra-web.service" "$APP/desplegament/hebra-copia.service" \
    "$APP/desplegament/hebra-copia.timer" /etc/systemd/system/
install -m 755 "$APP/desplegament/hebra-admin" /usr/local/bin/hebra-admin
systemctl daemon-reload
systemctl restart hebra-web

for i in $(seq 1 20); do curl -fsS http://127.0.0.1:8000/salut >/dev/null 2>&1 && break; sleep 1; done
if curl -fsS http://127.0.0.1:8000/salut; then
    echo; echo "Actualitzat: $ABANS -> $(sudo -u hebra git -C "$APP" rev-parse --short HEAD)"
else
    echo "La web no respon després d'actualitzar. Tornar enrere:"
    echo "  sudo -u hebra git -C $APP reset --hard $ABANS && sudo systemctl restart hebra-web"
    exit 1
fi
