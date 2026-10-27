import pytest
from django.contrib.auth.models import User

from core.models import Counterparty, Equipment, EquipmentType, Machine, MachineModel


@pytest.fixture
def engineer(db):
    return User.objects.create_user("engineer", password="secret-pass-1")


@pytest.fixture
def counterparty(db):
    return Counterparty.objects.create(name="Track Service LLC", region="Western Kazakhstan")


@pytest.fixture
def other_counterparty(db):
    return Counterparty.objects.create(name="Rail Repair JSC")


@pytest.fixture
def machine(db):
    model = MachineModel.objects.create(name="Duomatic 09-32 CSM", manufacturer="Plasser & Theurer")
    return Machine.objects.create(model=model, factory_number="67")


@pytest.fixture
def other_machine(machine):
    return Machine.objects.create(model=machine.model, factory_number="68")


@pytest.fixture
def equipment(db):
    controller = EquipmentType.objects.create(name="Controller")
    return Equipment.objects.create(type=controller, serial_number="C-1001", production_year=2023)
