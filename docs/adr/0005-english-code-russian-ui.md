# ADR-0005: English codebase, Russian UI via Django i18n

**Status:** accepted

## Context
The repository (code, comments, docs, commits) must be in English. The people using the service
work in Russian, so the UI must be Russian.

## Decision
- Every user-facing string is written in English in the source and marked for translation:
  `gettext_lazy as _` in Python (`verbose_name`, choice labels, form and validation errors,
  messages) and `{% translate %}` / `{% blocktranslate %}` in templates.
- The Russian text lives in `locale/ru/LC_MESSAGES/django.po`, which is committed.
  The compiled `.mo` file is not committed; it is built with `compilemessages`
  locally and in the Docker image.
- `LANGUAGE_CODE = "ru"`, `LOCALE_PATHS = [BASE_DIR / "locale"]`. No language switcher in the MVP.
- Data entered by users (machine names, log text) is stored as is and is not translated.

## Consequences
- No Russian strings are hardcoded in code or templates; reviewers can reject them.
- Adding a string requires `makemessages -l ru`, translating it in the `.po` file and `compilemessages`.
  An untranslated string shows up in English, which is easy to spot.
- GNU gettext must be installed for development and in the Docker image.
- An English UI can be enabled later by adding `LocaleMiddleware` and a language switcher.
