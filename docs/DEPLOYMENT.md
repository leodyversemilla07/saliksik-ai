# Deployment Guide

Production deployment guide for Saliksik AI

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
- [Docker Deployment](#docker-deployment)
- [Manual Deployment](#manual-deployment)
- [Nginx Configuration](#nginx-configuration)
- [SSL/TLS Setup](#ssltls-setup)
- [Monitoring](#monitoring)
- [Backup Strategy](#backup-strategy)
- [Troubleshooting](#troubleshooting)

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

- Docker 24+ & Docker Compose 2.20+
- PostgreSQL 15+
- Redis 7+
- Nginx 1.24+ (for reverse proxy)
- Python 3.12+ (for manual deployment)

---

## Environment Setup

### 1. Create Production Environment File

```bash
cp .env.example .env.production
```

### 2. Configure Production Variables

Edit `.env.production`:

```bash
# Application
DEBUG=False
SECRET_KEY=<generate-strong-random-key-here>
ALLOWED_ORIGINS=https://your-domain.com,https://api.your-domain.com

# Database
DATABASE_URL=postgresql://saliksik:secure_password@db:5432/saliksik_ai_prod

# Redis
REDIS_URL=redis://redis:6379/0

# Celery
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/1

# Security
MAX_FILE_SIZE_MB=10
API_RATE_LIMIT=100/hour

# PostgreSQL
POSTGRES_DB=saliksik_ai_prod
POSTGRES_USER=saliksik
POSTGRES_PASSWORD=<strong-database-password>
```

### 3. Generate Secret Key

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Docker Deployment

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/saliksik-ai.git
cd saliksik-ai
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with production values
```

### 3. Build and Start Services

```bash
docker-compose up -d --build
```

### 4. Verify Deployment

```bash
# Check running containers
docker-compose ps

# View logs
docker-compose logs -f web

# Test health endpoint
curl http://localhost:8000/health
```

### 5. Create Initial Admin User (Optional)

```bash
docker-compose exec web python -c "
from app.core.database import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

db = SessionLocal()
admin = User(
 username='admin',
 email='admin@yourdomain.com',
 hashed_password=get_password_hash('your-admin-password')
)
db.add(admin)
db.commit()
print('Admin user created')
"
```

---

## Manual Deployment

### 1. System Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.12 python3.12-venv python3-pip \
 postgresql-15 redis-server nginx git
```

### 2. Create Application User

```bash
sudo useradd -m -s /bin/bash saliksik
sudo su - saliksik
```

### 3. Setup Application

```bash
# Clone repository
git clone https://github.com/yourusername/saliksik-ai.git
cd saliksik-ai

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download AI models
python -m spacy download en_core_web_sm
python -c "import nltk; nltk.download('punkt')"
```

### 4. Configure PostgreSQL

```bash
# Switch to postgres user
sudo su - postgres

# Create database and user
createdb saliksik_ai_prod
createuser saliksik_user
psql -c "ALTER USER saliksik_user WITH PASSWORD 'secure_password';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE saliksik_ai_prod TO saliksik_user;"

# Exit postgres user
exit
```

### 5. Initialize Database

```bash
# As saliksik user
cd ~/saliksik-ai
source .venv/bin/activate

python -c "from app.core.database import Base, engine; Base.metadata.create_all(bind=engine)"
```

### 6. Create Systemd Service

Create `/etc/systemd/system/saliksik-ai.service`:

```ini
[Unit]
Description=Saliksik AI FastAPI Application
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=saliksik
Group=saliksik
WorkingDirectory=/home/saliksik/saliksik-ai
Environment="PATH=/home/saliksik/saliksik-ai/.venv/bin"
EnvironmentFile=/home/saliksik/saliksik-ai/.env
ExecStart=/home/saliksik/saliksik-ai/.venv/bin/gunicorn main:app \
 --workers 4 \
 --worker-class uvicorn.workers.UvicornWorker \
 --bind 127.0.0.1:8000 \
 --access-logfile /var/log/saliksik-ai/access.log \
 --error-logfile /var/log/saliksik-ai/error.log
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 7. Start Service

```bash
# Create log directory
sudo mkdir -p /var/log/saliksik-ai
sudo chown saliksik:saliksik /var/log/saliksik-ai

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable saliksik-ai
sudo systemctl start saliksik-ai

# Check status
sudo systemctl status saliksik-ai
```

---

## Nginx Configuration

### 1. Create Nginx Config

Create `/etc/nginx/sites-available/saliksik-ai`:

```nginx
server {
 listen 80;
 server_name api.yourdomain.com;

 # Rate limiting
 limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
 limit_req zone=api_limit burst=20 nodelay;

 # Client body size
 client_max_body_size 10M;

 # Logging
 access_log /var/log/nginx/saliksik-ai-access.log;
 error_log /var/log/nginx/saliksik-ai-error.log;

 location / {
 proxy_pass http://127.0.0.1:8000;
 proxy_set_header Host $host;
 proxy_set_header X-Real-IP $remote_addr;
 proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
 proxy_set_header X-Forwarded-Proto $scheme;

 # Timeouts
 proxy_connect_timeout 300s;
 proxy_send_timeout 300s;
 proxy_read_timeout 300s;

 # WebSocket support (if needed)
 proxy_http_version 1.1;
 proxy_set_header Upgrade $http_upgrade;
 proxy_set_header Connection "upgrade";
 }

 # Security headers
 add_header X-Frame-Options "SAMEORIGIN" always;
 add_header X-Content-Type-Options "nosniff" always;
 add_header X-XSS-Protection "1; mode=block" always;
}
```

### 2. Enable Site

```bash
sudo ln -s /etc/nginx/sites-available/saliksik-ai /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## SSL/TLS Setup

### Using Let's Encrypt (Certbot)

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d api.yourdomain.com

# Auto-renewal (already configured with certbot)
sudo certbot renew --dry-run
```

### Manual SSL Configuration

Update Nginx config:

```nginx
server {
 listen 443 ssl http2;
 server_name api.yourdomain.com;

 ssl_certificate /path/to/fullchain.pem;
 ssl_certificate_key /path/to/privkey.pem;
 ssl_protocols TLSv1.2 TLSv1.3;
 ssl_ciphers HIGH:!aNULL:!MD5;
 ssl_prefer_server_ciphers on;

 # HSTS
 add_header Strict-Transport-Security "max-age=31536000" always;

 # ... rest of configuration
}

# Redirect HTTP to HTTPS
server {
 listen 80;
 server_name api.yourdomain.com;
 return 301 https://$server_name$request_uri;
}
```

---

## Monitoring

### 1. Application Logs

```bash
# Systemd service logs
sudo journalctl -u saliksik-ai -f

# Application logs
tail -f /var/log/saliksik-ai/error.log

# Nginx logs
tail -f /var/log/nginx/saliksik-ai-access.log
```

### 2. Health Monitoring

```bash
# Create health check script
cat > /usr/local/bin/check-saliksik.sh << 'EOF'
#!/bin/bash
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
if [ $response != "200" ]; then
 echo "Health check failed with status $response"
 sudo systemctl restart saliksik-ai
fi
EOF

chmod +x /usr/local/bin/check-saliksik.sh

# Add to crontab
crontab -e
# Add: */5 * * * * /usr/local/bin/check-saliksik.sh
```

### 3. Resource Monitoring

```bash
# Install monitoring tools
sudo apt install -y htop iotop nethogs

# Monitor processes
htop

# Monitor Docker resources (if using Docker)
docker stats
```

---

## Backup Strategy

### 1. Database Backup

```bash
# Create backup script
cat > /usr/local/bin/backup-saliksik-db.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/saliksik-ai"
mkdir -p $BACKUP_DIR

pg_dump -U saliksik_user saliksik_ai_prod | \
 gzip > $BACKUP_DIR/db_backup_$DATE.sql.gz

# Keep only last 30 days
find $BACKUP_DIR -name "db_backup_*.sql.gz" -mtime +30 -delete
EOF

chmod +x /usr/local/bin/backup-saliksik-db.sh

# Schedule daily backups
crontab -e
# Add: 0 2 * * * /usr/local/bin/backup-saliksik-db.sh
```

### 2. Restore Database

```bash
gunzip < /var/backups/saliksik-ai/db_backup_YYYYMMDD_HHMMSS.sql.gz | \
 psql -U saliksik_user saliksik_ai_prod
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check service status
sudo systemctl status saliksik-ai

# View recent logs
sudo journalctl -u saliksik-ai -n 50

# Check port availability
sudo lsof -i :8000
```

### Database Connection Issues

```bash
# Test database connection
psql -U saliksik_user -d saliksik_ai_prod -h localhost

# Check PostgreSQL status
sudo systemctl status postgresql

# View PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-15-main.log
```

### High Memory Usage

```bash
# Restart service
sudo systemctl restart saliksik-ai

# Reduce workers in systemd service
# Edit: --workers 2 (instead of 4)
sudo systemctl daemon-reload
sudo systemctl restart saliksik-ai
```

### Clear Cache

```bash
# Using Docker
docker-compose exec redis redis-cli FLUSHALL

# Manual
redis-cli FLUSHALL
```

---

## Production Checklist

Before going live:

- [ ] `DEBUG=False` in environment
- [ ] Strong `SECRET_KEY` configured
- [ ] Database password changed
- [ ] SSL/TLS certificates installed
- [ ] Firewall configured (allow 80, 443)
- [ ] Database backups scheduled
- [ ] Log rotation configured
- [ ] Monitoring setup
- [ ] Health checks configured
- [ ] Rate limiting enabled
- [ ] CORS properly configured
- [ ] Admin user created
- [ ] API documentation accessible
- [ ] Security headers configured
- [ ] Error tracking setup (Sentry, etc.)

---

## Support

For deployment issues:
- Check logs first
- Review this guide
- Check [GitHub Issues](https://github.com/yourusername/saliksik-ai/issues)
- Contact support
