import pytest
from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import PermissionDenied, ValidationError

from core.models import LogKind
from core.roles import ENGINEER
from core.services import amend_log_entry, can_amend, create_log_entry


@pytest.fixture
def entry(engineer, machine):
    engineer.groups.add(Group.objects.get(name=ENGINEER))
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
    stranger.groups.add(Group.objects.get(name=ENGINEER))
    with pytest.raises(PermissionDenied):
        amend_log_entry(entry, editor=stranger, title="Hacked", text="")


def test_superuser_may_amend(entry):
    admin = User.objects.create_superuser("admin")
    assert amend_log_entry(entry, editor=admin, title="Fixed typo", text="")


def test_title_required(engineer, entry):
    with pytest.raises(ValidationError):
        amend_log_entry(entry, editor=engineer, title="", text="x")


@pytest.mark.parametrize("permission_source", ["group", "direct"])
def test_author_cannot_amend_after_permission_is_revoked(engineer, entry, permission_source):
    if permission_source == "direct":
        engineer.groups.clear()
        engineer.user_permissions.add(Permission.objects.get(content_type__app_label="core", codename="change_logentry"))
    assert can_amend(engineer, entry)
    engineer.groups.clear()
    engineer.user_permissions.clear()
    editor = User.objects.get(pk=engineer.pk)
    assert not can_amend(editor, entry)
    with pytest.raises(PermissionDenied):
        amend_log_entry(entry, editor=editor, title="Changed", text="Changed")
    entry.refresh_from_db()
    assert entry.title == "Stalls"
    assert entry.text == "Stalls while moving"
    assert entry.edited_at is None
    assert not entry.revisions.exists()


def test_inactive_author_cannot_amend(engineer, entry):
    engineer.is_active = False
    engineer.save()
    with pytest.raises(PermissionDenied):
        amend_log_entry(entry, editor=engineer, title="Changed", text="")
    assert not entry.revisions.exists()
