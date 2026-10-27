"""User roles as Django groups (ADR-0004), kept in sync after every migrate."""

from django.contrib.auth.models import Group, Permission

ENGINEER = "Engineer"
ADMINISTRATOR = "Administrator"

REFERENCE_MODELS = ["counterparty", "contactperson", "machinemodel", "machine", "equipmenttype", "equipment"]
LOG_MODELS = ["logentry", "logentryrevision"]

ROLE_PERMISSIONS = {
    # Reads everything, adds and amends log entries.
    ENGINEER: [f"core.view_{m}" for m in REFERENCE_MODELS + LOG_MODELS]
    + ["core.add_logentry", "core.change_logentry"],
    # Additionally maintains reference data and users.
    ADMINISTRATOR: [f"core.view_{m}" for m in REFERENCE_MODELS + LOG_MODELS]
    + ["core.add_logentry", "core.change_logentry"]
    + [f"core.{action}_{m}" for m in REFERENCE_MODELS for action in ("add", "change")]
    + ["auth.view_user", "auth.add_user", "auth.change_user", "auth.view_group"],
}


def ensure_roles(**kwargs):
    for name, codenames in ROLE_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=name)
        permissions = [
            Permission.objects.get(content_type__app_label=app_label, codename=codename)
            for app_label, codename in (perm.split(".") for perm in codenames)
        ]
        group.permissions.set(permissions)
