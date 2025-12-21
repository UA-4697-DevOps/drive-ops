# Vagrant Setup - VirtualBox (x86/x64)

For Intel/AMD processors (Windows, Linux, Intel Mac).

## Prerequisites

- [VirtualBox](https://www.virtualbox.org/) 6.1+
- [Vagrant](https://www.vagrantup.com/) 2.3+

### Installation (macOS)
```bash
brew install --cask virtualbox
brew install --cask vagrant
```

### Installation (Windows)
```bash
choco install virtualbox
choco install vagrant
```

### Installation (Linux/Debian)
```bash
sudo apt install virtualbox vagrant
```

## Usage
```bash
# Start VM
cd infra/vagrant-virtualbox
vagrant up

# SSH into VM
vagrant ssh

# Stop VM
vagrant halt

# Destroy VM
vagrant destroy -f

# Restart VM
vagrant reload

# Check status
vagrant status
```

## Next Steps

After `vagrant up` completes:

### 1. Configure VM with Ansible
```bash
cd ../ansible
ansible-playbook -i inventory/hosts playbook.yml
```

### 2. Start Services
```bash
vagrant ssh
cd /vagrant
docker compose up -d
```

### 3. Access Services

- Client Gateway: http://localhost:3000
- Driver Service: http://localhost:5001
- Trip Service: http://localhost:5002
- PostgreSQL: localhost:5432

## Common Commands
```bash
# View logs
vagrant ssh -c "cd /vagrant && docker compose logs -f"

# Restart services
vagrant ssh -c "cd /vagrant && docker compose restart"

# Stop services
vagrant ssh -c "cd /vagrant && docker compose down"

# Re-provision VM
vagrant provision
```

## Troubleshooting

### VM fails to start
```bash
vagrant destroy -f
vagrant up
```

### "Platform architecture not supported" error

You are on Apple Silicon Mac. Use `../vagrant-qemu/` instead.

### VirtualBox kernel modules issue (macOS)

Go to: **System Settings → Privacy & Security → Allow** apps from Oracle

### Port already in use
```bash
# Check what's using the port
lsof -i :3000

# Change port in Vagrantfile or stop the conflicting service
```

### Slow file sync

VirtualBox shared folders can be slow. Consider using NFS:
```ruby
# In Vagrantfile, replace synced_folder with:
config.vm.synced_folder "../..", "/vagrant", 
    type: "nfs",
    nfs_version: 4,
    nfs_udp: false
```

## File Structure
```
vagrant-virtualbox/
├── Vagrantfile          # VM configuration
├── README.md            # This file
└── .vagrant/            # Vagrant metadata (auto-generated)
```