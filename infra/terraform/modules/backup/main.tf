# ------------------------------------------------------------------------------
# S3 BUCKET FOR BACKUPS
# ------------------------------------------------------------------------------
resource "aws_s3_bucket" "db_backups" {
  bucket = "${var.project_name}-db-backups-${var.env}"
}

# Fix 1: Add CMK-backed Server-Side Encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "db_backups_crypto" {
  bucket = aws_s3_bucket.db_backups.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = var.backup_kms_key_arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "db_backups" {
  bucket                  = aws_s3_bucket.db_backups.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "db_backups_lifecycle" {
  bucket = aws_s3_bucket.db_backups.id

  rule {
    id     = "archive-and-prune"
    status = "Enabled"

    # NEW: Automatically delete failed upload chunks after 7 days
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    expiration {
      days = 90
    }
  }
}

# ------------------------------------------------------------------------------
# IAM ROLE FOR EKS SERVICE ACCOUNT (IRSA)
# ------------------------------------------------------------------------------
data "aws_iam_policy_document" "eks_assume_role" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"

    principals {
      type        = "Federated"
      identifiers = [var.eks_oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(var.eks_oidc_provider_url, "https://", "")}:sub"
      values   = ["system:serviceaccount:${var.k8s_namespace}:${var.k8s_service_account_name}"]
    }

    # Fix 2: Add aud condition to restrict token acceptance to AWS STS
    condition {
      test     = "StringEquals"
      variable = "${replace(var.eks_oidc_provider_url, "https://", "")}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

module "backup_iam_role" {
  source = "../iam-role"

  role_name            = "${var.project_name}-backup-role-${var.env}"
  assume_role_policy   = data.aws_iam_policy_document.eks_assume_role.json
  permissions_boundary = var.permissions_boundary
  tags                 = var.tags

  # Создаем управляемую политику для S3 и KMS доступа
  custom_policies = {
    "${var.project_name}-backup-s3-access-${var.env}" = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Action = [
            "s3:PutObject",
            "s3:ListBucket"
          ]
          Effect = "Allow"
          Resource = [
            aws_s3_bucket.db_backups.arn,
            "${aws_s3_bucket.db_backups.arn}/*"
          ]
        },
        {
          # NEW: Allow the role to request a Data Key for encryption
          Action = [
            "kms:GenerateDataKey"
          ]
          Effect = "Allow"
          Resource = [
            var.backup_kms_key_arn
          ]
        }
      ]
    })
  }

  custom_policies_descriptions = {
    "${var.project_name}-backup-s3-access-${var.env}" = "Allow backup process to upload to S3 and encrypt with KMS"
  }
}
