"""The only place where machine and equipment state changes (ADR-0002)."""

import unicodedata

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import (
    EQUIPMENT_KINDS,
    TEXT_MAX_LENGTH,
    Equipment,
    EquipmentState,
    IssueStatus,
    LogEntry,
    LogKind,
    LogSource,
    Machine,
)


def normalize_text(text):
    """Line endings to \\n, Unicode NFC, no trailing spaces on lines, no blank lines around (ADR-0008)."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFC", text)
    return "\n".join(line.rstrip() for line in text.split("\n")).strip("\n")


@transaction.atomic
def create_log_entry(
    *,
    author,
    kind,
    title,
    machine=None,
    text="",
    event_date=None,
    source=LogSource.OTHER,
    contact=None,
    equipment=None,
    software_version=None,
    new_owner=None,
    new_status=None,
    resolves=(),
    extra=None,
):
    """Record an entry and apply its effect on current state in one transaction.

    Affected machine, equipment and resolved issues are locked with SELECT ... FOR UPDATE,
    so concurrent entries cannot install one unit on two machines or resolve an issue twice.
    Raises ValidationError if the entry is not allowed in the current state.
    """
    kind = LogKind(kind)
    title = " ".join(normalize_text(title).split())
    text = normalize_text(text)
    event_date = event_date or timezone.localdate()
    software_version = software_version.strip() if software_version else None

    if not title:
        raise ValidationError(_("Title is required."))
    if len(text) > TEXT_MAX_LENGTH:
        raise ValidationError(_("Text is too long."))
    if event_date > timezone.localdate():
        raise ValidationError(_("Event date cannot be in the future."))
    _reject_unused_fields(
        kind,
        equipment=equipment,
        software_version=software_version,
        new_owner=new_owner,
        new_status=new_status,
        resolves=resolves,
    )

    if machine is not None:
        machine = Machine.objects.select_for_update().get(pk=machine.pk)
    elif kind != LogKind.EQUIPMENT_WRITE_OFF:
        raise ValidationError(_("Machine is required."))
    if equipment is not None:
        equipment = Equipment.objects.select_for_update().get(pk=equipment.pk)
    elif kind in EQUIPMENT_KINDS:
        raise ValidationError(_("Equipment is required."))

    entry = LogEntry(
        machine=machine,
        author=author,
        kind=kind,
        title=title,
        text=text,
        event_date=event_date,
        source=source,
        contact=contact,
        owner_snapshot=machine.current_owner if machine else None,
        equipment=equipment,
        extra=extra or {},
    )
    machine_fields = []
    issues = []

    match kind:
        case LogKind.REQUEST:
            machine.last_contact_at = timezone.now()
            machine_fields = ["last_contact_at"]
        case LogKind.ISSUE:
            entry.is_issue = True
            entry.issue_status = IssueStatus.OPEN
        case LogKind.MAINTENANCE:
            issues = list(
                LogEntry.objects.select_for_update().filter(pk__in=[issue.pk for issue in resolves]).order_by("pk")
            )
            for issue in issues:
                if issue.machine_id != machine.pk or not issue.is_open_issue:
                    raise ValidationError(
                        _("“%(title)s” is not an open issue of this machine.") % {"title": issue.title}
                    )
        case LogKind.EQUIPMENT_INSTALL:
            if equipment.state not in (EquipmentState.IN_STOCK, EquipmentState.REMOVED):
                raise ValidationError(
                    _("%(equipment)s cannot be installed: it is %(state)s.")
                    % {"equipment": equipment, "state": equipment.get_state_display()}
                )
            entry.software_version = software_version or equipment.software_version
            equipment.state = EquipmentState.INSTALLED
            equipment.current_machine = machine
            equipment.software_version = entry.software_version
        case LogKind.EQUIPMENT_REMOVAL:
            _require_installed_on(equipment, machine)
            equipment.state = EquipmentState.REMOVED
            equipment.current_machine = None
        case LogKind.EQUIPMENT_WRITE_OFF:
            if equipment.state == EquipmentState.WRITTEN_OFF:
                raise ValidationError(_("%(equipment)s is already written off.") % {"equipment": equipment})
            if equipment.state == EquipmentState.INSTALLED or machine is not None:
                # Installed equipment is written off together with its machine (ADR-0011).
                _require_installed_on(equipment, machine)
            equipment.state = EquipmentState.WRITTEN_OFF
            equipment.current_machine = None
        case LogKind.SOFTWARE_UPDATE:
            _require_installed_on(equipment, machine)
            if not software_version:
                raise ValidationError(_("Software version is required."))
            if software_version == equipment.software_version:
                raise ValidationError(_("This software version is already installed."))
            entry.software_version = software_version
            equipment.software_version = software_version
        case LogKind.OWNERSHIP_CHANGE:
            if new_owner is None:
                raise ValidationError(_("New owner is required."))
            if new_owner.pk == machine.current_owner_id:
                raise ValidationError(_("This counterparty already owns the machine."))
            entry.new_owner = new_owner
            machine.current_owner = new_owner
            machine_fields = ["current_owner"]
        case LogKind.STATUS_CHANGE:
            if new_status not in Machine.Status.values:
                raise ValidationError(_("New status is required."))
            if new_status == machine.status:
                raise ValidationError(_("The machine already has this status."))
            entry.new_status = new_status
            machine.status = new_status
            machine_fields = ["status"]

    entry.save()
    if machine_fields:
        machine.save(update_fields=machine_fields)
    if equipment is not None:
        equipment.save(update_fields=["state", "current_machine", "software_version"])
    now = timezone.now()
    for issue in issues:
        issue.issue_status = IssueStatus.RESOLVED
        issue.resolved_by = entry
        issue.resolved_at = now
        issue.save(update_fields=["issue_status", "resolved_by", "resolved_at"])
    return entry


def _require_installed_on(equipment, machine):
    if machine is None or equipment.current_machine_id != machine.pk:
        raise ValidationError(_("%(equipment)s is not installed on this machine.") % {"equipment": equipment})


def _reject_unused_fields(kind, **fields):
    used = {
        "equipment": kind in EQUIPMENT_KINDS,
        "software_version": kind in (LogKind.EQUIPMENT_INSTALL, LogKind.SOFTWARE_UPDATE),
        "new_owner": kind == LogKind.OWNERSHIP_CHANGE,
        "new_status": kind == LogKind.STATUS_CHANGE,
        "resolves": kind == LogKind.MAINTENANCE,
    }
    for name, value in fields.items():
        if value and not used[name]:
            raise ValueError(f"{name} is not used by {kind} entries")
