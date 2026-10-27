import pytest
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError

from core.models import LogKind
from core.services import amend_log_entry, create_log_entry


@pytest.fixture
def entry(engineer, machine):
    return create_log_entry(
        author=engineer, machine=machine, kind=LogKind.ISSUE, title="Stalls", text="Stalls while moving"
    )


def test_amend_keeps_previous_version(engineer, entry):
    changed = amend_log_entry(entry, editor=engineer, title="Engine stalls", text="Stalls at low speed\r\n")
    entry.refresh_from_db()
    assert changed
    assert entry.title == "Engine stalls"
    assert entry.text == "Stalls at low speed"
    assert entry.edited_at is not None
    revision = entry.revisions.get()
    assert (revision.title, revision.text, revision.edited_by) == ("Stalls", "Stalls while moving", engineer)


def test_every_amendment_is_a_revision(engineer, entry):
    amend_log_entry(entry, editor=engineer, title="v2", text="")
    amend_log_entry(entry, editor=engineer, title="v3", text="")
    assert list(entry.revisions.values_list("title", flat=True)) == ["v2", "Stalls"]


def test_unchanged_amendment_is_ignored(engineer, entry):
    assert not amend_log_entry(entry, editor=engineer, title=" Stalls ", text="Stalls while moving\n")
    assert not entry.revisions.exists()


def test_amendment_does_not_touch_state(engineer, entry):
    amend_log_entry(entry, editor=engineer, title="Changed", text="")
    entry.refresh_from_db()
    assert entry.is_open_issue


def test_only_author_may_amend(entry):
    stranger = User.objects.create_user("stranger")
    with pytest.raises(PermissionDenied):
        amend_log_entry(entry, editor=stranger, title="Hacked", text="")


def test_superuser_may_amend(entry):
    admin = User.objects.create_superuser("admin")
    assert amend_log_entry(entry, editor=admin, title="Fixed typo", text="")


def test_title_required(engineer, entry):
    with pytest.raises(ValidationError):
        amend_log_entry(entry, editor=engineer, title="", text="x")
