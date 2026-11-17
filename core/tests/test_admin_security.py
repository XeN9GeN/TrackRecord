import pytest
from django.contrib.auth.models import Group, Permission, User
from django.urls import reverse

from core.models import EquipmentState, LogKind, MachineStatus
from core.roles import ADMINISTRATOR, ENGINEER
from core.services import create_log_entry


@pytest.fixture
def administrator(db):
    user = User.objects.create_user("administrator", password="admin-test-pass", is_staff=True)
    user.groups.add(Group.objects.get(name=ADMINISTRATOR))
    return user


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser("root", "root@example.test", "root-test-pass")


@pytest.mark.parametrize("target_kind", ["self", "staff", "superuser", "administrator_group", "direct_permission"])
@pytest.mark.parametrize("action", ["edit", "password"])
def test_administrator_cannot_modify_privileged_accounts(client, administrator, target_kind, action):
    target = administrator if target_kind == "self" else User.objects.create_user("privileged")
    if target_kind in ("staff", "superuser"):
        setattr(target, "is_" + target_kind, True)
        target.save()
    elif target_kind == "administrator_group":
        target.groups.add(Group.objects.get(name=ADMINISTRATOR))
    elif target_kind == "direct_permission":
        target.user_permissions.add(Permission.objects.get(codename="change_user"))
    client.force_login(administrator)
    original_password = target.password
    if action == "password":
        url = reverse("admin:auth_user_password_change", args=[target.pk])
        data = {"password1": "changed-test-pass", "password2": "changed-test-pass"}
    else:
        url = reverse("admin:auth_user_change", args=[target.pk])
        data = {"username": "taken_over", "is_superuser": "on", "is_active": "on"}
    assert client.post(url, data).status_code == 403
    target.refresh_from_db()
    assert target.username != "taken_over"
    assert target.password == original_password
    if target_kind != "superuser":
        assert not target.is_superuser


def test_administrator_can_edit_engineer_but_cannot_grant_direct_privileges(client, administrator, engineer):
    engineer.groups.add(Group.objects.get(name=ENGINEER))
    client.force_login(administrator)
    response = client.post(reverse("admin:auth_user_change", args=[engineer.pk]), {
        "username": engineer.username, "first_name": "Updated", "is_active": "on",
        "is_staff": "on", "is_superuser": "on",
        "user_permissions": [Permission.objects.get(codename="change_user").pk],
        "groups": [Group.objects.get(name=ENGINEER).pk],
    })
    assert response.status_code == 302
    engineer.refresh_from_db()
    assert engineer.first_name == "Updated"
    assert not engineer.is_staff
    assert not engineer.is_superuser
    assert not engineer.user_permissions.exists()
    assert list(engineer.groups.values_list("name", flat=True)) == [ENGINEER]


def test_administrator_cannot_assign_administrator_group(client, administrator, engineer):
    client.force_login(administrator)
    response = client.post(reverse("admin:auth_user_change", args=[engineer.pk]), {
        "username": engineer.username, "is_active": "on",
        "groups": [Group.objects.get(name=ADMINISTRATOR).pk],
    })
    assert response.status_code == 200
    assert "groups" in response.context["adminform"].form.errors
    assert not engineer.groups.exists()


def test_administrator_can_create_ordinary_user(client, administrator):
    client.force_login(administrator)
    response = client.post(reverse("admin:auth_user_add"), {
        "username": "new_engineer", "password1": "new-engineer-test-pass",
        "password2": "new-engineer-test-pass", "usable_password": "true",
        "is_staff": "on", "is_superuser": "on",
        "groups": [Group.objects.get(name=ADMINISTRATOR).pk],
        "user_permissions": [Permission.objects.get(codename="change_user").pk],
    })
    assert response.status_code == 302
    user = User.objects.get(username="new_engineer")
    assert user.check_password("new-engineer-test-pass")
    assert not user.is_staff
    assert not user.is_superuser
    assert not user.groups.exists()
    assert not user.user_permissions.exists()


def test_administrator_can_reset_engineer_password(client, administrator, engineer):
    client.force_login(administrator)
    response = client.post(reverse("admin:auth_user_password_change", args=[engineer.pk]), {
        "password1": "changed-engineer-pass", "password2": "changed-engineer-pass",
        "usable_password": "true",
    })
    assert response.status_code == 302
    engineer.refresh_from_db()
    assert engineer.check_password("changed-engineer-pass")


def test_superuser_can_manage_privileges(client, superuser, administrator):
    client.force_login(superuser)
    response = client.post(reverse("admin:auth_user_change", args=[administrator.pk]), {
        "username": administrator.username, "is_active": "on", "is_staff": "on", "is_superuser": "on",
        "groups": [Group.objects.get(name=ADMINISTRATOR).pk],
        "user_permissions": [Permission.objects.get(codename="change_user").pk],
    })
    assert response.status_code == 302
    administrator.refresh_from_db()
    assert administrator.is_superuser
    assert administrator.user_permissions.filter(codename="change_user").exists()


@pytest.mark.parametrize("actor", ["administrator", "superuser"])
@pytest.mark.parametrize("model_name", ["machine", "equipment"])
def test_state_history_is_viewable_but_cannot_be_restored(
    client, request, actor, model_name, engineer, machine, equipment, counterparty,
):
    obj = machine if model_name == "machine" else equipment
    old_version = obj.history.first()
    create_log_entry(
        author=engineer, machine=machine, kind=LogKind.OWNERSHIP_CHANGE,
        title="Bought", new_owner=counterparty,
    )
    create_log_entry(
        author=engineer, machine=machine, kind=LogKind.STATUS_CHANGE,
        title="Repair", new_status=MachineStatus.UNDER_REPAIR,
    )
    create_log_entry(
        author=engineer, machine=machine, equipment=equipment, kind=LogKind.EQUIPMENT_INSTALL,
        title="Installed", software_version="2.0",
    )
    client.force_login(request.getfixturevalue(actor))
    history_count = obj.history.count()
    log_count = machine.log_entries.count()
    history_url = reverse(f"admin:core_{model_name}_history", args=[obj.pk])
    version_url = reverse(f"admin:core_{model_name}_simple_history", args=[obj.pk, old_version.history_id])
    assert client.get(history_url).status_code == 200
    response = client.get(version_url)
    assert response.status_code == 200
    assert response.context["revert_disabled"] is True
    assert client.post(version_url, {"_save": "1"}).status_code == 403
    machine.refresh_from_db()
    equipment.refresh_from_db()
    assert machine.current_owner_id == counterparty.pk
    assert machine.status == MachineStatus.UNDER_REPAIR
    assert equipment.current_machine_id == machine.pk
    assert equipment.state == EquipmentState.INSTALLED
    assert equipment.software_version == "2.0"
    assert obj.history.count() == history_count
    assert machine.log_entries.count() == log_count
