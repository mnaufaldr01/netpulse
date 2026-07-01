output "aws_region" {
  description = "Deployed AWS region"
  value       = var.aws_region
}

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.netpulse.id
}

output "s3_bucket_name" {
  description = "Data lake S3 bucket name"
  value       = aws_s3_bucket.netpulse_lake.id
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint (hostname only)"
  value       = aws_db_instance.netpulse_postgres.address
}

output "rds_port" {
  description = "RDS PostgreSQL port"
  value       = aws_db_instance.netpulse_postgres.port
}

output "ec2_instance_id" {
  description = "Airflow EC2 instance ID"
  value       = aws_instance.airflow_host.id
}

output "ssm_connect_command" {
  description = "Start an SSM shell session on the Airflow host"
  value       = "aws ssm start-session --target ${aws_instance.airflow_host.id} --region ${var.aws_region}"
}

output "ssm_port_forward_airflow" {
  description = "Forward Airflow UI (8080) via SSM"
  value       = "aws ssm start-session --target ${aws_instance.airflow_host.id} --region ${var.aws_region} --document-name AWS-StartPortForwardingSession --parameters portNumber=8080,localPortNumber=8080"
}

output "ssm_port_forward_rds" {
  description = "Forward RDS (5432) via SSM through EC2 bastion"
  value       = "aws ssm start-session --target ${aws_instance.airflow_host.id} --region ${var.aws_region} --document-name AWS-StartPortForwardingSessionToRemoteHost --parameters host=${aws_db_instance.netpulse_postgres.address},portNumber=5432,localPortNumber=15432"
}

output "db_password_ssm_parameter" {
  description = "SSM parameter name for RDS password"
  value       = aws_ssm_parameter.db_password.name
}
