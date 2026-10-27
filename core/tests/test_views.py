import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from core.models import LogKind
from core.roles import ENGINEER
from core.services import create_log_entry


@pytest.fixture
def client_logged_in(client, engineer):
    engineer.groups.add(Group.objects.get(name=ENGINEER))
    client.force_login(engineer)
    return client


def test_pages_require_login(client, machine):
    for url in (reverse("core:home"), reverse("core:machine_detail", args=[machine.pk])):
        response = client.get(url)
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))


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
