resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = { Name = "${var.project_name}-${var.env}-vpc" }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.project_name}-${var.env}-igw" }
}

# Public subnets - using fixed AZs from variables
resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name                     = "${var.project_name}-public-subnet-${count.index + 1}"
    "kubernetes.io/role/elb" = "1"
  }
}

# Private subnets - using fixed AZs from variables
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 10)
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name                              = "${var.project_name}-private-subnet-${count.index + 1}"
    "kubernetes.io/role/internal-elb" = "1"
  }
}

# --- Routing ---

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
  tags = { Name = "${var.project_name}-${var.env}-public-rt" }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  # No route to 0.0.0.0/0 ensures isolation (unless NAT is enabled)
  tags = { Name = "${var.project_name}-${var.env}-private-rt" }
}

# Default route through NAT Instance for private subnet outbound internet access
resource "aws_route" "private_nat_instance" {
  count                  = var.use_nat_instance ? 1 : 0
  route_table_id         = aws_route_table.private.id
  destination_cidr_block = "0.0.0.0/0"
  network_interface_id   = aws_instance.nat_instance[0].primary_network_interface_id
  depends_on             = [aws_instance.nat_instance]
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# --- Default Resources Management (Naming & Security) ---

# Manage the default (Main) Route Table to name it properly
resource "aws_default_route_table" "main" {
  default_route_table_id = aws_vpc.main.default_route_table_id

  # We keep it empty/local only for security
  tags = {
    Name = "${var.project_name}-${var.env}-main-rt"
  }
}

# Manage the default Network ACL to name it properly
resource "aws_default_network_acl" "default" {
  default_network_acl_id = aws_vpc.main.default_network_acl_id

  # Ingress: Allow all (default behavior for NACL)
  ingress {
    protocol   = -1
    rule_no    = 100
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 0
    to_port    = 0
  }

  # Egress: Allow all (default behavior for NACL)
  egress {
    protocol   = -1
    rule_no    = 100
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 0
    to_port    = 0
  }

  tags = {
    Name = "${var.project_name}-${var.env}-default-nacl"
  }
}

# Manage the default Security Group to lock it down completely.
resource "aws_default_security_group" "default" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-${var.env}-default-sg"
  }
}

# --- VPC Flow Logs (Cost-Optimized & Boundary-Compliant) ---

resource "aws_cloudwatch_log_group" "flow_log" {
  count             = var.enable_flow_logs ? 1 : 0
  name              = "/aws/vpc-flow-log/${var.project_name}-${var.env}"
  retention_in_days = var.flow_log_retention_in_days
  tags              = { Name = "${var.project_name}-${var.env}-flow-log-group" }
}

resource "aws_iam_role" "flow_log_role" {
  count                = var.enable_flow_logs ? 1 : 0
  name                 = "Training-${var.project_name}-${var.env}-vpc-flow-log-role"
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "vpc-flow-logs.amazonaws.com"
        }
      }
    ]
  })

  tags = { Name = "Training-${var.project_name}-${var.env}-vpc-flow-log-role" }
}

resource "aws_iam_role_policy" "flow_log_policy" {
  count = var.enable_flow_logs ? 1 : 0
  name  = "Training-${var.project_name}-${var.env}-vpc-flow-log-policy"
  role  = aws_iam_role.flow_log_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Effect   = "Allow"
        Resource = "${aws_cloudwatch_log_group.flow_log[0].arn}:*"
      }
    ]
  })
}

resource "aws_flow_log" "main" {
  count           = var.enable_flow_logs ? 1 : 0
  iam_role_arn    = aws_iam_role.flow_log_role[0].arn
  log_destination = aws_cloudwatch_log_group.flow_log[0].arn
  traffic_type    = "ALL"
  vpc_id          = aws_vpc.main.id

  tags = { Name = "${var.project_name}-${var.env}-flow-log" }
}

# --- NAT Instance IAM Role & Instance Profile ---

# IAM Role for NAT Instance (enables SSM and CloudWatch agent access)
resource "aws_iam_role" "nat_instance" {
  count                = var.use_nat_instance ? 1 : 0
  name                 = "Training-${var.project_name}-${var.env}-nat-instance-role"
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = { Name = "Training-${var.project_name}-${var.env}-nat-instance-role" }
}

# Attach SSM policy for Session Manager access (if enabled)
resource "aws_iam_role_policy_attachment" "nat_instance_ssm" {
  count      = var.use_nat_instance && var.enable_nat_instance_ssm ? 1 : 0
  role       = aws_iam_role.nat_instance[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Attach CloudWatch policy for monitoring (if enabled)
resource "aws_iam_role_policy_attachment" "nat_instance_cloudwatch" {
  count      = var.use_nat_instance && var.enable_nat_instance_cloudwatch ? 1 : 0
  role       = aws_iam_role.nat_instance[0].name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

# Instance Profile for NAT Instance
resource "aws_iam_instance_profile" "nat_instance" {
  count = var.use_nat_instance ? 1 : 0
  name  = "Training-${var.project_name}-${var.env}-nat-instance-profile"
  role  = aws_iam_role.nat_instance[0].name
}

# --- NAT Instance (cost-effective outbound internet access for private subnets) ---

# fck-nat: Community-maintained, production-ready NAT AMI (ARM64 for Graviton)
# https://github.com/AndrewGuenther/fck-nat
data "aws_ami" "nat_instance" {
  count       = var.use_nat_instance ? 1 : 0
  most_recent = true
  owners      = ["568608671756"] # fck-nat official AWS account

  filter {
    name   = "name"
    values = ["fck-nat-al2023-*-arm64-*"]
  }

  filter {
    name   = "architecture"
    values = ["arm64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Security Group for NAT Instance
resource "aws_security_group" "nat_instance" {
  count       = var.use_nat_instance ? 1 : 0
  name        = "${var.project_name}-${var.env}-nat-instance-sg"
  description = "Security group for NAT Instance - allows traffic from private subnets"
  vpc_id      = aws_vpc.main.id

  # Allow all inbound traffic from private subnets (for NAT forwarding)
  ingress {
    description = "Allow all traffic from private subnets for NAT"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [for subnet in aws_subnet.private : subnet.cidr_block]
  }

  # Allow SSH from specific bastion/VPN CIDRs (if configured)
  dynamic "ingress" {
    for_each = length(var.nat_bastion_allowed_ssh_cidrs) > 0 ? [1] : []
    content {
      description = "Allow SSH from bastion/VPN CIDR blocks"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = var.nat_bastion_allowed_ssh_cidrs
    }
  }

  # Allow all outbound traffic to internet
  egress {
    description = "Allow all outbound traffic to internet"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${var.env}-nat-instance-sg"
  }
}

# Elastic IP for NAT Instance
resource "aws_eip" "nat_instance" {
  count  = var.use_nat_instance ? 1 : 0
  domain = "vpc"
  tags   = { Name = "${var.project_name}-${var.env}-nat-instance-eip" }
}

# NAT Instance (EC2) - using fck-nat AMI (pre-configured, no user-data needed)
resource "aws_instance" "nat_instance" {
  count                       = var.use_nat_instance ? 1 : 0
  ami                         = data.aws_ami.nat_instance[0].id
  instance_type               = var.nat_instance_type
  subnet_id                   = aws_subnet.public[0].id
  vpc_security_group_ids      = [aws_security_group.nat_instance[0].id]
  iam_instance_profile        = aws_iam_instance_profile.nat_instance[0].name
  key_name                    = var.nat_instance_key_name
  associate_public_ip_address = true
  source_dest_check           = false # Critical: allows instance to forward traffic

  # fck-nat AMI is pre-configured with:
  # - IP forwarding enabled
  # - iptables NAT rules configured
  # - Auto-recovery scripts
  # - CloudWatch monitoring integration
  # No user_data needed!

  # IMDSv2 enforcement for security
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  # Encrypted root volume
  root_block_device {
    volume_type           = "gp3"
    volume_size           = 8
    encrypted             = true
    delete_on_termination = true
  }

  tags = {
    Name = "${var.project_name}-${var.env}-nat-instance"
    Role = "NAT"
  }

  # Prevent unintended replacement when new fck-nat AMIs are published
  # Explicit AMI updates can be applied via: terraform apply -replace=aws_instance.nat_instance[0]
  lifecycle {
    ignore_changes = [ami]
  }

  depends_on = [aws_internet_gateway.igw]
}

# Associate EIP with NAT Instance
resource "aws_eip_association" "nat_instance" {
  count         = var.use_nat_instance ? 1 : 0
  instance_id   = aws_instance.nat_instance[0].id
  allocation_id = aws_eip.nat_instance[0].id
}

