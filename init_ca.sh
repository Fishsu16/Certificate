#!/bin/bash
set -e

mkdir -p ca/root ca/intermediate

echo "Generating Root CA key..."
openssl genrsa -out ca/root/root.key.pem 4096

echo "Generating Root CA certificate..."
openssl req -x509 -new -nodes -key ca/root/root.key.pem -sha256 -days 3650 -out ca/root/root.cert.pem -subj "/CN=My Root CA"

echo "Generating Intermediate CA key..."
openssl genrsa -out ca/intermediate/intermediate.key.pem 4096

echo "Generating Intermediate CA CSR..."
openssl req -new -key ca/intermediate/intermediate.key.pem -out ca/intermediate/intermediate.csr.pem -subj "/CN=My Intermediate CA"

echo "Signing Intermediate CA with Root CA..."
openssl x509 -req -in ca/intermediate/intermediate.csr.pem -CA ca/root/root.cert.pem -CAkey ca/root/root.key.pem -CAcreateserial -out ca/intermediate/intermediate.cert.pem -days 1825 -sha256

echo "Initialization done."
