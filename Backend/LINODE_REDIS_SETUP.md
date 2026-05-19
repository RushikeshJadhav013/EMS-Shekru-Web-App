# Redis OTP setup — Linode production (`ems-fastapi`)

End-to-end guide for `/root/staffly/EMS-Shekru-Web-App/Backend` with Gunicorn + nginx.

---

## 1. Install Redis on Linode

```bash
sudo apt update
sudo apt install -y redis-server
```

Secure Redis (localhost only + password):

```bash
sudo nano /etc/redis/redis.conf
```

Set:

```conf
bind 127.0.0.1 ::1
protected-mode yes
requirepass YOUR_STRONG_REDIS_PASSWORD
```

Restart and test:

```bash
sudo systemctl enable redis-server
sudo systemctl restart redis-server
redis-cli -a YOUR_STRONG_REDIS_PASSWORD ping
# PONG
```

Do **not** open port 6379 in Linode Cloud Firewall.

---

## 2. Application env (`.env.production`)

On the server:

```bash
cd /root/staffly/EMS-Shekru-Web-App/Backend
nano .env.production
```

Add:

```bash
REDIS_URL=redis://:YOUR_STRONG_REDIS_PASSWORD@127.0.0.1:6379/0
OTP_REDIS_KEY_PREFIX=staffly:otp:
```

Keep existing `ENVIRONMENT=production`, database, SMTP, etc.

---

## 3. Deploy code + Python dependency

```bash
cd /root/staffly/EMS-Shekru-Web-App/Backend
git pull origin <your-branch>
source venv/bin/activate
pip install -r requirements.txt
```

Confirm `redis` is installed:

```bash
pip show redis
```

---

## 4. Update `ems-fastapi.service`

```bash
sudo nano /etc/systemd/system/ems-fastapi.service
```

Use this structure (additions marked):

```ini
[Unit]
Description=EMS FastAPI Backend
After=network.target redis-server.service
Wants=redis-server.service

[Service]
User=root
Group=www-data
WorkingDirectory=/root/staffly/EMS-Shekru-Web-App/Backend
Environment="PATH=/root/staffly/EMS-Shekru-Web-App/Backend/venv/bin"
Environment="ENV_FILE=.env.production"
Environment="DB_POOL_SIZE=6"
Environment="DB_MAX_OVERFLOW=4"
Environment="DB_POOL_TIMEOUT=60"
Environment="DB_POOL_RECYCLE=1800"

ExecStart=/root/staffly/EMS-Shekru-Web-App/Backend/venv/bin/gunicorn \
    -k uvicorn.workers.UvicornWorker \
    -w 2 \
    -b 127.0.0.1:8000 \
    app.main:app

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`REDIS_URL` is loaded from `.env.production` via your app settings (`ENV_FILE`).

Reload:

```bash
sudo systemctl daemon-reload
sudo systemctl restart redis-server
sudo systemctl restart ems-fastapi
sudo systemctl status redis-server ems-fastapi
```

---

## 5. nginx

**No changes** for Redis. nginx only proxies HTTP to `127.0.0.1:8000`.

---

## 6. Verify

### Redis

```bash
redis-cli -a YOUR_STRONG_REDIS_PASSWORD
KEYS staffly:otp:*
```

### App logs

```bash
sudo journalctl -u ems-fastapi -f
```

After `send-otp`, you should see OTP keys in Redis. After successful `verify-otp`, the key should be deleted.

### Login test

1. Request OTP once.
2. Click **Verify OTP** once with the correct code.
3. Should succeed on the **first** click (no more `No OTP record found` across workers).

### Debug (non-production only)

```bash
curl https://staffly.space/auth/debug/environment
```

Look for `"redis_otp_enabled": true`.

---

## 7. Rollback

1. Remove `REDIS_URL` from `.env.production` (falls back to in-memory per worker).
2. `sudo systemctl restart ems-fastapi`
3. Or temporarily set Gunicorn `-w 1` until Redis is fixed.

---

## Troubleshooting

| Symptom | Check |
|--------|--------|
| `No OTP record found` still | `REDIS_URL` in `.env.production`, `pip install redis`, restart service |
| Redis connection refused | `systemctl status redis-server`, `bind 127.0.0.1` |
| Auth errors | Password in URL must match `requirepass` |
| Wrong OTP / Expected X | User resend OTP; only latest code in Redis is valid |
