# SkillForge EC2 Deploy Runbook

Target: single AWS EC2 instance running Nginx + Gunicorn + Celery + Next.js + PostgreSQL + Redis.

Defer until development is complete. No Docker required.

## 1. Instance

- Ubuntu 22.04/24.04 LTS
- Security group: 80/443 public; SSH restricted to your IP
- Elastic IP recommended

## 2. System packages

```bash
sudo apt update
sudo apt install -y nginx postgresql redis-server python3-venv python3-pip git curl
# Node 20 via NodeSource or nvm
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

## 3. PostgreSQL & Redis

```bash
sudo -u postgres createuser skillforge
sudo -u postgres createdb skillforge -O skillforge
sudo -u postgres psql -c "ALTER USER skillforge PASSWORD 'strong-password';"
sudo systemctl enable --now redis-server
```

## 4. Backend

```bash
cd /opt
sudo git clone <backend-repo> skillforge-backend
cd skillforge-backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements/base.txt gunicorn
cp .env.example .env
# Set SECRET_KEY, DEBUG=False, DATABASE_URL, REDIS_URL, COOKIE_SECURE=True,
# COOKIE_SAMESITE=Lax, ALLOWED_HOSTS, CORS_ALLOWED_ORIGINS, CSRF_TRUSTED_ORIGINS,
# GOOGLE_CLIENT_ID, CLAUDE_API_KEY
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py seed_data  # optional for first boot
```

### Gunicorn systemd — `/etc/systemd/system/skillforge-api.service`

```ini
[Unit]
Description=SkillForge API
After=network.target postgresql.service redis-server.service

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/skillforge-backend
EnvironmentFile=/opt/skillforge-backend/.env
ExecStart=/opt/skillforge-backend/.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3
Restart=always

[Install]
WantedBy=multi-user.target
```

### Celery systemd — `/etc/systemd/system/skillforge-celery.service`

```ini
[Unit]
Description=SkillForge Celery Worker
After=network.target redis-server.service

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/skillforge-backend
EnvironmentFile=/opt/skillforge-backend/.env
ExecStart=/opt/skillforge-backend/.venv/bin/celery -A config worker -l info
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now skillforge-api skillforge-celery
```

## 5. Frontend

```bash
cd /opt
sudo git clone <frontend-repo> skillforge-frontend
cd skillforge-frontend
npm ci
# .env.production
# NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api/v1
# NEXT_PUBLIC_GOOGLE_CLIENT_ID=...
npm run build
```

### Next systemd — `/etc/systemd/system/skillforge-web.service`

```ini
[Unit]
Description=SkillForge Next.js
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/skillforge-frontend
Environment=NODE_ENV=production
Environment=PORT=3000
ExecStart=/usr/bin/npm run start
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now skillforge-web
```

## 6. Nginx

Terminate TLS with Let's Encrypt. Example reverse proxy:

- `yourdomain.com` → `127.0.0.1:3000`
- `api.yourdomain.com` → `127.0.0.1:8000`

Ensure cookie domain / CORS origins match. Use HTTPS so `COOKIE_SECURE=True` works.

## 7. Checklist

- [ ] HTTPS certificates
- [ ] `DEBUG=False`
- [ ] Strong `SECRET_KEY`
- [ ] DB backups (pg_dump cron)
- [ ] Log rotation for gunicorn/celery/nginx
- [ ] Rate limits remain enabled in DRF settings
- [ ] Google OAuth authorized JS origins / redirect URIs updated
