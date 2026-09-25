# Roadmap

## MVP

Goal: start collecting information about machines in one place.

1. **Skeleton.** Models, migrations, Django admin for reference data, docker-compose.
2. **Log.** `create_log_entry` service with side effects and validation, tests.
3. **Machine page — the service book:**
   - header: model, number, current owner with contacts, status;
   - installed equipment: type, serial number, year, software version, who installed it and when;
   - open issues (highlighted);
   - log feed filterable by kind, with photos, video and audio inline;
   - new entry form whose fields depend on the kind, with attachments.
4. **Machine list and search** by model, number, owner, region, equipment serial number.
5. **Counterparty and equipment pages**, a global feed of recent entries.
6. **Import** of existing machines, customers and equipment from Excel/CSV.
7. **Pilot** with 2–3 engineers.

Roles: *engineer* (reads everything, adds entries), *administrator* (reference data, users).
Sign-in with local accounts. UI in Russian.

## After MVP

- Sign-in with domain accounts (Active Directory / LDAP).
- Machine configuration "as of a date": what was installed at a given moment.
- Automated log audit and analysis, a machine summary before a site visit (possibly LLM-based).
- Reminders about scheduled maintenance and long-open issues.
- Creating entries from email and messengers.
