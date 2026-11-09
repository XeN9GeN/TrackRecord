# Docker deployment

The production stack is defined in [`compose.yaml`](../compose.yaml): PostgreSQL 16, Django
under gunicorn, and nginx. PostgreSQL data, uploaded media and collected static files are named
Docker volumes. nginx is the only service published on the host.

On a host that already runs nginx as the TLS terminator, [`compose.override.yaml`](../compose.override.yaml)
puts the container nginx behind the `container-edge` profile, publishes the web container on
`127.0.0.1:8000` and bind-mounts `media/` and `staticfiles/` so the host nginx can serve them.

## First start

Install Docker Engine with the Compose plugin on the host, then prepare the environment:

```bash
cp .env.example .env
# Edit .env: set a new SECRET_KEY, DEBUG=False, a strong URL-safe POSTGRES_PASSWORD,
# ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS.
```

The `web` service overrides `DATABASE_URL` for the container network and connects to the `db`
service. The `DATABASE_URL` value in `.env` remains suitable for local development.

Start the stack:

```bash
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f web
```

The web container runs migrations, compiles the Russian catalog and collects static files before
starting gunicorn. Open `http://<host>/` after the `web` and `nginx` services are healthy.

Create an administrator once:

```bash
docker compose exec web python manage.py createsuperuser
```

For a demo database, use the management command instead:

```bash
docker compose exec web python manage.py seed_demo --password 'change-this-demo-password'
```

## HTTPS

The included nginx container listens on port 80. Put it behind the company's TLS terminator or
extend `deploy/nginx.conf` and the Compose service with certificate volumes when certificates are
managed on this host. When TLS is terminated outside the container, set:

```dotenv
ALLOWED_HOSTS=example.internal
CSRF_TRUSTED_ORIGINS=https://example.internal
SECURE_COOKIES=True
```

The proxy must forward `Host`, `X-Forwarded-For` and `X-Forwarded-Proto`; nginx already forwards
these headers to Django.

## Updates and backups

After code or dependency changes:

```bash
docker compose build web
docker compose up -d
docker compose logs -f web
```

Back up PostgreSQL and the media volume separately:

```bash
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > trackrecord.sql
docker compose run --rm --no-deps -v "$PWD:/backup" nginx \
  tar czf /backup/trackrecord-media.tar.gz -C /media .
```

Restore the database and media volume together so log entries and their attachments remain
consistent.

## Host reverse proxy

On a host where nginx is already installed (for example, with a Let's Encrypt
certificate for `<ip>.sslip.io`), [`compose.override.yaml`](../compose.override.yaml) keeps
the application in Docker and lets the host nginx terminate TLS:

1. Point `location /` at `http://127.0.0.1:8000`.
2. Keep `location /static/` and `location /protected-media/` pointing at
   `staticfiles/` and `media/` in the repository; the override bind-mounts them.
3. Disable any old gunicorn unit so it does not take port 8000:
   `sudo systemctl disable --now trackrecord`.

TCP 80 and 443 must be forwarded by the router to this host. Some routers reserve
those ports for their own web interface and refuse a UPnP mapping with
`ConflictInMappingEntry`; add the forwarding rule in the router interface or use
another external port.

With a non-standard external port, use `proxy_set_header Host $http_host;` and
`proxy_set_header X-Forwarded-Host $http_host;` in the host nginx. `$host` strips
the port, so absolute URLs and CSRF origins would point at 443.
