# Vagrant Setup

Local development environment using VirtualBox and Ansible.

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
# Start VM (automatically runs Ansible provisioning)
cd infra/vagrant
vagrant up

# SSH into VM
vagrant ssh

# Stop VM
vagrant halt

# Destroy VM
vagrant destroy -f

# Restart VM
vagrant reload

# Re-provision VM
vagrant provision

# Check status
vagrant status
```

## What Happens During Setup

When you run `vagrant up`, the VM will automatically:

1. Download and configure Debian 12 base box
2. Install Python and build tools
3. Install and run Ansible provisioning
4. Set up Docker and all required dependencies

After provisioning completes, you can:

### Access Services

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
vagrant/
├── Vagrantfile          # VM configuration
├── README.md            # This file
└── .vagrant/            # Vagrant metadata (auto-generated)
```

## VM Configuration

- **OS**: Debian 12 (bento/debian-12)
- **Memory**: 4GB RAM
- **CPUs**: 2 cores
- **IP**: 192.168.56.10
- **Hostname**: drive-ops