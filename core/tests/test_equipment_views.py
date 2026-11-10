import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils.translation import gettext as _

from core.models import Equipment, EquipmentState, EquipmentType, LogKind
from core.roles import ADMINISTRATOR
from core.services import create_log_entry


@pytest.fixture
def other_equipment(db):
    sensor = EquipmentType.objects.create(name="Sensor")
    return Equipment.objects.create(type=sensor, serial_number="S-2002")


def test_equipment_pages_require_login(client, equipment):
    for url in (reverse("core:equipment_list"), reverse("core:equipment_detail", args=[equipment.pk])):
        response = client.get(url)
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))


def test_equipment_list_includes_stock_and_installed_units(
    client_logged_in, engineer, equipment, other_equipment, machine, counterparty
):
    create_log_entry(
        author=engineer, machine=machine, kind=LogKind.OWNERSHIP_CHANGE, title="Bought", new_owner=counterparty
    )
    create_log_entry(
        author=engineer, machine=machine, kind=LogKind.EQUIPMENT_INSTALL,
        title="Installed controller", equipment=equipment, software_version="3.2",
    )
    response = client_logged_in.get(reverse("core:equipment_list"))
    assert response.status_code == 200
    assert list(response.context["equipment"]) == [equipment, other_equipment]
    content = response.content.decode()
    assert "3.2" in content
    assert "2023" in content
    assert str(EquipmentState.IN_STOCK.label) in content
    for view, pk in (
        ("equipment_detail", equipment.pk), ("equipment_detail", other_equipment.pk),
        ("machine_detail", machine.pk), ("counterparty_detail", counterparty.pk),
    ):
        assert reverse(f"core:{view}", args=[pk]) in content


@pytest.mark.parametrize("query", ["1001", "controller", "duomatic", "67", "track service", "  C-1001  "])
def test_equipment_search(
    client_logged_in, engineer, equipment, other_equipment, machine, counterparty, query
):
    create_log_entry(
        author=engineer, machine=machine, kind=LogKind.OWNERSHIP_CHANGE, title="Bought", new_owner=counterparty
    )
    create_log_entry(
        author=engineer, machine=machine, kind=LogKind.EQUIPMENT_INSTALL, title="Installed", equipment=equipment
    )
    response = client_logged_in.get(reverse("core:equipment_list"), {"q": query})
    assert list(response.context["equipment"]) == [equipment]
    assert response.context["query"] == query.strip()


def test_equipment_search_in_stock(client_logged_in, equipment, other_equipment):
    response = client_logged_in.get(reverse("core:equipment_list"), {"q": "C-1001"})
    assert list(response.context["equipment"]) == [equipment]


def test_equipment_state_filter_preserves_search(client_logged_in, engineer, equipment, other_equipment, machine):
    create_log_entry(
        author=engineer, machine=machine, kind=LogKind.EQUIPMENT_INSTALL, title="Installed", equipment=equipment
    )
    url = reverse("core:equipment_list")
    installed = client_logged_in.get(url, {"state": "installed", "q": "C-1001"})
    stock = client_logged_in.get(url, {"state": "in_stock"})
    empty = client_logged_in.get(url, {"state": "in_stock", "q": "C-1001"})
    assert list(installed.context["equipment"]) == [equipment]
    assert list(stock.context["equipment"]) == [other_equipment]
    assert list(empty.context["equipment"]) == []
    assert installed.context["filter_form"]["state"].value() == "installed"
    assert {item["name"] for item in installed.context["active_filters"]} == {"q", "state"}
    assert 'href="?q=C-1001"' in installed.content.decode()
    assert _("No equipment found.") in empty.content.decode()


def test_equipment_invalid_state_is_reported(client_logged_in, equipment):
    response = client_logged_in.get(reverse("core:equipment_list"), {"state": "missing"})
    assert list(response.context["equipment"]) == [equipment]
    assert "state" in response.context["filter_form"].errors


def test_equipment_card_shows_current_state_and_own_history(
    client_logged_in, engineer, equipment, other_equipment, machine, counterparty
):
    create_log_entry(
        author=engineer, machine=machine, kind=LogKind.OWNERSHIP_CHANGE, title="Bought", new_owner=counterparty
    )
    installation = create_log_entry(
        author=engineer, machine=machine, kind=LogKind.EQUIPMENT_INSTALL,
        title="Installed controller", equipment=equipment, software_version="3.2",
    )
    update = create_log_entry(
        author=engineer, machine=machine, kind=LogKind.SOFTWARE_UPDATE,
        title="Updated controller", equipment=equipment, software_version="4.0",
        text="**Restart required**\n\n<script>alert(1)</script>",
    )
    unrelated = create_log_entry(
        author=engineer, machine=machine, kind=LogKind.EQUIPMENT_INSTALL,
        title="Installed sensor", equipment=other_equipment,
    )
    response = client_logged_in.get(reverse("core:equipment_detail", args=[equipment.pk]))
    assert response.status_code == 200
    assert response.context["equipment"].state == EquipmentState.INSTALLED
    assert response.context["equipment"].software_version == "4.0"
    assert response.context["equipment"].current_machine == machine
    assert list(response.context["page"]) == [update, installation]
    content = response.content.decode()
    for value in (equipment.serial_number, equipment.type.name, "2023", "4.0", counterparty.region):
        assert value in content
    assert reverse("core:machine_detail", args=[machine.pk]) in content
    assert reverse("core:counterparty_detail", args=[counterparty.pk]) in content
    assert reverse("core:log_entry_detail", args=[update.pk]) in content
    assert unrelated.title not in content
    assert "<strong>Restart required</strong>" in content
    assert "<script>" not in content
    assert "&lt;script&gt;" in content


def test_equipment_card_tracks_moves_between_machines(
    client_logged_in, engineer, equipment, machine, other_machine
):
    installation = create_log_entry(
        author=engineer, machine=machine, kind=LogKind.EQUIPMENT_INSTALL, title="Installed", equipment=equipment
    )
    removal = create_log_entry(
        author=engineer, machine=machine, kind=LogKind.EQUIPMENT_REMOVAL, title="Removed", equipment=equipment
    )
    url = reverse("core:equipment_detail", args=[equipment.pk])
    removed = client_logged_in.get(url)
    assert removed.context["equipment"].state == EquipmentState.REMOVED
    assert removed.context["equipment"].current_machine is None
    assert _("Not installed on a machine.") in removed.content.decode()
    reinstallation = create_log_entry(
        author=engineer, machine=other_machine, kind=LogKind.EQUIPMENT_INSTALL,
        title="Reinstalled", equipment=equipment,
    )
    response = client_logged_in.get(url)
    assert response.context["equipment"].current_machine == other_machine
    assert list(response.context["page"]) == [reinstallation, removal, installation]
    for current_machine in (machine, other_machine):
        assert reverse("core:machine_detail", args=[current_machine.pk]) in response.content.decode()


def test_equipment_location_follows_machine_ownership(
    client_logged_in, engineer, equipment, machine, counterparty, other_counterparty
):
    create_log_entry(
        author=engineer, machine=machine, kind=LogKind.OWNERSHIP_CHANGE, title="Bought", new_owner=counterparty
    )
    create_log_entry(
        author=engineer, machine=machine, kind=LogKind.EQUIPMENT_INSTALL, title="Installed", equipment=equipment
    )
    create_log_entry(
        author=engineer, machine=machine, kind=LogKind.OWNERSHIP_CHANGE,
        title="Transferred", new_owner=other_counterparty,
    )
    response = client_logged_in.get(reverse("core:equipment_detail", args=[equipment.pk]))
    assert reverse("core:counterparty_detail", args=[other_counterparty.pk]) in response.content.decode()
    assert reverse("core:counterparty_detail", args=[counterparty.pk]) not in response.content.decode()
    previous_owner = client_logged_in.get(reverse("core:equipment_list"), {"q": counterparty.name})
    current_owner = client_logged_in.get(reverse("core:equipment_list"), {"q": other_counterparty.name})
    assert list(previous_owner.context["equipment"]) == []
    assert list(current_owner.context["equipment"]) == [equipment]


def test_equipment_write_off_without_machine(client_logged_in, engineer, equipment):
    entry = create_log_entry(
        author=engineer, kind=LogKind.EQUIPMENT_WRITE_OFF, title="Written off in stock", equipment=equipment
    )
    response = client_logged_in.get(reverse("core:equipment_detail", args=[equipment.pk]))
    assert response.status_code == 200
    assert response.context["equipment"].state == EquipmentState.WRITTEN_OFF
    assert list(response.context["page"]) == [entry]
    assert _("Not installed on a machine.") in response.content.decode()
    written_off = client_logged_in.get(reverse("core:equipment_list"), {"state": "written_off"})
    assert list(written_off.context["equipment"]) == [equipment]
    entry_page = client_logged_in.get(reverse("core:log_entry_detail", args=[entry.pk]))
    assert entry_page.status_code == 200
    assert reverse("core:equipment_detail", args=[equipment.pk]) in entry_page.content.decode()


def test_equipment_empty_history(client_logged_in, equipment):
    response = client_logged_in.get(reverse("core:equipment_detail", args=[equipment.pk]))
    assert response.status_code == 200
    assert list(response.context["page"]) == []
    assert _("No entries yet.") in response.content.decode()
    assert _("Not installed on a machine.") in response.content.decode()
    assert reverse("admin:core_equipment_change", args=[equipment.pk]) not in response.content.decode()


def test_equipment_history_filter_and_pagination(client_logged_in, engineer, equipment, machine):
    installation = create_log_entry(
        author=engineer, machine=machine, kind=LogKind.EQUIPMENT_INSTALL, title="Installed", equipment=equipment
    )
    updates = [
        create_log_entry(
            author=engineer, machine=machine, kind=LogKind.SOFTWARE_UPDATE,
            title=f"Update {version}", equipment=equipment, software_version=str(version),
        )
        for version in range(1, 32)
    ]
    url = reverse("core:equipment_detail", args=[equipment.pk])
    first = client_logged_in.get(url, {"kind": "software_update"})
    second = client_logged_in.get(url, {"kind": "software_update", "page": 2})
    assert list(first.context["page"]) == list(reversed(updates[1:]))
    assert list(second.context["page"]) == [updates[0]]
    assert first.context["page"].paginator.count == 31
    assert "kind=software_update&amp;page=2" in first.content.decode()
    invalid = client_logged_in.get(url, {"kind": "missing", "page": "invalid"})
    assert invalid.context["selected_kind"] == ""
    assert invalid.context["page"].number == 1
    assert invalid.context["page"].paginator.count == 32
    assert installation not in first.context["page"]


def test_equipment_links_and_administration(client_logged_in, engineer, equipment, machine):
    entry = create_log_entry(
        author=engineer, machine=machine, kind=LogKind.EQUIPMENT_INSTALL, title="Installed", equipment=equipment
    )
    for url in (reverse("core:machine_detail", args=[machine.pk]), reverse("core:log_entry_detail", args=[entry.pk])):
        response = client_logged_in.get(url)
        assert reverse("core:equipment_detail", args=[equipment.pk]) in response.content.decode()
        assert reverse("core:equipment_list") in response.content.decode()
    engineer.is_staff = True
    engineer.save()
    engineer.groups.add(Group.objects.get(name=ADMINISTRATOR))
    directory = client_logged_in.get(reverse("core:equipment_list"))
    detail = client_logged_in.get(reverse("core:equipment_detail", args=[equipment.pk]))
    assert reverse("admin:core_equipment_add") in directory.content.decode()
    assert reverse("admin:core_equipment_change", args=[equipment.pk]) in detail.content.decode()


def test_equipment_not_found(client_logged_in):
    assert client_logged_in.get(reverse("core:equipment_detail", args=[999999])).status_code == 404
