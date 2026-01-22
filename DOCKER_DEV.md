# Docker Development Environment - Quick Reference

## 🎯 Most Used Commands

```bash
# Start everything
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f app

# Stop everything
docker-compose -f docker-compose.dev.yml down

# Rebuild after code changes
docker-compose -f docker-compose.dev.yml up -d --build app

# Shell into app container
docker-compose -f docker-compose.dev.yml exec app bash

# Run tests
docker-compose -f docker-compose.dev.yml exec app pytest
```

## 🚀 Getting Started

1. **First time setup:**
   ```bash
   # Start services
   docker-compose -f docker-compose.dev.yml up -d
   
   # Wait for health checks, then run migrations
   docker-compose -f docker-compose.dev.yml exec app alembic upgrade head
   ```

2. **Daily development:**
   ```bash
   # Start services
   docker-compose -f docker-compose.dev.yml up -d
   
   # Edit code in ./app/ - changes auto-reload!
   
   # View logs if needed
   docker-compose -f docker-compose.dev.yml logs -f
   ```

3. **End of day:**
   ```bash
   # Stop services (keeps data)
   docker-compose -f docker-compose.dev.yml down
   ```

## 🔧 Key Features

- **Hot Reload**: Edit Python files, server restarts automatically
- **Debug Port**: 5678 for remote debugging
- **Admin Tools**: pgAdmin (port 5050) and Redis Commander (port 8081)
- **Persistent Data**: Database and Redis data survives container restarts

## 📦 Services

| Service | Port | Purpose |
|---------|------|---------|
| app | 8000 | FastAPI application |
| celery-worker | - | Background tasks |
| db | 5432 | PostgreSQL database |
| redis | 6379 | Cache & message broker |
| pgadmin | 5050 | DB admin (optional) |
| redis-commander | 8081 | Redis admin (optional) |

## 🐛 Troubleshooting

**Container won't start?**
```bash
docker-compose -f docker-compose.dev.yml logs app
```

**Port already in use?**
```bash
# Change in .env file
APP_PORT=8001
```

**Need fresh database?**
```bash
docker-compose -f docker-compose.dev.yml down -v
docker-compose -f docker-compose.dev.yml up -d
```

See [full documentation](./README.md) for detailed guide.
