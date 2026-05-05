# Terraform — SRE Shop infrastructure (Assignment 5)

This directory provisions the cloud infrastructure for the SRE Shop microservices stack on AWS.

## What it creates

| Resource              | Purpose                                                         |
|-----------------------|-----------------------------------------------------------------|
| `aws_vpc`             | Isolated VPC `10.20.0.0/16`                                     |
| `aws_internet_gateway`| Internet egress                                                 |
| `aws_subnet` (public) | `10.20.1.0/24`, auto-assigns public IPs                         |
| `aws_route_table`     | Routes `0.0.0.0/0` through the IGW                              |
| `aws_security_group`  | Opens ports **80, 3000, 9090, 22**                              |
| `aws_instance`        | Ubuntu 22.04, `t3.medium`, runs cloud-init to install Docker    |

## Prerequisites

1. Terraform ≥ 1.5
2. AWS CLI configured (`aws configure`) **OR** the env vars
   `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_DEFAULT_REGION`.
3. An EC2 key pair created in the target region — copy its name into `terraform.tfvars`.

## Usage

```bash
cd terraform

# 1. Edit terraform.tfvars - set key_name, region, ssh_allowed_cidr
nano terraform.tfvars

# 2. Init: download AWS provider
terraform init

# 3. Plan: preview the change set
terraform plan -out=tfplan

# 4. Apply: create the resources
terraform apply tfplan

# 5. Get the public IP (and other outputs)
terraform output
```

When `apply` completes you'll see something like:

```
app_url        = "http://3.65.45.21"
grafana_url    = "http://3.65.45.21:3000"
prometheus_url = "http://3.65.45.21:9090"
public_ip      = "3.65.45.21"
ssh_command    = "ssh -i ~/.ssh/sre-shop-key.pem ubuntu@3.65.45.21"
```

## Deploy the application onto the new EC2

```bash
# wait until cloud-init finished installing Docker
ssh -i ~/.ssh/sre-shop-key.pem ubuntu@$(terraform output -raw public_ip) \
    'until [ -f /etc/sre-shop-ready ]; do sleep 5; done; echo READY'

# copy the project tree to the instance
rsync -avz --exclude .git --exclude terraform/.terraform \
    .. ubuntu@$(terraform output -raw public_ip):/home/ubuntu/sre-microservices/

# bring it up
ssh -i ~/.ssh/sre-shop-key.pem ubuntu@$(terraform output -raw public_ip) \
    'cd sre-microservices && docker compose up -d'
```

Then open:

* `http://<public_ip>`         → SRE Shop frontend
* `http://<public_ip>:9090`    → Prometheus
* `http://<public_ip>:3000`    → Grafana (admin / admin)

## Tear down

```bash
terraform destroy
```

## Cost estimate

| Item               | Approx (eu-central-1) |
|--------------------|-----------------------|
| `t3.medium` 24/7   | ~$30 / month          |
| 20 GB gp3 volume   | ~$1.6 / month         |
| Data transfer (low)| ~$0–2 / month         |

`terraform destroy` whenever the stack is not needed.

## Maps to assignment requirements

| Requirement (§ 6.2)                   | File                                    |
|---------------------------------------|-----------------------------------------|
| 1. Provision a VM                     | `main.tf` → `aws_instance.app`          |
| 2. Network rules (80, 3000, 9090, 22) | `main.tf` → `aws_security_group.app`    |
| 3. Output public IP                   | `outputs.tf` → `public_ip`              |
| 4. init / plan / apply reproducibility| All `.tf` files; pinned in `versions.tf`|
