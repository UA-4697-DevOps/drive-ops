# Drive-Ops Monorepo

## Project Status
| Service | Status CI |
| :--- | :--- |
| **Driver Service** | ![Driver Status](https://github.com/UA-4697-DevOps/drive-ops/actions/workflows/driver-service-ci.yml/badge.svg) |
| **Trip Service** | ![Trip Status](https://github.com/UA-4697-DevOps/drive-ops/actions/workflows/trip-service-ci.yml/badge.svg) |
| **Client Gateway** | ![Client Status](https://github.com/UA-4697-DevOps/drive-ops/actions/workflows/client-gateway-ci.yml/badge.svg) |

---

## CI/CD Pipeline
This monorepo uses GitHub Actions to automate development workflows. Each service has its own pipeline configured to ensure reliability.

### What runs per service:
* **Linting & Syntax:** Automated checks for Python (flake8) and Go (golangci-lint) to maintain code style.
* **Unit Tests:** Automated execution of `pytest` (for Python) or `go test` (for Go) on every push or Pull Request.
* **Docker Build:** Automatic verification of the Docker image build process (specifically for `driver-service` as part of the CI/CD setup).
* **Status Visibility:** Live status indicators (badges) are located at the top of this README to provide instant visibility into service health.


## Test
* **Syntax & Linting:** Automated checks for Python (flake8) and Go (golangci-lint).
* **Unit Testing:** Every push triggers a test suite execution on **Python 3.13.8** or **Go 1.23**.
* **Accuracy:** Workflows are linked to service directories to ensure only relevant tests run per change.

### 1. Driver Service (Python)
- **Location**: All logic and tests are located in the `driver-service/` directory.
- **How to run tests**:
  1. Navigate to the directory: `cd driver-service`
  2. Install dependencies: `pip install -r requirements.txt`
  3. Set Python path: `export PYTHONPATH=$PYTHONPATH:$(pwd)`
  4. Execute tests: `pytest`

### 2. Trip Service (Go)
- **Location**: Code resides in the `trip-service/` directory.
- **How to run tests**:
  1. Navigate to the directory: `cd trip-service`
  2. Execute tests: `go test ./...`

### 3. Client Gateway (Python)
- **Location**: Service-specific logic is in `client-gateway/`.
- **How to run tests**: Follow the same steps as for the **Driver Service**.


## Documentation Accuracy & CI Links

To ensure these instructions remain up-to-date, they are directly linked to our automation suite:

- **CI Logic**: All automated checks are defined in [GitHub Workflows](.github/workflows/).
- **Driver Service Tests**: The logic for Python tests is validated by [driver-service-ci.yml](.github/workflows/driver-service-ci.yml).
- **Trip Service Tests**: Go testing procedures follow the steps in [trip-service-ci.yml](.github/workflows/trip-service-ci.yml).
- **Environment**: Local setup instructions are mirrored from the `Install dependencies` and `Run tests` steps in the CI configuration to ensure consistency between local and remote environments.