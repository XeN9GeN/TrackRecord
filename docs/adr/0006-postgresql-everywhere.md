# ADR-0006: PostgreSQL everywhere

**Status:** accepted

## Context
The data is relational: counterparties own machines, equipment is installed on machines,
log entries reference machines, contacts, equipment and other entries. The rules of ADR-0002
need transactions, row locks and constraints. We also need Russian full-text search and
the service must later move from the MVP to a corporate server with minimal effort.

## Decision
- PostgreSQL 16 is the only database, in development, tests and production.
  Connection is configured with `DATABASE_URL`; there is no SQLite fallback.
- Development: PostgreSQL installed natively in WSL (`apt`), not in Docker Desktop, to save
  memory on developer laptops. Production: the `db` service of `docker compose` or a
  PostgreSQL instance provided by IT.
- Integrity lives in the database: foreign keys, unique constraints
  (machine model + factory number, equipment type + serial number), check constraints.
- `django.contrib.postgres` is used for Russian full-text search (`tsvector`, config `russian`)
  and `pg_trgm` for fuzzy search on serial numbers and names.
- `JSONB` is allowed only for rare kind-specific attributes of log entries; anything used in
  filters, joins or rules is a regular column.

## Alternatives considered
- **SQLite for development:** rejected; search, JSONB, locking and transaction behaviour would
  differ from production.
- **MongoDB / other NoSQL:** rejected; no foreign keys or cross-collection constraints, joins via
  aggregation, weaker Django support, SSPL licence often not approved by corporate policy.
  Flexibility for kind-specific fields is covered by `JSONB`.
- **MS SQL / Oracle:** only if IT mandates them; Django supports them, but the
  `django.contrib.postgres` features would have to be replaced.

## Consequences
- Moving to the corporate server is `pg_dump` / `pg_restore` plus `DATABASE_URL`.
- Compatible with PostgreSQL-based distributions (e.g. Postgres Pro) if a domestic DBMS is required.
- Developers must install PostgreSQL locally (see AGENTS.md).
