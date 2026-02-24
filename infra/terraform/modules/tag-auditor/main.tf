# Package Lambda Code
data "archive_file" "tag_auditor_zip" {
  type        = "zip"
  source_file = "${path.module}/tag_auditor.py"
  output_path = "${path.module}/tag_auditor.zip"
}

resource "aws_lambda_function" "tag_auditor" {
  filename         = data.archive_file.tag_auditor_zip.output_path
  function_name    = "${var.project_name}-${var.env}-tag-auditor"
  role             = aws_iam_role.tag_auditor_exec.arn
  handler          = "tag_auditor.lambda_handler"
  runtime          = "python3.12"
  timeout          = 60
  memory_size      = 128
  source_code_hash = data.archive_file.tag_auditor_zip.output_base64sha256

  environment {
    variables = {
      SNS_TOPIC_ARN = var.sns_topic_arn
    }
  }

  tags = { Name = "${var.project_name}-${var.env}-tag-auditor" }
}

# IAM Role 
resource "aws_iam_role" "tag_auditor_exec" {
  name                 = "Training-${var.project_name}-${var.env}-lambda-tag-auditor-role"
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.tag_auditor_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "tag_auditor_policy" {
  name = "Training-${var.project_name}-${var.env}-tag-auditor-policy"
  role = aws_iam_role.tag_auditor_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "tag:GetResources",
          "tag:GetTagKeys",
          "tag:GetTagValues"
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = [var.sns_topic_arn]
      }
    ]
  })
}


resource "aws_cloudwatch_event_rule" "daily_audit" {
  name                = "${var.project_name}-${var.env}-tag-auditor-schedule"
  description         = "Triggers the tag auditor Lambda once per day"
  schedule_expression = "rate(24 hours)"

  tags = { Name = "${var.project_name}-${var.env}-tag-auditor-schedule" }
}

resource "aws_cloudwatch_event_target" "tag_auditor_target" {
  rule      = aws_cloudwatch_event_rule.daily_audit.name
  target_id = "TagAuditorLambda"
  arn       = aws_lambda_function.tag_auditor.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.tag_auditor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_audit.arn
}

resource "aws_cloudwatch_log_group" "tag_auditor_logs" {
  name              = "/aws/lambda/${aws_lambda_function.tag_auditor.function_name}"
  retention_in_days = 3

  tags = { Name = "${var.project_name}-${var.env}-tag-auditor-logs" }
}
