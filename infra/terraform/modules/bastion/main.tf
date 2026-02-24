# ==============================================================================
# BASTION HOST MODULE
# ==============================================================================
# Deploys a hardened bastion EC2 instance in a public subnet with:
#   - Strict source-IP SSH allowlist (Security Group)
#   - IMDSv2 enforced (prevents SSRF / credential theft)
#   - SSH hardening via user_data (root login disabled, key-only auth)
#   - Elastic IP for a stable public address
#   - Encrypted root volume
# ==============================================================================

# --- Latest Amazon Linux 2023 AMI ---

# Amazon Linux 2023 AMI (ARM64 for Graviton)
data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-arm64"]
  }

  filter {
    name   = "architecture"
    values = ["arm64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# --- Validation: OpenVPN requires valid VPC CIDR ---

resource "null_resource" "validate_openvpn_cidr" {
  lifecycle {
    precondition {
      condition     = !var.enable_openvpn || (var.vpc_cidr != "" && can(cidrhost(var.vpc_cidr, 0)))
      error_message = "vpc_cidr must be a valid CIDR block when enable_openvpn is true. OpenVPN requires this to push routes to clients for private subnet access."
    }
  }
}

# --- IAM Role & Instance Profile (SSM access + least-privilege Secrets Manager for OpenVPN PKI) ---

data "aws_iam_policy_document" "bastion_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "bastion" {
  name               = "${var.project_name}-${var.env}-bastion-role"
  assume_role_policy = data.aws_iam_policy_document.bastion_assume_role.json

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.env}-bastion-role"
  })
}

# SSM Session Manager — engineers can open a shell without opening port 22
resource "aws_iam_role_policy_attachment" "bastion_ssm" {
  role       = aws_iam_role.bastion.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Least-privilege: only the OpenVPN secret paths for this project/env
resource "aws_iam_role_policy" "bastion_secrets" {
  name = "${var.project_name}-${var.env}-bastion-openvpn-secrets"
  role = aws_iam_role.bastion.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Effect = "Allow"
          Action = [
            "secretsmanager:CreateSecret",
            "secretsmanager:DescribeSecret",
            "secretsmanager:GetSecretValue",
            "secretsmanager:PutSecretValue",
          ]
          Resource = "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:${var.project_name}/${var.env}/openvpn/*"
        },
      ],
      var.kms_key_arn != null ? [
        {
          Effect = "Allow"
          Action = [
            "kms:Decrypt",
            "kms:DescribeKey",
            "kms:GenerateDataKey",
          ]
          Resource = var.kms_key_arn
        },
      ] : []
    )
  })
}

resource "aws_iam_instance_profile" "bastion" {
  name = "${var.project_name}-${var.env}-bastion-profile"
  role = aws_iam_role.bastion.name

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.env}-bastion-profile"
  })
}

# --- Elastic IP (allocated first so it can be interpolated into user_data) ---

resource "aws_eip" "bastion" {
  domain = "vpc"

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.env}-bastion-eip"
  })
}

# --- EC2 Instance ---

resource "aws_instance" "bastion" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  subnet_id              = var.public_subnet_id
  vpc_security_group_ids = [aws_security_group.bastion.id]
  key_name               = var.key_name
  iam_instance_profile   = aws_iam_instance_profile.bastion.name
  monitoring             = true

  user_data = <<-EOF
    #!/bin/bash
    set -euo pipefail

    # Harden SSH
    sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/'           /etc/ssh/sshd_config
    sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
    sed -i 's/^#\?X11Forwarding.*/X11Forwarding no/'               /etc/ssh/sshd_config
    sed -i 's/^#\?MaxAuthTries.*/MaxAuthTries 3/'                   /etc/ssh/sshd_config
    sed -i 's/^#\?ClientAliveInterval.*/ClientAliveInterval 300/'   /etc/ssh/sshd_config
    sed -i 's/^#\?ClientAliveCountMax.*/ClientAliveCountMax 2/'     /etc/ssh/sshd_config
    systemctl restart sshd

    # System updates
    dnf update -y || true

    # Automatic security updates
    dnf install -y dnf-automatic
    sed -i 's/apply_updates = no/apply_updates = yes/' /etc/dnf/automatic.conf
    systemctl enable --now dnf-automatic-install.timer

    # Useful tools
    dnf install -y htop tmux

    %{if var.enable_openvpn}
    # =========================================================================
    # OpenVPN Server Setup
    # =========================================================================
    # easy-rsa is NOT available in AL2023 default repos — install from GitHub
    EASYRSA_VERSION="3.2.0"
    # NOTE: SHA256 digest for EasyRSA v3.2.0 (EasyRSA-3.2.0.tgz).
    # Recompute with: curl -fsSL "https://github.com/OpenVPN/easy-rsa/releases/download/v$${EASYRSA_VERSION}/EasyRSA-$${EASYRSA_VERSION}.tgz" | sha256sum
    EASYRSA_SHA256="db8164165a109bf1f6dbf578c3341349821bb4fde5629398d82918330134b43c"
    dnf install -y openvpn iptables-services

    echo ">>> Installing EasyRSA v$EASYRSA_VERSION from GitHub..."
    curl -fsSL "https://github.com/OpenVPN/easy-rsa/releases/download/v$${EASYRSA_VERSION}/EasyRSA-$${EASYRSA_VERSION}.tgz" \
      -o /tmp/easyrsa.tgz

    # Verify SHA256 checksum if an expected digest is provided
    if [ -n "$EASYRSA_SHA256" ]; then
      echo "$EASYRSA_SHA256  /tmp/easyrsa.tgz" | sha256sum -c - || { echo "SHA256 checksum verification failed!"; exit 1; }
    else
      echo "Skipping EasyRSA checksum verification (no expected digest provided)."
    fi

    # Extract and install
    tar -xzf /tmp/easyrsa.tgz -C /opt
    ln -sf "/opt/EasyRSA-$${EASYRSA_VERSION}/easyrsa" /usr/local/bin/easyrsa

    # --- PKI (Certificate Authority) ---
    # PKI is durable: generated on first boot, persisted to Secrets Manager, and
    # restored from there on every subsequent boot (including after instance replacement).
    # Existing client .ovpn files therefore remain valid indefinitely.
    export EASYRSA_BATCH=1
    export EASYRSA_PKI=/etc/openvpn/easy-rsa/pki
    PKI_SECRET="${var.project_name}/${var.env}/openvpn/pki"
    CLIENT_SECRET="${var.project_name}/${var.env}/openvpn/clients/client1"
    REGION="${var.aws_region}"

    # Optional KMS key arg — empty string when no CMK is configured
    KMS_ARG=""
    %{if var.kms_key_arn != null}
    KMS_ARG="--kms-key-id ${var.kms_key_arn}"
    %{endif}

    mkdir -p /etc/openvpn/easy-rsa/pki/issued \
             /etc/openvpn/easy-rsa/pki/private \
             /etc/openvpn/server

    if aws secretsmanager describe-secret \
         --secret-id "$PKI_SECRET" \
         --region "$REGION" >/dev/null 2>&1; then
      echo ">>> PKI found in Secrets Manager — restoring to /etc/openvpn ..."
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
      echo ">>> PKI not found in Secrets Manager — generating new PKI ..."
      cd /etc/openvpn/easy-rsa
      /usr/local/bin/easyrsa init-pki
      /usr/local/bin/easyrsa build-ca nopass
      /usr/local/bin/easyrsa build-server-full server nopass
      /usr/local/bin/easyrsa build-client-full client1 nopass
      /usr/local/bin/easyrsa gen-dh
      openvpn --genkey secret /etc/openvpn/ta.key

      echo ">>> Persisting PKI to Secrets Manager (durable store) ..."
      PKI_JSON=$(python3 -c "
import json
PEMS = {
    '/etc/openvpn/easy-rsa/pki/ca.crt':             open('/etc/openvpn/easy-rsa/pki/ca.crt').read(),
    '/etc/openvpn/easy-rsa/pki/private/ca.key':     open('/etc/openvpn/easy-rsa/pki/private/ca.key').read(),
    '/etc/openvpn/easy-rsa/pki/issued/server.crt':  open('/etc/openvpn/easy-rsa/pki/issued/server.crt').read(),
    '/etc/openvpn/easy-rsa/pki/private/server.key': open('/etc/openvpn/easy-rsa/pki/private/server.key').read(),
    '/etc/openvpn/easy-rsa/pki/issued/client1.crt': open('/etc/openvpn/easy-rsa/pki/issued/client1.crt').read(),
    '/etc/openvpn/easy-rsa/pki/private/client1.key':open('/etc/openvpn/easy-rsa/pki/private/client1.key').read(),
    '/etc/openvpn/easy-rsa/pki/dh.pem':             open('/etc/openvpn/easy-rsa/pki/dh.pem').read(),
    '/etc/openvpn/ta.key':                          open('/etc/openvpn/ta.key').read(),
}
print(json.dumps(PEMS))
")

      aws secretsmanager create-secret \
        --name "$PKI_SECRET" \
        --description "OpenVPN PKI for ${var.project_name}-${var.env} — DO NOT DELETE (loss = client lockout)" \
        $KMS_ARG \
        --secret-string "$PKI_JSON" \
        --region "$REGION"
    fi

    # --- Server config (no leading whitespace!) ---
    cat > /etc/openvpn/server/server.conf <<'OVPN'
port 1194
proto udp
dev tun
ca       /etc/openvpn/easy-rsa/pki/ca.crt
cert     /etc/openvpn/easy-rsa/pki/issued/server.crt
key      /etc/openvpn/easy-rsa/pki/private/server.key
dh       /etc/openvpn/easy-rsa/pki/dh.pem
tls-auth /etc/openvpn/ta.key 0

server ${var.vpn_client_cidr} ${cidrnetmask(var.vpn_client_cidr)}
push "route ${cidrhost(var.vpc_cidr, 0)} ${cidrnetmask(var.vpc_cidr)}"
push "dhcp-option DNS ${cidrhost(var.vpc_cidr, 2)}"

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

    # --- IP forwarding & NAT ---
    echo "net.ipv4.ip_forward = 1" > /etc/sysctl.d/99-openvpn.conf
    sysctl -w net.ipv4.ip_forward=1

    # Masquerade VPN traffic so it can reach VPC resources
    IFACE=$(ip -o route get 1 | awk '{print $5}')
    iptables -t nat -A POSTROUTING -s ${var.vpn_client_cidr} -o "$IFACE" -j MASQUERADE
    iptables -A FORWARD -i tun0 -o "$IFACE" -j ACCEPT
    iptables -A FORWARD -i "$IFACE" -o tun0 -m state --state RELATED,ESTABLISHED -j ACCEPT
    service iptables save

    # --- Start OpenVPN ---
    systemctl enable --now openvpn-server@server

    # --- Use EIP (interpolated from Terraform, not IMDS) ---
    BASTION_PUBLIC_IP="${aws_eip.bastion.public_ip}"

    # --- Generate client .ovpn, upload to Secrets Manager, delete local copy ---
    # The profile is never left on disk — sensitive key material is only at rest
    # inside the KMS-encrypted Secrets Manager secret.
    OVPN_TMP=$(mktemp)
    cat > "$OVPN_TMP" <<CLIENTEOF
client
dev tun
proto udp
remote $BASTION_PUBLIC_IP 1194
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

    echo ">>> Uploading client .ovpn to Secrets Manager ..."
    aws secretsmanager create-secret \
      --name "$CLIENT_SECRET" \
      --description "OpenVPN client config for ${var.project_name}-${var.env}/client1" \
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
    %{endif}
  EOF

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 1
  }

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.env}-bastion"
  })

  depends_on = [
    aws_iam_role_policy.bastion_secrets,
    aws_iam_role_policy_attachment.bastion_ssm,
    aws_iam_instance_profile.bastion,
  ]

  lifecycle {
    ignore_changes = [ami]
  }
}

# --- Associate EIP with Instance ---

resource "aws_eip_association" "bastion" {
  instance_id   = aws_instance.bastion.id
  allocation_id = aws_eip.bastion.id
}
