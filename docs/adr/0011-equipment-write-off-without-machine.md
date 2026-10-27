# ADR-0011: Equipment write-off without a machine

**Status:** accepted

## Context
Every log entry belonged to a machine (`log_entry.machine_id NOT NULL`). Equipment that is in
stock or already removed is not on any machine, so writing it off could not be recorded in the log,
although ADR-0002 requires every state change to go through a log entry.

## Decision
- `log_entry.machine_id` is nullable, with `CHECK (machine_id IS NOT NULL OR kind = 'equipment_write_off')`:
  only a write-off may have no machine; every other kind still requires one.
- `create_log_entry()` requires the machine when the equipment being written off is installed,
  and it must be the machine the equipment is installed on.
- Receiving new equipment into stock is creating an `Equipment` row in admin (state `in_stock`,
  tracked by `django-simple-history`). A dedicated log entry kind may be added later.

## Consequences
- The full life of a unit of equipment is in the log, queried by `equipment_id`.
- Machine-oriented queries must not assume every entry has a machine.
