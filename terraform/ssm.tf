resource "random_password" "db_password" {
  length  = 32
  special = false
}

resource "aws_ssm_parameter" "db_password" {
  name        = "/${var.project_name}/db_password"
  description = "RDS PostgreSQL password for netpulse"
  type        = "SecureString"
  value       = random_password.db_password.result
}
