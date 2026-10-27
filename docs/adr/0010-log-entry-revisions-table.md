# ADR-0010: Log entry text revisions in a dedicated table

**Status:** accepted; amends ADR-0002 (how previous versions of title and text are kept)

## Context
ADR-0002 allows the author to amend the title and free text of a log entry and keeps the
previous versions with `django-simple-history`. simple-history copies the whole row on every
save: state-changing columns that must never change, `extra`, and the generated
`search_vector` column, which historical models do not handle well. Only title and text are
editable, so most of that history would be noise.

## Decision
- Previous versions of a log entry's title and text are stored in `LogEntryRevision`
  (`log_entry`, `title`, `text`, `edited_by`, `edited_at`), see [ER model](../ER_MODEL.md).
- A revision row is written by `core/services.py` in the same transaction that amends the entry;
  the entry gets `edited_at`.
- `LogEntry` is not tracked by `django-simple-history`. simple-history is still used for
  reference data edited through admin (counterparties, contacts, models, equipment).

## Consequences
- "Versions of this entry" is a simple query on one small table with an explicit editor.
- The amendment logic lives in the service and is covered by tests.
