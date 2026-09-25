# AGENTS.md

Instructions for developers and AI agents working in this repository.
Read the domain model in [docs/DOMAIN.md](docs/DOMAIN.md) before changing models.

## Environment

- Development happens in WSL (Ubuntu), Python 3.12, virtualenv in `.venv/`.
- SQLite is used locally (when `DATABASE_URL` is not set), PostgreSQL in production via `DATABASE_URL`.
- All environment-specific settings come from environment variables (see `.env.example`).
- GNU gettext is required for translations: `sudo apt install gettext`.

## Commands

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py compilemessages
.venv/bin/python manage.py runserver
.venv/bin/pytest
.venv/bin/python manage.py makemessages -l ru   # after adding or changing UI strings
```

## Layout

```
config/     Django settings, root urls
core/       the application: models, services, forms, views, admin, templates, tests
templates/  base template and login page
static/     CSS and JS (no external CDNs)
locale/     Russian translation catalog (locale/ru/LC_MESSAGES/django.po)
docs/       domain model, roadmap, ADRs
```

## Rules

- **Current machine and equipment state changes only through log entries.**
  `Machine.current_owner`, `Machine.status`, `Equipment.current_machine`,
  `Equipment.state` and `Equipment.software_version` must not be set directly from views or forms:
  everything goes through `core/services.py::create_log_entry()` in a single transaction (ADR-0002).
- Log entries are never deleted or rewritten after the fact. A correction is a new entry.
- No external CDNs or internet access: the service runs inside the internal network (ADR-0003).
- **Language (ADR-0005).** Everything in the repository is English: identifiers, comments,
  docstrings, test names, docs, commit messages, branch and PR names.
  The UI is Russian through Django i18n: write user-facing strings in English and wrap them in
  `gettext_lazy` (`_("...")`) or `{% translate %}`; put the Russian text in
  `locale/ru/LC_MESSAGES/django.po`. Never hardcode Russian strings in code or templates.
- Every change to logic in `services.py` comes with a test in `core/tests/`.
- Before committing run `pytest`; after changing models run `makemigrations`;
  after changing UI strings run `makemessages -l ru`, translate new entries, run `compilemessages`.

## Git

- `main` is the stable branch; work happens in `feature/*` and reaches `main` through a PR.
- Commit messages are short, imperative, in English
  (`Add log entry service`, `Fix equipment removal validation`).
