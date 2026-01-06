# Drive-Ops Ansible Infrastructure
This directory contains Ansible playbooks and roles designed to automate the deployment of the drive-ops microservices stack.

## 🚀 Quick Start
### In GitHub Codespaces:
For local deployment within the cloud environment (skips Docker engine re-installation):

```bash
# Deploying in Codespaces using relative paths
ansible-playbook -i infra/ansible/inventory/localhost infra/ansible/playbook.yaml --tags infrastructure
```
### In Vagrant:
For full provisioning of the virtual machine:

```bash
# From the project root
ansible-playbook -i infra/ansible/inventory/localhost infra/ansible/playbook.yaml --tags infrastructure
```
### 🛠 Configuration (.env)
The playbook implements a Fail-Fast pattern and requires a .env file to be present in the project root. The deployment will halt immediately if the file is missing or mandatory variables are not defined.

Mandatory variables:

BOT_TOKEN — Telegram Bot API token for the Client Gateway.

DB_USER / DB_PASSWORD — Credentials for the PostgreSQL database.

RABBITMQ_USER / RABBITMQ_PASSWORD — Credentials for the RabbitMQ message broker.

### 🏷 Using Tags
infrastructure — Performs configuration validation and deploys the stack via Docker Compose.

docker — Full cycle: installs the Docker Engine, dependencies, and starts services.

### 🏗 Deployment Architecture
The playbook orchestrates the following services as part of the drive-ops ecosystem:

Database (PostgreSQL) — Handles data persistence with automated initialization of trip_db and driver_db.

Message Broker (RabbitMQ) — Facilitates asynchronous communication between Go and Python microservices.

Trip Service (Go) — Manages ride requests and trip logic.

Driver Service (Python) — Handles driver availability and matching.

Client Gateway (Python) — The Orchestrator & Entry Point:

* User Interface: Acts as the primary Telegram bot interface for all users.

* System Orchestrator: In our automation logic, this is the "Master Service" that triggers the deployment of the entire stack. It ensures that infrastructure (DB, MQ) and backend services (Trip, Driver) are online and healthy before accepting user requests.
## ✅ Verification

Once the deployment is complete, verify the stack status:

1. **Containers**: Run `docker ps` to ensure all 5 services are **(healthy)**.
2. **RabbitMQ**: Access the Management UI via the **Ports** tab in Codespaces (port `15672`).
3. **Logs**: Check the logs of the Go service to ensure DB connectivity:
   ```bash
   docker compose logs trip-service
