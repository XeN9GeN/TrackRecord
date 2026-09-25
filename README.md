# TrackRecord — service books for track maintenance machines

An internal web service that keeps the full history of every railway track maintenance
(tamping/lining) machine our company equips and services: customer requests, calls, issues,
equipment installation and removal, software versions, ownership changes, acceptance
certificates, photos and videos.

Think of a car service book: open a machine's page and immediately see what equipment is
installed, who owns it now, which issues are still open and what happened before.

## Why

- Before a site visit or a call, engineers don't remember the machine's history and waste time reconstructing it.
- Complaints about "our system" are often caused by unresolved machine issues left over from installation.
- It is hard to recover what equipment is installed (serial numbers, production year, software version, who installed it and when).
- Machines change hands between customers and the history gets lost.

A complete history lets the team resolve more issues remotely, without an expensive trip to the machine.

## Documentation

| Document | Contents |
|---|---|
| [docs/DOMAIN.md](docs/DOMAIN.md) | Domain model: glossary, entities, log entry kinds |
| [docs/ROADMAP.md](docs/ROADMAP.md) | MVP scope and what comes next |
| [docs/adr/](docs/adr/) | Architecture decisions and their rationale |
| [AGENTS.md](AGENTS.md) | Coding rules for developers and AI agents |

## Stack

Python 3.12, Django 5.2, PostgreSQL 16 (SQLite for local development), server-rendered templates
with no external CDNs, deployed with `docker compose` inside the company's internal network.
The codebase is in English; the user interface is in Russian via Django i18n (see ADR-0005).

## Status

Design is done, MVP development is in progress (branch `feature/mvp`).
Setup instructions will appear here together with the code.
