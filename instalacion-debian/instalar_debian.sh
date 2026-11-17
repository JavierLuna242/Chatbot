#!/bin/bash
# Instala en la VM Debian 12/13 de Azure, como servicios systemd: el servidor MCP (127.0.0.1:9000) y la web Laravel (127.0.0.1:8000).
# La base de datos es Supabase y los flujos corren en n8n Cloud: aquí no se instala PostgreSQL, Ollama ni n8n.
# El túnel de Cloudflare (ya existente) publica los dos servicios; ver el mensaje final.
# Uso, como root, desde la carpeta del proyecto copiada a la VM:  bash instalacion-debian/instalar_debian.sh
# Se puede volver a ejecutar: solo instala lo que falte y aplica los cambios del proyecto.
set -euo pipefail
PROY="$(cd "$(dirname "$0")/.." && pwd)"
paso() { echo; echo "=== $*"; }
umask 077   # todo lo que crea este script (secretos, .env) nace legible solo por root

paso "Variables"
mkdir -p /etc/unab && chmod 700 /etc/unab
# .env del proyecto, sin \r de Windows, comentarios ni espacios finales
grep -E '^[A-Z][A-Z0-9_]*=' "$PROY/.env" | tr -d '\r' | sed -e 's/[[:space:]]*#.*$//' -e 's/[[:space:]]*$//' > /etc/unab/env
set -a; . /etc/unab/env; set +a
for v in DATABASE_URL MCP_TOKEN N8N_CHAT_URL N8N_CHAT_USER N8N_CHAT_PASSWORD; do
  [ -n "${!v:-}" ] || { echo "ERROR: falta $v en .env"; exit 1; }
done
[ "${#MCP_TOKEN}" -ge 32 ] || { echo "ERROR: MCP_TOKEN debe tener al menos 32 caracteres (openssl rand -hex 32)"; exit 1; }

paso "Paquetes de Debian"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq curl ca-certificates gnupg >/dev/null
CODENAME=$(. /etc/os-release; echo "$VERSION_CODENAME")
umask 022   # llaves y listas de apt deben ser legibles por el usuario _apt (con umask 077 apt falla: "is not signed")
# PHP 8.4+ (el composer.lock exige 8.4.1 o superior): Debian 12 solo trae 8.2, así que se instala php8.4-cli en paralelo desde el repositorio de Sury
# (prioridad baja y sin cambiar el php por defecto: una VM compartida puede tener otros proyectos con su propio PHP)
PHP=php; PHPPAQ="php-cli php-mbstring php-xml php-curl"
if ! apt-cache policy php-cli | grep -qE 'Candidate: [0-9]+:8\.([4-9]|[1-9][0-9])'; then
  curl -fsSLo /tmp/sury-keyring.deb https://packages.sury.org/debsuryorg-archive-keyring.deb && dpkg -i /tmp/sury-keyring.deb >/dev/null && rm /tmp/sury-keyring.deb
  echo "deb [signed-by=/usr/share/keyrings/deb.sury.org-php.gpg] https://packages.sury.org/php/ ${CODENAME} main" > /etc/apt/sources.list.d/sury-php.list
  # php8.4-* exige php-common >= 2:95: solo ese paquete auxiliar se toma de Sury; todo lo demás queda con prioridad mínima
  printf 'Package: php-common\nPin: origin packages.sury.org\nPin-Priority: 500\n\nPackage: *\nPin: origin packages.sury.org\nPin-Priority: 1\n' > /etc/apt/preferences.d/sury-php
  PHP=php8.4; PHPPAQ="php8.4-cli php8.4-mbstring php8.4-xml php8.4-curl"
fi
apt-get update -qq
PHP_ANTES=$(readlink -f /usr/bin/php 2>/dev/null || true)
apt-get install -y -qq python3-venv rsync unzip $PHPPAQ composer >/dev/null
# el php por defecto de la VM sigue siendo el que era
[ "$PHP" = php ] || [ -z "$PHP_ANTES" ] || update-alternatives --set php "$PHP_ANTES" >/dev/null
PHP_BIN=$(command -v "$PHP")
# El composer de Debian 12 (2.5) no corre bajo PHP 8.4: usa el PHP del sistema solo para copiar los paquetes del lock;
# la aplicación siempre se ejecuta con $PHP_BIN (por eso "install" va con --ignore-platform-req=php y sin scripts).
composer() { COMPOSER_ALLOW_SUPERUSER=1 php /usr/bin/composer "$@"; }
umask 077

paso "Servidor MCP"
mkdir -p /opt/unab && chmod 755 /opt/unab   # con umask 077 nace 700 y los servicios (usuarios no root) no podrían entrar
[ -x /opt/unab/venv/bin/python ] || python3 -m venv /opt/unab/venv
/opt/unab/venv/bin/pip install -q -r "$PROY/servidor-mcp/requirements.txt"
chmod -R go+rX /opt/unab/venv
# el servicio no puede leer /home (ProtectHome): se publica una copia del código en /opt/unab/mcp
mkdir -p /opt/unab/mcp && rsync -a --delete --chmod=Dgo+rx,Fgo+r "$PROY/servidor-mcp/" /opt/unab/mcp/
# cada servicio recibe solo las variables que necesita
cat > /etc/unab/mcp.env <<EOF
DATABASE_URL=${DATABASE_URL}
MCP_TOKEN=${MCP_TOKEN}
MCP_HOST=127.0.0.1
CALENDARIO_CSV_URL=${CALENDARIO_CSV_URL:-}
TZ=America/Bogota
EOF
cat > /etc/systemd/system/unab-mcp.service <<EOF
[Unit]
Description=Servidor MCP del asistente (FastMCP, 127.0.0.1:9000, con token Bearer)
After=network-online.target
[Service]
DynamicUser=yes
# FastMCP necesita un HOME escribible: directorio de estado privado del servicio
StateDirectory=unab-mcp
Environment=HOME=/var/lib/unab-mcp
EnvironmentFile=/etc/unab/mcp.env
WorkingDirectory=/opt/unab/mcp
ExecStart=/opt/unab/venv/bin/python servidor_mcp.py
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
[Install]
WantedBy=multi-user.target
EOF

paso "Web Laravel (solo chat)"
WEB=/opt/unab/web
mkdir -p "$WEB"
rsync -a --delete --chmod=Dgo+rx,Fgo+r --exclude /vendor --exclude /.env --exclude /storage --exclude /bootstrap/cache "$PROY/sitio-web/" "$WEB/"
# storage/ y bootstrap/cache los crea composer (script post-autoload-dump); rsync no los toca
mkdir -p "$WEB/storage/framework/cache/data" "$WEB/storage/framework/sessions" "$WEB/storage/framework/views" "$WEB/storage/logs" "$WEB/bootstrap/cache"
(cd "$WEB" && composer install --no-dev --optimize-autoloader --no-interaction -q --no-scripts --ignore-platform-req=php \
  && "$PHP_BIN" artisan package:discover -q)   # lo que haría el script post-autoload-dump, pero con el PHP del proyecto
chmod -R go+rX "$WEB/vendor"
# .env de Laravel: se regenera en cada ejecución (conserva APP_KEY, que cifra las sesiones)
APP_KEY=$(grep -s '^APP_KEY=' "$WEB/.env" | cut -d= -f2- || true)
cat > "$WEB/.env" <<EOF
APP_NAME="Asistente Académico"
APP_ENV=production
APP_KEY=${APP_KEY}
APP_DEBUG=false
APP_URL=https://chatbot.javier.life
APP_LOCALE=es
APP_FALLBACK_LOCALE=es
LOG_CHANNEL=stack
LOG_LEVEL=info
SESSION_DRIVER=file
SESSION_LIFETIME=120
SESSION_ENCRYPT=true
SESSION_COOKIE=__Host-sesion
SESSION_SECURE_COOKIE=true
SESSION_HTTP_ONLY=true
SESSION_SAME_SITE=lax
CACHE_STORE=file
QUEUE_CONNECTION=sync
N8N_CHAT_URL=${N8N_CHAT_URL}
N8N_CHAT_USER=${N8N_CHAT_USER}
N8N_CHAT_PASSWORD=${N8N_CHAT_PASSWORD}
EOF
[ -n "$APP_KEY" ] || (cd "$WEB" && "$PHP_BIN" artisan key:generate --force -q)
(cd "$WEB" && "$PHP_BIN" artisan config:clear -q && "$PHP_BIN" artisan view:clear -q)
chown -R www-data:www-data "$WEB/storage" "$WEB/bootstrap/cache"   # después de artisan, que corre como root
chmod 640 "$WEB/.env" && chown root:www-data "$WEB/.env"
cat > /etc/systemd/system/unab-web.service <<EOF
[Unit]
Description=Web Laravel del asistente (127.0.0.1:8000)
After=network-online.target
[Service]
User=www-data
WorkingDirectory=$WEB
# Limitación: servidor embebido de PHP con 4 procesos; con muchos usuarios a la vez conviene nginx + php-fpm
Environment=PHP_CLI_SERVER_WORKERS=4
ExecStart=$PHP_BIN artisan serve --host=127.0.0.1 --port=8000 --no-reload
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
[Install]
WantedBy=multi-user.target
EOF

paso "Escaneo de dependencias (composer audit)"
(cd "$WEB" && composer audit --no-dev --locked 2>&1 | tail -5) || echo "AVISO: composer audit encontró problemas (ver arriba)"

paso "Servicios"
systemctl daemon-reload
systemctl enable --now unab-mcp unab-web
systemctl restart unab-mcp unab-web
for i in $(seq 30); do curl -s -o /dev/null http://127.0.0.1:9000/mcp && break; sleep 1; done
for i in $(seq 30); do curl -fs -o /dev/null http://127.0.0.1:8000/up && break; sleep 1; done
[ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:9000/mcp)" = 401 ] && echo "MCP: responde 401 sin token (correcto)" || echo "AVISO: el MCP no respondió 401 sin token; revisa: journalctl -u unab-mcp"
systemctl --no-pager --plain list-units 'unab-*' | grep -E 'service'
echo
echo "Listo. Túnel de Cloudflare (Zero Trust > Networks > Tunnels > tu túnel > Public hostnames), servicio HTTP:"
echo "  chatbot.javier.life -> http://localhost:8000"
echo "  mcp.javier.life     -> http://localhost:9000   (n8n Cloud llama a https://mcp.javier.life/mcp con el token Bearer)"
echo "Logs: journalctl -u unab-mcp -u unab-web -f"
