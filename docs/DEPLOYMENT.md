# Deployment Guide

Production deployment guide for Saliksik AI using Python, uv, systemd, PostgreSQL, Redis, and Nginx.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Server Preparation](#server-preparation)
- [Application Setup](#application-setup)
- [Environment Configuration](#environment-configuration)
- [PostgreSQL Setup](#postgresql-setup)
- [Database Migrations](#database-migrations)
- [Systemd Services](#systemd-services)
- [Nginx Configuration](#nginx-configuration)
- [SSL/TLS Setup](#ssltls-setup)
- [Monitoring](#monitoring)
- [Backup Strategy](#backup-strategy)
- [Troubleshooting](#troubleshooting)
- [Production Checklist](#production-checklist)

---

## Prerequisites

### System Requirements

**Minimum:**
- 2 CPU cores
- 4GB RAM
- 20GB storage
- Ubuntu 20.04+ / Debian 11+ / CentOS 8+

**Recommended:**
- 4 CPU cores
- 8GB RAM
- 50GB SSD storage
- Ubuntu 22.04 LTS

### Software Requirements

- Linux server with `systemd`
- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- PostgreSQL 15+
- Redis 7+
- Nginx 1.24+ (optional, for reverse proxy and TLS)
- Git

> Redis is required for the Celery task queue. The cache layer also uses Redis but falls back to an in-memory cache when `REDIS_URL` is not set.

---

## Server Preparation

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y postgresql redis-server nginx git curl

# Start and enable services
sudo systemctl enable --now postgresql redis-server
```

### Create Application User

```bash
sudo useradd --create-home --shell /bin/bash saliksik
sudo su - saliksik
```

---

## Application Setup

Run the remaining commands as the `saliksik` user.

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
```

The installer normally adds `$HOME/.local/bin` to your shell profile. Verify with:

```bash
uv --version
```

### 2. Clone and Install

```bash
git clone https://github.com/leodyversemilla07/saliksik-ai.git
cd saliksik-ai

# Install the project's Python version and locked dependencies
uv python install 3.12
uv sync --frozen

# Download NLP models
uv run python -m spacy download en_core_web_sm
uv run python -c "import nltk; nltk.download('punkt')"
```

---

## Environment Configuration

### 1. Create the Environment File

```bash
cd /home/saliksik/saliksik-ai
cp .env.example .env
chmod 600 .env
```

### 2. Configure Production Values

Edit `.env`:

```bash
# Application
DEBUG=False
SECRET_KEY=<generate-a-strong-random-key>

# Comma-separated list of allowed frontend origins
ALLOWED_ORIGINS=https://your-domain.com,https://app.your-domain.com

# Database (async driver required)
DATABASE_URL=postgresql+asyncpg://saliksik_user:secure_password@localhost:5432/saliksik_ai_prod

# Redis cache (database 0)
REDIS_URL=redis://localhost:6379/0

# Celery broker and result backend (database 1)
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Uploads and rate limits
MAX_FILE_SIZE_MB=10
RATE_LIMIT_ANON=60/hour
RATE_LIMIT_USER=100/hour
```

Notes:

- `DATABASE_URL` must use `postgresql+asyncpg://` because the API uses an async SQLAlchemy engine. The sync URL used by Celery and Alembic is derived automatically.
- Set `SMTP_*` values if you want email verification messages delivered.
- Keep `.env` readable only by the application user (`chmod 600 .env`).

### 3. Generate a Secret Key

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy the output into `SECRET_KEY`. It must be at least 32 characters.

> The systemd services read `.env` with `EnvironmentFile=`, so use one `KEY=value` pair per line and avoid inline comments after values.

---

## PostgreSQL Setup

Create the production database and user:

```bash
sudo -u postgres psql <<'SQL'
CREATE USER saliksik_user WITH PASSWORD 'secure_password';
CREATE DATABASE saliksik_ai_prod OWNER saliksik_user;
SQL
```

Replace `secure_password` with a strong password, and use the same password in `DATABASE_URL`.

Verify the connection:

```bash
psql "postgresql://saliksik_user:secure_password@localhost:5432/saliksik_ai_prod" -c "SELECT 1;"
```

---

## Database Migrations

Apply the Alembic migrations as the application user:

```bash
cd /home/saliksik/saliksik-ai
uv run alembic upgrade head
```

The API also creates any missing tables at startup, but running migrations explicitly is recommended for production.

### Create an Initial Admin User (Optional)

```bash
cd /home/saliksik/saliksik-ai
uv run python - <<'PY'
from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User

db = SessionLocal()
try:
    admin = User(
        username="admin",
        email="admin@your-domain.com",
        hashed_password=get_password_hash("change-this-password"),
        role="admin",
        is_active=True,
        is_email_verified=True,
    )
    db.add(admin)
    db.commit()
    print("Admin user created")
finally:
    db.close()
PY
```

---

## Systemd Services

The application needs two long-running services: the FastAPI API and a Celery worker that processes analysis jobs.

### 1. API Service

Create `/etc/systemd/system/saliksik-ai.service`:

```ini
[Unit]
Description=Saliksik AI FastAPI Application
After=network-online.target postgresql.service redis-server.service
Wants=network-online.target postgresql.service redis-server.service

[Service]
Type=simple
User=saliksik
Group=saliksik
WorkingDirectory=/home/saliksik/saliksik-ai
Environment="PATH=/home/saliksik/saliksik-ai/.venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=/home/saliksik/saliksik-ai/.env
ExecStart=/home/saliksik/saliksik-ai/.venv/bin/uvicorn main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --workers 4 \
    --proxy-headers \
    --forwarded-allow-ips=127.0.0.1
Restart=always
RestartSec=10
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

### 2. Celery Worker Service

Create `/etc/systemd/system/saliksik-worker.service`:

```ini
[Unit]
Description=Saliksik AI Celery Worker
After=network-online.target postgresql.service redis-server.service
Wants=network-online.target postgresql.service redis-server.service

[Service]
Type=simple
User=saliksik
Group=saliksik
WorkingDirectory=/home/saliksik/saliksik-ai
Environment="PATH=/home/saliksik/saliksik-ai/.venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=/home/saliksik/saliksik-ai/.env
ExecStart=/home/saliksik/saliksik-ai/.venv/bin/celery \
    -A app.celery_app.celery_app \
    worker \
    --loglevel=INFO \
    --queues=analysis,default \
    --concurrency=2
Restart=always
RestartSec=10
TimeoutStopSec=60

[Install]
WantedBy=multi-user.target
```

### 3. Start the Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now saliksik-ai saliksik-worker

# Check status
sudo systemctl status saliksik-ai
sudo systemctl status saliksik-worker

# Verify the API
curl http://127.0.0.1:8000/health
```

If the API starts but analysis jobs stay in `PENDING`, check the worker logs:

```bash
sudo journalctl -u saliksik-worker -n 100 --no-pager
```

---

## Nginx Configuration

### 1. Configure the Rate-Limit Zone

`limit_req_zone` must be defined in the Nginx `http` context. Create `/etc/nginx/conf.d/saliksik-rate-limit.conf`:

```nginx
limit_req_zone $binary_remote_addr zone=saliksik_api:10m rate=10r/s;
```

### 2. Create the Site Configuration

Create `/etc/nginx/sites-available/saliksik-ai`:

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    client_max_body_size 10M;

    access_log /var/log/nginx/saliksik-ai-access.log;
    error_log /var/log/nginx/saliksik-ai-error.log;

    location / {
        limit_req zone=saliksik_api burst=20 nodelay;

        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # AI analysis requests can take several minutes
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

### 3. Enable the Site

```bash
sudo ln -s /etc/nginx/sites-available/saliksik-ai /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## SSL/TLS Setup

### Using Let's Encrypt (Certbot)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d api.yourdomain.com
sudo certbot renew --dry-run
```

### Manual SSL Configuration

Update the Nginx server block:

```nginx
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    add_header Strict-Transport-Security "max-age=31536000" always;

    # ... rest of the location configuration
}

server {
    listen 80;
    server_name api.yourdomain.com;
    return 301 https://$server_name$request_uri;
}
```

---

## Monitoring

### Application Logs

```bash
# API service logs
sudo journalctl -u saliksik-ai -f

# Celery worker logs
sudo journalctl -u saliksik-worker -f

# Nginx logs
tail -f /var/log/nginx/saliksik-ai-access.log
```

### Health Checks

```bash
# API health endpoint
curl -s http://localhost:8000/health

# PostgreSQL
sudo systemctl status postgresql

# Redis
redis-cli ping

# Celery worker
sudo -u saliksik bash -lc \
  'cd ~/saliksik-ai && .venv/bin/celery -A app.celery_app.celery_app inspect ping'
```

Create a simple API health-check script at `/usr/local/bin/check-saliksik.sh`:

```bash
#!/bin/bash
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
if [ "$response" != "200" ]; then
    echo "Health check failed with status $response"
    systemctl restart saliksik-ai
fi
```

```bash
sudo chmod +x /usr/local/bin/check-saliksik.sh
```

Add it to root's crontab (the script restarts the service, so it needs root privileges):

```bash
sudo crontab -e
```

```cron
*/5 * * * * /usr/local/bin/check-saliksik.sh
```

### Resource Monitoring

```bash
sudo apt install -y htop iotop
htop
```

Also monitor disk usage and Redis memory:

```bash
df -h
redis-cli info memory
```

---

## Backup Strategy

### Database Backup

Create `/usr/local/bin/backup-saliksik-db.sh`:

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/saliksik-ai"
mkdir -p "$BACKUP_DIR"

pg_dump -h localhost -U saliksik_user saliksik_ai_prod | \
    gzip > "$BACKUP_DIR/db_backup_$DATE.sql.gz"

# Keep the last 30 days
find "$BACKUP_DIR" -name "db_backup_*.sql.gz" -mtime +30 -delete
```

```bash
sudo chmod +x /usr/local/bin/backup-saliksik-db.sh
```

Configure a `~/.pgpass` entry for the account running the backup so `pg_dump` can connect without a password prompt, then schedule daily backups from root's crontab:

```bash
sudo crontab -e
```

```cron
0 2 * * * /usr/local/bin/backup-saliksik-db.sh
```

### Restore Database

```bash
gunzip < /var/backups/saliksik-ai/db_backup_YYYYMMDD_HHMMSS.sql.gz | \
    psql -h localhost -U saliksik_user saliksik_ai_prod
```

Redis stores cache data and queued tasks, not the source of truth. No Redis backup is required for normal operations.

---

## Troubleshooting

### Service Won't Start

```bash
sudo systemctl status saliksik-ai -l
sudo journalctl -u saliksik-ai -n 100 --no-pager
sudo lsof -i :8000
```

Common causes are an invalid `SECRET_KEY`, an unreachable database, or a malformed `.env` entry.

### Database Connection Issues

```bash
psql "postgresql://saliksik_user:secure_password@localhost:5432/saliksik_ai_prod" -c "SELECT 1;"
sudo systemctl status postgresql
sudo tail -f /var/log/postgresql/postgresql-15-main.log
```

The log filename may use a different PostgreSQL major version.

### Analysis Jobs Stay PENDING

```bash
sudo systemctl status saliksik-worker
sudo journalctl -u saliksik-worker -n 100 --no-pager
redis-cli ping
redis-cli -n 1 LLEN analysis
```

If the queue is growing, increase `--concurrency` in the worker service or add another worker instance.

### High Memory Usage

Reduce the API worker count in `saliksik-ai.service`:

```ini
ExecStart=/home/saliksik/saliksik-ai/.venv/bin/uvicorn main:app \
    --host 127.0.0.1 --port 8000 --workers 2
```

Reduce Celery concurrency in `saliksik-worker.service`:

```ini
ExecStart=/home/saliksik/saliksik-ai/.venv/bin/celery \
    -A app.celery_app.celery_app worker \
    --loglevel=INFO --queues=analysis,default --concurrency=1
```

Then reload and restart:

```bash
sudo systemctl daemon-reload
sudo systemctl restart saliksik-ai saliksik-worker
```

### Clear the Cache

```bash
# Clear the application cache (Redis database 0)
redis-cli -n 0 FLUSHDB
```

Do not use `FLUSHALL` unless you intentionally want to clear the Celery queue and results in database 1 as well.

---

## Production Checklist

Before going live:

- [ ] `DEBUG=False` in `.env`
- [ ] Strong `SECRET_KEY` configured
- [ ] Database password changed
- [ ] `.env` permissions set to `600`
- [ ] PostgreSQL running and reachable
- [ ] Redis running
- [ ] `uv run alembic upgrade head` completed
- [ ] `saliksik-ai` service running
- [ ] `saliksik-worker` service running
- [ ] SSL/TLS certificates installed
- [ ] Firewall configured (allow 22, 80, 443)
- [ ] Database backups scheduled
- [ ] Log rotation configured
- [ ] Monitoring and health checks configured
- [ ] Rate limiting enabled
- [ ] CORS origins restricted to trusted frontends
- [ ] Admin user created
- [ ] API documentation access reviewed
- [ ] Security headers verified
- [ ] Error tracking configured (Sentry, etc.)

---

## Support

For deployment issues:

- Check the service logs first
- Review this guide
- Open an issue at [GitHub Issues](https://github.com/leodyversemilla07/saliksik-ai/issues)
