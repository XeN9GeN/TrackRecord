"""Domain model, see docs/DOMAIN.md and docs/ER_MODEL.md.

Current state fields (machine owner and status, equipment machine, state and software version)
are changed only by services.create_log_entry() (ADR-0002).
"""

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Length
from django.db.models.lookups import LessThanOrEqual
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords


class MachineStatus(models.TextChoices):
    IN_SERVICE = "in_service", _("in service")
    UNDER_REPAIR = "under_repair", _("under repair")
    SOLD = "sold", _("sold")
    DECOMMISSIONED = "decommissioned", _("decommissioned")
    UNKNOWN = "unknown", _("unknown")


class EquipmentState(models.TextChoices):
    IN_STOCK = "in_stock", _("in stock")
    INSTALLED = "installed", _("installed")
    REMOVED = "removed", _("removed")
    WRITTEN_OFF = "written_off", _("written off")


class LogKind(models.TextChoices):
    REQUEST = "request", _("Request / call / info")
    ISSUE = "issue", _("Issue")
    MAINTENANCE = "maintenance", _("Maintenance / repair / remote consultation")
    EQUIPMENT_INSTALL = "equipment_install", _("Equipment installation")
    EQUIPMENT_REMOVAL = "equipment_removal", _("Equipment removal")
    EQUIPMENT_WRITE_OFF = "equipment_write_off", _("Equipment write-off")
    SOFTWARE_UPDATE = "software_update", _("Software update")
    OWNERSHIP_CHANGE = "ownership_change", _("Ownership change")
    STATUS_CHANGE = "status_change", _("Machine status change")
    DOCUMENT = "document", _("Document")
    INITIAL_IMPORT = "initial_import", _("Initial data import")


class LogSource(models.TextChoices):
    PHONE = "phone", _("phone call")
    EMAIL = "email", _("email")
    MESSENGER = "messenger", _("messenger")
    SITE_VISIT = "site_visit", _("site visit")
    REMOTE = "remote", _("remote")
    OTHER = "other", _("other")


class IssueStatus(models.TextChoices):
    OPEN = "open", _("open")
    RESOLVED = "resolved", _("resolved")


EQUIPMENT_KINDS = (
    LogKind.EQUIPMENT_INSTALL,
    LogKind.EQUIPMENT_REMOVAL,
    LogKind.EQUIPMENT_WRITE_OFF,
    LogKind.SOFTWARE_UPDATE,
)
SOFTWARE_VERSION_KINDS = (LogKind.EQUIPMENT_INSTALL, LogKind.SOFTWARE_UPDATE)
TEXT_MAX_LENGTH = 50_000


class Counterparty(models.Model):
    name = models.CharField(_("name"), max_length=255)
    inn = models.CharField(_("taxpayer id (INN)"), max_length=12, null=True, blank=True, unique=True)
    region = models.CharField(_("region"), max_length=255, blank=True)
    notes = models.TextField(_("notes"), blank=True)
    is_active = models.BooleanField(_("active"), default=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = _("counterparty")
        verbose_name_plural = _("counterparties")
        ordering = ["name"]

    def __str__(self):
        return self.name


class ContactPerson(models.Model):
    counterparty = models.ForeignKey(
        Counterparty, on_delete=models.PROTECT, related_name="contacts", verbose_name=_("counterparty")
    )
    full_name = models.CharField(_("full name"), max_length=255)
    position = models.CharField(_("position"), max_length=255, blank=True)
    phones = models.CharField(_("phones"), max_length=255, blank=True)
    email = models.EmailField(_("email"), blank=True)
    notes = models.TextField(_("notes"), blank=True)
    is_active = models.BooleanField(_("active"), default=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = _("contact person")
        verbose_name_plural = _("contact persons")
        ordering = ["full_name"]

    def __str__(self):
        if self.position:
            return f"{self.full_name} ({self.position}, {self.counterparty})"
        return f"{self.full_name} ({self.counterparty})"


class MachineModel(models.Model):
    name = models.CharField(_("name"), max_length=255, unique=True)
    manufacturer = models.CharField(_("manufacturer"), max_length=255, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = _("machine model")
        verbose_name_plural = _("machine models")
        ordering = ["name"]

    def __str__(self):
        return self.name


class Machine(models.Model):
    Status = MachineStatus

    model = models.ForeignKey(MachineModel, on_delete=models.PROTECT, related_name="machines", verbose_name=_("model"))
    factory_number = models.CharField(_("factory number"), max_length=64)
    current_owner = models.ForeignKey(
        Counterparty,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="machines",
        verbose_name=_("current owner"),
    )
    status = models.CharField(_("status"), max_length=32, choices=Status, default=Status.UNKNOWN)
    last_contact_at = models.DateTimeField(_("last contact"), null=True, blank=True)
    created_at = models.DateTimeField(_("created"), default=timezone.now)

    history = HistoricalRecords()

    class Meta:
        verbose_name = _("machine")
        verbose_name_plural = _("machines")
        ordering = ["model__name", "factory_number"]
        constraints = [
            models.UniqueConstraint(fields=["model", "factory_number"], name="machine_model_number_uniq"),
            models.CheckConstraint(condition=Q(status__in=MachineStatus.values), name="machine_status_valid"),
        ]

    def __str__(self):
        return f"{self.model} №{self.factory_number}"


class EquipmentType(models.Model):
    name = models.CharField(_("name"), max_length=255, unique=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = _("equipment type")
        verbose_name_plural = _("equipment types")
        ordering = ["name"]

    def __str__(self):
        return self.name


class Equipment(models.Model):
    State = EquipmentState

    type = models.ForeignKey(EquipmentType, on_delete=models.PROTECT, related_name="units", verbose_name=_("type"))
    serial_number = models.CharField(_("serial number"), max_length=128)
    production_year = models.PositiveSmallIntegerField(_("production year"), null=True, blank=True)
    software_version = models.CharField(_("software version"), max_length=64, blank=True)
    state = models.CharField(_("state"), max_length=32, choices=State, default=State.IN_STOCK)
    current_machine = models.ForeignKey(
        Machine,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="installed_equipment",
        verbose_name=_("installed on"),
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = _("equipment")
        verbose_name_plural = _("equipment")
        ordering = ["type__name", "serial_number"]
        constraints = [
            models.UniqueConstraint(fields=["type", "serial_number"], name="equipment_type_serial_uniq"),
            models.CheckConstraint(condition=Q(state__in=EquipmentState.values), name="equipment_state_valid"),
            models.CheckConstraint(
                condition=Q(production_year__isnull=True) | Q(production_year__gte=1950, production_year__lte=2100),
                name="equipment_production_year_range",
            ),
            # Attached to a machine exactly when installed: never on two machines at once.
            models.CheckConstraint(
                condition=Q(state="installed", current_machine__isnull=False)
                | (~Q(state="installed") & Q(current_machine__isnull=True)),
                name="equipment_installed_has_machine",
            ),
        ]

    def __str__(self):
        return f"{self.type} SN {self.serial_number}"


class LogEntry(models.Model):
    Kind = LogKind
    Source = LogSource
    IssueStatus = IssueStatus

    EQUIPMENT_KINDS = EQUIPMENT_KINDS
    SOFTWARE_VERSION_KINDS = SOFTWARE_VERSION_KINDS
    TEXT_MAX_LENGTH = TEXT_MAX_LENGTH

    machine = models.ForeignKey(
        Machine,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="log_entries",
        verbose_name=_("machine"),
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="log_entries", verbose_name=_("author")
    )
    created_at = models.DateTimeField(_("recorded at"), default=timezone.now)
    event_date = models.DateField(_("event date"), default=timezone.localdate)
    kind = models.CharField(_("kind"), max_length=32, choices=Kind)
    source = models.CharField(_("source"), max_length=32, choices=Source, default=Source.OTHER)
    contact = models.ForeignKey(
        ContactPerson,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="log_entries",
        verbose_name=_("contact person"),
    )
    owner_snapshot = models.ForeignKey(
        Counterparty,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("owner at the time"),
    )
    title = models.CharField(_("title"), max_length=200)
    text = models.TextField(_("text"), blank=True, help_text=_("Markdown is supported."))
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="log_entries",
        verbose_name=_("equipment"),
    )
    software_version = models.CharField(_("software version"), max_length=64, null=True, blank=True)
    new_owner = models.ForeignKey(
        Counterparty,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("new owner"),
    )
    new_status = models.CharField(_("new status"), max_length=32, choices=Machine.Status, null=True, blank=True)
    is_issue = models.BooleanField(_("issue"), default=False)
    issue_status = models.CharField(_("issue status"), max_length=16, choices=IssueStatus, null=True, blank=True)
    resolved_by = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="resolved_issues",
        verbose_name=_("resolved by"),
    )
    resolved_at = models.DateTimeField(_("resolved at"), null=True, blank=True)
    extra = models.JSONField(_("extra attributes"), default=dict, blank=True)
    search_vector = models.GeneratedField(
        expression=SearchVector("title", weight="A", config="russian")
        + SearchVector("text", weight="B", config="russian"),
        output_field=SearchVectorField(),
        db_persist=True,
    )
    edited_at = models.DateTimeField(_("edited at"), null=True, blank=True)

    class Meta:
        verbose_name = _("log entry")
        verbose_name_plural = _("log entries")
        ordering = ["-event_date", "-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(kind__in=LogKind.values), name="log_entry_kind_valid"),
            models.CheckConstraint(condition=Q(source__in=LogSource.values), name="log_entry_source_valid"),
            models.CheckConstraint(
                condition=Q(new_status__isnull=True) | Q(new_status__in=Machine.Status.values),
                name="log_entry_new_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(issue_status__isnull=True) | Q(issue_status__in=IssueStatus.values),
                name="log_entry_issue_status_valid",
            ),
            # Only a write-off of equipment that is not on a machine may have no machine (ADR-0011).
            models.CheckConstraint(
                condition=Q(machine__isnull=False) | Q(kind="equipment_write_off"),
                name="log_entry_machine_required",
            ),
            models.CheckConstraint(
                condition=Q(kind__in=EQUIPMENT_KINDS, equipment__isnull=False)
                | (~Q(kind__in=EQUIPMENT_KINDS) & Q(equipment__isnull=True)),
                name="log_entry_equipment_iff_kind",
            ),
            models.CheckConstraint(
                condition=~Q(kind__in=SOFTWARE_VERSION_KINDS) | Q(software_version__isnull=False),
                name="log_entry_software_version_req",
            ),
            models.CheckConstraint(
                condition=Q(kind="ownership_change", new_owner__isnull=False)
                | (~Q(kind="ownership_change") & Q(new_owner__isnull=True)),
                name="log_entry_new_owner_iff_kind",
            ),
            models.CheckConstraint(
                condition=Q(kind="status_change", new_status__isnull=False)
                | (~Q(kind="status_change") & Q(new_status__isnull=True)),
                name="log_entry_new_status_iff_kind",
            ),
            models.CheckConstraint(
                condition=Q(is_issue=True, issue_status__isnull=False)
                | Q(is_issue=False, issue_status__isnull=True),
                name="log_entry_issue_status_iff_issue",
            ),
            models.CheckConstraint(
                condition=Q(issue_status="resolved", resolved_by__isnull=False, resolved_at__isnull=False)
                | (~Q(issue_status="resolved") & Q(resolved_by__isnull=True, resolved_at__isnull=True)),
                name="log_entry_resolution_complete",
            ),
            models.CheckConstraint(
                condition=Q(resolved_by__isnull=True) | ~Q(resolved_by=F("id")),
                name="log_entry_not_resolved_by_self",
            ),
            models.CheckConstraint(
                condition=LessThanOrEqual(Length("text"), TEXT_MAX_LENGTH),
                name="log_entry_text_max_length",
            ),
        ]
        indexes = [
            models.Index(F("machine"), F("event_date").desc(), name="log_entry_machine_feed_idx"),
            models.Index(fields=["machine"], condition=Q(issue_status="open"), name="log_entry_open_issues_idx"),
            models.Index(F("equipment"), F("event_date").desc(), name="log_entry_equipment_idx"),
            GinIndex(fields=["search_vector"], name="log_entry_search_idx"),
        ]

    def __str__(self):
        return f"{self.event_date:%d.%m.%Y} {self.get_kind_display()}: {self.title}"

    @property
    def is_open_issue(self):
        return self.issue_status == self.IssueStatus.OPEN


class LogEntryRevision(models.Model):
    """Previous title and text of a log entry before its author amended it (ADR-0010)."""

    log_entry = models.ForeignKey(
        LogEntry, on_delete=models.PROTECT, related_name="revisions", verbose_name=_("log entry")
    )
    title = models.CharField(_("title"), max_length=200)
    text = models.TextField(_("text"), blank=True)
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", verbose_name=_("edited by")
    )
    edited_at = models.DateTimeField(_("edited at"), default=timezone.now)

    class Meta:
        verbose_name = _("log entry revision")
        verbose_name_plural = _("log entry revisions")
        ordering = ["-edited_at"]

    def __str__(self):
        return f"{self.log_entry_id} @ {self.edited_at:%d.%m.%Y %H:%M}"
