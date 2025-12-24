# Drive-Ops Platform 🚗

Welcome to the **Drive-Ops** monorepo. This repository contains the distributed infrastructure and microservices powering the platform. We use a modular architecture to ensure scalability and independent service management.

## 🏗 Repository Structure

This project is organized as a monorepo to streamline development across multiple services:

* **`client-gateway/`** — The entry point for client requests and authentication.
* **`driver-service/`** — Handles driver-related logic and state management.
* **`trip-service/`** — Manages the core business logic for trip processing.
* **`.github/workflows/`** — Centralized CI/CD automation logic.

---

## 🚀 CI/CD & Automation

We have implemented a baseline CI/CD infrastructure using GitHub Actions to maintain high code quality standards. 

### Current Status:
* **Infrastructure Stubs**: Pipelines are currently configured with stable stubs to ensure green builds while service logic is being integrated.
* **Independent Triggers**: Workflows are optimized to run only when changes are detected in specific service directories.
* **Status Visibility**: Service health and build status are tracked via the badges below.

### Service Health:
| Service | Build Status |
| :--- | :--- |
| **Driver Service** | ![Driver Status](https://github.com/UA-4697-DevOps/drive-ops/actions/workflows/driver-service-ci.yml/badge.svg) |
| **Trip Service** | ![Trip Status](https://github.com/UA-4697-DevOps/drive-ops/actions/workflows/trip-service-ci.yml/badge.svg) |
| **Client Gateway** | ![Client Status](https://github.com/UA-4697-DevOps/drive-ops/actions/workflows/client-gateway-ci.yml/badge.svg) |

---

## 🛠 Getting Started

### Local Setup
1. Clone the repository: `git clone https://github.com/UA-4697-DevOps/drive-ops.git`
2. Explore individual service directories for specific environment requirements.

### Running Tests
Testing is encouraged for every contribution. You can run tests locally within each service folder using the standard testing tools provided for that environment.

### Contribution Flow
1. **Infrastructure**: Ensure your service folder contains the necessary configuration files.
2. **Implementation**: Build your service logic within the assigned directory.
3. **CI Integration**: Once your tests are ready, the CI stubs in `.github/workflows/` should be updated to execute your specific test suites.

---

## 📝 Documentation
Continuous documentation is a core part of this project. Each directory contains localized documentation to help you get started with that specific module.


**Action Items for Service Teams:**
Each team should update the `README.md` file in their service folder with the following details:
* **Tech Stack**: Specify the programming languages, frameworks, and versions used (e.g., Python 3.13/FastAPI, Go 1.23).
* **Local Development**: Step-by-step instructions on environment setup, dependency installation, and local execution.
* **Testing Suite**: Details on how to write and run service-specific unit and integration tests.
* **API Definitions**: Documentation of endpoints, data models, or links to Swagger/OpenAPI specs.