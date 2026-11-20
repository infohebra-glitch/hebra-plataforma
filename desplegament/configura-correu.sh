#!/usr/bin/env bash
# Configura (o canvia) el compte de correu que envia els informes. Es pot tornar a executar sempre que calgui.
#   sudo bash /opt/hebra-plataforma/desplegament/configura-correu.sh
#
# Pregunta el servidor SMTP, l'usuari, la contrasenya, el remitent i l'adreça del «mode de proves»,
# ho desa a /etc/hebra/plataforma.env, reinicia la plataforma i envia un correu de prova.
#
# Mode de proves (HEBRA_CORREU_REDIRIGEIX): si hi poseu una adreça, TOTS els correus van només allà,
# amb els destinataris de veritat a l'assumpte. Quan vulgueu enviar als clients, torneu a executar
# aquest script i deixeu-la buida (escriviu un guió: -).
#
# Amb Gmail: servidor smtp.gmail.com, port 587, usuari = l'adreça de Gmail, contrasenya = una
# «contrasenya d'aplicació» (Compte de Google > Seguretat > Verificació en 2 passos > Contrasenyes
# d'aplicacions). Per enviar com a clientes@hebraia.com, a Gmail: Configuració > Comptes >
# «Envia el correu com a» > afegeix clientes@hebraia.com.
set -euo pipefail
ENVF=/etc/hebra/plataforma.env
[ "$(id -u)" = 0 ] || { echo "Executeu-ho amb sudo"; exit 1; }
[ -f "$ENVF" ] || { echo "No trobo $ENVF: primer instal·leu la plataforma (instal-la-servidor.sh)"; exit 1; }

actual() { sed -n "s/^$1=//p" "$ENVF" | tail -n 1; }
pregunta() {  # pregunta <variable> <text> <valor per defecte>
    local v; read -r -p "$2 [$3]: " v
    if [ "$v" = "-" ]; then v=""; elif [ -z "$v" ]; then v="$3"; fi
    printf '%s' "$v"
}

echo "Correu dels informes. Prem Enter per deixar el valor entre claudàtors; «-» per deixar-lo buit."
HOST=$(pregunta HOST "Servidor SMTP" "$(actual HEBRA_SMTP_HOST || true)")
HOST=${HOST:-}
PORT=$(pregunta PORT "Port" "$(actual HEBRA_SMTP_PORT | grep . || echo 587)")
USUARI=$(pregunta USUARI "Usuari (normalment l'adreça del compte)" "$(actual HEBRA_SMTP_USUARI || true)")
read -r -s -p "Contrasenya (no es veu mentre l'escrius; Enter = no la canviïs): " CONTRA; echo
[ -n "$CONTRA" ] || CONTRA="$(actual HEBRA_SMTP_CONTRASENYA || true)"
REMITENT=$(pregunta REMITENT "Remitent" "$(actual HEBRA_SMTP_REMITENT | grep . || echo 'Hebra <clientes@hebraia.com>')")
REDIR=$(pregunta REDIR "Mode de proves: envia-ho TOT només a (- per enviar als destinataris reals)" \
    "$(actual HEBRA_CORREU_REDIRIGEIX | grep . || echo clientes@hebraia.com)")

python3 - "$ENVF" "HEBRA_SMTP_HOST=$HOST" "HEBRA_SMTP_PORT=$PORT" "HEBRA_SMTP_USUARI=$USUARI" \
    "HEBRA_SMTP_CONTRASENYA=$CONTRA" "HEBRA_SMTP_REMITENT=$REMITENT" "HEBRA_CORREU_REDIRIGEIX=$REDIR" <<'PY'
import re, sys
ruta, parells = sys.argv[1], [a.split("=", 1) for a in sys.argv[2:]]
linies = open(ruta, encoding="utf-8").read().splitlines()
claus = {k for k, _ in parells}
# Treu les línies (també les comentades) d'aquestes claus i les torna a escriure juntes al final.
linies = [l for l in linies if not re.match(r"^#?\s*(%s)=" % "|".join(map(re.escape, claus)), l)
          and not l.startswith("# Correu dels informes")]
while linies and not linies[-1].strip():
    linies.pop()
linies += ["", "# Correu dels informes (desplegament/configura-correu.sh)"] + [f"{k}={v}" for k, v in parells]
open(ruta, "w", encoding="utf-8").write("\n".join(linies) + "\n")
PY
chown root:hebra "$ENVF" && chmod 640 "$ENVF"
systemctl restart hebra-web
echo "Desat i plataforma reiniciada. Envio un correu de prova..."
if hebra-admin correu; then
    echo "Fet. Mireu la safata d'entrada (i el correu brossa)."
else
    echo "No s'ha pogut enviar. Reviseu les dades i torneu a executar aquest script."
    exit 1
fi
