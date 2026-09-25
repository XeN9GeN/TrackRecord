# ADR-0003: No external CDNs or internet dependencies

**Status:** accepted

## Context
The service is deployed inside the company's internal network, which may have no internet access.

## Decision
Do not load CSS/JS libraries from CDNs. Use a small custom stylesheet and vanilla JS
(e.g. to toggle form fields by log entry kind), all served from `static/`.
If a library is needed, its files are vendored into the repository.

## Consequences
- The UI is simpler than with a ready-made UI framework, but works without internet.
- Python dependencies are installed from PyPI or an internal mirror when building the Docker image.
