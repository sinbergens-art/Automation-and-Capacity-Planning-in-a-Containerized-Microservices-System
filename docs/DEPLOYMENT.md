# Deployment Guide — SRE Shop

Two supported targets:

* **Local** — Docker Compose on your laptop (everything runs on `localhost`).
* **Cloud** — AWS EC2 provisioned by Terraform (Assignment 5).


## 1. Local deployment

### 1.1 Prerequisites

| Tool          | Version                    |
|---------------|----------------------------|
| Docker Desktop| ≥ 4.30 (Compose V2 bundled)|
| 4 GB free RAM | for the 9 containers       |
| 5 GB free disk| for images + volumes       |

### 1.2 Steps

```bash
git clone <this-repo>
cd sre-microservices

# (optional) review / edit .env
cat .env

# Build the application images (microservices + frontend)
docker compose build

# Start everything in the background
docker compose up -d

# Watch the stack come up - all services should turn (healthy)
docker compose ps
```

### 1.3 First-time DB initialisation

Each service runs its own `init_db()` on startup; tables are created idempotently with `CREATE TABLE IF NOT EXISTS`. Postgres data is persisted in the `pgdata` volume so subsequent restarts re-use it.

### 1.4 Access points

| What        | URL                                      |
|-------------|------------------------------------------|
| Frontend    | http://localhost                         |
| Auth API    | http://localhost:8001                    |
| Product API | http://localhost:8002                    |
| Order API   | http://localhost:8003                    |
| User API    | http://localhost:8004                    |
| Chat API    | http://localhost:8005                    |
| Prometheus  | http://localhost:9090                    |
| Grafana     | http://localhost:3001  *(admin / admin)* |

### 1.5 Validate

```bash
# All metrics endpoints respond
for p in 8001 8002 8003 8004 8005; do
  curl -s http://localhost:$p/health
  echo
done

# Prometheus has all 5 targets UP
open http://localhost:9090/targets

# Grafana dashboard is provisioned automatically
open http://localhost:3001/d/sre-shop-overview
```

### 1.6 Stop / clean up

```bash
docker compose stop          # stop containers, keep state
docker compose down          # remove containers, keep volumes
docker compose down -v       # full wipe (data loss!)
docker system prune -f       # reclaim image disk space
```

---

## 2. Cloud deployment (AWS via Terraform)

Maps directly to the **Assignment 5 § 6.2** requirements: a single EC2 host with a security group exposing the four required ports.

### 2.1 Prerequisites

| Tool         | Version                  | Why         |
|--------------|--------------------------|-------------|
| Terraform    | ≥ 1.5                    | apply IaC   |
| AWS CLI      | ≥ 2                      | credentials |
| AWS account  | any                      | target      |
| EC2 key pair | created in target region | SSH access  |

### 2.2 One-time setup

1. **Create an EC2 Key Pair** in the AWS Console (`EC2 → Key Pairs → Create`). Download the `.pem` file:

   ```bash
   mv ~/Downloads/sre-shop-key.pem ~/.ssh/
   chmod 400 ~/.ssh/sre-shop-key.pem
   ```

2. **Create an IAM user** with `AdministratorAccess` (demo) and an Access Key, then:

   ```bash
   aws configure
   # AWS Access Key ID:     AKIA...
   # AWS Secret Access Key: ...
   # Default region:        eu-central-1
   ```

3. **Edit `terraform/terraform.tfvars`** with your key name and (optionally) tighten `ssh_allowed_cidr` to your IP `/32`.

### 2.3 Provision the infrastructure

```bash
cd terraform

terraform init                    # download AWS provider
terraform validate                # syntactic + semantic check
terraform fmt -check              # style check
terraform plan -out=tfplan        # preview what will change
terraform apply tfplan            # create the resources (~3 min)
```

When `apply` completes, Terraform prints the outputs:

```
app_url        = "http://3.65.45.21"
grafana_url    = "http://3.65.45.21:3000"
prometheus_url = "http://3.65.45.21:9090"
public_ip      = "3.65.45.21"
ssh_command    = "ssh -i ~/.ssh/sre-shop-key.pem ubuntu@3.65.45.21"
```

### 2.4 Deploy the application onto the new instance

```bash
PUB_IP=$(terraform output -raw public_ip)

# Wait until cloud-init finished installing Docker
ssh -i ~/.ssh/sre-shop-key.pem ubuntu@$PUB_IP \
    'until [ -f /etc/sre-shop-ready ]; do sleep 5; done; echo READY'

# Push the project tree to the host
rsync -avz \
  --exclude .git \
  --exclude terraform/.terraform \
  --exclude '**/__pycache__' \
  ../ ubuntu@$PUB_IP:/home/ubuntu/sre-microservices/

# Bring it up
ssh -i ~/.ssh/sre-shop-key.pem ubuntu@$PUB_IP \
    'cd sre-microservices && docker compose up -d && docker compose ps'
```

### 2.5 Validate

```bash
curl -s http://$PUB_IP/         | head -c 80
curl -s http://$PUB_IP:9090/-/healthy
curl -s http://$PUB_IP:3000/api/health
```

Then open `http://<public_ip>` in a browser.

### 2.6 Tear down

```bash
cd terraform
terraform destroy
```

`destroy` removes the EC2, security group, subnet, IGW, route table and VPC — leaving no AWS spend.


## 3. Troubleshooting

| Symptom                                | Likely cause                      | Fix                                        |
|----------------------------------------|-------------------------------|------------------------------------------------|
| `docker compose ps` shows `Restarting` | service crashed at startup    | `docker compose logs <svc> --tail 50`          |
| Frontend says `HTTP 500/502`           | downstream service unhealthy  | check that service's logs                      |
| Prometheus target `DOWN`           | service crashed or wrong scrape URL | check `monitoring/prometheus/prometheus.yml` |
| Grafana shows `No data`           | no traffic yet, or scrape interval not elapsed | wait 30 s after generating traffic |
| `terraform apply` errors with `UnauthorizedOperation` | IAM user missing rights | attach `AdministratorAccess` (demo) |
| Port 80 / 3000 already in use locally  | other app holds the port        | `lsof -i :PORT` then change mapping in `docker-compose.yml` |

## 4. Operations cheatsheet

```bash
# Tail logs of one service
docker compose logs -f order-service

# Restart a single service
docker compose restart order-service

# Run an ad-hoc psql against the DB
docker compose exec postgres psql -U appuser -d appdb

# Rebuild only one service (after editing its code)
docker compose build order-service && docker compose up -d order-service

# Force fresh build (no cache)
docker compose build --no-cache
```
