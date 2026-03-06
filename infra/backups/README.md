# 🗄️ Drive-Ops Database Backup System

This module provides automated, secure backups of PostgreSQL databases to an encrypted AWS S3 bucket using Kubernetes CronJobs.

## 🏗️ Architecture and Security

The system is built with modern DevOps standards and best practices in mind:
- **Container Security:** The Docker image runs as a non-root user, has a read-only file system (with a mounted `/tmp` volume for dumps), and drops all privileges (`capabilities drop`).
- **IaC (Terraform/Terragrunt):** The S3 bucket is automatically encrypted using AWS KMS (AWS-managed key). A Lifecycle Rule is configured to automatically delete orphaned (incomplete multipart) uploads after 7 days.
- **IRSA (IAM Roles for Service Accounts):** S3 access is granted via an IAM role bound to a Kubernetes ServiceAccount. No hardcoded AWS keys! Strict validation for `sub` and `aud` (STS) claims is configured.
- **Kustomize:** Kubernetes manifests are divided into a universal `base` and environment-specific `overlays` (e.g., `dev`), ensuring a DRY (Don't Repeat Yourself) approach.

## 📁 Directory Structure

```text
infra/
├── backups/                 # Backup creation logic
│   ├── backup.sh            # Backup script (pg_dump + aws s3 cp)
│   └── Dockerfile           # Image definition (Alpine, non-root, aws-cli, postgresql-client)
├── k8s/backups/             # Kubernetes manifests
│   ├── base/                # Base configurations (CronJob, ServiceAccount)
│   └── overlays/dev/        # Dev environment-specific configurations (Kustomize)
├── terraform/modules/backup/# Terraform module for S3 and IAM
└── terragrunt/envs/dev/     # Terragrunt configurations for IaC deployment
