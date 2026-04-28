#!/usr/bin/env bash
# Hook de despliegue de Certbot para modelo push de certificados en el Gateway.

set -euo pipefail

SOURCE_DIR="${RENEWED_LINEAGE:-}"
GATEWAY_CERT_DIR="${GATEWAY_CERT_DIR:-/opt/gateway/certs}"
NGINX_SERVICE="${NGINX_SERVICE:-nginx}"
NGINX_GROUP="${NGINX_GROUP:-www-data}"
LOG_FILE="${LOG_FILE:-/var/log/cert_push.log}"

log() {
	printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "$LOG_FILE"
}

if [[ -z "$SOURCE_DIR" ]]; then
	echo "RENEWED_LINEAGE no definido. Este script debe ejecutarse como deploy-hook de Certbot." >&2
	exit 1
fi

FULLCHAIN_SRC="$SOURCE_DIR/fullchain.pem"
PRIVKEY_SRC="$SOURCE_DIR/privkey.pem"

if [[ ! -f "$FULLCHAIN_SRC" || ! -f "$PRIVKEY_SRC" ]]; then
	echo "No se encontraron fullchain.pem o privkey.pem en $SOURCE_DIR" >&2
	exit 1
fi

install -d -m 750 "$GATEWAY_CERT_DIR"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

install -m 640 -g "$NGINX_GROUP" "$FULLCHAIN_SRC" "$tmp_dir/fullchain.pem"
install -m 640 -g "$NGINX_GROUP" "$PRIVKEY_SRC" "$tmp_dir/privkey.pem"

if [[ -f "$GATEWAY_CERT_DIR/fullchain.pem" ]]; then
	cp "$GATEWAY_CERT_DIR/fullchain.pem" "$GATEWAY_CERT_DIR/fullchain.pem.bak"
fi
if [[ -f "$GATEWAY_CERT_DIR/privkey.pem" ]]; then
	cp "$GATEWAY_CERT_DIR/privkey.pem" "$GATEWAY_CERT_DIR/privkey.pem.bak"
fi

mv "$tmp_dir/fullchain.pem" "$GATEWAY_CERT_DIR/fullchain.pem"
mv "$tmp_dir/privkey.pem" "$GATEWAY_CERT_DIR/privkey.pem"

if ! nginx -t >/dev/null 2>&1; then
	log "ERROR: nginx -t fallo tras actualizar certificados"
	exit 1
fi

systemctl reload "$NGINX_SERVICE"
log "Certificados actualizados en $GATEWAY_CERT_DIR y servicio $NGINX_SERVICE recargado"
