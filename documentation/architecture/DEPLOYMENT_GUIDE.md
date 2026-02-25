# Quick Reference: Hardened VPC Deployment Guide

## Pre-Deployment Checklist

```bash
# 1. Set required environment variables
export TF_VAR_discord_webhook_url="https://discord.com/api/webhooks/your-webhook-url"
export TG_VAR_BASTION_ALLOWED_SSH_CIDRS='["203.0.113.0/32"]'  # Your IP

# 2. Create bastion SSH key pair
aws ec2 create-key-pair --key-name bastion-key \
  --query 'KeyMaterial' --output text > ~/.ssh/bastion-key.pem
chmod 600 ~/.ssh/bastion-key.pem

# 3. Verify AWS credentials
aws sts get-caller-identity

# 4. Verify Terraform/Terragrunt installed
terraform --version  # Should be >= 1.0
terragrunt --version  # Should be >= 0.50
```

## Deployment Steps

```bash
# Navigate to the deployment directory
cd infra/terragrunt/envs/dev

# Step 1: Initialize all modules
echo "=== STEP 1: Initialize Terraform modules ==="
terragrunt run-all init --terragrunt-non-interactive

# Step 2: Validate configuration
echo "=== STEP 2: Validate Terraform configuration ==="
terragrunt run-all validate

# Step 3: Plan infrastructure
echo "=== STEP 3: Plan infrastructure changes ==="
terragrunt run-all plan --terragrunt-non-interactive 2>&1 | tee /tmp/tg-plan.log

# Review plan output
echo "--- PLAN SUMMARY ---"
grep -E "Plan:|No changes|must be replaced" /tmp/tg-plan.log

# Step 4: Deploy infrastructure
echo "=== STEP 4: Deploy infrastructure ==="
terragrunt run-all apply --terragrunt-non-interactive --auto-approve

# Wait for all resources to be created (5-10 minutes)

# Step 5: Retrieve outputs
echo "=== STEP 5: Retrieve deployment outputs ==="
terragrunt run-all output
```

## Verification Steps

```bash
# Get the bastion public IP
BASTION_IP=$(terragrunt output -raw bastion_public_ip 2>/dev/null || \
  aws ec2 describe-addresses --filters Name=tag:Name,Values="*bastion-eip" \
  --query 'Addresses[0].PublicIp' --output text)

echo "Bastion Public IP: $BASTION_IP"

# Test SSH access
ssh -i ~/.ssh/bastion-key.pem -o ConnectTimeout=5 ec2-user@$BASTION_IP "echo 'SSH works!' && exit"

# Get EKS cluster name
CLUSTER_NAME=$(terragrunt output -raw -chdir=eks cluster_name 2>/dev/null)
echo "EKS Cluster: $CLUSTER_NAME"

# Get kubeconfig
$(terragrunt output -raw -chdir=eks kubeconfig_command 2>/dev/null | head -1)

# Verify nodes are in private subnets (no public IPs)
kubectl get nodes -o wide

# Verify nodes can reach internet via NAT
kubectl run -it --rm debug --image=busybox --restart=Never -- sh -c "curl -s ifconfig.io"
```

## Common Operations

### Connect to Bastion

```bash
# SSH (direct)
ssh -i ~/.ssh/bastion-key.pem ec2-user@$BASTION_IP

# SSH (with port forward - useful for kubectl API access)
ssh -i ~/.ssh/bastion-key.pem -D 9999 ec2-user@$BASTION_IP

# SSM Session Manager (no SSH key needed)
BASTION_ID=$(aws ec2 describe-instances \
  --filters Name=tag:Name,Values="*bastion" \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)
aws ssm start-session --target $BASTION_ID
```

### Access Private EKS Nodes

```bash
# Option 1: SSH tunnel through bastion
NODE_IP="10.0.10.X"  # Get from EC2 console or kubectl get nodes -o wide
ssh -i ~/.ssh/private-key.pem -J ec2-user@$BASTION_IP ec2-user@$NODE_IP

# Option 2: SSM Session Manager (if node has SSM permissions)
NODE_ID=$(aws ec2 describe-instances \
  --filters Name=tag:Name,Values="*eks*" \
  --query 'Reservations[].Instances[].InstanceId' --output text | head -1)
aws ssm start-session --target $NODE_ID

# Option 3: kubectl debug pod
kubectl debug node/node-name -it --image=ubuntu
```

### Destroy Infrastructure

```bash
# WARNING: This will delete all resources including data!
cd infra/terragrunt/envs/dev

# Plan destruction
terragrunt run-all destroy --terragrunt-non-interactive --auto-approve

# Alternative: Destroy specific stack only
terragrunt destroy -chdir=eks --auto-approve
```

## Connectivity Matrix

| Source | Destination | Port | Method |
|--------|-------------|------|--------|
| Your PC | Bastion SSH | 22 | Direct SSH (allowlist) |
| Your PC | Bastion Console | ANY | SSM Session Manager |
| Bastion | Private Nodes | 22 | SSH tunnel (no direct access) |
| Bastion | EKS API | 443 | HTTPS (via VPC private subnet) |
| Private Nodes | Internet | ANY | NAT instance (outbound only) |
| Private Nodes | RDS | 5432 | Private subnet routing |
| Private Nodes | EKS API | 443 | VPC private endpoint |

## Network Topology Verification

```bash
# 1. Verify VPC and subnets
aws ec2 describe-vpcs --query 'Vpcs[?Tags[?Key==`Name`]].{Name:Tags[?Key==`Name`].Value|[0],CIDR:CidrBlock}'

# 2. List subnets and their routing
aws ec2 describe-subnets --filters "Name=vpc-id,Values=vpc-xxxx" \
  --query 'Subnets[].{SubnetId:SubnetId,CIDR:CidrBlock,AZ:AvailabilityZone,Public:MapPublicIpOnLaunch}'

# 3. Verify route tables
aws ec2 describe-route-tables --filters "Name=vpc-id,Values=vpc-xxxx" \
  --query 'RouteTables[].{RouteTableId:RouteTableId,Routes:Routes[].{Destination:DestinationCidrBlock,Target:GatewayId||NatGatewayId||InstanceId||NetworkInterfaceId}}'

# 4. Verify security groups
aws ec2 describe-security-groups --filters "Name=vpc-id,Values=vpc-xxxx" \
  --query 'SecurityGroups[].{GroupId:GroupId,GroupName:GroupName,Rules:IpPermissions[].{Port:FromPort,Protocol:IpProtocol}}'

# 5. Verify NAT instance configuration
aws ec2 describe-network-interfaces \
  --filters "Name=vpc-id,Values=vpc-xxxx" \
  --query 'NetworkInterfaces[?SourceDestCheck==`false`].{ENI:NetworkInterfaceId,Status:Status,SourceDestCheck:SourceDestCheck}'
```

## Troubleshooting

### Issue: Terraform init fails with "file does not exist"

**Cause:** Missing secrets/terragrunt.hcl

**Fix:** ✅ Already fixed in this deployment (file created)

```bash
ls -la infra/terragrunt/envs/dev/secrets/terragrunt.hcl
```

### Issue: Bastion deployment fails - "Key does not exist"

**Cause:** EC2 Key Pair not in AWS

**Fix:**
```bash
aws ec2 create-key-pair --key-name bastion-key \
  --query 'KeyMaterial' --output text > ~/.ssh/bastion-key.pem
chmod 600 ~/.ssh/bastion-key.pem
```

### Issue: Cannot SSH to bastion - Connection refused

**Cause:** IP not in BASTION_ALLOWED_SSH_CIDRS

**Fix:**
```bash
# Get your public IP
curl -s ifconfig.io

# Update env var and re-deploy
export TG_VAR_BASTION_ALLOWED_SSH_CIDRS='["YOUR_IP/32"]'
terragrunt apply -chdir=bastion --auto-approve
```

### Issue: EKS nodes cannot reach internet

**Cause:** NAT instance not running or not in route table

**Fix:**
```bash
# 1. Verify NAT is running
aws ec2 describe-instances \
  --filters Name=tag:Role,Values=NAT \
  --query 'Reservations[].Instances[].InstanceId'

# 2. Verify it's in the private route table
aws ec2 describe-route-tables \
  --filters Name=tag:Name,Values="*private*" \
  --query 'RouteTables[].Routes[].{Destination:DestinationCidrBlock,Target:NetworkInterfaceId}'

# 3. If missing, enable NAT in terragrunt and re-apply
# Set `enabled = true` in nat/terragrunt.hcl
terragrunt apply -chdir=nat --auto-approve
```

### Issue: Cannot connect to Kubernetes API

**Cause:** Missing kubeconfig or cluster endpoint restricted

**Fix:**
```bash
# 1. Generate/update kubeconfig
aws eks update-kubeconfig --region us-east-2 --name Training-drive-ops-dev-eks

# 2. Verify context is set
kubectl config current-context

# 3. Test connectivity
kubectl cluster-info

# 4. If still failing, may need SSH tunnel through bastion to EKS endpoint
# (private endpoint not directly reachable from outside VPC)
```

## File Structure

```
infra/
├── terraform/
│   └── modules/
│       ├── vpc/                      # VPC with public/private subnets
│       ├── bastion/                  # Hardened jumphost
│       ├── nat/                      # NAT instance for egress
│       ├── eks/                      # EKS cluster with private nodes
│       └── ...
└── terragrunt/
    └── envs/dev/
        ├── shared-infra/             # VPC, KMS, SQS, ECR
        ├── secrets/           ✅ NEW  # RDS secrets Manager
        ├── bastion/                  # Bastion host deployment
        ├── nat/              ✅ UPDATED  # NAT instance (enabled)
        ├── eks/              ✅ UPDATED  # EKS cluster (bastion integration)
        ├── rds/                      # RDS database
        ├── deploy-config/            # App configuration
        └── ...
```

## Security Best Practices Applied

✅ **Network Security**
- No public IPs on compute (EKS nodes, NAT instance)
- Bastion as single entry point
- Private subnets for resources
- NAT for controlled egress

✅ **IAM & Access Control**  
- SSM Session Manager for keyless access
- Instance profiles with least privilege permissions
- Bastion SSH allowlist (no 0.0.0.0/0)
- IRSA for pod-level permissions

✅ **Encryption**
- IMDSv2 (prevents SSRF)
- TLS for EKS API
- Encrypted EBS volumes
- KMS envelope encryption for secrets

✅ **Monitoring & Logging**
- VPC Flow Logs enabled
- CloudWatch monitoring for NAT instance
- EKS control plane audit logs
- CloudTrail for API calls

✅ **Compliance**
- No sensitive data in code (env vars)
- Encryption in transit and at rest
- Hardened bastion configuration
- Network isolation by design

## Next Steps

1. **Configure OpenVPN** (Optional)
   ```bash
   cd infra/terragrunt/envs/dev/vpn
   terragrunt plan
   terragrunt apply
   ```

2. **Deploy applications to EKS**
   ```bash
   kubectl apply -f k8s/manifests/
   ```

3. **Set up monitoring and alerts**
   ```bash
   # Use CloudWatch dashboards and alarms
   ```

4. **Implement backup & disaster recovery**
   ```bash
   # RDS automated backups (configured)
   # EBS snapshots
   # ECR image retention
   ```

---

**Documentation:** See [hardened-vpc-private-nodes-implementation.md](hardened-vpc-private-nodes-implementation.md) for detailed architecture and troubleshooting.
