import pytest
from django.urls import reverse

from core.models import LogKind
from core.services import create_log_entry


@pytest.fixture
def client_logged_in(client, engineer):
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
