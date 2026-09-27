# ADR-0003: No external CDNs or internet dependencies

**Status:** accepted

## Context
The service is deployed inside the company's internal network, which may have no internet access.

## Decision
- Do not load CSS/JS libraries from CDNs. Use a small custom stylesheet and vanilla JS
  (e.g. toggling form fields and text skeletons by log entry kind), all served from `static/`.
- If a browser library is needed (htmx, a Markdown editor such as EasyMDE), its release files
  are vendored into `static/vendor/<name>-<version>/` together with its licence.
- The application makes no outgoing internet requests at runtime.

## Consequences
- The UI is simpler than with a ready-made UI framework, but works without internet.
- Python dependencies and Docker images are installed from PyPI / Docker Hub or an internal
  mirror at build time.
