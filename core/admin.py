from django.contrib import admin
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

admin.site.site_header = _("TrackRecord administration")
admin.site.site_title = "TrackRecord"


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
class MachineAdmin(SimpleHistoryAdmin):
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
class EquipmentAdmin(SimpleHistoryAdmin):
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
