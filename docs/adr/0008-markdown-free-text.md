# ADR-0008: Structured fields plus raw Markdown for free text

**Status:** accepted

## Context
A log entry has facts the system must query and enforce (kind, dates, contact, equipment, issue
status) and a free description written by people, often copied from messengers. A single
Markdown document per entry (wiki style) would make those facts unqueryable; storing HTML from
a WYSIWYG editor is hard to search, analyse and keep safe.

## Decision
- Facts are regular columns and foreign keys. Only the description is free text.
- `LogEntry.text` stores **raw Markdown** as typed: `TextField`, empty string instead of NULL,
  check constraint of at most 50 000 characters. Before saving, `services.normalize_text()`
  converts line endings to `\n`, applies Unicode NFC and trims whitespace.
- HTML is never stored. Rendering happens on display in one function,
  `core/markdown.py::render_markdown()`: `markdown-it-py` (CommonMark, tables, strikethrough,
  `breaks=True` so single line breaks are kept, linkify) followed by `nh3` sanitising with an
  allow-list (no raw HTML, no images, headings h3/h4 only, `rel="noopener noreferrer"` on links).
  It is the only place that calls `mark_safe`.
- Templates use the filters `render_markdown` and `render_markdown_plain` (text without markup,
  for lists and previews) from `core/templatetags/markdown_tags.py`. An optional preview
  endpoint uses the same function.
- The form is a plain `<textarea>`; per-kind text skeletons (e.g. "Symptoms / When it happens /
  What was checked") are inserted by `static/js/log_form.js`. A vendored Markdown editor can be
  added later (ADR-0003).
- Search: a generated column `search_vector` (`to_tsvector('russian', …)`, title weight A,
  text weight B) with a GIN index, created with `RunSQL` in a migration.
- The text column uses lz4 TOAST compression; list views use `.defer("text")`.

## Consequences
- Engineers can write plain text; Markdown is optional.
- Rendering rules and sanitising can be changed at any time and apply to all old entries.
- Text is directly usable for search, audits and future analysis.
- Security depends on keeping `render_markdown()` the single rendering path; tests cover XSS cases.
