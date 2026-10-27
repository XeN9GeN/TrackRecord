# Deployment on a single Ubuntu host

nginx terminates TLS and serves static files; gunicorn runs Django on `127.0.0.1:8000`.
The host name is `<ip-with-dashes>.sslip.io`, which resolves to the IP and lets
Let's Encrypt issue a certificate without buying a domain.

Prerequisites: a public (non-CGNAT) IP, TCP 80 and 443 forwarded from the router to this host.

```bash
sudo apt install nginx certbot python3-certbot-nginx

# .env: DEBUG=False, a new SECRET_KEY, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, SECURE_COOKIES=True
.venv/bin/python manage.py migrate
.venv/bin/python manage.py compilemessages
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py check --deploy

# nginx (www-data) needs read access to staticfiles/ under the home directory
sudo usermod -aG mannobody www-data

sudo cp deploy/trackrecord.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now trackrecord

sed "s/SERVER_NAME/1-2-3-4.sslip.io/" deploy/nginx.conf | sudo tee /etc/nginx/sites-available/trackrecord
sudo ln -s /etc/nginx/sites-available/trackrecord /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d 1-2-3-4.sslip.io --redirect

sudo ufw allow OpenSSH && sudo ufw allow 'Nginx Full' && sudo ufw enable
```

After code changes: `collectstatic` (if static changed), `migrate`, `sudo systemctl restart trackrecord`.
