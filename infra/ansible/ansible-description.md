# Drive-Ops Ansible Infrastructure
This directory contains Ansible playbooks and roles designed to automate the deployment of the drive-ops microservices stack.

## 📋 Prerequisites
Before running the playbook, ensure the following requirements are met:
* **Repository**: Clone the GitHub repository and checkout the desired branch.
* **Ansible**: Ensure Ansible is installed on your local machine or WSL.
* **Environment**: A `.env` file with your credentials must be created in the project root.
```bash
cp .env.example .env
vi .env
```
### If dont want to search or create bot_token. write  me (Davlit) in discord to get token
* **Docker Engine**:

| Option | Environment | Requirement | Command Flag |
| :--- | :--- | :--- | :--- |
| **Option 1** | **No Docker Desktop** | (WSL/Linux) | No extra flags needed. |
| **Option 2** | **With Docker Desktop** | Docker Desktop running + WSL Integration enabled | Add `--skip-tags docker` to q-start command|

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


### 🏷 Using Tags

* **`app`** — Application Stack Tag. Orchestrates all microservices at once (Trip Service, Driver Service, and Client Gateway). This is the primary tag for day-to-day code updates across the entire project.
* **`infra`** — Shared Infrastructure Tag. Manages the foundation of the platform: PostgreSQL and centralized configuration files like .env and docker-compose.yml.
* **`docker`** — System Engine Tag. Installs the Docker Engine, manages GPG keys, and handles dynamic user permissions (adding the current user to the docker group).
* **`trip` / `gateway` / `driver`** — Service-Specific Tags. Allow for targeted deployment of a single microservice without touching the rest of the stack.
* **`always`** — Tasks that execute during every run, such as updating the apt cache and printing the final infrastructure status report.
* **`upgrade`** — An explicit tag used to perform a full sudo apt upgrade and dist-upgrade on the host machine.
* **`verify`** — A lightweight tag used to quickly confirm the Docker installation and version without re-running the setup tasks.

### 🏗 Deployment Architecture
The playbook orchestrates 5 key components within a dedicated Docker network:

* PostgreSQL (db): The primary database engine hosting isolated schemas for trip_db and driver_db. It utilizes a custom initialization script to ensure multi-service data support on first boot.

* Database Migrations: Automated standalone containers for both Go (golang-migrate) and Python (Alembic) that apply schema updates before services launch.

* Trip Service (Go): The high-performance backend microservice managing core ride-sharing state and trip lifecycles.

* Driver Service (Python): A FastAPI-based service dedicated to driver management, availability tracking, and geospatial searching.

* Client Gateway (Python): The Telegram bot interface (BFF) that serves as the primary entry point for users, handling synchronous API calls to backend services.
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
## 🧹 Clean Up & Environment Reset

Follow these steps to completely remove the deployed infrastructure and reclaim system resources. This procedure ensures a "clean slate" for testing deployments from scratch.

### 1. Stop Services and Wipe Data
This command stops all containers and **permanently deletes** persistent volumes (resetting database and message broker state).
```bash
sudo docker compose -f /opt/drive-ops/docker-compose.yml down -v
```
### 2. Remove Deployment Directory
Delete the /opt/drive-ops directory, which removes all configuration files and the symbolic links created by Ansible.
```bash
sudo rm -rf /opt/drive-ops
```
### 3. Deep System Prune (Optional)

Reclaim disk space by removing all unused Docker images, networks, and build cache. 

> [!WARNING]
> This will remove **all** images not currently used by a container, not just those from the `drive-ops` project.

```bash
docker system prune -a
```
## 🚀 To Redeploy
To start the entire stack again on a clean system:
```bash
ansible-playbook -i infra/ansible/inventory/localhost infra/ansible/playbook.yaml -e "drive_ops_src_root=$(pwd)" -K
```
