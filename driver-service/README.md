## Docker Setup

### Prerequisites
- Docker and Docker Compose installed
- (For Vagrant deployment) Ansible installed

### Local Development

1. **Setup environment:**
```bash
   cp .env.example .env
   # Edit .env with your values
```

2. **Start services:**
```bash
   docker-compose up -d --build
```

3. **Check if running:**
```bash
   docker-compose ps
```

4. **View logs:**
```bash
   docker-compose logs -f driver-service
```

5. **Stop services:**
```bash
   docker-compose down
```

### Vagrant VM Deployment
```bash
ansible-playbook -i inventory deploy.yml
```

### Troubleshooting

**Service not starting?**
```bash
# Check container status
docker-compose ps

# View all logs
docker-compose logs

# View specific service logs
docker-compose logs -f driver-service
```

**Port already in use?**
```bash
# Check what's using port 8000
lsof -i :8000
```

**Need to rebuild?**
```bash
docker-compose down -v
docker-compose up --build
```