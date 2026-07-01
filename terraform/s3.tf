resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "netpulse_lake" {
  bucket = "${var.project_name}-lake-${random_id.bucket_suffix.hex}"

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name = "${var.project_name}-lake"
  }
}

resource "aws_s3_bucket_versioning" "netpulse_lake" {
  bucket = aws_s3_bucket.netpulse_lake.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "netpulse_lake" {
  bucket = aws_s3_bucket.netpulse_lake.id

  rule {
    id     = "raw-staging-to-ia"
    status = "Enabled"

    filter {
      prefix = ""
    }

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "netpulse_lake" {
  bucket = aws_s3_bucket.netpulse_lake.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

data "aws_iam_policy_document" "s3_vpc_endpoint_only" {
  statement {
    sid    = "AllowVpcEndpointAccess"
    effect = "Allow"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]

    resources = [
      aws_s3_bucket.netpulse_lake.arn,
      "${aws_s3_bucket.netpulse_lake.arn}/*",
    ]

    condition {
      test     = "StringEquals"
      variable = "aws:SourceVpce"
      values   = [aws_vpc_endpoint.s3.id]
    }
  }

  statement {
    sid    = "AllowAirflowRoleFullAccess"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = [aws_iam_role.airflow.arn]
    }

    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]

    resources = [
      aws_s3_bucket.netpulse_lake.arn,
      "${aws_s3_bucket.netpulse_lake.arn}/*",
    ]
  }
}

resource "aws_s3_bucket_policy" "netpulse_lake" {
  bucket = aws_s3_bucket.netpulse_lake.id
  policy = data.aws_iam_policy_document.s3_vpc_endpoint_only.json
}
