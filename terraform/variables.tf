variable "aws_region" {
  type        = string
  default     = "ap-southeast-2"
  description = "AWS region for all resources. Change to ap-southeast-1 when relocating."
}

variable "project_name" {
  type    = string
  default = "netpulse"
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "public_subnet_cidr" {
  type    = string
  default = "10.0.1.0/24"
}

variable "private_subnet_a_cidr" {
  type    = string
  default = "10.0.2.0/24"
}

variable "private_subnet_b_cidr" {
  type    = string
  default = "10.0.3.0/24"
}

variable "ec2_instance_type" {
  type    = string
  default = "t3.small"
}

variable "rds_instance_class" {
  type    = string
  default = "db.t3.micro"
}

variable "rds_allocated_storage" {
  type    = number
  default = 20
}

variable "db_name" {
  type    = string
  default = "netpulse"
}

variable "db_username" {
  type    = string
  default = "netpulse"
}

variable "opencellid_api_key" {
  type        = string
  sensitive   = true
  description = "OpenCelliD API access token (pk.xxx). Pass at apply: -var=opencellid_api_key=..."
}

variable "git_repo_url" {
  type        = string
  default     = ""
  description = "Optional git URL to clone netpulse onto EC2 at bootstrap (e.g. https://github.com/you/netpulse.git)"
}

variable "tags" {
  type = map(string)
  default = {
    Project = "netpulse"
    Stage   = "phase2"
  }
}
