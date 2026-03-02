# Hardened VPC with Private Nodes and Bastion Host Implementation

## Overview

This document describes the implementation of a security-hardened VPC architecture with:
- **Public subnets** for bastion host and NAT instance
- **Private subnets** for EKS worker nodes (no public IPs)
- **Bastion host** as the single hardened entry point for administrative access
- **NAT instance** for egress traffic from private resources

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          AWS VPC (10.0.0.0/16)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────── PUBLIC SUBNETS ───────────────────┐          │
│  │                                                    │          │
│  │  Subnet 1: 10.0.0.0/24 (us-east-2a)      │          │
│  │  ┌────────────────────────────────┐       │          │
│  │  │  🛡️  Bastion Host (Hardened)    │       │          │
│  │  │  ├─ t4g.nano (ARM/Graviton)    │       │          │
│  │  │  ├─ IMDSv2 required            │       │          │
│  │  │  ├─ Strict SSH allowlist       │       │          │
│  │  │  └─ Elastic IP (static public) │       │          │
│  │  └────────────────────────────────┘       │          │
│  │                                            │          │
│  │  ┌────────────────────────────────┐       │          │
│  │  │  🔄 NAT Instance (fck-nat)     │       │          │
│  │  │  ├─ Egress only (no SSH key)   │       │          │
│  │  │  ├─ SSM Session Manager        │       │          │
│  │  │  └─ Public subnet in AZ-a      │       │          │
│  │  └────────────────────────────────┘       │          │
│  │                                            │          │
│  │                                    IGW    │          │
│  │                ┌───────────────────────┐  │          │
│  │                │ Internet Gateway      │  │          │
│  │                └───────────────────────┘  │          │
│  └────────────────────────────────────────────┘          │
│           │                                              │
│           ├─ Route: 0.0.0.0/0 → IGW                      │
│           │                                              │
│  ┌────────────────── PRIVATE SUBNETS ───────────────────┐       │
│  │                                                       │       │
│  │  Subnet 2: 10.0.10.0/24 (us-east-2a)      │       │
│  │  ┌──────────────────────────────────────┐  │       │
│  │  │  🎯 EKS Worker Nodes (Private)       │  │       │
│  │  │  ├─ No public IP addresses          │  │       │
│  │  │  ├─ Access via bastion SSH tunnel   │  │       │
│  │  │  ├─ Or SSM Session Manager          │  │       │
│  │  │  └─ Access to: RDS, ECR, SQS        │  │       │
│  │  └──────────────────────────────────────┘  │       │
│  │                                    │        │       │
│  │  Subnet 3: 10.0.11.0/24 (us-east-2b)      │       │
│  │  ┌──────────────────────────────────────┐  │       │
│  │  │  🎯 EKS Worker Nodes (Private)       │  │       │
│  │  │                                      │  │       │
│  │  └──────────────────────────────────────┘  │       │
│  │           │                                 │       │
│  │           └─ Route: 0.0.0.0/0 → NAT → IGW │       │
│  └───────────────────────────────────────────────┘       │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

## Implementation Details

### 1. VPC Infrastructure (Already Present)

**File: [infra/terraform/modules/vpc/main.tf](../../terraform/modules/vpc/main.tf)**

- Creates VPC with 10.0.0.0/16 CIDR
- 2 public subnets (10.0.0.0/24, 10.0.1.0/24) in AZs a and b
- 2 private subnets (10.0.10.0/24, 10.0.11.0/24) in AZs a and b
- Internet Gateway for public subnet egress
- Route tables with proper associations
- VPC Flow Logs for network traffic monitoring

**Why public subnets exist:**
- Bastion host needs internet access for SSH connections
- NAT instance needs internet access to route egress traffic
- Both instances have public IPs but are behind strict security groups

### 2. Bastion Host (Hardened Jumphost)

**File: [infra/terraform/modules/bastion/](../../terraform/modules/bastion/)**

**Security Controls:**
- **SSH Allowlist**: Strict source-IP restrictions (no 0.0.0.0/0)
- **IMDSv2 Required**: Prevents SSRF credential theft
- **Root Login Disabled**: SSH configuration in user_data
- **Key-Only Authentication**: No password login
- **Instance Profile**: SSM Session Manager for keyless access
- **Elastic IP**: Stable public address

**Access Methods:**
```bash
# Method 1: SSH (via allowlisted IPs only)
ssh -i ~/.ssh/bastion-key.pem ec2-user@<bastion-elastic-ip>

# Method 2: SSM Session Manager (requires no SSH port)
aws ssm start-session --target <bastion-instance-id>

# Method 3: SSH to private nodes via bastion tunnel
ssh -i ~/.ssh/bastion-key.pem -J ec2-user@<bastion-eip> ec2-user@<private-node-ip>
```

### 3. NAT Instance for Egress

**File: [infra/terraform/modules/nat/](../../terraform/modules/nat/)**

**Features:**
- Uses **fck-nat** community AMI (production-ready, ARM64/Graviton)
- Single instance in public subnet (us-east-2a)
- Private subnet route: 0.0.0.0/0 → NAT instance
- Source/destination check disabled for IP forwarding
- Encrypted EBS volume (gp3)
- CloudWatch monitoring enabled
- SSM Session Manager access (no SSH port)

**Why fck-nat:**
- Maintained by community with long track record
- Pre-configured for NAT with IP forwarding and iptables rules
- No user_data needed
- Affordable for dev/test environments ($0.016/hour for t4g.nano)

**Cost Note:**
- For production HA, consider AWS NAT Gateway ($32/month base + data transfer)
- For dev/test, NAT instance ($0.384/month compute + data transfer)

### 4. EKS Worker Nodes in Private Subnets

**Files:**
- [infra/terraform/modules/eks/main.tf](../../terraform/modules/eks/main.tf)
- [infra/terragrunt/envs/dev/eks/terragrunt.hcl](../../terragrunt/envs/dev/eks/terragrunt.hcl)

**Key Configuration:**
```hcl
node_groups {
  "default" = {
    # ...
    associate_public_ip = false      # ✓ No public IPs
    # ...
  }
}
```

**Security Group Rules Implemented:**
1. ✓ Node-to-node communication (all protocols)
2. ✓ Cluster control plane → nodes (kubelet, kube-proxy)
3. ✓ **NEW**: Bastion → nodes SSH (port 22) - for administrative debugging
4. ✓ Nodes → internet via NAT instance

**Administrative Access to Private Nodes:**

```bash
# Option 1: SSH via bastion (jumps through bastion)
ssh -i private-node-key.pem -J ec2-user@<bastion-eip> ec2-user@<node-private-ip>

# Option 2: SSM Session Manager (if node has proper IAM role)
aws ssm start-session --target <node-instance-id>

# Option 3: Port-forward via bastion for kubectl access
ssh -i bastion-key.pem -L 6443:eks-api-endpoint:6443 ec2-user@<bastion-eip>
```

## Terragrunt Stack Configuration

### Deployment Order

```
1. shared-infra           (VPC, subnets, security groups)
2. secrets               (RDS master password in Secrets Manager)
3. bastion               (Hardened jumphost)
4. nat                   (NAT instance for egress)
5. eks                   (EKS cluster with private nodes)
6. rds                   (Database in private subnet)
7. deploy-config         (Application configuration)
```

### Created/Modified Files

#### 1. **NEW: Secrets Terragrunt Configuration**
**File: [infra/terragrunt/envs/dev/secrets/terragrunt.hcl](../../terragrunt/envs/dev/secrets/terragrunt.hcl)**

```hcl
# Fixed: Missing secrets/terragrunt.hcl causing "file does not exist" errors
# Enables AWS Secrets Manager for RDS credentials
```

**Why it was needed:**
- The deploy-config module had a dependency on secrets module
- But the terragrunt file was missing, causing init failures
- Now properly declares the AWS Secrets Manager resources

#### 2. **UPDATED: NAT Instance Enabled**
**File: [infra/terragrunt/envs/dev/nat/terragrunt.hcl](../../terragrunt/envs/dev/nat/terragrunt.hcl)**

```hcl
enabled = true  # Changed from false to enable NAT instance

# Now provides:
# - Elastic IP for stable outbound address
# - Route: private subnets 0.0.0.0/0 → NAT instance
# - CloudWatch+SSM monitoring
```

**Why enabled:**
- Private subnet nodes need internet access for:
  - Pulling container images from ECR
  - Downloading package updates
  - Reaching AWS APIs (SQS, RDS, etc.)

#### 3. **ENHANCED: EKS with Bastion Access**
**File: [infra/terraform/modules/eks/variables.tf](../../terraform/modules/eks/variables.tf)**

Added new variable:
```hcl
variable "bastion_security_group_id" {
  description = "Security group ID of the bastion host"
  type        = string
  default     = null
  nullable    = true
}
```

**File: [infra/terraform/modules/eks/main.tf](../../terraform/modules/eks/main.tf)**

Added dynamic security group rule:
```hcl
bastion_ssh_rule = var.bastion_security_group_id != null ? {
  bastion_ssh_to_nodes = {
    type              = "ingress"
    from_port         = 22
    to_port           = 22
    protocol          = "tcp"
    source_sg_id      = var.bastion_security_group_id
    security_group_id = aws_security_group.eks_nodes.id
    description       = "Allow SSH from bastion host to worker nodes"
  }
} : {}
```

**File: [infra/terragrunt/envs/dev/eks/terragrunt.hcl](../../terragrunt/envs/dev/eks/terragrunt.hcl)**

Updated inputs:
```hcl
bastion_security_group_id = dependency.bastion.outputs.bastion_security_group_id
```

## Security Posture

### Network-Level Security ✅

| Component | Public IP | SSH | Internet | Access via |
|-----------|-----------|-----|----------|-----------|
| **Bastion** | Yes (EIP) | ✓ (allowlist) | ✓ | Direct SSH / SSM |
| **NAT Instance** | Yes (EIP) | ✗ (SSM only) | ✓ | SSM Session Manager |
| **EKS Nodes** | ✗ | ✓ (via bastion) | ✗ direct (via NAT) | SSH tunnel / SSM |
| **RDS** | ✗ | N/A | ✗ | Private subnet only |

### Hardening Features ✅

1. **Zero Trust Network Access**
   - No public IPs on compute resources
   - No default internet routes
   - Explicit ingress/egress rules
   - Bastion is single entry point

2. **Bastion Hardening**
   - SSH allowlist (no 0.0.0.0/0)
   - IMDSv2 enforced
   - IAM instance profile for Session Manager
   - Root login disabled
   - Key-based auth only

3. **Worker Node Isolation**
   - Deployed in private subnets
   - No public DynamicIP
   - Outbound via NAT instance only
   - Access via bastion tunnel or SSM

4. **Encryption in Transit**
   - TLS for EKS API endpoint
   - SSH for bastion access
   - IMDSv2 (vs v1) prevents SSRF

5. **Encryption at Rest**
   - Root volumes encrypted (gp3)
   - EBS encrypted
   - KMS key for EKS secrets
   - RDS encryption

## Deployment Instructions

### Prerequisites

```bash
# Set required environment variables
export TF_VAR_discord_webhook_url="https://discord.com/api/webhooks/..."
export TG_VAR_BASTION_ALLOWED_SSH_CIDRS='["YOUR_IP/32"]'

# Create bastion SSH key
aws ec2 create-key-pair --key-name bastion-key \
  --query 'KeyMaterial' --output text > ~/.ssh/bastion-key.pem
chmod 600 ~/.ssh/bastion-key.pem
```

### Step-by-Step Deployment

```bash
cd infra/terragrunt/envs/dev

# 1. Initialize Terragrunt (downloads modules, validates config)
terragrunt run-all init

# 2. Validate Terraform syntax and schema
terragrunt run-all validate

# 3. Plan Infrastructure Changes
terragrunt run-all plan

# 4. Deploy infrastructure
terragrunt run-all apply

# 5. Retrieve outputs
terragrunt run-all output
```

### Post-Deployment Verification

```bash
# Get bastion public IP
BASTION_IP=$(terragrunt output -raw -chdir=bastion bastion_public_ip)

# Test SSH access (if in allowlist)
ssh -i ~/.ssh/bastion-key.pem ec2-user@$BASTION_IP

# Connect via SSM Session Manager
BASTION_ID=$(terragrunt output -raw -chdir=bastion bastion_instance_id)
aws ssm start-session --target $BASTION_ID

# From bastion, SSH to private EKS nodes
EKS_NODE_IP="10.0.10.X"  # Get from EC2 console
ssh -i private-key.pem ec2-user@$EKS_NODE_IP

# Verify NAT instance is routing traffic
aws ec2 describe-network-interfaces \
  --filters Name=vpc-id,Values=vpc-xxx \
  --query 'NetworkInterfaces[?SourceDestCheck==`false`]'
```

## Cost Impact (Dev Environment)

| Component | Type | Monthly Cost |
|-----------|------|--------------|
| NAT Instance (t4g.nano) | Compute | $0.38 |
| NAT Instance EIP | Allocation | $0.00 (free if associated) |
| Data transfer (egress) | Network | $0.09/GB |
| Bastion (t4g.nano) | Compute | $0.38 |
| **Total Base** | - | **~$0.76** |
| Plus data transfer | Network | Variable |

**Comparison:**
- NAT Gateway: $32/month base + $0.045/GB (much higher for prod)
- NAT Instance: Best for dev/test with same functionality

## Operational Procedures

### Break-Glass Access (Emergency)

If bastion is compromised or unreachable:

```bash
# Connect to EKS nodes directly via SSM (if agent running)
aws ssm start-session --target <node-id>

# Connect to NAT instance (for debugging routing)
aws ssm start-session --target <nat-instance-id>

# Note: Requires IAM permissions for SSM but no direct network access
```

### Monitoring

```bash
# VPC Flow Logs (config in shared-infra)
aws logs describe-log-groups --log-group-name-prefix "/aws/vpc-flow-log"

# NAT Instance CloudWatch Metrics
aws cloudwatch list-metrics --namespace AWS/EC2 \
  --dimensions Name=InstanceId,Value=i-xxx
```

### Scaling

- **Bastion**: Single instance sufficient for dev (t4g.nano)
- **NAT**: Single instance for dev; production should have HA (one per AZ)
- **EKS Nodes**: Autoscaling configured (2-4 nodes in dev)

## Future Enhancements (Optional)

1. **NAT Gateway for Production**
   ```terraform
   # Alternative to NAT instance for HA
   # One per AZ for fault tolerance
   # Higher cost but better SLA
   ```

2. **VPC Endpoints**
   ```terraform
   # Avoid NAT for AWS service calls:
   # - S3 VPC Endpoint
   # - ECR VPC Endpoints
   # - SQS VPC Endpoint
   # - DynamoDB VPC Endpoint
   ```

3. **Bastion Autoscaling Group**
   ```terraform
   # Replace single instance with ASG
   # Automatic recovery if unhealthy
   ```

4. **OpenVPN for Encrypted Remote Access** ✓
   - [infra/terraform/modules/vpn/](../../terraform/modules/vpn/) (already present)
   - Alternative to SSH-based access

5. **Network ACLs for Additional Tiering**
   - Subnet-level stateless firewall
   - Added security for defense-in-depth

## Troubleshooting

### Nodes Cannot Access Internet

```bash
# 1. Verify NAT instance is running
aws ec2 describe-instances --filters Name=tag:Role,Values=NAT

# 2. Check private route table routes
aws ec2 describe-route-tables --filters Name=tag:Name,Values="*private*"

# 3. Verify source_dest_check is disabled on NAT
aws ec2 describe-network-attributes --network-interface-id eni-xxx \
  --query 'SourceDestCheck.Value'

# 4. Check NAT security group allows private subnet CIDR
aws ec2 describe-security-groups --group-ids sg-xxx
```

### Cannot SSH to Bastion

```bash
# 1. Verify IP is in BASTION_ALLOWED_SSH_CIDRS
terraform output -chdir=bastion -json | jq '.allowed_ssh_cidrs'

# 2. Verify bastion SG exists and has SSH rule
aws ec2 describe-security-groups --group-ids sg-xxx

# 3. Verify bastion has Elastic IP
aws ec2 describe-addresses --filters Name=instance-id,Values=i-xxx
```

### Nodes Cannot Reach EKS API

```bash
# 1. Verify cluster endpoint is accessible from private subnet
kubectl get nodes  # Should work from within VPC

# 2. Check security group allows nodes → cluster
aws ec2 describe-security-groups --filters \
  Name=group-name,Values="*eks*cluster*"

# 3. Verify private route table has NAT route for 0.0.0.0/0
aws ec2 describe-route-tables --filters Name=tag:Name,Values="*private*"
```

---

## Implementation Summary

✅ **Completed Tasks:**

1. ✅ VPC infrastructure with public and private subnets  
2. ✅ Bastion host with strict source-IP allowlist
3. ✅ NAT instance for private subnet egress
4. ✅ EKS worker nodes deployed to private subnets (no public IPs)
5. ✅ Security group rules allowing bastion → nodes SSH
6. ✅ Missing secrets terragrunt file created
7. ✅ VPC Flow Logs enabled for network monitoring
8. ✅ Encryption at rest and in transit configured
9. ✅ SSM Session Manager as keyless access alternative
10. ✅ Documentation for deployment and troubleshooting

**Result:** Infrastructure meets security requirements with worker nodes in private subnets and hardened bastion as the single entry point for administrative access.
