#!/bin/bash
set -euo pipefail

# ------------------------------------------------------------------------------
# SSH HARDENING
# ------------------------------------------------------------------------------
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/'           /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#\?X11Forwarding.*/X11Forwarding no/'               /etc/ssh/sshd_config
sed -i 's/^#\?MaxAuthTries.*/MaxAuthTries 3/'                   /etc/ssh/sshd_config
sed -i 's/^#\?ClientAliveInterval.*/ClientAliveInterval 300/'   /etc/ssh/sshd_config
sed -i 's/^#\?ClientAliveCountMax.*/ClientAliveCountMax 2/'     /etc/ssh/sshd_config
sshd -t
systemctl restart sshd

# ------------------------------------------------------------------------------
# SYSTEM UPDATES
# ------------------------------------------------------------------------------
dnf update -y || true

# Automatic security updates
dnf install -y dnf-automatic
sed -i 's/apply_updates = no/apply_updates = yes/' /etc/dnf/automatic.conf
systemctl enable --now dnf-automatic-install.timer

# ------------------------------------------------------------------------------
# TOOLS
# ------------------------------------------------------------------------------
dnf install -y htop tmux

# ------------------------------------------------------------------------------
# PREVENT STALE IAM CREDENTIALS
# ------------------------------------------------------------------------------
# Remove any static AWS credentials that may have been left behind by a
# previous operator running `aws configure`. The bastion must always use its
# IAM Instance Profile — never long-lived access keys.
rm -f /home/ec2-user/.aws/credentials /root/.aws/credentials
