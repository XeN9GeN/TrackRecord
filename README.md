# TrackRecord — service books for track maintenance machines

An internal web service that keeps the full history of every railway track maintenance
(tamping/lining) machine our company equips and services: customer requests, calls, issues,
equipment installation and removal, software versions, ownership changes, acceptance
certificates, photos and videos.

Think of a car service book: open a machine's page and immediately see what equipment is
installed, who owns it now, which issues are still open and what happened before.

## Why

- Before a site visit or a call, engineers don't remember the machine's history and waste time reconstructing it.
- Complaints about "our system" are often caused by unresolved machine issues left over from installation.
- It is hard to recover what equipment is installed (serial numbers, production year, software version, who installed it and when).
- Machines change hands between customers and the history gets lost.

A complete history lets the team resolve more issues remotely, without an expensive trip to the machine.

## How it works

Every piece of information about a machine is a **log entry**: a record with structured fields
(kind, event date, who reported it, related equipment, issue status) and a free-text description
in Markdown, plus attachments. Entries of certain kinds (installation, removal, ownership change…)
update the machine's current state, so the machine page always shows the up-to-date
configuration and open issues, backed by the full history.

## Stack

| Layer | Choice |
|---|---|
| Application | Python 3.12, Django 5.2 LTS, one `core` app, server-rendered templates, vanilla JS (ADR-0001, ADR-0003) |
| Database | PostgreSQL 16 in development, tests and production; Russian full-text search, `pg_trgm` (ADR-0006) |
| Free text | Raw Markdown in the database, rendered with `markdown-it-py` and sanitised with `nh3` (ADR-0008) |
| Attachments | Outside the database: local volume in the MVP, S3-compatible storage later via `django-storages`; served by nginx after an auth check (ADR-0007) |
| History | The log itself (ADR-0002) plus `django-simple-history` |
| Auth | Local Django accounts with groups and `django-axes`; AD/LDAP or SSO later (ADR-0004) |
| UI language | English codebase, Russian UI via Django i18n (ADR-0005) |
| Runtime | gunicorn behind nginx, deployed with `docker compose` in the internal network |
| Tests | pytest, pytest-django |

A wiki engine is intentionally not part of the platform (ADR-0009); it may be added later as a
knowledge base linked from machine pages.

## Documentation

| Document | Contents |
|---|---|
| [docs/DOMAIN.md](docs/DOMAIN.md) | Domain model: glossary, entities, log entry kinds |
| [docs/ROADMAP.md](docs/ROADMAP.md) | MVP scope and what comes next |
| [docs/adr/](docs/adr/) | Architecture decisions and their rationale |
| [AGENTS.md](AGENTS.md) | Setup, commands and coding rules for developers and AI agents |

## Status

Design is done, MVP development is in progress (branch `feature/mvp`).
See [AGENTS.md](AGENTS.md) for local setup.
