resource "aws_iam_role" "airflow" {
  name = "${var.project_name}-airflow-role"

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

  tags = {
    Name = "${var.project_name}-airflow-role"
  }
}

resource "aws_iam_role_policy_attachment" "ssm_managed" {
  role       = aws_iam_role.airflow.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "s3_readwrite" {
  statement {
    sid    = "LakeBucketAccess"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetBucketLocation",
      "s3:HeadBucket",
      "s3:CreateBucket",
    ]

    resources = [
      aws_s3_bucket.netpulse_lake.arn,
      "${aws_s3_bucket.netpulse_lake.arn}/*",
    ]
  }
}

resource "aws_iam_role_policy" "s3_readwrite" {
  name   = "${var.project_name}-s3-readwrite"
  role   = aws_iam_role.airflow.id
  policy = data.aws_iam_policy_document.s3_readwrite.json
}

data "aws_iam_policy_document" "ssm_parameter_read" {
  statement {
    sid    = "ReadNetpulseParameters"
    effect = "Allow"

    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
    ]

    resources = [
      aws_ssm_parameter.db_password.arn,
      aws_ssm_parameter.opencellid_api_key.arn,
    ]
  }

  statement {
    sid    = "DecryptSecureStrings"
    effect = "Allow"

    actions = [
      "kms:Decrypt",
    ]

    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${var.aws_region}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "ssm_parameter_read" {
  name   = "${var.project_name}-ssm-parameter-read"
  role   = aws_iam_role.airflow.id
  policy = data.aws_iam_policy_document.ssm_parameter_read.json
}

resource "aws_iam_instance_profile" "airflow" {
  name = "${var.project_name}-airflow-profile"
  role = aws_iam_role.airflow.name
}
