# VPC Networking Module

## Overview
This module provisions the foundational networking infrastructure for the **drive-ops** platform in the **us-east-2** region. It is designed to provide a minimal, secure development environment that prioritizes cost-efficiency while supporting the microservices architecture.

## Architecture
The module implements a high-availability network layout across **2 Availability Zones** (AZs).

### Subnet Strategy
* **Public Subnets (x2):** Hosts the NAT Instance and bastion host. These subnets have direct access to the Internet Gateway (IGW).
* **Private Subnets (x2):** Hosts application workloads (EKS nodes), persistent data stores (RDS PostgreSQL) and other resources that require outbound internet access via the NAT Instance. These subnets are isolated from direct internet access.

### NAT Strategy — Cost-Optimised

The module uses a **NAT Instance** (EC2-based) instead of the AWS-managed NAT Gateway to achieve ~90% cost savings.

#### NAT Instance (fck-nat) — Recommended
> ⚠ **Warning:** `use_nat_instance` defaults to `false`. Private subnets will have no outbound internet unless you explicitly set `use_nat_instance = true`. For most development and staging environments, enabling a NAT Instance is recommended. For production, consider HA (one NAT per AZ) and review `nat_instance_type` sizing.
* **NAT Instance:** A t4g.nano (ARM/Graviton) EC2 instance in a public subnet that performs Network Address Translation for private subnet traffic.
* **AMI:** [fck-nat](https://github.com/AndrewGuenther/fck-nat) — production-ready, community-maintained NAT solution
* **Traffic Flow:** Private subnet → NAT Instance (0.0.0.0/0) → Internet Gateway → Internet
* **Features:**
  - Pre-configured with IP forwarding and iptables NAT rules
  - Auto-recovery scripts and health checks
  - CloudWatch monitoring integration
  - Source/destination check disabled for packet forwarding
  - Encrypted root volume with IMDSv2 enforcement
  - Optional SSH access for troubleshooting
  - ARM64 architecture (Graviton) for better performance/cost ratio
* **Performance:** Network interface hardware may support bursts up to 5 Gbps, but this is an NIC burst ceiling — not sustained NAT throughput on tiny instances. `iptables` MASQUERADE is CPU-bound on a `t4g.nano`; real-world sustained NAT throughput on a `t4g.nano` is typically in the tens-to-low-hundreds of Mbps. For higher-volume or production NAT use, upgrade to `t4g.small`/`t4g.medium` (or larger), or consider using an AWS NAT Gateway.
* **Cost:** ~$3.06/month (t4g.nano on-demand pricing) — **~$36.72/year**
* **Enable with:** `use_nat_instance = true`, `nat_instance_type = "t4g.nano"`

> **Why not AWS NAT Gateway?**
> AWS NAT Gateway costs ~$32+/month ($388/year). The NAT Instance at $3/month saves
> **~$350/year (90%)** with no meaningful trade-off for a dev/staging workload.
> NAT Gateway was intentionally removed from this module to prevent accidental cost overruns.

## Security Boundaries & Traffic Flows
Access control is enforced via Security Groups to implement the principle of least privilege. **Zero Trust Ingress** is applied for the application layer.

| Source | Destination | Protocol | Port | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Internet** | `sg-app` | - | - | **DENY ALL**. No inbound traffic allowed from the internet. |
| `sg-app` | **Internet** | ALL | ALL | Outbound traffic for **Long Polling** (Telegram), system updates, and AWS Service access (SQS, SSM). |
| `sg-app` | `sg-db` | TCP | 5432 | Internal connection from Application services to the PostgreSQL database. |

## NAT Instance Traffic Flow

```
┌─────────────────────────────────────────────────────────────┐
│                         Internet                            │
└────────────────────────┬────────────────────────────────────┘
                         │
              ┌──────────────────────┐
              │  Internet Gateway    │
              │       (IGW)          │
              └──────────┬───────────┘
                         │
      ┌──────────────────┼──────────────────┐
      │         VPC      │                  │
      │  ┌───────────────▼─────────────┐    │
      │  │   Public Subnet (AZ1)       │    │
      │  │  ┌───────────────────────┐  │    │
      │  │  │  NAT Instance         │  │    │
      │  │  │  (t4g.nano)           │  │    │
      │  │  │  - IP Forwarding: ON  │  │    │
      │  │  │  - src/dst check: OFF │  │    │
      │  │  │  - iptables NAT       │  │    │
      │  │  └──────────┬────────────┘  │    │
      │  └─────────────┼───────────────┘    │
      │                │                     │
      │                │ private → NAT (0.0.0.0/0 route) │
      │                │                     │
      │  ┌─────────────▼───────────────┐    │
      │  │   Private Subnet (AZ1)      │    │
      │  │  ┌───────────────────────┐  │    │
      │  │  │  EKS Nodes / RDS      │  │    │
      │  │  │  Private Workloads    │  │    │
      │  │  └───────────────────────┘  │    │
      │  └─────────────────────────────┘    │
      └─────────────────────────────────────┘

Private Route Table:
  Destination: 0.0.0.0/0   → Target: NAT Instance ENI
  Destination: 10.0.0.0/16 → Target: local
```

**Key Points:**
                         │
                         ↓
              ┌──────────────────────┐
              │  Internet Gateway    │
              │       (IGW)          │
              └──────────┬───────────┘
                         │
      ┌──────────────────┼──────────────────┐
      │         VPC      │                  │
      │  ┌───────────────▼─────────────┐    │
      │  │   Public Subnet (AZ1)       │    │
      │  │  ┌───────────────────────┐  │    │
      │  │  │  NAT Instance         │  │    │
      │  │  │  (t4g.nano)           │  │    │
      │  │  │  - IP Forwarding: ON  │  │    │
      │  │  │  - src/dst check: OFF │  │    │
      │  │  │  - iptables NAT       │  │    │
      │  │  └──────────┬────────────┘  │    │
      │  └─────────────┼───────────────┘    │
      │                │                     │
      │                │ private → NAT (0.0.0.0/0 route) │
      │                │                     │
      │  ┌─────────────▼───────────────┐    │
      │  │   Private Subnet (AZ1)      │    │
      │  │  ┌───────────────────────┐  │    │
      │  │  │  EKS Nodes / RDS      │  │    │
      │  │  │  Private Workloads    │  │    │
      │  │  └───────────────────────┘  │    │
      │  └─────────────────────────────┘    │
      └─────────────────────────────────────┘

Private Route Table:
  Destination: 0.0.0.0/0   → Target: NAT Instance ENI
  Destination: 10.0.0.0/16 → Target: local
```

**Key Points:**
- Private subnets: outbound-only (no unsolicited inbound)
- Private subnet resources route all internet-bound traffic (0.0.0.0/0) to the NAT Instance
- NAT Instance performs Network Address Translation (iptables MASQUERADE)
- Outbound traffic appears to originate from the NAT Instance's public IP
- Return traffic is automatically routed back through the NAT Instance
- NAT Instance is deployed in public subnet with direct IGW route

## Inputs

| Name | Description | Type | Default | Required |
| :--- | :--- | :--- | :--- | :--- |
| `project_name` | The name of the project (e.g., drive-ops). | `string` | n/a | **Yes** |
| `env` | The environment name (e.g., dev, prod). | `string` | n/a | **Yes** |
| `account_id` | The AWS Account ID for permissions boundaries. | `string` | n/a | **Yes** |
| `vpc_cidr` | The CIDR block for the VPC. | `string` | `"10.0.0.0/16"` | No |
| `availability_zones` | Fixed list of AZs to prevent infrastructure shuffling. | `list(string)` | `["us-east-2a", "us-east-2b"]` | No |
| `enable_flow_logs` | Whether to enable VPC Flow Logs. | `bool` | `false` | No |
| `flow_log_retention_in_days` | Number of days to retain VPC Flow Logs in CloudWatch. | `number` | `7` | No |
| `use_nat_instance` | Whether to use NAT Instance (t4g.nano ARM/Graviton) for private subnet outbound. Defaults to `false` — must be set to `true` to enable outbound internet for private subnets. | `bool` | `false` | No |
| `nat_instance_type` | Instance type for NAT Instance. | `string` | `"t4g.nano"` | No |
| `nat_instance_key_name` | Optional SSH key name for NAT Instance troubleshooting. | `string` | `""` | No |

## Outputs

| Name | Description |
| :--- | :--- |
| `vpc_id` | The ID of the created VPC. |
| `vpc_cidr` | The CIDR block of the VPC. |
| `public_subnet_ids` | List of IDs for public subnets (bastion, NAT Instance). |
| `private_subnet_ids` | List of IDs for private subnets (EKS nodes, RDS). |
| `sg_app_id` | Security Group ID to attach to Application instances. |
| `sg_db_id` | Security Group ID to attach to RDS instances. |
| `nat_instance_id` | The ID of the NAT Instance (null if disabled). |
| `nat_instance_public_ip` | The public IP address of the NAT Instance (null if disabled). |
| `nat_instance_private_ip` | The private IP address of the NAT Instance (null if disabled). |
