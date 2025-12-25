#!/usr/bin/env bash
set -euo pipefail

CERT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CA_KEY="${CERT_DIR}/ca.key"
CA_CRT="${CERT_DIR}/ca.crt"
SERVER_KEY="${CERT_DIR}/server.key"
SERVER_CSR="${CERT_DIR}/server.csr"
SERVER_CRT="${CERT_DIR}/server.crt"
CLIENT_KEY="${CERT_DIR}/client.key"
CLIENT_CSR="${CERT_DIR}/client.csr"
CLIENT_CRT="${CERT_DIR}/client.crt"

mkdir -p "${CERT_DIR}"

# Create CA
if [[ ! -f "${CA_KEY}" ]]; then
  openssl genrsa -out "${CA_KEY}" 4096
fi

if [[ ! -f "${CA_CRT}" ]]; then
  openssl req -x509 -new -nodes -key "${CA_KEY}" -sha256 -days 3650 \
    -subj "/CN=local-mtls-ca" \
    -out "${CA_CRT}"
fi

# Server cert
cat > "${CERT_DIR}/server.ext" <<EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
IP.1 = 127.0.0.1
EOF

if [[ ! -f "${SERVER_KEY}" ]]; then
  openssl genrsa -out "${SERVER_KEY}" 2048
fi

openssl req -new -key "${SERVER_KEY}" -subj "/CN=vertex-chat-bot" -out "${SERVER_CSR}"
openssl x509 -req -in "${SERVER_CSR}" -CA "${CA_CRT}" -CAkey "${CA_KEY}" -CAcreateserial \
  -out "${SERVER_CRT}" -days 825 -sha256 -extfile "${CERT_DIR}/server.ext"

# Client cert
cat > "${CERT_DIR}/client.ext" <<EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = clientAuth
EOF

if [[ ! -f "${CLIENT_KEY}" ]]; then
  openssl genrsa -out "${CLIENT_KEY}" 2048
fi

openssl req -new -key "${CLIENT_KEY}" -subj "/CN=vertex-chat-client" -out "${CLIENT_CSR}"
openssl x509 -req -in "${CLIENT_CSR}" -CA "${CA_CRT}" -CAkey "${CA_KEY}" -CAcreateserial \
  -out "${CLIENT_CRT}" -days 825 -sha256 -extfile "${CERT_DIR}/client.ext"

echo "Certificates generated under ${CERT_DIR}"

