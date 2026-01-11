# Ansible Configuration

Automated provisioning for the Drive-Ops development environment.

## Overview

This Ansible playbook configures a Debian-based VM with:
- Docker Engine and Docker Compose
- Development tools (git, vim, htop)
- Python packages for container management
- User permissions for Docker access

## Prerequisites

- [Ansible](https://www.ansible.com/) 2.9+
- Target VM running Debian 12

### Installation (macOS)
```bash
brew install ansible
```

### Installation (Windows - WSL)
```bash
sudo apt install ansible
```

### Installation (Linux/Debian)
```bash
sudo apt install ansible
```

## Inventory Files

### `inventory/localhost`
Used when running Ansible **inside** the VM (local execution):
```bash
ansible-playbook -i inventory/localhost playbook.yaml
```

This inventory uses `ansible_connection=local` and is automatically used by Vagrant during provisioning.

### `inventory/hosts`
Used when running Ansible **from your host machine** to configure the VM via SSH:
```bash
ansible-playbook -i inventory/hosts playbook.yaml
```

This inventory connects to the VM at `192.168.56.10` via SSH.

## Usage

### Automatic (Recommended)
The playbook runs automatically when you use `vagrant up` - no manual execution needed.

### Manual Execution

#### From inside the VM:
```bash
vagrant ssh
cd /vagrant/infra/ansible
ansible-playbook -i inventory/localhost playbook.yaml
```

#### From your host machine:
```bash
cd infra/ansible
ansible-playbook -i inventory/hosts playbook.yaml
```

### Run specific tasks with tags:
```bash
# Only install Docker
ansible-playbook -i inventory/localhost playbook.yaml --tags docker

# Only install prerequisites
ansible-playbook -i inventory/localhost playbook.yaml --tags prerequisites

# Skip upgrade tasks
ansible-playbook -i inventory/localhost playbook.yaml --skip-tags upgrade

# Only verify installation
ansible-playbook -i inventory/localhost playbook.yaml --tags verify
```

## What the Playbook Does

1. **Pre-tasks**:
   - Updates apt package cache
   - Upgrades all system packages (optional, use `--skip-tags upgrade` to skip)

2. **Main tasks**:
   - Installs prerequisites (curl, git, vim, htop, net-tools, etc.)
   - Adds Docker's official GPG key and repository
   - Installs Docker Engine, CLI, and Compose plugin
   - Adds `vagrant` user to `docker` group (allows running Docker without sudo)
   - Starts and enables Docker service
   - Installs Python Docker SDK for Ansible container modules

3. **Verification**:
   - Checks Docker and Docker Compose versions
   - Displays installation confirmation

## Available Tags

- `always` - Always runs (apt cache update, completion message)
- `upgrade` - System package upgrade
- `prerequisites` - Install base packages
- `docker` - Docker installation and configuration
- `verify` - Verify installations

## Testing the Setup

After provisioning, verify Docker is working:

```bash
# Check Docker version
docker --version

# Check Docker Compose version
docker compose version

# Run test container (should work without sudo)
docker run hello-world

# Check Docker service status
systemctl status docker
```

## File Structure
```
ansible/
├── playbook.yaml           # Main playbook
├── inventory/
│   ├── localhost          # Local execution inventory
│   └── hosts              # Remote SSH inventory
└── README.md              # This file
```

## Customization

### Add users to Docker group
Edit `playbook.yaml` and modify the `docker_users` variable:
```yaml
vars:
  docker_users:
    - vagrant
    - youruser
```

### Install additional packages
Add packages to the prerequisites task in `playbook.yaml`:
```yaml
- name: Install prerequisites
  apt:
    name:
      - apt-transport-https
      - ca-certificates
      # ... existing packages ...
      - your-package-here
```

## Troubleshooting

### "Authentication failure" when using hosts inventory
Make sure the Vagrant VM is running and SSH keys are configured:
```bash
cd infra/vagrant
vagrant up
vagrant ssh-config
```

### Docker permission denied
Log out and back in after provisioning, or run:
```bash
newgrp docker
```

### Playbook fails on Python Docker SDK
This is usually safe to ignore if Docker is working. The playbook handles both Debian 12's externally-managed environment and older systems.

### Re-run provisioning
If something fails, you can re-run the playbook:
```bash
# From host machine
cd infra/ansible
ansible-playbook -i inventory/hosts playbook.yaml

# Or from VM
vagrant ssh
cd /vagrant/infra/ansible
ansible-playbook -i inventory/localhost playbook.yaml
```

## Notes

- The playbook is idempotent - safe to run multiple times
- Uses `become: yes` for sudo privileges
- Skips SSH host key checking for local development convenience
- Python Docker SDK installation handles Debian 12's PEP 668 restrictions
