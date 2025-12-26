# Contributing to Driver Service

This document outlines the workflow for contributing features and bug fixes specifically to the **Driver Service**. Please follow the guidelines below to ensure a clean and manageable history.

## Branching Strategy

We use a team-specific branching model. All work targeting this service should ultimately flow through the `driver-service` branch before reaching production (`main`).

### The Flow
`feature/<name>` —(Squash Merge)→ `driver-service` —(Merge Commit)→ `main`

### 1. Create a Feature Branch
For any new feature or fix, create a dedicated branch. **Do not** branch off `main` directly.
* **Base Branch:** `driver-service`
* **Naming Convention:** `feature/<short-description>` or `fix/<short-description>`

```bash
# Example
git checkout driver-service
git pull origin driver-service
git checkout -b feature/new-logic
```

### 2. Development & Push

Commit your changes to your feature branch and push them to the repository as usual.

## Pull Request & Merging Process

### Step 1: Merge to Team Branch (`driver-service`)

When your task is complete:

1. Open a **Pull Request (PR)** targeting the `driver-service` branch.
2. **Review:** Assign a team member for code review.
* *Note: If the changes were pre-discussed and approved, you may merge immediately.*


3. **Merge Strategy:** Use **Squash and Merge**.
* This ensures the `driver-service` history remains clean, with one commit per feature/task.

### Step 2: Release to Main (`main`)

Promoting changes from the team branch to production requires a formal cross-team review.

1. **Prepare the Source:** Choose one of the following methods:
* **Full Update:** Use the `driver-service` branch directly.
* **Specific Release:** Create a new branch pointing to a specific commit on `driver-service` (e.g., if you only want to release changes up to a certain point).

2. **Open Pull Request:** Create a PR merging your chosen source branch into `main`.
3. **Cross-Team Review:** You **must** assign a reviewer from a **different team** to verify the integration.
4. **Merge Strategy:** Once approved by the external reviewer, perform a **Merge Commit (No Squash)**.
* *Important:* Do not squash commits here. We must preserve the history of the individual features that were merged into the team branch.
