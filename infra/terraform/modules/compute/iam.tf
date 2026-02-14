data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2_ssm_role" {
  name                 = "${var.name}-ec2-role"
  assume_role_policy   = data.aws_iam_policy_document.ec2_assume_role.json
  permissions_boundary = local.permissions_boundary
  tags                 = var.tags
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.name}-profile"
  role = aws_iam_role.ec2_ssm_role.name
  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "ssm_managed_instance" {
  role       = aws_iam_role.ec2_ssm_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_policy" "ecr_pull" {
  count       = var.ecr_repository_url != null ? 1 : 0
  name        = "${var.name}-ecr-pull"
  description = "Allow EC2 to pull images from ECR"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      }
    ]
  })
  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "ecr_pull" {
  count      = var.ecr_repository_url != null ? 1 : 0
  role       = aws_iam_role.ec2_ssm_role.name
  policy_arn = aws_iam_policy.ecr_pull[0].arn
}

# State migration: client-gateway had these resources without count index
moved {
  from = aws_iam_policy.ecr_pull
  to   = aws_iam_policy.ecr_pull[0]
}

moved {
  from = aws_iam_role_policy_attachment.ecr_pull
  to   = aws_iam_role_policy_attachment.ecr_pull[0]
}
