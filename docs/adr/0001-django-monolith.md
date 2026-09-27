# ADR-0001: Django monolith with server-side rendering

**Status:** accepted

## Context
We need an internal web service with CRUD over several entities, file uploads, authentication
and an admin for reference data. The team is small and the MVP is needed quickly.

## Decision
- Django 5.2 LTS on Python 3.12, a single `core` app.
- Pages are rendered on the server with Django templates (DTL); a little vanilla JS where needed
  (see ADR-0003). No SPA and no separate frontend build.
- Reference data and users are managed through Django admin.
- In production Django runs under **gunicorn** (WSGI, several worker processes) behind **nginx**,
  which terminates HTTPS and serves static files and attachments (ADR-0007).
  `manage.py runserver` is for development only.

## Consequences
- Authentication, ORM, migrations, admin, forms and file uploads come with the framework.
- One codebase and one deployable; no API contract to maintain between frontend and backend.
- There is no public API. If one is needed (mobile app, integrations), it can be added later,
  e.g. with Django REST Framework on top of the same services.
- Live updates without a page reload are not available out of the box; if needed, htmx can be
  vendored into `static/` without changing the architecture.
