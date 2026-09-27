# ADR-0009: A wiki engine is not the platform

**Status:** accepted

## Context
The service book looks similar to a wiki (pages per machine, history, attachments), so building
it on a wiki engine was considered, including using the wiki only as a frontend.

## Options considered
- **XWiki + PostgreSQL:** structured classes, forms, queries, server-side event listeners.
  No transactions across pages, so current state would have to be computed from the log;
  development in Velocity/Groovy, versioning through XAR exports; JVM needs 2+ GB RAM.
- **GROWI + MongoDB:** Markdown pages only, no typed data. Script plugins run only in the
  browser, so forms can be added but validation, storage and authorship need a separate
  service with its own auth. Workers can be made read-only (ROM users), but then the wiki is
  only a shell around our own backend. MongoDB (SSPL) and Elasticsearch would be added to the
  internal network.
- **Wiki as a backend behind our own frontend:** we would still write a full backend, without
  database transactions or locks.

## Decision
TrackRecord is its own Django application with PostgreSQL (ADR-0001, ADR-0006). A wiki engine
may be added later **next to it** as a knowledge base (connection diagrams, manuals, typical
faults), linked from machine pages and log entries. Data never lives in the wiki.

## Consequences
- One system holds all service-book data and rules.
- Features a wiki gives for free are implemented in the app: history (ADR-0002), rich text
  (ADR-0008), attachments (ADR-0007), search (ADR-0006).
