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
