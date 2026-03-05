# NAT Instance Module

Deploys a **cost-effective NAT instance** using the fck-nat community AMI (ARM64/Graviton) to provide outbound internet access for resources in private subnets (EKS worker nodes, RDS patch downloads, etc.).

## Quick Enable/Disable

The NAT instance is **disabled by default** (`enabled = false`). To provision it:

### Enable NAT

Edit [`infra/terragrunt/envs/dev/nat/terragrunt.hcl`](../../../terragrunt/envs/dev/nat/terragrunt.hcl):

```hcl
inputs = {
  enabled = true  # ← Change this to true

  project_name = local.common_vars.project_name
  env          = local.env_vars.env
  # ... rest of config
}
```

Then apply:

```bash
cd infra/terragrunt/envs/dev/nat
terragrunt apply
```

### Disable NAT

Set `enabled = false` in the same file and apply:

```bash
terragrunt apply
```

All NAT resources (EC2, EIP, security group, route) will be destroyed.

---

## What This Module Does

| Component | Description |
|---|---|
| **EC2 Instance** | fck-nat community AMI (ARM64/Graviton, ~$3/mo compute cost) |
| **Elastic IP** | Stable public outbound address for private-subnet traffic |
| **Security Group** | Allows ingress from private subnet CIDRs for NAT forwarding; optional SSH from bastion |
| **Private Route** | Injects `0.0.0.0/0 → NAT ENI` into the private route table |
| **IAM Role** | SSM Session Manager access (management without SSH port 22) |

### Architecture

```text
Private Subnets (EKS nodes, RDS, etc.)
      ↓
    Private Route Table
      ↓
    0.0.0.0/0 → NAT Instance ENI
      ↓
    NAT Instance (source_dest_check disabled)
      ↓
    Elastic IP (stable outbound address)
      ↓
    Internet Gateway
      ↓
    Internet
```

---

## Variables

| Variable | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `false` | Master switch: `true` to provision, `false` to destroy. |
| `project_name` | string | — | Project name (e.g., `drive-ops`) |
| `env` | string | — | Environment (e.g., `dev`, `prod`) |
| `account_id` | string | — | AWS account ID (for IAM permissions boundary) |
| `vpc_id` | string | — | VPC ID where the instance is deployed |
| `public_subnet_id` | string | — | Public subnet for the NAT instance (must have IGW route) |
| `private_subnet_cidrs` | list(string) | — | Private subnet CIDR blocks (for SG ingress allowlist) |
| `private_route_table_id` | string | — | Private route table where `0.0.0.0/0 → NAT` is injected |
| `instance_type` | string | `t4g.nano` | EC2 instance type (must be ARM/Graviton: t4g, m6g, c6g, etc.) |
| `key_name` | string | `null` | Optional EC2 Key Pair for SSH break-glass access |
| `allowed_ssh_cidrs` | list(string) | `[]` | CIDR blocks allowed to SSH (e.g., bastion EIP). If empty, SSH ingress is not created. |
| `enable_ssm` | bool | `true` | Attach SSM Session Manager IAM policy |
| `enable_cloudwatch` | bool | `true` | Attach CloudWatch Agent IAM policy |

---

## Outputs

When `enabled = true`:

```text
nat_instance_id          → NAT EC2 instance ID
nat_instance_public_ip   → Elastic IP (stable outbound address)
nat_instance_private_ip  → Private IP within the VPC
nat_security_group_id    → NAT security group ID
```

When `enabled = false`:

All outputs return `null`.

---

## Usage: Enable for Dev

### Step 1: Set enabled = true

```bash
cd infra/terragrunt/envs/dev/nat
# Edit terragrunt.hcl
# Change: enabled = false → enabled = true
```

### Step 2: Plan

```bash
terragrunt plan
```

Expected output: 9 resources to be created (IAM role, SG, EIP, EC2, route, etc.).

### Step 3: Apply

```bash
terragrunt apply
```

The NAT instance boots. Wait ~2 min for system startup and iptables rules to initialize.

### Step 4: Verify

```bash
# Check the instance is healthy
aws ec2 describe-instances --instance-ids $(terragrunt output -raw nat_instance_id) --query 'Reservations[0].Instances[0].State.Name'

# Should return: "running"

# Check the route exists
aws ec2 describe-route-tables --route-table-ids $(terragrunt output -raw private_route_table_id) \
  --query 'RouteTables[0].Routes[?DestinationCidrBlock==`0.0.0.0/0`]'
```

### Step 5: Route outbound traffic

To verify private-subnet workloads can reach the internet:

```bash
# From an EKS node or RDS instance in a private subnet:
curl https://ifconfig.io  # Should return the NAT EIP
```

---

## How to Manage SSH Access

### Option A: Via Bastion (Recommended)

Set `allowed_ssh_cidrs` to the bastion's Elastic IP:

```hcl
inputs = {
  enabled = true
  allowed_ssh_cidrs = ["<bastion-eip>/32"]
  # ...
}
```

Then reach the NAT instance from the bastion:

```bash
ssh -A ec2-user@<nat-private-ip>
```

### Option B: Via SSM Session Manager (No SSH Key)

By default, `enable_ssm = true`. Open a shell without port 22:

```bash
aws ssm start-session --target $(terragrunt output -raw nat_instance_id)
```

### Option C: Provide SSH Key

Set `key_name`:

```hcl
inputs = {
  enabled = true
  key_name = "nat-key"
  allowed_ssh_cidrs = ["0.0.0.0/0"]  # Not recommended — be specific
  # ...
}
```

---

## Cost & Performance

- **Instance**: t4g.nano (ARM/Graviton) — ~$3/month compute
- **EIP**: $0.01/hour if not associated (included here) + $0.005/hour for data processed (varies)
- **Throughput**: t4g.nano can handle ~50–100 Mbps reliably; larger workloads need m6g or larger

For **production HA**, deploy one NAT instance per AZ (use `enable_ha = true` pattern).

---

## Troubleshooting

### NAT instance not reachable from private subnets

1. Check the route:
   ```bash
   aws ec2 describe-route-tables --route-table-ids <private-rt-id>
   ```
   Should show: `Destination: 0.0.0.0/0, Target: <nat-instance-eni>`

2. Check security groups:
   - Private-subnet SG must allow egress to NAT SG (port 0-65535, all protocols)
   - NAT SG must allow ingress from private-subnet CIDRs

3. Check NAT instance state:
   ```bash
   aws ec2 describe-instances --instance-ids <nat-instance-id> \
     --query 'Reservations[0].Instances[0].[State.Name,PrivateIpAddress,PublicIpAddress]'
   ```

### Route not being created

- Verify `private_route_table_id` is passed correctly
- Check NAT instance is in "running" state
- Verify primary ENI is attached and in "available" state

### Performance degradation

- Monitor CloudWatch metrics (if `enable_cloudwatch = true`):
  ```bash
  aws cloudwatch get-metric-statistics \
    --namespace AWS/EC2 \
    --metric-name NetworkOut \
    --start-time 2026-03-01T00:00:00Z \
    --end-time 2026-03-01T01:00:00Z \
    --period 300 \
    --statistics Sum \
    --dimensions Name=InstanceId,Value=<nat-instance-id>
  ```
- If throughput is high, upgrade `instance_type` to m6g.large or larger

---

## See Also

- [VPC Module](../vpc/README.md) — Creates subnets and routes
- [NAT Variables](./variables.tf) — All configuration options
- [fck-nat GitHub](https://github.com/AndrewGuenther/fck-nat) — Community project details
