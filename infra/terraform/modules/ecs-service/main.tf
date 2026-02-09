resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-${var.env}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.env}-cluster"
  })
}

resource "aws_cloudwatch_log_group" "service" {
  name              = "/ecs/${var.project_name}-${var.env}/${var.service_name}"
  retention_in_days = 7

  tags = merge(var.tags, {
    Name = "${var.service_name}-logs"
  })
}

resource "aws_iam_role" "ecs_task_execution" {
  name                 = "${var.project_name}-${var.env}-${var.service_name}-exec-role"
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_policy" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_policy" "secrets_access" {
  count = length(var.secrets_arns) > 0 ? 1 : 0

  name        = "${var.project_name}-${var.env}-${var.service_name}-secrets-policy"
  description = "Allow ECS tasks to read secrets"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ]
      Resource = var.secrets_arns
    }]
  })
}

resource "aws_iam_role_policy_attachment" "secrets_access" {
  count = length(var.secrets_arns) > 0 ? 1 : 0

  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = aws_iam_policy.secrets_access[0].arn
}

resource "aws_iam_role" "ecs_task" {
  name                 = "${var.project_name}-${var.env}-${var.service_name}-task-role"
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })

  tags = var.tags
}

resource "aws_iam_policy" "sqs_access" {
  count = length(var.sqs_queue_arns) > 0 ? 1 : 0

  name        = "${var.project_name}-${var.env}-${var.service_name}-sqs-policy"
  description = "Allow ECS tasks to access SQS queues"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes",
        "sqs:GetQueueUrl"
      ]
      Resource = var.sqs_queue_arns
    }]
  })
}

resource "aws_iam_role_policy_attachment" "sqs_access" {
  count = length(var.sqs_queue_arns) > 0 ? 1 : 0

  role       = aws_iam_role.ecs_task.name
  policy_arn = aws_iam_policy.sqs_access[0].arn
}

resource "aws_ecs_task_definition" "service" {
  family                   = "${var.project_name}-${var.env}-${var.service_name}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.container_cpu
  memory                   = var.container_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name  = var.service_name
    image = "${var.ecr_repository_url}:${var.image_tag}"

    portMappings = [{
      containerPort = var.container_port
      protocol      = "tcp"
    }]

    environment = [
      for key, value in var.environment_variables : {
        name  = key
        value = value
      }
    ]

    secrets = [
      for key, secret in var.secrets : {
        name      = key
        valueFrom = secret.valueFrom
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.service.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }

    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:${var.container_port}${var.health_check_path} || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  }])

  tags = var.tags
}

resource "aws_ecs_service" "main" {
  name            = "${var.project_name}-${var.env}-${var.service_name}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.service.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.security_group_id]
    assign_public_ip = false
  }

  tags = var.tags
}
