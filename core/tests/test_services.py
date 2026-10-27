import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from core.models import EquipmentState, IssueStatus, LogEntry, LogKind, MachineStatus
from core.services import create_log_entry, normalize_text


def install(engineer, machine, equipment, version="1.0"):
    return create_log_entry(
        author=engineer,
        machine=machine,
        kind=LogKind.EQUIPMENT_INSTALL,
        title="Installed",
        equipment=equipment,
        software_version=version,
    )


class TestNormalizeText:
    def test_line_endings_and_trailing_spaces(self):
        assert normalize_text("a  \r\nb\rc\n\n") == "a\nb\nc"

    def test_unicode_nfc(self):
        assert normalize_text("ё") == "ё"

    def test_keeps_inner_blank_lines_and_indent(self):
        assert normalize_text("\n\n  - a\n\n  - b\n") == "  - a\n\n  - b"

    def test_none_is_empty(self):
        assert normalize_text(None) == ""


class TestCommon:
    def test_entry_keeps_owner_snapshot_and_normalized_text(self, engineer, machine, counterparty):
        create_log_entry(
            author=engineer, machine=machine, kind=LogKind.OWNERSHIP_CHANGE, title="Bought", new_owner=counterparty
        )
        entry = create_log_entry(
            author=engineer, machine=machine, kind=LogKind.DOCUMENT, title="  Contract ", text="line\r\n"
        )
        assert entry.owner_snapshot == counterparty
        assert entry.title == "Contract"
        assert entry.text == "line"

    def test_title_required(self, engineer, machine):
        with pytest.raises(ValidationError):
            create_log_entry(author=engineer, machine=machine, kind=LogKind.DOCUMENT, title="  ")

    def test_machine_required(self, engineer):
        with pytest.raises(ValidationError):
            create_log_entry(author=engineer, kind=LogKind.REQUEST, title="Call")

    def test_future_event_date_rejected(self, engineer, machine):
        with pytest.raises(ValidationError):
            create_log_entry(
                author=engineer,
                machine=machine,
                kind=LogKind.REQUEST,
                title="Call",
                event_date=timezone.localdate() + datetime.timedelta(days=1),
            )

    def test_unused_field_is_a_programming_error(self, engineer, machine, counterparty):
        with pytest.raises(ValueError):
            create_log_entry(
                author=engineer, machine=machine, kind=LogKind.REQUEST, title="Call", new_owner=counterparty
            )

    def test_request_updates_last_contact(self, engineer, machine):
        create_log_entry(author=engineer, machine=machine, kind=LogKind.REQUEST, title="Asked about price")
        machine.refresh_from_db()
        assert machine.last_contact_at is not None

    def test_document_does_not_touch_machine_history(self, engineer, machine):
        create_log_entry(author=engineer, machine=machine, kind=LogKind.DOCUMENT, title="Manual")
        assert machine.history.count() == 1


class TestIssues:
    def test_issue_is_open(self, engineer, machine):
        issue = create_log_entry(author=engineer, machine=machine, kind=LogKind.ISSUE, title="Stalls while moving")
        assert issue.is_issue
        assert issue.issue_status == IssueStatus.OPEN

    def test_maintenance_resolves_selected_issues(self, engineer, machine):
        first = create_log_entry(author=engineer, machine=machine, kind=LogKind.ISSUE, title="A")
        second = create_log_entry(author=engineer, machine=machine, kind=LogKind.ISSUE, title="B")
        fix = create_log_entry(
            author=engineer, machine=machine, kind=LogKind.MAINTENANCE, title="Fixed A", resolves=[first]
        )
        first.refresh_from_db()
        second.refresh_from_db()
        assert first.issue_status == IssueStatus.RESOLVED
        assert first.resolved_by == fix
        assert first.resolved_at is not None
        assert second.issue_status == IssueStatus.OPEN

    def test_cannot_resolve_issue_of_another_machine(self, engineer, machine, other_machine):
        issue = create_log_entry(author=engineer, machine=other_machine, kind=LogKind.ISSUE, title="A")
        with pytest.raises(ValidationError):
            create_log_entry(author=engineer, machine=machine, kind=LogKind.MAINTENANCE, title="Fix", resolves=[issue])

    def test_cannot_resolve_twice(self, engineer, machine):
        issue = create_log_entry(author=engineer, machine=machine, kind=LogKind.ISSUE, title="A")
        create_log_entry(author=engineer, machine=machine, kind=LogKind.MAINTENANCE, title="Fix", resolves=[issue])
        with pytest.raises(ValidationError):
            create_log_entry(author=engineer, machine=machine, kind=LogKind.MAINTENANCE, title="Again", resolves=[issue])


class TestEquipment:
    def test_install(self, engineer, machine, equipment):
        entry = install(engineer, machine, equipment, "2.4.1")
        equipment.refresh_from_db()
        assert equipment.state == EquipmentState.INSTALLED
        assert equipment.current_machine == machine
        assert equipment.software_version == "2.4.1"
        assert entry.software_version == "2.4.1"

    def test_install_keeps_current_version_when_not_given(self, engineer, machine, equipment):
        equipment.software_version = "1.7"
        equipment.save()
        entry = install(engineer, machine, equipment, version=None)
        assert entry.software_version == "1.7"

    def test_cannot_install_on_two_machines(self, engineer, machine, other_machine, equipment):
        install(engineer, machine, equipment)
        with pytest.raises(ValidationError):
            install(engineer, other_machine, equipment)

    def test_removal_only_from_its_machine(self, engineer, machine, other_machine, equipment):
        install(engineer, machine, equipment)
        with pytest.raises(ValidationError):
            create_log_entry(
                author=engineer,
                machine=other_machine,
                kind=LogKind.EQUIPMENT_REMOVAL,
                title="Removed",
                equipment=equipment,
            )
        create_log_entry(
            author=engineer, machine=machine, kind=LogKind.EQUIPMENT_REMOVAL, title="Removed", equipment=equipment
        )
        equipment.refresh_from_db()
        assert equipment.state == EquipmentState.REMOVED
        assert equipment.current_machine is None

    def test_removed_equipment_can_be_reinstalled_elsewhere(self, engineer, machine, other_machine, equipment):
        install(engineer, machine, equipment)
        create_log_entry(
            author=engineer, machine=machine, kind=LogKind.EQUIPMENT_REMOVAL, title="Removed", equipment=equipment
        )
        install(engineer, other_machine, equipment)
        equipment.refresh_from_db()
        assert equipment.current_machine == other_machine

    def test_software_update(self, engineer, machine, equipment):
        install(engineer, machine, equipment, "1.0")
        create_log_entry(
            author=engineer,
            machine=machine,
            kind=LogKind.SOFTWARE_UPDATE,
            title="Updated",
            equipment=equipment,
            software_version="1.1",
        )
        equipment.refresh_from_db()
        assert equipment.software_version == "1.1"

    def test_software_update_requires_new_version(self, engineer, machine, equipment):
        install(engineer, machine, equipment, "1.0")
        for version in (None, "1.0"):
            with pytest.raises(ValidationError):
                create_log_entry(
                    author=engineer,
                    machine=machine,
                    kind=LogKind.SOFTWARE_UPDATE,
                    title="Updated",
                    equipment=equipment,
                    software_version=version,
                )

    def test_write_off_from_stock_without_machine(self, engineer, equipment):
        entry = create_log_entry(
            author=engineer, kind=LogKind.EQUIPMENT_WRITE_OFF, title="Broken", equipment=equipment
        )
        equipment.refresh_from_db()
        assert entry.machine is None
        assert equipment.state == EquipmentState.WRITTEN_OFF

    def test_write_off_installed_requires_its_machine(self, engineer, machine, equipment):
        install(engineer, machine, equipment)
        with pytest.raises(ValidationError):
            create_log_entry(author=engineer, kind=LogKind.EQUIPMENT_WRITE_OFF, title="Broken", equipment=equipment)
        create_log_entry(
            author=engineer, machine=machine, kind=LogKind.EQUIPMENT_WRITE_OFF, title="Broken", equipment=equipment
        )
        equipment.refresh_from_db()
        assert equipment.state == EquipmentState.WRITTEN_OFF
        assert equipment.current_machine is None

    def test_written_off_cannot_be_installed(self, engineer, machine, equipment):
        create_log_entry(author=engineer, kind=LogKind.EQUIPMENT_WRITE_OFF, title="Broken", equipment=equipment)
        with pytest.raises(ValidationError):
            install(engineer, machine, equipment)


class TestMachineState:
    def test_ownership_change(self, engineer, machine, counterparty, other_counterparty):
        create_log_entry(
            author=engineer, machine=machine, kind=LogKind.OWNERSHIP_CHANGE, title="Bought", new_owner=counterparty
        )
        sold = create_log_entry(
            author=engineer,
            machine=machine,
            kind=LogKind.OWNERSHIP_CHANGE,
            title="Sold",
            new_owner=other_counterparty,
        )
        machine.refresh_from_db()
        assert machine.current_owner == other_counterparty
        assert sold.owner_snapshot == counterparty

    def test_ownership_change_to_same_owner_rejected(self, engineer, machine, counterparty):
        create_log_entry(
            author=engineer, machine=machine, kind=LogKind.OWNERSHIP_CHANGE, title="Bought", new_owner=counterparty
        )
        with pytest.raises(ValidationError):
            create_log_entry(
                author=engineer, machine=machine, kind=LogKind.OWNERSHIP_CHANGE, title="Again", new_owner=counterparty
            )

    def test_status_change(self, engineer, machine):
        create_log_entry(
            author=engineer,
            machine=machine,
            kind=LogKind.STATUS_CHANGE,
            title="Repair",
            new_status=MachineStatus.UNDER_REPAIR,
        )
        machine.refresh_from_db()
        assert machine.status == MachineStatus.UNDER_REPAIR

    def test_status_change_requires_valid_new_status(self, engineer, machine):
        for status in (None, "flying", machine.status):
            with pytest.raises(ValidationError):
                create_log_entry(
                    author=engineer, machine=machine, kind=LogKind.STATUS_CHANGE, title="?", new_status=status
                )


class TestDatabaseConstraints:
    """The database rejects inconsistent rows even if the service is bypassed."""

    def test_equipment_entry_requires_equipment(self, engineer, machine):
        with pytest.raises(IntegrityError):
            LogEntry.objects.create(author=engineer, machine=machine, kind=LogKind.EQUIPMENT_INSTALL, title="x")

    def test_installed_equipment_requires_machine(self, equipment):
        equipment.state = EquipmentState.INSTALLED
        with pytest.raises(IntegrityError):
            equipment.save()

    def test_only_write_off_may_have_no_machine(self, engineer):
        with pytest.raises(IntegrityError):
            LogEntry.objects.create(author=engineer, kind=LogKind.REQUEST, title="x")
