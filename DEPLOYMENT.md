# Saliksik AI Deployment Guide

This guide covers deploying Saliksik AI in different environments.

## Quick Deploy Options

### 🐳 Docker Deployment (Recommended)

#### Development Deployment
```bash
# Clone repository
git clone https://github.com/leodyversemilla07/saliksik-ai.git
cd saliksik-ai

# Simple development deployment (SQLite)
docker-compose -f docker-compose.dev.yml up --build
```

#### Production Deployment
```bash
# Full production stack (PostgreSQL + Redis + Nginx)
docker-compose up --build -d
```

### 🔧 Manual Deployment

#### Prerequisites
- Python 3.8+
- PostgreSQL (for production)
- Redis (optional, for caching)
- Java 8+ (optional, for LanguageTool)

#### Setup Steps
```bash
# 1. Clone and setup
git clone https://github.com/leodyversemilla07/saliksik-ai.git
cd saliksik-ai
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Environment configuration
cp .env.example .env
# Edit .env with your production settings

# 3. Database setup
python manage.py migrate
python manage.py collectstatic

# 4. AI models setup
python -m spacy download en_core_web_sm
python -c "import nltk; nltk.download('punkt')"

# 5. Create superuser
python manage.py createsuperuser

# 6. Start server
python manage.py runserver
```

## Environment Configuration

### Required Environment Variables

```bash
# Security (REQUIRED)
SECRET_KEY=your-secure-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database (PostgreSQL recommended for production)
DATABASE_URL=postgresql://user:password@localhost:5432/saliksik_ai

# CORS (adjust for your frontend domain)
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

### Optional Environment Variables

```bash
# File upload limits
MAX_FILE_SIZE_MB=10

# API rate limiting
API_RATE_LIMIT=1000/hour

# Caching (if using Redis)
CACHE_URL=redis://localhost:6379/1

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/saliksik_ai.log
```

## Database Setup

### SQLite (Development)
- Default configuration
- No additional setup required
- Not recommended for production

### PostgreSQL (Production)
```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
CREATE DATABASE saliksik_ai;
CREATE USER saliksik WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE saliksik_ai TO saliksik;
\q

# Update DATABASE_URL in .env
DATABASE_URL=postgresql://saliksik:your_password@localhost:5432/saliksik_ai
```

## Web Server Configuration

### Nginx Configuration

Create `/etc/nginx/sites-available/saliksik_ai`:

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;
    
    # SSL Configuration
    ssl_certificate /path/to/your/certificate.crt;
    ssl_certificate_key /path/to/your/private.key;
    
    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    
    # Static files
    location /static/ {
        alias /path/to/saliksik_ai/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Media files
    location /media/ {
        alias /path/to/saliksik_ai/media/;
    }
    
    # API requests
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Upload size limit
        client_max_body_size 10M;
    }
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/saliksik_ai /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Systemd Service (for manual deployment)

Create `/etc/systemd/system/saliksik_ai.service`:

```ini
[Unit]
Description=Saliksik AI Django Application
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/path/to/saliksik_ai
Environment=PATH=/path/to/saliksik_ai/venv/bin
EnvironmentFile=/path/to/saliksik_ai/.env
ExecStart=/path/to/saliksik_ai/venv/bin/gunicorn \
    --workers 3 \
    --bind 127.0.0.1:8000 \
    saliksik_ai.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable saliksik_ai
sudo systemctl start saliksik_ai
```

## Cloud Deployment

### AWS ECS with Docker

1. Build and push image:
```bash
# Build image
docker build -t saliksik-ai .

# Tag for ECR
docker tag saliksik-ai:latest your-account.dkr.ecr.region.amazonaws.com/saliksik-ai:latest

# Push to ECR
aws ecr get-login-password --region region | docker login --username AWS --password-stdin your-account.dkr.ecr.region.amazonaws.com
docker push your-account.dkr.ecr.region.amazonaws.com/saliksik-ai:latest
```

2. Create ECS task definition and service
3. Configure RDS PostgreSQL instance
4. Set up ElastiCache Redis (optional)
5. Configure ALB with SSL termination

### Heroku Deployment

1. Create `Procfile`:
```
web: gunicorn saliksik_ai.wsgi --log-file -
release: python manage.py migrate
```

2. Deploy:
```bash
heroku create your-app-name
heroku addons:create heroku-postgresql:mini
heroku addons:create heroku-redis:mini
heroku config:set SECRET_KEY=your-secret-key
heroku config:set DEBUG=False
git push heroku main
```

### DigitalOcean App Platform

1. Create `app.yaml`:
```yaml
name: saliksik-ai
services:
- name: web
  source_dir: /
  github:
    repo: your-username/saliksik-ai
    branch: main
  run_command: gunicorn saliksik_ai.wsgi:application
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-xxs
  envs:
  - key: SECRET_KEY
    value: your-secret-key
  - key: DEBUG
    value: "False"
databases:
- name: db
  engine: PG
  num_nodes: 1
  size: db-s-dev-database
```

## Monitoring & Maintenance

### Health Checks

Add to your monitoring system:
```bash
# Basic health check
curl -f http://localhost:8000/demo/ \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"manuscript_text":"Health check test text for monitoring"}'
```

### Log Management

```bash
# Rotate logs
sudo logrotate -f /etc/logrotate.d/saliksik_ai

# Monitor logs
tail -f /var/log/saliksik_ai.log
```

### Database Backups

```bash
# PostgreSQL backup
pg_dump -h localhost -U saliksik saliksik_ai > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore
psql -h localhost -U saliksik saliksik_ai < backup_file.sql
```

## Security Checklist

### Production Security

- [ ] Set `DEBUG=False`
- [ ] Use strong `SECRET_KEY`
- [ ] Configure HTTPS/SSL
- [ ] Set proper `ALLOWED_HOSTS`
- [ ] Configure CORS properly
- [ ] Enable rate limiting
- [ ] Set up firewall rules
- [ ] Regular security updates
- [ ] Monitor for vulnerabilities

### API Security

- [ ] Token authentication enabled
- [ ] Rate limiting configured
- [ ] Input validation in place
- [ ] File upload restrictions
- [ ] Error message sanitization
- [ ] Request size limits

## Performance Optimization

### Database Optimization

```python
# Add to settings.py for production
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'OPTIONS': {
            'MAX_CONNS': 20,
            'CONN_MAX_AGE': 600,
        }
    }
}
```

### Caching Setup

```python
# Redis caching
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
```

### Static Files

```bash
# Collect static files
python manage.py collectstatic --noinput

# Compress static files (optional)
python manage.py compress
```

## Troubleshooting

### Common Issues

1. **AI Models not found**
```bash
python -m spacy download en_core_web_sm
python -c "import nltk; nltk.download('punkt')"
```

2. **Database connection errors**
- Check DATABASE_URL format
- Verify database credentials
- Ensure database server is running

3. **Permission errors**
```bash
sudo chown -R www-data:www-data /path/to/saliksik_ai
sudo chmod -R 755 /path/to/saliksik_ai
```

4. **Large file upload failures**
- Check `MAX_FILE_SIZE_MB` setting
- Verify nginx `client_max_body_size`
- Check Django `FILE_UPLOAD_MAX_MEMORY_SIZE`

### Debug Mode

For troubleshooting, temporarily enable debug mode:
```bash
export DEBUG=True
python manage.py runserver
```

**Remember to disable debug mode in production!**

## Support

For deployment issues:
1. Check application logs
2. Verify environment variables
3. Test database connectivity
4. Review security settings
5. Contact support if needed

## Next Steps

After successful deployment:
1. Set up monitoring and alerting
2. Configure automated backups
3. Plan for scaling and load balancing
4. Implement CI/CD pipeline
5. Set up staging environment
