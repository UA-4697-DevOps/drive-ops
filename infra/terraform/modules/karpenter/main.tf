locals {
  karpenter_namespace = "kube-system"
  karpenter_sa_name   = "karpenter"
  interruption_queue  = "Training-${var.project_name}-${var.env}-karpenter"
}

data "aws_iam_policy_document" "karpenter_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:sub"
      values   = ["system:serviceaccount:${local.karpenter_namespace}:${local.karpenter_sa_name}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "karpenter_controller" {
  statement {
    sid    = "EC2InstanceManagement"
    effect = "Allow"
    actions = [
      "ec2:RunInstances",
      "ec2:CreateFleet",
      "ec2:CreateLaunchTemplate",
      "ec2:DeleteLaunchTemplate",
      "ec2:DescribeLaunchTemplates",
      "ec2:DescribeInstances",
      "ec2:DescribeInstanceTypes",
      "ec2:DescribeInstanceTypeOfferings",
      "ec2:DescribeAvailabilityZones",
      "ec2:DescribeImages",
      "ec2:DescribeSpotPriceHistory",
      "ec2:DescribeSecurityGroups",
      "ec2:DescribeSubnets",
      "ec2:TerminateInstances",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "EC2Tagging"
    effect    = "Allow"
    actions   = ["ec2:CreateTags"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "ec2:CreateAction"
      values   = ["RunInstances", "CreateFleet", "CreateLaunchTemplate"]
    }
  }

  statement {
    sid       = "IAMPassRole"
    effect    = "Allow"
    actions   = ["iam:PassRole"]
    resources = [var.node_role_arn]
  }

  statement {
    sid    = "IAMInstanceProfile"
    effect = "Allow"
    actions = [
      "iam:GetInstanceProfile",
      "iam:CreateInstanceProfile",
      "iam:TagInstanceProfile",
      "iam:AddRoleToInstanceProfile",
      "iam:RemoveRoleFromInstanceProfile",
      "iam:DeleteInstanceProfile",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "SSMGetParameter"
    effect    = "Allow"
    actions   = ["ssm:GetParameter"]
    resources = ["arn:aws:ssm:${var.aws_region}::parameter/aws/service/*"]
  }

  statement {
    sid       = "EKSClusterAccess"
    effect    = "Allow"
    actions   = ["eks:DescribeCluster"]
    resources = ["arn:aws:eks:${var.aws_region}:${var.account_id}:cluster/${var.cluster_name}"]
  }

  statement {
    sid    = "SQSInterruption"
    effect = "Allow"
    actions = [
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl",
      "sqs:ReceiveMessage",
    ]
    resources = [aws_sqs_queue.interruption.arn]
  }

  statement {
    sid       = "PricingAccess"
    effect    = "Allow"
    actions   = ["pricing:GetProducts"]
    resources = ["*"]
  }
}

module "karpenter_irsa" {
  source = "../iam-role"

  role_name            = "Training-${var.project_name}-${var.env}-karpenter-role"
  assume_role_policy   = data.aws_iam_policy_document.karpenter_assume_role.json
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"
  custom_policies = {
    "Training-${var.project_name}-${var.env}-karpenter-policy" = data.aws_iam_policy_document.karpenter_controller.json
  }
  custom_policies_descriptions = {
    "Training-${var.project_name}-${var.env}-karpenter-policy" = "IAM policy for Karpenter node autoscaler"
  }
  managed_policy_arns = []

  tags = var.tags
}

resource "aws_sqs_queue" "interruption" {
  name                      = local.interruption_queue
  message_retention_seconds = 300
  sqs_managed_sse_enabled   = true

  tags = merge(var.tags, {
    Name      = local.interruption_queue
    Component = "karpenter-interruption"
  })
}

resource "aws_sqs_queue_policy" "interruption" {
  queue_url = aws_sqs_queue.interruption.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowEventBridgePublish"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.interruption.arn
      }
    ]
  })
}

resource "aws_cloudwatch_event_rule" "spot_interruption" {
  name        = "Training-${var.project_name}-${var.env}-karpenter-spot-interruption"
  description = "Karpenter: EC2 Spot Instance Interruption Warning"

  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["EC2 Spot Instance Interruption Warning"]
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "spot_interruption" {
  rule      = aws_cloudwatch_event_rule.spot_interruption.name
  target_id = "KarpenterInterruptionQueue"
  arn       = aws_sqs_queue.interruption.arn
}

resource "aws_cloudwatch_event_rule" "instance_rebalance" {
  name        = "Training-${var.project_name}-${var.env}-karpenter-rebalance"
  description = "Karpenter: EC2 Instance Rebalance Recommendation"

  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["EC2 Instance Rebalance Recommendation"]
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "instance_rebalance" {
  rule      = aws_cloudwatch_event_rule.instance_rebalance.name
  target_id = "KarpenterInterruptionQueue"
  arn       = aws_sqs_queue.interruption.arn
}

resource "aws_cloudwatch_event_rule" "instance_state_change" {
  name        = "Training-${var.project_name}-${var.env}-karpenter-state-change"
  description = "Karpenter: EC2 Instance State-change Notification"

  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["EC2 Instance State-change Notification"]
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "instance_state_change" {
  rule      = aws_cloudwatch_event_rule.instance_state_change.name
  target_id = "KarpenterInterruptionQueue"
  arn       = aws_sqs_queue.interruption.arn
}


resource "helm_release" "karpenter" {
  name       = "karpenter"
  repository = "oci://public.ecr.aws/karpenter"
  chart      = "karpenter"
  version    = var.karpenter_version
  namespace  = local.karpenter_namespace

  values = [
    yamlencode({
      settings = {
        clusterName       = var.cluster_name
        interruptionQueue = aws_sqs_queue.interruption.name
      }
      serviceAccount = {
        annotations = {
          "eks.amazonaws.com/role-arn" = module.karpenter_irsa.iam_role_arn
        }
      }
      controller = {
        resources = {
          requests = { cpu = "100m", memory = "256Mi" }
          limits   = { cpu = "500m", memory = "512Mi" }
        }
      }
      affinity = {
        nodeAffinity = {
          requiredDuringSchedulingIgnoredDuringExecution = {
            nodeSelectorTerms = [
              {
                matchExpressions = [
                  {
                    key      = "karpenter.sh/nodepool"
                    operator = "DoesNotExist"
                  }
                ]
              }
            ]
          }
        }
      }
    })
  ]

  depends_on = [module.karpenter_irsa]
}