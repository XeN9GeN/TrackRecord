# Architecture Decision Records

One decision per file: context, decision, consequences. Accepted decisions are not rewritten;
if a decision changes, a new ADR is added and the old one is marked "superseded by ADR-XXXX".

| # | Decision | Status |
|---|---|---|
| [0001](0001-django-monolith.md) | Django monolith with server-side rendering | Accepted |
| [0002](0002-log-as-source-of-truth.md) | The log is the only way to change state | Accepted |
| [0003](0003-no-external-cdn.md) | No external CDNs or internet dependencies | Accepted |
| [0004](0004-local-auth-first.md) | Local accounts in the MVP, Active Directory later | Accepted |
| [0005](0005-english-code-russian-ui.md) | English codebase, Russian UI via Django i18n | Accepted |
| [0006](0006-postgresql-everywhere.md) | PostgreSQL everywhere | Accepted |
| [0007](0007-attachments-outside-db.md) | Attachments are stored outside the database | Accepted |
| [0008](0008-markdown-free-text.md) | Structured fields plus raw Markdown for free text | Accepted |
| [0009](0009-wiki-engine-not-platform.md) | A wiki engine is not the platform | Accepted |
