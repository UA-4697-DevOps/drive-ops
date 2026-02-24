#!/bin/bash
# EKS Node Bootstrap Script
# Configures kubelet with extra arguments for compatibility with custom AMIs or specific configurations.

set -e

# Add kubelet extra arguments to the kubelet systemd service
# WARNING: The systemd drop-in below (`/etc/systemd/system/kubelet.service.d/99-kubelet-extra-args.conf`)
# sets the `KUBELET_EXTRA_ARGS` environment variable. An `Environment=` assignment replaces any
# previously-set `KUBELET_EXTRA_ARGS` value, so this will overwrite bootstrap-provided flags
# (for example `--node-labels`, `--hostname-override`, `--cloud-provider`).
#
# If you need to preserve bootstrap flags, prefer applying a KubeletConfiguration overlay
# (e.g., via nodeadm for AL2023/nodeadm-based images) or ensure `kubelet_extra_args` includes
# all required bootstrap flags. This drop-in is intended as a last-resort override for custom AMIs.
echo "Configuring kubelet with extra arguments: ${kubelet_extra_args} (drop-in: /etc/systemd/system/kubelet.service.d/99-kubelet-extra-args.conf)"

# Create a drop-in directory for kubelet systemd service customization
mkdir -p /etc/systemd/system/kubelet.service.d

# Create a drop-in configuration file with extra kubelet arguments
# Escape double-quote characters in kubelet_extra_args so the resulting
# `Environment="KUBELET_EXTRA_ARGS=..."` line is valid for systemd parsing.
escaped_kubelet_extra_args="${kubelet_extra_args//\"/\\\"}"

cat > /etc/systemd/system/kubelet.service.d/99-kubelet-extra-args.conf <<EOF
[Service]
Environment="KUBELET_EXTRA_ARGS=${escaped_kubelet_extra_args}"
EOF

# Reload systemd and restart kubelet to apply changes
systemctl daemon-reload
systemctl restart kubelet

echo "Kubelet configured with extra arguments"
