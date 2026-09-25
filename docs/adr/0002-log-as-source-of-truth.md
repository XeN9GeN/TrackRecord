# ADR-0002: The log is the only way to change state

**Status:** accepted

## Context
The core value of the service is a trustworthy machine history. If the current owner or installed
equipment can be edited by hand on the machine page, history and current state quickly diverge.

## Decision
- Current state (machine owner and status; equipment assignment, state and software version)
  is stored in denormalized fields for fast display, but is changed **only** by
  `core/services.py::create_log_entry()`, in the same transaction that creates the entry.
- The service validates transitions: equipment already installed on another machine cannot be
  installed; equipment can only be removed from the machine it is installed on; written-off
  equipment cannot be installed.
- Log entries are never deleted. Fields that affect state are not editable after creation;
  mistakes are corrected with a new entry. The author may amend text and attachments.
- Manual edits of reference data through admin are tracked with `django-simple-history`.

## Consequences
- The history always explains the current state.
- "Configuration as of a date" can later be implemented by replaying the log.
- The initial data import also creates log entries ("Initial data import").
