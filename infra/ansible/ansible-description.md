# Drive-Ops Ansible Infrastructure
This directory contains Ansible playbooks and roles designed to automate the deployment of the drive-ops microservices stack.

## 📋 Prerequisites
Before running the playbook, ensure the following requirements are met:
* Docker Desktop is running on your OS.
* Ansible is installed.
* .env file with your credentials is created
### If dont want to search or create bot_token. write  me (Davlit) in discord to get token
```bash
cp .env.example .env
vi .env
```
* The Docker community collection is installed:
```bash
ansible-galaxy collection install community.docker
```
## 🚀 Quick Start
```bash
# Navigate to the project root
cd <path_to_project>
# Execute the deployment
ansible-playbook -i infra/ansible/inventory/localhost infra/ansible/playbook.yaml -e "drive_ops_src_root=$(pwd)" -K
```
### 🛠 Configuration (.env)
The playbook implements a Fail-Fast pattern and requires a .env file to be present in the project root. Deployment will halt if mandatory variables are missing.

Mandatory variables:

* BOT_TOKEN — Valid Telegram API token obtained from @BotFather.

* DB_USER / DB_PASSWORD — Credentials for the PostgreSQL database.

* RABBITMQ_USER / RABBITMQ_PASSWORD — Credentials for the RabbitMQ message broker.

### 🏷 Using Tags

* **`infrastructure`** — This is a "group" tag. It runs everything related to the application stack, including the shared infrastructure (DB/MQ) and all microservices (infra, trip-service, and client-gateway).
* **`infra`** — Deploys the shared infrastructure (PostgreSQL and RabbitMQ) and copies core configuration files.
* **`docker`** — Installs the Docker Engine and system-level dependencies.
* **`trip` / `gateway`** — Deploy specific microservices (Go Trip Service or Python Gateway) individually.
* **`always`** — Tasks that run every time (e.g., updating the package cache and printing the final status report).
* **`upgrade`** — Explicitly used to perform a sudo apt upgrade on the host machine.

### 🏗 Deployment Architecture
The playbook orchestrates 5 key components within a dedicated Docker network:

* PostgreSQL (db): The primary database for persisting trip and driver data.

* RabbitMQ (mq): The message broker facilitating asynchronous communication between Go and Python microservices.

* Trip Migrations: A standalone container that automatically applies SQL schemas and ENUM types to the database.

* Trip Service (Go): The backend microservice handling core ride-sharing logic.

* Client Gateway (Python): The Telegram bot interface and primary entry point for users.
## ✅ Verification

Once the playbook finishes successfully (failed=0), perform the following checks:

* Container Status: Run command. All containers should be Up or healthy.
```bash
 docker ps
```
* Bot Logs: Run command to verify Telegram API authorization.
```bash
docker logs client-gateway-bot
```
* Migration Logs: Run command to ensure the database schema was applied correctly.
```bash
docker logs trip-migrations
```
