# ADR-0001: Django monolith with server-side rendering

**Status:** accepted

## Context
We need an internal web service with CRUD over several entities, file uploads, authentication
and an admin for reference data. The team is small and the MVP is needed quickly.

## Decision
Django 5.2 + PostgreSQL, a single `core` app, server-rendered HTML templates, no SPA.
Reference data and users are managed through Django admin.

## Consequences
- Authentication, ORM, migrations, admin and file uploads come with the framework.
- There is no separate API. If one is needed (mobile app, integrations), it can be added later,
  e.g. with Django REST Framework on top of the same services.
