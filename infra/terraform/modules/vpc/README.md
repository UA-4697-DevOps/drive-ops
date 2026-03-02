# VPC Networking Module

## Overview
This module provisions the foundational networking infrastructure for the **drive-ops** platform in the **us-east-2** region. It is designed to provide a minimal, secure development environment that prioritizes cost-efficiency while supporting the microservices architecture.

## Architecture
The module implements a high-availability network layout across **2 Availability Zones** (AZs).

### Subnet Strategy
* **Public Subnets (x2):** Hosts compute resources (EC2/ECS) running the **Go** and **Python** services. These subnets have direct access to the Internet Gateway (IGW).
* **Private Subnets (x2):** Hosts persistent data stores (RDS PostgreSQL). These subnets are completely isolated from the public internet (no route to IGW).

### Cost Optimization (NAT-less Approach)
To maintain the infrastructure within the **AWS Free Tier**, this module deliberately avoids using NAT Gateways (which incur hourly charges).
* **App Compute:** Placed in public subnets to allow outbound access to AWS APIs (SQS, SSM) and Docker Hub without a NAT Gateway.
* **Security:** Despite being in public subnets, compute instances are protected by strict Security Group rules (`sg-app`) which deny all inbound traffic from the internet.

## Security Boundaries & Traffic Flows
Access control is enforced via Security Groups to implement the principle of least privilege. **Zero Trust Ingress** is applied for the application layer.

| Source | Destination | Protocol | Port | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Internet** | `sg-app` | - | - | **DENY ALL**. No inbound traffic allowed from the internet. |
| `sg-app` | **Internet** | ALL | ALL | Outbound traffic for **Long Polling** (Telegram), system updates, and AWS Service access (SQS, SSM). |
| `sg-app` | `sg-db` | TCP | 5432 | Internal connection from Application services to the PostgreSQL database. |

## Inputs

| Name | Description | Type | Default | Required |
| :--- | :--- | :--- | :--- | :--- |
| `project_name` | The name of the project (e.g., drive-ops). | `string` | n/a | **Yes** |
| `env` | The environment name (e.g., dev, prod). | `string` | n/a | **Yes** |
| `vpc_cidr` | The CIDR block for the VPC. | `string` | `"10.0.0.0/16"` | No |
| `availability_zones` | Fixed list of AZs to prevent infrastructure shuffling. | `list(string)` | `["us-east-2a", "us-east-2b"]` | No |

## Outputs

| Name | Description |
| :--- | :--- |
| `vpc_id` | The ID of the created VPC. |
| `public_subnet_ids` | List of IDs for public subnets (use for EC2/ECS). |
| `private_subnet_ids` | List of IDs for private subnets (use for RDS). |
| `sg_app_id` | Security Group ID to attach to Application instances. |
| `sg_db_id` | Security Group ID to attach to RDS instances. |
