FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# gettext compiles the Russian catalog; libmagic is required by python-magic.
RUN apt-get update \
    && apt-get install --no-install-recommends --yes gettext libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY deploy/entrypoint.sh /usr/local/bin/trackrecord-entrypoint

# The container user matches the host user (uid 1000) so the bind-mounted
# media and static files stay writable without permissive modes.
ARG APP_UID=1000
ARG APP_GID=1000

RUN groupadd --gid "${APP_GID}" app \
    && useradd --uid "${APP_UID}" --gid app --home-dir /app app \
    && mkdir -p /app/media /app/staticfiles \
    && chown -R app:app /app /usr/local/bin/trackrecord-entrypoint \
    && chmod 0755 /usr/local/bin/trackrecord-entrypoint

USER app

ENTRYPOINT ["/usr/local/bin/trackrecord-entrypoint"]
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
