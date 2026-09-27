# Roadmap

## MVP

Goal: start collecting information about machines in one place.

1. **Skeleton.** Django project on PostgreSQL, models and migrations, Django admin for reference
   data, i18n setup, `docker compose` (web + db + nginx).
2. **Log.** `create_log_entry` service with side effects, validation and row locks; tests.
3. **Free text.** Markdown rendering and sanitising (`render_markdown`), text normalisation,
   per-kind text skeletons, text revisions.
4. **Attachments.** Upload to the local volume with SHA-256 and MIME checks, photo thumbnails
   (incl. HEIC), auth-checked downloads via nginx `X-Accel-Redirect`.
5. **Machine page — the service book:**
   - header: model, number, current owner with contacts, status;
   - installed equipment: type, serial number, year, software version, who installed it and when;
   - open issues (highlighted);
   - log feed filterable by kind, with photos, video and audio inline;
   - new entry form whose fields depend on the kind, with attachments.
6. **Machine list and search:** by model, number, owner, region, equipment serial number
   (`pg_trgm`) and full-text search in entries (Russian `tsvector`).
7. **Counterparty and equipment pages**, a global feed of recent entries.
8. **Import** of existing machines, customers and equipment from Excel (`openpyxl`).
9. **Deployment** on a test server in the internal network: gunicorn + nginx, nightly
   `pg_dump` and attachment backups.
10. **Pilot** with 2–3 engineers.

Roles: *engineer* (reads everything, adds entries), *administrator* (reference data, users).
Sign-in with local accounts. UI in Russian.

## After MVP

- Sign-in with domain accounts: AD/LDAP (`django-auth-ldap`) or corporate SSO (OIDC).
- Media processing in the background: video transcoding to browser-friendly MP4, PDF previews.
- S3-compatible attachment storage via `django-storages` when volume or number of servers grows.
- Optional Markdown editor with a toolbar (vendored EasyMDE or Toast UI Editor).
- Machine configuration "as of a date": what was installed at a given moment.
- Automated log audit and analysis, a machine summary before a site visit (possibly LLM-based, `pgvector`).
- Reminders about scheduled maintenance and long-open issues.
- Creating entries from email and messengers.
- Optional wiki knowledge base (diagrams, manuals, typical faults) linked from machine pages (ADR-0009).
