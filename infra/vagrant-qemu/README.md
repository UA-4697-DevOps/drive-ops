# Vagrant Setup - QEMU (ARM)

For Apple Silicon (M1/M2/M3 Mac).

## Prerequisites

- [Vagrant](https://www.vagrantup.com/) 2.3+
- [UTM](https://mac.getutm.app/) or QEMU
- vagrant-qemu plugin

## Installation
```bash
# UTM (recommended)
brew install --cask utm

# Vagrant
brew install --cask vagrant

# vagrant-qemu plugin
vagrant plugin install vagrant-qemu

# Optional: libvirt for better performance
# brew install libvirt qemu
# vagrant plugin install vagrant-libvirt
```

## Usage
```bash
# Start VM
cd infra/vagrant-qemu
vagrant up

# SSH into VM
vagrant ssh

# File sync (in separate terminal!)
vagrant rsync-auto

# Manual sync
vagrant rsync

# Stop VM
vagrant halt

# Destroy VM
vagrant destroy -f

# Restart VM
vagrant reload

# Check status
vagrant status
```

## ⚠️ Important: File Synchronization

Unlike VirtualBox, this setup uses **rsync** for file synchronization.

**This means:**
- Changes in code on host machine do NOT immediately appear in VM
- You need to run `vagrant rsync-auto` in a separate terminal window
- Or manually run `vagrant rsync` after making changes

### Recommended Workflow
```bash
# Terminal 1: VM management
cd infra/vagrant-qemu
vagrant up
vagrant ssh

# Terminal 2: Auto file sync (keep this running!)
cd infra/vagrant-qemu
vagrant rsync-auto
```

**Files excluded from sync:**
- `.git/`
- `node_modules/`
- `__pycache__/`
- `venv/`
- `.vagrant/`

## Next Steps

After `vagrant up` completes:

### 1. Start file sync (separate terminal)
```bash
cd infra/vagrant-qemu
vagrant rsync-auto
```

### 2. Configure VM with Ansible
```bash
cd ../ansible
ansible-playbook -i inventory/hosts playbook.yml
```

### 3. Start Services
```bash
vagrant ssh
cd /vagrant
docker compose up -d
```

### 4. Access Services

- Client Gateway: http://localhost:3000
- Driver Service: http://localhost:5001
- Trip Service: http://localhost:5002
- PostgreSQL: localhost:5432

## Common Commands
```bash
# Sync files manually
vagrant rsync

# View sync status
vagrant rsync-auto --help

# View logs
vagrant ssh -c "cd /vagrant && docker compose logs -f"

# Restart services
vagrant ssh -c "cd /vagrant && docker compose restart"

# Stop services
vagrant ssh -c "cd /vagrant && docker compose down"
```

## Troubleshooting

### Plugin not found
```bash
vagrant plugin install vagrant-qemu
```

### Slow performance

Try using libvirt provider instead:
```bash
brew install libvirt qemu
vagrant plugin install vagrant-libvirt
vagrant up --provider=libvirt
```

### Files not syncing
```bash
# Check if rsync-auto is running
# Start it in separate terminal:
vagrant rsync-auto

# Or manually sync:
vagrant rsync

# Force full re-sync:
vagrant rsync --rsync-force
```

### SSH connection issues
```bash
# Check SSH config
vagrant ssh-config

# Update inventory/hosts with the correct settings
```

### First boot takes too long (5-10 minutes)

This is normal for ARM emulation. Subsequent boots are faster.

### Port conflicts
```bash
# QEMU uses different SSH port (50022)
# Other ports should match VirtualBox setup
# Check Vagrantfile for port configuration
```

## File Structure
```
vagrant-qemu/
├── Vagrantfile          # VM configuration
├── README.md            # This file
└── .vagrant/            # Vagrant metadata (auto-generated)
```

## Performance Tips

1. **Use libvirt** provider for better performance (if installed)
2. **Allocate enough resources** in Vagrantfile (4GB RAM, 2 CPUs)
3. **Keep rsync-auto running** to avoid manual sync delays
4. **Exclude unnecessary directories** from rsync (already configured)
5. **Use SSD** for better I/O performance