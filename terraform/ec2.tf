locals {
  bootstrap_script = templatefile("${path.module}/../scripts/ec2_bootstrap.sh", {
    aws_region      = var.aws_region
    rds_endpoint    = aws_db_instance.netpulse_postgres.address
    s3_bucket       = aws_s3_bucket.netpulse_lake.id
    db_name         = var.db_name
    db_username     = var.db_username
    db_password_ssm = aws_ssm_parameter.db_password.name
    project_root    = "/opt/netpulse"
    git_repo_url    = var.git_repo_url
  })
}

resource "aws_instance" "airflow_host" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = var.ec2_instance_type
  subnet_id              = aws_subnet.private_a.id
  vpc_security_group_ids = [aws_security_group.airflow.id]
  iam_instance_profile   = aws_iam_instance_profile.airflow.name
  associate_public_ip_address = false

  user_data = base64encode(local.bootstrap_script)

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  tags = {
    Name = "${var.project_name}-airflow"
  }

  depends_on = [
    aws_nat_gateway.nat,
    aws_db_instance.netpulse_postgres,
    aws_ssm_parameter.db_password,
  ]
}
