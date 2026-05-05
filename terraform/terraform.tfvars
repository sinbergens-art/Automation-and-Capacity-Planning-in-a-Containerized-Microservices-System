# ----- Region & project identity --------
aws_region   = "eu-central-1"
project_name = "sre-shop"
environment  = "dev"

# ----- Compute --------------------------
# t3.medium has enough RAM for the full stack (5 services + DB + monitoring).
# t3.small works but is tight; t2.micro will OOM.
instance_type = "t3.medium"

# ----- SSH access -----------------------
# Name of an existing AWS key pair (created in EC2 console -> Key Pairs).
# Replace with your own key name.
key_name = "sre-shop-key"

# IMPORTANT: tighten this to YOUR public IP for production.
# Find your IP at https://checkip.amazonaws.com  →  e.g. "203.0.113.7/32"
ssh_allowed_cidr = "0.0.0.0/0"

# ----- Networking (defaults usually fine) --
# vpc_cidr    = "10.20.0.0/16"
# subnet_cidr = "10.20.1.0/24"
 