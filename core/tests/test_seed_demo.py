from io import StringIO

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command

from core.models import ContactPerson, Counterparty, Equipment, LogEntry, LogKind, Machine
from core.roles import ENGINEER


@pytest.mark.django_db
def test_append_demo_replays_history_once_and_preserves_existing_data(machine, engineer):
    engineer.groups.add(Group.objects.get(name=ENGINEER))
    existing_machine = Machine.objects.values().get(pk=machine.pk)

    call_command("seed_demo", append=True, author=engineer.username)

    assert Machine.objects.values().get(pk=machine.pk) == existing_machine
    assert not LogEntry.objects.filter(machine=machine).exists()
    assert list(User.objects.values_list("pk", flat=True)) == [engineer.pk]
    demo_machines = Machine.objects.filter(factory_number__startswith="DEMO-")
    assert demo_machines.count() > 25
    assert demo_machines.get(factory_number="DEMO-001").log_entries.count() > 30
    assert not demo_machines.filter(current_owner__isnull=True).exists()

    removal = LogEntry.objects.get(machine__factory_number="DEMO-031", kind=LogKind.EQUIPMENT_REMOVAL)
    transfer = removal.equipment.log_entries.get(
        machine__factory_number="DEMO-032", kind=LogKind.EQUIPMENT_INSTALL
    )
    assert removal.machine.factory_number == "DEMO-031"
    assert removal.event_date < transfer.event_date
    assert transfer.equipment.current_machine == transfer.machine
    assert LogEntry.objects.filter(issue_status="open").exists()
    assert LogEntry.objects.filter(issue_status="resolved", resolved_by__isnull=False).exists()

    tables = (Machine, Counterparty, ContactPerson, Equipment, LogEntry)
    counts = [table.objects.count() for table in tables]
    output = StringIO()
    call_command("seed_demo", append=True, author=engineer.username, stdout=output)
    assert "already present" in output.getvalue()
    assert [table.objects.count() for table in tables] == counts
