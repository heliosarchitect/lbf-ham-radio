#!/bin/bash
# Generate self-signed certs for the radio web interface
# Reads hostname from config.env

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.env"

DOMAIN="${RADIO_HOSTNAME:-radio.fleet.wood}"
CERT_DIR="$SCRIPT_DIR/certs"
DAYS="${CERT_DAYS:-3650}"

mkdir -p "$CERT_DIR"

openssl req -x509 -newkey rsa:4096 -sha256 -days "$DAYS" \
  -nodes -keyout "$CERT_DIR/cert.key" -out "$CERT_DIR/cert.crt" \
  -subj "/CN=$DOMAIN" \
  -addext "subjectAltName=DNS:$DOMAIN,DNS:radio,IP:10.0.0.0/8,IP:192.168.0.0/16,IP:172.16.0.0/12"

echo "Certs generated for: $DOMAIN"
echo "  $CERT_DIR/cert.crt"
echo "  $CERT_DIR/cert.key"
echo ""
echo "Add cert.crt to your browser/OS trust store to avoid warnings."
