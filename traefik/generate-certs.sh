#!/bin/bash
# Generate self-signed certs for radio.fleet.wood
# Run once on the radio box

DOMAIN="radio.fleet.wood"
CERT_DIR="$(dirname "$0")/certs"
mkdir -p "$CERT_DIR"

openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 \
  -nodes -keyout "$CERT_DIR/$DOMAIN.key" -out "$CERT_DIR/$DOMAIN.crt" \
  -subj "/CN=$DOMAIN" \
  -addext "subjectAltName=DNS:$DOMAIN,DNS:radio,IP:10.0.0.0/8,IP:192.168.0.0/16,IP:172.16.0.0/12"

echo "Certs generated at $CERT_DIR/"
echo "  $DOMAIN.crt"
echo "  $DOMAIN.key"
echo ""
echo "Add the .crt to your browser/OS trust store to avoid warnings."
