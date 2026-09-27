# AGENTS.md

Instructions for developers and AI agents working in this repository.
Read the domain model in [docs/DOMAIN.md](docs/DOMAIN.md) before changing models,
and the decisions in [docs/adr/](docs/adr/) before changing architecture.

## Environment

- Development happens in WSL (Ubuntu), Python 3.12, virtualenv in `.venv/`.
- PostgreSQL 16 is required everywhere, including development and tests (ADR-0006).
  Locally it runs natively in WSL, not in Docker. Connection comes from `DATABASE_URL`.
- System packages: `sudo apt install postgresql gettext libmagic1`.
- All environment-specific settings come from environment variables (see `.env.example`).

## Commands

```bash
# one-time setup
sudo service postgresql start
sudo -u postgres createuser --createdb trackrecord -P
sudo -u postgres createdb -O trackrecord trackrecord
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env            # set DATABASE_URL=postgres://trackrecord:<password>@localhost:5432/trackrecord

# daily
.venv/bin/python manage.py migrate
.venv/bin/python manage.py compilemessages
.venv/bin/python manage.py runserver
.venv/bin/pytest
.venv/bin/python manage.py makemessages -l ru   # after adding or changing UI strings
```

## Layout

```
config/     Django settings, root urls, wsgi
core/       the application: models, services, markdown, forms, views, admin, templates, tests
templates/  base template and login page
static/     CSS and JS; third-party browser libraries only in static/vendor/ (no CDNs)
locale/     Russian translation catalog (locale/ru/LC_MESSAGES/django.po)
docs/       domain model, roadmap, ADRs
```

## Rules

- **Current machine and equipment state changes only through log entries.**
  `Machine.current_owner`, `Machine.status`, `Equipment.current_machine`,
  `Equipment.state` and `Equipment.software_version` must not be set directly from views or forms:
  everything goes through `core/services.py::create_log_entry()` in a single transaction
  with row locks (ADR-0002).
- Log entries are never deleted. State-changing fields are never edited; a correction is a new entry.
  Only title, text and attachments may be amended, and old versions are kept.
- **Data integrity belongs in the database**: foreign keys, unique and check constraints.
  Use `django.contrib.postgres` features freely; do not add SQLite or other DB fallbacks (ADR-0006).
  `JSONB` only for rare kind-specific attributes, never for fields used in filters or rules.
- **Free text is raw Markdown** (ADR-0008). Never store HTML. Render only through
  `core/markdown.py::render_markdown()` (template filters `render_markdown` /
  `render_markdown_plain`); it is the only place allowed to call `mark_safe` on user content.
  Normalise text with `services.normalize_text()` before saving. Use `.defer("text")` in list views.
- **Attachments** (ADR-0007): only through the `Attachment` model and the Django Storage API
  (`default_storage`), never direct filesystem paths. Never expose `MEDIA_ROOT` publicly;
  downloads go through the auth-checking view with `X-Accel-Redirect`. Check size and MIME
  type from content.
- No external CDNs or internet access at runtime (ADR-0003).
- **Language (ADR-0005).** Everything in the repository is English: identifiers, comments,
  docstrings, test names, docs, commit messages, branch and PR names.
  The UI is Russian through Django i18n: write user-facing strings in English and wrap them in
  `gettext_lazy` (`_("...")`) or `{% translate %}`; put the Russian text in
  `locale/ru/LC_MESSAGES/django.po`. Never hardcode Russian strings in code or templates.
- Every change to logic in `services.py` or `markdown.py` comes with a test in `core/tests/`.
- Before committing run `pytest`; after changing models run `makemigrations`;
  after changing UI strings run `makemessages -l ru`, translate new entries, run `compilemessages`.

## Git

- `main` is the stable branch; work happens in `feature/*` and reaches `main` through a PR.
- Commit messages are short, imperative, in English
  (`Add log entry service`, `Fix equipment removal validation`).
