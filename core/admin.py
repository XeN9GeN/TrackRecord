from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext_lazy as _
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    ContactPerson,
    Counterparty,
    Equipment,
    EquipmentType,
    LogEntry,
    LogEntryRevision,
    Machine,
    MachineModel,
)
from .roles import ENGINEER

admin.site.site_header = _("TrackRecord administration")
admin.site.site_title = "TrackRecord"

admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Let ordinary administrators maintain users without granting privileges."""

    readonly_fields = ("last_login", "date_joined")

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if request.user.is_superuser:
            return fields
        return (*fields, "is_staff", "is_superuser", "user_permissions")

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "groups" and not request.user.is_superuser:
            kwargs["queryset"] = db_field.remote_field.model.objects.filter(name=ENGINEER)
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request, obj):
            return False
        if request.user.is_superuser or obj is None:
            return True
        # Password resets and account edits must not grant control of privileged users.
        return not (
            obj.is_staff or obj.is_superuser or obj.user_permissions.exists()
            or obj.groups.exclude(name=ENGINEER).exists()
        )


class StateHistoryAdmin(SimpleHistoryAdmin):
    """Keep state history inspectable; all state changes require a log entry."""

    def revert_disabled(self, request, obj=None):
        return True

    def history_form_view(self, request, object_id, version_id, extra_context=None):
        # Hiding the revert button alone does not prevent a crafted POST.
        if request.method == "POST":
            raise PermissionDenied
        return super().history_form_view(request, object_id, version_id, extra_context)


class ContactPersonInline(admin.TabularInline):
    model = ContactPerson
    extra = 0
    fields = ["full_name", "position", "phones", "email", "is_active"]


@admin.register(Counterparty)
class CounterpartyAdmin(SimpleHistoryAdmin):
    list_display = ["name", "inn", "region", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "inn", "region"]
    inlines = [ContactPersonInline]

    def has_delete_permission(self, request, obj=None):
        # Counterparties are deactivated, not deleted.
        return False


@admin.register(ContactPerson)
class ContactPersonAdmin(SimpleHistoryAdmin):
    list_display = ["full_name", "position", "counterparty", "phones", "email", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["full_name", "phones", "email", "counterparty__name"]
    autocomplete_fields = ["counterparty"]


@admin.register(MachineModel)
class MachineModelAdmin(SimpleHistoryAdmin):
    list_display = ["name", "manufacturer"]
    search_fields = ["name", "manufacturer"]


@admin.register(EquipmentType)
class EquipmentTypeAdmin(SimpleHistoryAdmin):
    search_fields = ["name"]


@admin.register(Machine)
class MachineAdmin(StateHistoryAdmin):
    list_display = ["__str__", "current_owner", "status", "last_contact_at"]
    list_filter = ["status", "model"]
    search_fields = ["factory_number", "model__name", "current_owner__name"]
    # Owner and status are changed only by log entries (ADR-0002).
    readonly_fields = ["current_owner", "status", "last_contact_at", "created_at"]

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return self.readonly_fields
        # Model and factory number never change during the machine's life.
        return ["model", "factory_number", *self.readonly_fields]


@admin.register(Equipment)
class EquipmentAdmin(StateHistoryAdmin):
    list_display = ["__str__", "production_year", "software_version", "state", "current_machine"]
    list_filter = ["state", "type"]
    search_fields = ["serial_number", "type__name"]
    # State, location and software version are changed only by log entries (ADR-0002).
    readonly_fields = ["state", "current_machine", "software_version"]


class LogEntryRevisionInline(admin.TabularInline):
    model = LogEntryRevision
    extra = 0
    can_delete = False
    fields = ["edited_at", "edited_by", "title", "text"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    """Read-only: entries are created and amended in the application, never deleted (ADR-0002)."""

    list_display = ["event_date", "kind", "title", "machine", "author", "issue_status"]
    list_filter = ["kind", "issue_status", "source"]
    search_fields = ["title", "machine__factory_number"]
    date_hierarchy = "event_date"
    exclude = ["search_vector"]
    inlines = [LogEntryRevisionInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
