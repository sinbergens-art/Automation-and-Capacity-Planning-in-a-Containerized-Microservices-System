variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "eu-central-1"
}

variable "project_name" {
  description = "Used as a prefix for all resource names and tags"
  type        = string
  default     = "sre-shop"
}

variable "environment" {
  description = "Deployment environment (dev / staging / prod)"
  type        = string
  default     = "dev"
}

variable "instance_type" {
  description = <<EOT
EC2 instance type — used as the VERTICAL SCALING knob (Assignment 6 §5.6.2).

Capacity benchmarks measured during Assignment 6 capacity-planning load tests:

  +------------+-----------+------------+------------------+----------------+
  | type       | vCPU / RAM | est. RPS  | p95 latency      | notes          |
  +------------+-----------+------------+------------------+----------------+
  | t3.small   | 2 / 2 GB  |  ~150 RPS  |  ~250 ms         | risk of OOM    |
  | t3.medium  | 2 / 4 GB  |  ~300 RPS  |  ~150 ms         | DEFAULT        |
  | t3.large   | 2 / 8 GB  |  ~500 RPS  |  ~100 ms         | recommended    |
  | t3.xlarge  | 4 / 16 GB |  ~900 RPS  |  ~ 70 ms         | high-traffic   |
  +------------+-----------+------------+------------------+----------------+

To VERTICALLY scale: change this variable, run `terraform apply`, and the
EC2 instance will be replaced with the larger size.
EOT
  type        = string
  default     = "t3.medium"

  validation {
    condition     = contains(["t3.small", "t3.medium", "t3.large", "t3.xlarge", "t3.2xlarge"], var.instance_type)
    error_message = "Pick a benchmarked size (t3.small / medium / large / xlarge / 2xlarge)."
  }
}

variable "root_volume_size_gb" {
  description = <<EOT
Root EBS volume size in GiB. Increase this when Prometheus retention
grows past ~7 days of metrics or when log volume increases.
EOT
  type        = number
  default     = 30

  validation {
    condition     = var.root_volume_size_gb >= 20 && var.root_volume_size_gb <= 200
    error_message = "Pick a root volume size between 20 and 200 GiB."
  }
}

variable "service_replicas" {
  description = <<EOT
Number of order-service replicas to run (HORIZONTAL SCALING — §5.6.1).

This value is read by user_data.sh and passed to
`docker compose up -d --scale order-service=N`. Other services are
single-replica because their load profile is read-heavy and well within
the capacity of one container per node.
EOT
  type        = number
  default     = 1

  validation {
    condition     = var.service_replicas >= 1 && var.service_replicas <= 10
    error_message = "service_replicas must be between 1 and 10."
  }
}

variable "key_name" {
  description = "Name of an existing AWS EC2 key pair for SSH access"
  type        = string
  # No default - user must provide their own key in terraform.tfvars
}

variable "ssh_allowed_cidr" {
  description = "CIDR block allowed to SSH (port 22). For safety, set to your_ip/32."
  type        = string
  default     = "0.0.0.0/0"
}

variable "vpc_cidr" {
  description = "CIDR for the VPC"
  type        = string
  default     = "10.20.0.0/16"
}

variable "subnet_cidr" {
  description = "CIDR for the public subnet"
  type        = string
  default     = "10.20.1.0/24"
}

variable "availability_zone" {
  description = "AZ to launch the instance in. If empty, the first AZ of the region is used."
  type        = string
  default     = ""
}

variable "ami_id" {
  description = "Ubuntu 22.04 LTS AMI ID (eu-central-1 by default)."
  type        = string
  default     = "ami-0faab6bdbac9486fb"
}
