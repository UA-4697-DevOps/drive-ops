#!/bin/bash
set -euo pipefail

# IT IS Terraform shell template with variables injected via templatefile function logic.
# ------------------------------------------------------------------------------
# SYSTEM UPDATES
# ------------------------------------------------------------------------------
dnf update -y || true

dnf install -y dnf-automatic
sed -i 's/apply_updates = no/apply_updates = yes/' /etc/dnf/automatic.conf
systemctl enable --now dnf-automatic-install.timer

# ------------------------------------------------------------------------------
# OPENVPN SETUP
# easy-rsa is NOT available in AL2023 default repos — install from GitHub
# ------------------------------------------------------------------------------
EASYRSA_VERSION="3.2.0"
# NOTE: SHA256 digest for EasyRSA v3.2.0 (EasyRSA-3.2.0.tgz).
# Recompute with: curl -fsSL "https://github.com/OpenVPN/easy-rsa/releases/download/v$${EASYRSA_VERSION}/EasyRSA-$${EASYRSA_VERSION}.tgz" | sha256sum
EASYRSA_SHA256="db8164165a109bf1f6dbf578c3341349821bb4fde5629398d82918330134b43c"

dnf install -y openvpn iptables-services

echo ">>> Installing EasyRSA v$EASYRSA_VERSION from GitHub..."
curl -fsSL "https://github.com/OpenVPN/easy-rsa/releases/download/v$${EASYRSA_VERSION}/EasyRSA-$${EASYRSA_VERSION}.tgz" \
  -o /tmp/easyrsa.tgz

echo "$EASYRSA_SHA256  /tmp/easyrsa.tgz" | sha256sum -c - || {
  echo "SHA256 checksum verification failed!"
  exit 1
}

tar -xzf /tmp/easyrsa.tgz -C /opt
ln -sf "/opt/EasyRSA-$${EASYRSA_VERSION}/easyrsa" /usr/local/bin/easyrsa

# ------------------------------------------------------------------------------
# PKI — durable: generated on first boot, persisted to Secrets Manager, and
# restored from there on every subsequent boot (including after replacement).
# Existing client .ovpn files remain valid indefinitely.
# ------------------------------------------------------------------------------
export EASYRSA_BATCH=1
export EASYRSA_PKI=/etc/openvpn/easy-rsa/pki

PKI_SECRET="${project_name}/${env}/openvpn/pki"
CLIENT_SECRET="${project_name}/${env}/openvpn/clients/client1"
REGION="${aws_region}"

KMS_ARG=""
%{if kms_key_arn != null}
KMS_ARG="--kms-key-id ${kms_key_arn}"
%{endif}

mkdir -p /etc/openvpn/easy-rsa/pki/issued \
         /etc/openvpn/easy-rsa/pki/private \
         /etc/openvpn/server

if aws secretsmanager describe-secret \
     --secret-id "$PKI_SECRET" \
     --region "$REGION" >/dev/null 2>&1; then
  echo ">>> PKI found in Secrets Manager — restoring..."
  aws secretsmanager get-secret-value \
    --secret-id "$PKI_SECRET" \
    --region "$REGION" \
    --query SecretString \
    --output text | \
  python3 -c "
import sys, json, os
d = json.load(sys.stdin)
for path, content in d.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)
print('PKI restored.')
"
else
  echo ">>> PKI not found — generating new PKI..."
  cd /etc/openvpn/easy-rsa
  /usr/local/bin/easyrsa init-pki
  /usr/local/bin/easyrsa build-ca nopass
  /usr/local/bin/easyrsa build-server-full server nopass
  /usr/local/bin/easyrsa build-client-full client1 nopass
  /usr/local/bin/easyrsa gen-dh
  openvpn --genkey secret /etc/openvpn/ta.key

  echo ">>> Persisting PKI to Secrets Manager..."
  PKI_JSON=$(python3 -c "
import json
PEMS = {
    '/etc/openvpn/easy-rsa/pki/ca.crt':              open('/etc/openvpn/easy-rsa/pki/ca.crt').read(),
    '/etc/openvpn/easy-rsa/pki/private/ca.key':      open('/etc/openvpn/easy-rsa/pki/private/ca.key').read(),
    '/etc/openvpn/easy-rsa/pki/issued/server.crt':   open('/etc/openvpn/easy-rsa/pki/issued/server.crt').read(),
    '/etc/openvpn/easy-rsa/pki/private/server.key':  open('/etc/openvpn/easy-rsa/pki/private/server.key').read(),
    '/etc/openvpn/easy-rsa/pki/issued/client1.crt':  open('/etc/openvpn/easy-rsa/pki/issued/client1.crt').read(),
    '/etc/openvpn/easy-rsa/pki/private/client1.key': open('/etc/openvpn/easy-rsa/pki/private/client1.key').read(),
    '/etc/openvpn/easy-rsa/pki/dh.pem':              open('/etc/openvpn/easy-rsa/pki/dh.pem').read(),
    '/etc/openvpn/ta.key':                           open('/etc/openvpn/ta.key').read(),
}
print(json.dumps(PEMS))
")
  aws secretsmanager create-secret \
    --name "$PKI_SECRET" \
    --description "OpenVPN PKI for ${project_name}-${env} — DO NOT DELETE (loss = client lockout)" \
    $KMS_ARG \
    --secret-string "$PKI_JSON" \
    --region "$REGION"
fi

# ------------------------------------------------------------------------------
# SERVER CONFIG
# ------------------------------------------------------------------------------
cat > /etc/openvpn/server/server.conf <<'OVPN'
port 1194
proto udp
dev tun
ca       /etc/openvpn/easy-rsa/pki/ca.crt
cert     /etc/openvpn/easy-rsa/pki/issued/server.crt
key      /etc/openvpn/easy-rsa/pki/private/server.key
dh       /etc/openvpn/easy-rsa/pki/dh.pem
tls-auth /etc/openvpn/ta.key 0

server ${cidrhost(vpn_client_cidr, 0)} ${cidrnetmask(vpn_client_cidr)}
push "route ${cidrhost(vpc_cidr, 0)} ${cidrnetmask(vpc_cidr)}"
push "dhcp-option DNS ${cidrhost(vpc_cidr, 2)}"

keepalive 10 120
cipher AES-256-GCM
data-ciphers AES-256-GCM:AES-128-GCM
user nobody
group nobody
persist-key
persist-tun
status      /var/log/openvpn-status.log
log-append  /var/log/openvpn.log
verb 3
explicit-exit-notify 1
OVPN

# ------------------------------------------------------------------------------
# IP FORWARDING & NAT MASQUERADE
# ------------------------------------------------------------------------------
echo "net.ipv4.ip_forward = 1" > /etc/sysctl.d/99-openvpn.conf
sysctl -w net.ipv4.ip_forward=1

IFACE=$(ip -o route get 1 | awk '{print $5}')
iptables -t nat -A POSTROUTING -s ${vpn_client_cidr} -o "$IFACE" -j MASQUERADE
iptables -A FORWARD -i tun0 -o "$IFACE" -j ACCEPT
iptables -A FORWARD -i "$IFACE" -o tun0 -m state --state RELATED,ESTABLISHED -j ACCEPT
service iptables save

systemctl enable --now openvpn-server@server

# ------------------------------------------------------------------------------
# CLIENT CONFIG — generated, uploaded to Secrets Manager, deleted locally
# Sensitive key material is never left on disk.
# ------------------------------------------------------------------------------
OVPN_TMP=$(mktemp)
cat > "$OVPN_TMP" <<CLIENTEOF
client
dev tun
proto udp
remote ${eip_public_ip} 1194
resolv-retry infinite
nobind
user nobody
group nobody
persist-key
persist-tun
remote-cert-tls server
cipher AES-256-GCM
data-ciphers AES-256-GCM:AES-128-GCM
verb 3
key-direction 1
<ca>
$(cat /etc/openvpn/easy-rsa/pki/ca.crt)
</ca>
<cert>
$(cat /etc/openvpn/easy-rsa/pki/issued/client1.crt)
</cert>
<key>
$(cat /etc/openvpn/easy-rsa/pki/private/client1.key)
</key>
<tls-auth>
$(cat /etc/openvpn/ta.key)
</tls-auth>
CLIENTEOF

echo ">>> Uploading client .ovpn to Secrets Manager..."
aws secretsmanager create-secret \
  --name "$CLIENT_SECRET" \
  --description "OpenVPN client config for ${project_name}-${env}/client1" \
  $KMS_ARG \
  --secret-string "$(cat "$OVPN_TMP")" \
  --region "$REGION" 2>/dev/null || \
aws secretsmanager put-secret-value \
  --secret-id "$CLIENT_SECRET" \
  --secret-string "$(cat "$OVPN_TMP")" \
  --region "$REGION"

rm -f "$OVPN_TMP"
echo ">>> OpenVPN ready. Retrieve client config:"
echo "    aws secretsmanager get-secret-value --secret-id $CLIENT_SECRET --region $REGION --query SecretString --output text > client1.ovpn"
