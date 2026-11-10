from datetime import date

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils.translation import gettext as _

from core.models import ContactPerson, LogKind, MachineStatus
from core.roles import ADMINISTRATOR, ENGINEER
from core.services import create_log_entry


@pytest.fixture
def client_logged_in(client, engineer):
    engineer.groups.add(Group.objects.get(name=ENGINEER))
    client.force_login(engineer)
    return client


def test_pages_require_login(client, machine, counterparty):
    for url in (
        reverse("core:home"),
        reverse("core:machine_detail", args=[machine.pk]),
        reverse("core:counterparty_list"),
        reverse("core:counterparty_detail", args=[counterparty.pk]),
    ):
        response = client.get(url)
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))


def test_counterparty_list_shows_machine_counts(
    client_logged_in, engineer, machine, other_machine, counterparty, other_counterparty
):
    for owned_machine in (machine, other_machine):
        create_log_entry(
            author=engineer, machine=owned_machine, kind=LogKind.OWNERSHIP_CHANGE,
            title="Bought", new_owner=counterparty,
        )
    create_log_entry(author=engineer, machine=machine, kind=LogKind.ISSUE, title="Stalls")
    response = client_logged_in.get(reverse("core:counterparty_list"))
    assert response.status_code == 200
    assert [(item.pk, item.machine_count) for item in response.context["counterparties"]] == [
        (other_counterparty.pk, 0), (counterparty.pk, 2),
    ]
    assert reverse("core:counterparty_detail", args=[counterparty.pk]) in response.content.decode()


@pytest.mark.parametrize("query", ["track service", "kazakhstan", "123456", "  Track Service  "])
def test_counterparty_search(client_logged_in, counterparty, other_counterparty, query):
    counterparty.inn = "123456789012"
    counterparty.save()
    response = client_logged_in.get(reverse("core:counterparty_list"), {"q": query})
    assert response.status_code == 200
    assert list(response.context["counterparties"]) == [counterparty]
    assert response.context["query"] == query.strip()


def test_counterparty_search_empty_result(client_logged_in, counterparty):
    response = client_logged_in.get(reverse("core:counterparty_list"), {"q": "Missing customer"})
    assert list(response.context["counterparties"]) == []
    assert _("No counterparties found.") in response.content.decode()


def test_counterparty_page_shows_current_machines(
    client_logged_in, engineer, machine, other_machine, counterparty
):
    create_log_entry(
        author=engineer, machine=machine, kind=LogKind.OWNERSHIP_CHANGE,
        title="Bought", new_owner=counterparty,
    )
    create_log_entry(
        author=engineer, machine=machine, kind=LogKind.STATUS_CHANGE,
        title="Repair started", new_status=MachineStatus.UNDER_REPAIR,
    )
    create_log_entry(author=engineer, machine=machine, kind=LogKind.ISSUE, title="Stalls")
    resolved = create_log_entry(author=engineer, machine=machine, kind=LogKind.ISSUE, title="Leaks")
    create_log_entry(
        author=engineer, machine=machine, kind=LogKind.MAINTENANCE, title="Sealed", resolves=[resolved]
    )
    create_log_entry(
        author=engineer, machine=machine, kind=LogKind.REQUEST,
        title="Follow-up call", event_date=date(2026, 10, 1),
    )
    response = client_logged_in.get(reverse("core:counterparty_detail", args=[counterparty.pk]))
    assert response.status_code == 200
    assert list(response.context["machines"]) == [machine]
    assert response.context["machines"][0].open_issues == 1
    assert response.context["machines"][0].status == MachineStatus.UNDER_REPAIR
    content = response.content.decode()
    assert reverse("core:machine_detail", args=[machine.pk]) in content
    assert reverse("core:machine_detail", args=[other_machine.pk]) not in content
    assert str(MachineStatus.UNDER_REPAIR.label) in content
    assert "01.10.2026" in content


def test_counterparty_pages_follow_ownership_changes(
    client_logged_in, engineer, machine, counterparty, other_counterparty
):
    for owner in (counterparty, other_counterparty):
        create_log_entry(
            author=engineer, machine=machine, kind=LogKind.OWNERSHIP_CHANGE,
            title="Transferred", new_owner=owner,
        )
    previous = client_logged_in.get(reverse("core:counterparty_detail", args=[counterparty.pk]))
    current = client_logged_in.get(reverse("core:counterparty_detail", args=[other_counterparty.pk]))
    assert list(previous.context["machines"]) == []
    assert list(current.context["machines"]) == [machine]
    directory = client_logged_in.get(reverse("core:counterparty_list"))
    assert {item.pk: item.machine_count for item in directory.context["counterparties"]} == {
        counterparty.pk: 0, other_counterparty.pk: 1,
    }


def test_counterparty_details_and_contacts_render_markdown_safely(client_logged_in, counterparty):
    counterparty.inn = "123456789012"
    counterparty.notes = "**Visit by appointment**\n\n<script>alert(1)</script>"
    counterparty.save()
    contact = ContactPerson.objects.create(
        counterparty=counterparty, full_name="Alex <script>alert(2)</script>",
        position="Machine chief", phones="+7 999 123-45-67", email="alex@example.com",
        notes="**Call in the morning**\n\n<script>alert(3)</script>",
    )
    ContactPerson.objects.create(counterparty=counterparty, full_name="Former contact", is_active=False)
    response = client_logged_in.get(reverse("core:counterparty_detail", args=[counterparty.pk]))
    assert response.status_code == 200
    assert list(response.context["contacts"]) == [contact]
    content = response.content.decode()
    for value in (counterparty.inn, counterparty.region, contact.position, contact.phones, contact.email):
        assert value in content
    assert "<strong>Visit by appointment</strong>" in content
    assert "<strong>Call in the morning</strong>" in content
    assert "<script>" not in content
    assert "&lt;script&gt;" in content
    assert "Former contact" not in content


def test_inactive_counterparty_remains_accessible(client_logged_in, counterparty):
    counterparty.is_active = False
    counterparty.save()
    directory = client_logged_in.get(reverse("core:counterparty_list"))
    detail = client_logged_in.get(reverse("core:counterparty_detail", args=[counterparty.pk]))
    assert list(directory.context["counterparties"]) == [counterparty]
    assert _("Inactive") in directory.content.decode()
    assert detail.status_code == 200
    assert _("Inactive") in detail.content.decode()
    assert _("No machines found.") in detail.content.decode()
    assert _("No active contacts.") in detail.content.decode()
    assert reverse("admin:core_counterparty_change", args=[counterparty.pk]) not in detail.content.decode()


def test_counterparty_page_not_found(client_logged_in):
    assert client_logged_in.get(reverse("core:counterparty_detail", args=[999999])).status_code == 404


def test_counterparty_administration_links(client_logged_in, engineer, counterparty):
    engineer.is_staff = True
    engineer.save()
    engineer.groups.add(Group.objects.get(name=ADMINISTRATOR))
    directory = client_logged_in.get(reverse("core:counterparty_list"))
    detail = client_logged_in.get(reverse("core:counterparty_detail", args=[counterparty.pk]))
    assert reverse("admin:core_counterparty_add") in directory.content.decode()
    assert reverse("admin:core_counterparty_change", args=[counterparty.pk]) in detail.content.decode()


def test_machine_pages_link_to_counterparty(client_logged_in, engineer, machine, counterparty):
    create_log_entry(
        author=engineer, machine=machine, kind=LogKind.OWNERSHIP_CHANGE,
        title="Bought", new_owner=counterparty,
    )
    for url in (reverse("core:home"), reverse("core:machine_detail", args=[machine.pk])):
        content = client_logged_in.get(url).content.decode()
        assert reverse("core:counterparty_list") in content
        assert reverse("core:counterparty_detail", args=[counterparty.pk]) in content


def test_machine_list_and_search(client_logged_in, machine, other_machine):
    response = client_logged_in.get(reverse("core:home"), {"q": "68"})
    assert response.status_code == 200
    assert list(response.context["machines"]) == [other_machine]


def test_machine_page_shows_state(client_logged_in, engineer, machine, equipment, counterparty):
    create_log_entry(
        author=engineer, machine=machine, kind=LogKind.OWNERSHIP_CHANGE, title="Bought", new_owner=counterparty
    )
    create_log_entry(
        author=engineer,
        machine=machine,
        kind=LogKind.EQUIPMENT_INSTALL,
        title="Installed",
        equipment=equipment,
        software_version="3.2",
    )
    create_log_entry(author=engineer, machine=machine, kind=LogKind.ISSUE, title="Stalls", text="**Video** attached")
    response = client_logged_in.get(reverse("core:machine_detail", args=[machine.pk]))
    content = response.content.decode()
    assert response.status_code == 200
    assert counterparty.name in content
    assert equipment.serial_number in content
    assert "<strong>Video</strong>" in content
    assert [issue.title for issue in response.context["open_issues"]] == ["Stalls"]


def test_machine_feed_filter_by_kind(client_logged_in, engineer, machine):
    create_log_entry(author=engineer, machine=machine, kind=LogKind.ISSUE, title="Stalls")
    create_log_entry(author=engineer, machine=machine, kind=LogKind.REQUEST, title="Price")
    response = client_logged_in.get(reverse("core:machine_detail", args=[machine.pk]), {"kind": "request"})
    assert [entry.title for entry in response.context["page"]] == ["Price"]


def test_new_entry_kind_picker(client_logged_in, machine):
    response = client_logged_in.get(reverse("core:log_entry_create", args=[machine.pk]))
    assert response.status_code == 200
    assert "kind=issue" in response.content.decode()


def test_new_entry_form_suggests_skeleton(client_logged_in, machine):
    response = client_logged_in.get(reverse("core:log_entry_create", args=[machine.pk]), {"kind": "issue"})
    assert response.context["form"]["text"].initial


def test_create_install_entry_through_form(client_logged_in, machine, equipment):
    url = reverse("core:log_entry_create", args=[machine.pk]) + "?kind=equipment_install"
    response = client_logged_in.post(
        url,
        {
            "event_date": "2026-10-01",
            "source": "site_visit",
            "equipment": equipment.pk,
            "software_version": "4.0",
            "title": "Installed controller",
            "text": "Done",
        },
    )
    assert response.status_code == 302
    equipment.refresh_from_db()
    assert equipment.current_machine == machine
    assert equipment.software_version == "4.0"


def test_maintenance_form_resolves_issue(client_logged_in, engineer, machine):
    issue = create_log_entry(author=engineer, machine=machine, kind=LogKind.ISSUE, title="Stalls")
    url = reverse("core:log_entry_create", args=[machine.pk]) + "?kind=maintenance"
    response = client_logged_in.post(
        url, {"event_date": "2026-10-02", "source": "remote", "resolves": [issue.pk], "title": "Fixed"}
    )
    assert response.status_code == 302
    issue.refresh_from_db()
    assert not issue.is_open_issue


def test_service_errors_are_shown_on_form(client_logged_in, machine):
    url = reverse("core:log_entry_create", args=[machine.pk]) + "?kind=request"
    response = client_logged_in.post(url, {"event_date": "2999-01-01", "source": "phone", "title": "Call"})
    assert response.status_code == 200
    assert response.context["form"].non_field_errors()


def test_new_entry_requires_permission(client, machine):
    from django.contrib.auth.models import User

    client.force_login(User.objects.create_user("viewer"))
    response = client.get(reverse("core:log_entry_create", args=[machine.pk]))
    assert response.status_code == 403


def test_author_amends_entry_and_sees_previous_version(client_logged_in, engineer, machine):
    entry = create_log_entry(author=engineer, machine=machine, kind=LogKind.ISSUE, title="Stals")
    response = client_logged_in.post(
        reverse("core:log_entry_amend", args=[entry.pk]), {"title": "Stalls", "text": "At low speed"}
    )
    assert response.status_code == 302
    response = client_logged_in.get(reverse("core:log_entry_detail", args=[entry.pk]))
    assert [revision.title for revision in response.context["revisions"]] == ["Stals"]


def test_other_user_cannot_amend(client, engineer, machine):
    from django.contrib.auth.models import User

    entry = create_log_entry(author=engineer, machine=machine, kind=LogKind.ISSUE, title="Stalls")
    client.force_login(User.objects.create_user("other"))
    response = client.post(reverse("core:log_entry_amend", args=[entry.pk]), {"title": "Hacked"})
    assert response.status_code == 403


def test_seed_demo_fills_empty_database(db, client):
    from django.core.management import call_command

    from core.models import Machine

    call_command("seed_demo", password="x-demo-pass-1")
    machine = Machine.objects.get(factory_number="67")
    assert machine.current_owner is not None
    assert machine.log_entries.filter(issue_status="open").count() == 2
    from django.contrib.auth.models import User

    ivanov = User.objects.get(username="ivanov")
    assert ivanov.check_password("x-demo-pass-1")
    client.force_login(ivanov)
    assert client.get(reverse("core:machine_detail", args=[machine.pk])).status_code == 200
