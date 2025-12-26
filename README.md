# Introduction

Welcome to the **Drive-Ops** monorepo — distributed infrastructure and microservices powering the platform.

## Repository Structure
- `client-gateway/` — Entry point for client requests/auth.
- `driver-service/` — Driver logic and state.
- `trip-service/` — Core trip processing.
- `.github/workflows/` — Centralized CI/CD.

## CI/CD & Automation
### Workflows (GitHub Actions):
- `client-gateway-ci.yml` — triggers on `client-gateway/**` or workflow changes; currently stubbed (green).
- `driver-service-ci.yml` — triggers on `driver-service/**` or workflow changes; currently stubbed (green).
- `trip-service-ci.yml` — triggers on `trip-service/**` or workflow changes; currently stubbed (green).

### Status:

| Service | Build Status |
| :--- | :--- |
| **Client Gateway** | [![Client Status](https://github.com/UA-4697-DevOps/drive-ops/actions/workflows/client-gateway-ci.yml/badge.svg)](https://github.com/UA-4697-DevOps/drive-ops/actions/workflows/client-gateway-ci.yml) |
| **Driver Service** | [![Driver Status](https://github.com/UA-4697-DevOps/drive-ops/actions/workflows/driver-service-ci.yml/badge.svg)](https://github.com/UA-4697-DevOps/drive-ops/actions/workflows/driver-service-ci.yml) |
| **Trip Service** | [![Trip Status](https://github.com/UA-4697-DevOps/drive-ops/actions/workflows/trip-service-ci.yml/badge.svg)](https://github.com/UA-4697-DevOps/drive-ops/actions/workflows/trip-service-ci.yml) |

## Getting Started

Contribution Flow: [CONTRIBUTING.md](./CONTRIBUTING.md)

### Client Gateway
- Prereqs: `<list>`
- Env vars: `<LIST>`
- Run:
  ```
  <cmd>
  ```
- Test:
  ```
  <cmd>
  ```
- API docs: `<link>`

### Driver Service
- Prereqs: Python 3.14.2, [driver-service/requirements.txt](./driver-service/requirements.txt)
- Env vars: [driver-service/.env.example](./driver-service/.env.example)
- Run:
  ```bash
  python driver-service/src/main.py
  ```
- Test:
  ```bash
  pytest
  ```
- API docs: [driver-service/README.md](./driver-service/README.md)
- Contributing: [driver-service/CONTRIBUTING.md](./driver-service/CONTRIBUTING.md)

### Trip Service
- Prereqs: `<list>`
- Env vars: `<LIST>`
- Run:
  ```
  <cmd>
  ```
- Test:
  ```
  <cmd>
  ```
- API docs: `<link>`
