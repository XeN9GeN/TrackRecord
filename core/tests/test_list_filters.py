import html
import re
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from core.models import ContactPerson, Counterparty, Equipment, EquipmentType, LogKind, Machine, MachineModel
from core.services import create_log_entry


@pytest.fixture
def directory(engineer):
    owner = Counterparty.objects.create(name="Alpha Rail", region="North", inn="1000000001")
    inactive = Counterparty.objects.create(name="Beta Rail", region="South", inn="2000000002", is_active=False)
    empty = Counterparty.objects.create(name="Gamma Rail")
    model = MachineModel.objects.create(name="Alpha model")
    other_model = MachineModel.objects.create(name="Beta model")
    busy = Machine.objects.create(model=model, factory_number="101")
    old = Machine.objects.create(model=model, factory_number="102")
    unowned = Machine.objects.create(model=model, factory_number="103")
    other = Machine.objects.create(model=other_model, factory_number="201")

    def record(machine, kind, **kwargs):
        return create_log_entry(author=engineer, machine=machine, kind=kind, title="Recorded event", **kwargs)

    for machine, counterparty in ((busy, owner), (old, owner), (other, inactive)):
        record(machine, LogKind.OWNERSHIP_CHANGE, new_owner=counterparty)
    record(busy, LogKind.STATUS_CHANGE, new_status="under_repair")
    record(old, LogKind.STATUS_CHANGE, new_status="in_service")
    record(other, LogKind.STATUS_CHANGE, new_status="under_repair")
    for machine in (busy, busy, other):
        record(machine, LogKind.ISSUE)
    resolved = record(old, LogKind.ISSUE)
    record(old, LogKind.MAINTENANCE, resolves=[resolved])
    controller = EquipmentType.objects.create(name="Controller")
    sensor = EquipmentType.objects.create(name="Sensor")
    for serial, equipment_type, machine in (("CTRL-A", controller, busy), ("CTRL-B", controller, busy), ("S-1", sensor, other)):
        unit = Equipment.objects.create(type=equipment_type, serial_number=serial)
        record(machine, LogKind.EQUIPMENT_INSTALL, equipment=unit)
    Equipment.objects.create(type=controller, serial_number="STOCK-ONLY")
    for number in (1, 2):
        ContactPerson.objects.create(
            counterparty=owner, full_name=f"Bob Engineer {number}",
            phones=f"+7999000000{number}", email=f"bob{number}@example.com",
        )
    ContactPerson.objects.create(counterparty=owner, full_name="Former engineer", is_active=False)
    ContactPerson.objects.create(counterparty=inactive, full_name="Retired engineer", is_active=False)
    recent = timezone.localdate() - timedelta(days=5)
    record(busy, LogKind.REQUEST, event_date=recent)
    record(old, LogKind.REQUEST, event_date=timezone.localdate() - timedelta(days=100))
    record(other, LogKind.REQUEST, event_date=timezone.localdate() - timedelta(days=120))
    return {
        "owner": owner, "inactive": inactive, "empty": empty, "model": model, "other_model": other_model,
        "busy": busy, "old": old, "unowned": unowned, "other": other,
        "controller": controller, "sensor": sensor, "recent": recent,
    }


@pytest.mark.parametrize("query", ["Alpha 101", "CTRL-A", "Controller North", "101 Alpha North"])
def test_machine_search_across_fields(client_logged_in, directory, query):
    response = client_logged_in.get(reverse("core:home"), {"q": query})
    assert response.status_code == 200
    assert list(response.context["machines"]) == [directory["busy"]]
    assert response.context["machines"][0].open_issues == 2


def test_machine_search_excludes_uninstalled_equipment(client_logged_in, engineer, directory):
    unit = Equipment.objects.get(serial_number="CTRL-A")
    create_log_entry(
        author=engineer, machine=directory["busy"], kind=LogKind.EQUIPMENT_REMOVAL,
        title="Removed controller", equipment=unit,
    )
    for query in ("CTRL-A", "STOCK-ONLY", "Alpha South"):
        response = client_logged_in.get(reverse("core:home"), {"q": query})
        assert list(response.context["machines"]) == []


@pytest.mark.parametrize(("filters", "expected"), [
    ({"status": "under_repair"}, ["busy", "other"]),
    ({"model": "other_model"}, ["other"]),
    ({"owner": "owner"}, ["busy", "old"]),
    ({"owner": "unassigned"}, ["unowned"]),
    ({"region": "North"}, ["busy", "old"]),
    ({"issues": "yes"}, ["busy", "other"]),
    ({"issues": "no"}, ["old", "unowned"]),
    ({"equipment": "yes"}, ["busy", "other"]),
    ({"equipment": "no"}, ["old", "unowned"]),
    ({"equipment_type": "controller"}, ["busy"]),
    ({"contact": "never"}, ["unowned"]),
    ({"contact": "overdue"}, ["old", "unowned", "other"]),
    ({"region": "North", "status": "under_repair", "issues": "yes", "equipment_type": "controller"}, ["busy"]),
    ({"owner": "owner", "region": "South"}, []),
    ({"equipment": "no", "equipment_type": "controller"}, []),
])
def test_machine_filters_combine(client_logged_in, directory, filters, expected):
    params = {key: directory[value].pk if value in directory else value for key, value in filters.items()}
    response = client_logged_in.get(reverse("core:home"), params)
    assert response.status_code == 200
    assert not response.context["filter_form"].errors
    assert list(response.context["machines"]) == [directory[key] for key in expected]


@pytest.mark.parametrize("query", ["Bob", "BOB1@EXAMPLE.COM", "+79990000001", "Alpha 101", "Alpha Bob", "101"])
def test_counterparty_search_contacts_and_machines(client_logged_in, directory, query):
    response = client_logged_in.get(reverse("core:counterparty_list"), {"q": query})
    assert list(response.context["counterparties"]) == [directory["owner"]]
    owner = response.context["counterparties"][0]
    assert owner.machine_count == 2
    assert owner.active_contact_count == 2
    assert timezone.localdate(owner.last_contact_at) == directory["recent"]
    assert "notes" in owner.get_deferred_fields()


@pytest.mark.parametrize("query", ["Former", "Retired", "Beta Bob", "Alpha 201"])
def test_counterparty_search_requires_every_term_and_active_contacts(client_logged_in, directory, query):
    response = client_logged_in.get(reverse("core:counterparty_list"), {"q": query})
    assert list(response.context["counterparties"]) == []


@pytest.mark.parametrize(("filters", "expected"), [
    ({"activity": "active"}, ["owner", "empty"]),
    ({"activity": "inactive"}, ["inactive"]),
    ({"region": "South"}, ["inactive"]),
    ({"machines": "yes"}, ["owner", "inactive"]),
    ({"machines": "no"}, ["empty"]),
    ({"contacts": "yes"}, ["owner"]),
    ({"contacts": "no"}, ["inactive", "empty"]),
    ({"contact": "never"}, ["empty"]),
    ({"contact": "overdue"}, ["inactive", "empty"]),
    ({"activity": "active", "machines": "yes", "contacts": "yes", "region": "North"}, ["owner"]),
    ({"machines": "no", "contacts": "yes"}, []),
])
def test_counterparty_filters_combine(client_logged_in, directory, filters, expected):
    response = client_logged_in.get(reverse("core:counterparty_list"), filters)
    assert response.status_code == 200
    assert not response.context["filter_form"].errors
    assert list(response.context["counterparties"]) == [directory[key] for key in expected]


def test_directory_filters_follow_current_owner(client_logged_in, engineer, directory):
    create_log_entry(
        author=engineer, machine=directory["busy"], kind=LogKind.OWNERSHIP_CHANGE,
        title="Transferred", new_owner=directory["inactive"],
    )
    owner = client_logged_in.get(reverse("core:counterparty_list"), {"q": "101"})
    assert list(owner.context["counterparties"]) == [directory["inactive"]]
    assert owner.context["counterparties"][0].machine_count == 2
    machines = client_logged_in.get(reverse("core:home"), {"owner": directory["owner"].pk})
    assert list(machines.context["machines"]) == [directory["old"]]


@pytest.mark.parametrize(("route", "context_name", "expected"), [
    ("home", "machines", ["busy"]),
    ("counterparty_list", "counterparties", ["owner"]),
])
def test_last_contact_date_range_is_inclusive(client_logged_in, directory, route, context_name, expected):
    day = directory["recent"].isoformat()
    response = client_logged_in.get(reverse(f"core:{route}"), {"contact_from": day, "contact_to": day})
    assert not response.context["filter_form"].errors
    assert list(response.context[context_name]) == [directory[key] for key in expected]


def test_overdue_contact_includes_the_90_day_boundary(client_logged_in, engineer, directory):
    for machine, days in ((directory["old"], 90), (directory["other"], 89)):
        create_log_entry(
            author=engineer, machine=machine, kind=LogKind.REQUEST, title="Follow-up call",
            event_date=timezone.localdate() - timedelta(days=days),
        )
    response = client_logged_in.get(reverse("core:home"), {"contact": "overdue"})
    assert list(response.context["machines"]) == [directory["old"], directory["unowned"]]


@pytest.mark.parametrize(("sort", "direction", "expected"), [
    ("machine", "asc", ["busy", "old", "unowned", "other"]),
    ("machine", "desc", ["other", "unowned", "old", "busy"]),
    ("number", "desc", ["other", "unowned", "old", "busy"]),
    ("owner", "asc", ["busy", "old", "other", "unowned"]),
    ("region", "desc", ["other", "old", "busy", "unowned"]),
    ("issues", "desc", ["busy", "other", "unowned", "old"]),
    ("contact", "asc", ["other", "old", "busy", "unowned"]),
    ("contact", "desc", ["busy", "old", "other", "unowned"]),
])
def test_machine_sorting(client_logged_in, directory, sort, direction, expected):
    response = client_logged_in.get(reverse("core:home"), {"sort": sort, "direction": direction})
    assert list(response.context["machines"]) == [directory[key] for key in expected]


@pytest.mark.parametrize(("sort", "direction", "expected"), [
    ("name", "desc", ["empty", "inactive", "owner"]),
    ("inn", "asc", ["owner", "inactive", "empty"]),
    ("region", "desc", ["inactive", "owner", "empty"]),
    ("machines", "desc", ["owner", "inactive", "empty"]),
    ("contacts", "desc", ["owner", "empty", "inactive"]),
    ("contact", "asc", ["inactive", "owner", "empty"]),
    ("contact", "desc", ["owner", "inactive", "empty"]),
])
def test_counterparty_sorting(client_logged_in, directory, sort, direction, expected):
    response = client_logged_in.get(reverse("core:counterparty_list"), {"sort": sort, "direction": direction})
    assert list(response.context["counterparties"]) == [directory[key] for key in expected]


@pytest.mark.parametrize(("route", "context_name", "expected"), [
    ("home", "machines", ["busy", "old"]),
    ("counterparty_list", "counterparties", ["owner"]),
])
def test_removing_one_filter_keeps_other_filters_and_sorting(client_logged_in, directory, route, context_name, expected):
    params = {
        "q": "Alpha", "region": "North", "contact": "overdue",
        "sort": "contact", "direction": "desc", "per_page": "50", "page": "3",
    }
    if route == "home":
        params.update(model=str(directory["model"].pk), owner=str(directory["owner"].pk))
    else:
        params["machines"] = "yes"
    url = reverse(f"core:{route}")
    response = client_logged_in.get(url, params)
    chips = {item["name"]: item for item in response.context["active_filters"]}
    assert set(chips) == set(params) - {"sort", "direction", "per_page", "page"}
    assert response.context["additional_filter_count"] == 1
    assert chips["contact"]["value"] == _("No contact in 90 days")
    if route == "home":
        assert chips["model"]["value"] == directory["model"].name
        assert chips["owner"]["value"] == directory["owner"].name
    else:
        assert chips["machines"]["value"] == _("With machines")
    link = chips["contact"]["url"]
    expected_params = {key: [value] for key, value in params.items() if key not in {"contact", "page"}}
    assert parse_qs(urlsplit(link).query) == expected_params
    assert html.escape(link, quote=True) in response.content.decode()
    unfiltered = client_logged_in.get(url + link)
    assert unfiltered.context["page"].number == 1
    assert list(unfiltered.context[context_name]) == [directory[key] for key in expected]


@pytest.mark.parametrize("route", ["home", "counterparty_list"])
def test_removing_last_filter_returns_to_unfiltered_list(client_logged_in, directory, route):
    url = reverse(f"core:{route}")
    response = client_logged_in.get(url, {"q": "Alpha"})
    chip, = response.context["active_filters"]
    assert chip["url"] == "?"
    cleared = client_logged_in.get(url + chip["url"])
    assert cleared.context["active_filters"] == []
    assert cleared.context["page"].paginator.count == (4 if route == "home" else 3)


@pytest.mark.parametrize(("route", "context_name"), [("home", "machines"), ("counterparty_list", "counterparties")])
def test_invalid_filter_values_are_reported(client_logged_in, directory, route, context_name):
    params = {
        "region": "missing", "sort": "text__invalid", "direction": "invalid", "per_page": "100000000",
        "contact": "invalid", "contact_from": "bad date", "contact_to": "2026-99-99", "page": "bad page",
    }
    if route == "home":
        params.update(status="invalid", owner="not-an-id", model="bad-id", equipment_type="bad-id")
    else:
        params.update(activity="invalid", machines="invalid", contacts="invalid")
    response = client_logged_in.get(reverse(f"core:{route}"), params)
    assert response.status_code == 200
    form = response.context["filter_form"]
    assert set(form.errors) == set(params) - {"page"}
    assert response.context["page"].number == 1
    assert response.context["page"].paginator.per_page == 25
    assert len(response.context[context_name]) == (4 if route == "home" else 3)


@pytest.mark.parametrize("route", ["home", "counterparty_list"])
def test_reversed_contact_dates_show_error_and_keep_other_filters(client_logged_in, directory, route):
    response = client_logged_in.get(reverse(f"core:{route}"), {
        "region": "North", "contact_from": "2026-10-10", "contact_to": "2026-01-01",
    })
    assert response.status_code == 200
    assert response.context["filter_form"].non_field_errors()
    assert response.context["page"].paginator.count == (2 if route == "home" else 1)


@pytest.mark.parametrize(("route", "context_name"), [
    ("home", "machines"), ("counterparty_list", "counterparties"), ("equipment_list", "equipment"),
])
def test_listing_pagination_preserves_filters_and_sorting(client_logged_in, db, route, context_name):
    if route == "home":
        model = MachineModel.objects.create(name="Paged & model")
        records = Machine.objects.bulk_create([
            Machine(model=model, factory_number=f"{number:03}") for number in range(55)
        ])
        params = {"q": "Paged &", "status": "unknown", "sort": "number", "direction": "desc", "per_page": 25}
    elif route == "equipment_list":
        equipment_type = EquipmentType.objects.create(name="Paged & type")
        records = Equipment.objects.bulk_create([
            Equipment(type=equipment_type, serial_number=f"{number:03}") for number in range(55)
        ])
        params = {"q": "Paged &", "state": "in_stock", "sort": "serial", "direction": "desc", "per_page": 25}
    else:
        records = Counterparty.objects.bulk_create([
            Counterparty(name=f"Paged & customer {number:03}") for number in range(55)
        ])
        params = {"q": "Paged &", "activity": "active", "sort": "name", "direction": "desc", "per_page": 25}
    url = reverse(f"core:{route}")
    first = client_logged_in.get(url, params)
    second = client_logged_in.get(url, {**params, "page": 2})
    last = client_logged_in.get(url, {**params, "page": 999999})
    assert list(first.context[context_name]) == list(reversed(records[30:]))
    assert list(second.context[context_name]) == list(reversed(records[5:30]))
    assert list(last.context[context_name]) == list(reversed(records[:5]))
    assert first.context["page"].paginator.count == 55
    assert last.context["page"].number == 3
    links = [parse_qs(urlsplit(html.unescape(link)).query) for link in re.findall(r'href="([^"]+)"', first.content.decode())]
    next_page = next(link for link in links if link.get("page") == ["2"])
    assert next_page == {**{key: [str(value)] for key, value in params.items()}, "page": ["2"]}
    larger_page = client_logged_in.get(url, {**params, "per_page": 100})
    assert len(larger_page.context[context_name]) == 55
    assert larger_page.context["page"].paginator.num_pages == 1


@pytest.mark.parametrize(("filters", "serials"), [
    ({"type": "controller"}, ["CTRL-A", "CTRL-B", "STOCK-ONLY"]),
    ({"machine": "busy"}, ["CTRL-A", "CTRL-B"]),
    ({"owner": "owner"}, ["CTRL-A", "CTRL-B"]),
    ({"state": "installed"}, ["CTRL-A", "CTRL-B", "S-1"]),
    ({"state": "in_stock"}, ["STOCK-ONLY"]),
    ({"type": "sensor", "owner": "owner"}, []),
    ({"type": "controller", "machine": "busy", "owner": "owner", "state": "installed"}, ["CTRL-A", "CTRL-B"]),
    ({"q": "Alpha Controller"}, ["CTRL-A", "CTRL-B"]),
    ({"q": "Alpha S-1"}, []),
])
def test_equipment_directory_filters(client_logged_in, directory, filters, serials):
    params = {key: directory[value].pk if value in directory else value for key, value in filters.items()}
    response = client_logged_in.get(reverse("core:equipment_list"), params)
    assert not response.context["filter_form"].errors
    assert [unit.serial_number for unit in response.context["equipment"]] == serials


@pytest.mark.parametrize(("sort", "direction", "serials"), [
    ("serial", "desc", ["STOCK-ONLY", "S-1", "CTRL-B", "CTRL-A"]),
    ("type", "desc", ["S-1", "STOCK-ONLY", "CTRL-B", "CTRL-A"]),
    ("machine", "asc", ["CTRL-A", "CTRL-B", "S-1", "STOCK-ONLY"]),
    ("machine", "desc", ["S-1", "CTRL-B", "CTRL-A", "STOCK-ONLY"]),
    ("owner", "asc", ["CTRL-A", "CTRL-B", "S-1", "STOCK-ONLY"]),
    ("owner", "desc", ["S-1", "CTRL-B", "CTRL-A", "STOCK-ONLY"]),
])
def test_equipment_directory_sorting(client_logged_in, directory, sort, direction, serials):
    response = client_logged_in.get(reverse("core:equipment_list"), {"sort": sort, "direction": direction})
    assert [unit.serial_number for unit in response.context["equipment"]] == serials


def test_equipment_invalid_filters_keep_valid_conditions(client_logged_in, directory):
    params = {"type": "missing", "machine": "missing", "owner": "missing", "sort": "missing", "state": "in_stock"}
    response = client_logged_in.get(reverse("core:equipment_list"), params)
    assert set(response.context["filter_form"].errors) == {"type", "machine", "owner", "sort"}
    assert [unit.serial_number for unit in response.context["equipment"]] == ["STOCK-ONLY"]
