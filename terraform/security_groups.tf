resource "aws_security_group" "airflow" {
  name        = "${var.project_name}-airflow-sg"
  description = "Airflow EC2 - egress only, no inbound from internet"
  vpc_id      = aws_vpc.netpulse.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-airflow-sg"
  }
}

resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds-sg"
  description = "RDS PostgreSQL - inbound from Airflow EC2 only"
  vpc_id      = aws_vpc.netpulse.id

  ingress {
    description     = "PostgreSQL from Airflow EC2"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.airflow.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-rds-sg"
  }
}
