from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import (
    TEXT_MAX_LENGTH,
    ContactPerson,
    Counterparty,
    Equipment,
    EquipmentState,
    EquipmentType,
    LogEntry,
    LogKind,
    LogSource,
    Machine,
    MachineModel,
    MachineStatus,
)

# Kinds an engineer can record from the machine page; initial import is done by a command.
FORM_KINDS = [kind for kind in LogKind if kind != LogKind.INITIAL_IMPORT]

# Short text skeletons suggested per kind (ADR-0008); plain text is fine too.
TEXT_SKELETONS = {
    LogKind.REQUEST: _("**Question:** \n\n**Answer / agreed:** "),
    LogKind.ISSUE: _("**Symptoms:** \n\n**When it happens:** \n\n**What was checked:** "),
    LogKind.MAINTENANCE: _("**What was done:** \n\n**Result:** "),
    LogKind.EQUIPMENT_INSTALL: _("**Where it is mounted:** \n\n**Connection notes:** "),
    LogKind.EQUIPMENT_REMOVAL: _("**Reason:** \n\n**Where the equipment went:** "),
}


class DirectoryFilterForm(forms.Form):
    primary_filter_names = ()
    additional_filter_groups = ()
    searchable_filter_names = ()

    q = forms.CharField(
        label=_("Search"), required=False, max_length=255,
        widget=forms.TextInput(attrs={"type": "search"}),
        help_text=_("Use several words to narrow the search; all words must match."),
    )
    direction = forms.ChoiceField(
        label=_("Direction"), required=False,
        choices=[("asc", _("Ascending")), ("desc", _("Descending"))],
    )
    per_page = forms.TypedChoiceField(
        label=_("Rows per page"), required=False, coerce=int,
        choices=[(25, "25"), (50, "50"), (100, "100")],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.searchable_filter_names:
            self.fields[name].widget.attrs.update({
                "data-searchable-select": "true",
                "data-search-placeholder": _("Type to filter options"),
                "data-no-results": _("No matching options."),
                "data-open-label": _("Show options"),
            })

    class Media:
        js = ("js/searchable-select.js",)

    @property
    def primary_filters(self):
        return [self[name] for name in self.primary_filter_names]

    @property
    def additional_filters(self):
        return [
            {"label": label, "fields": [self[name] for name in names]}
            for label, names in self.additional_filter_groups
        ]


class ListFilterForm(DirectoryFilterForm):
    region = forms.ChoiceField(label=_("Region"), required=False)
    contact = forms.ChoiceField(
        label=_("Last contact"), required=False,
        choices=[("", _("Any date")), ("never", _("Never contacted")), ("overdue", _("No contact in 90 days"))],
    )
    contact_from = forms.DateField(
        label=_("Last contact from"), required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    contact_to = forms.DateField(
        label=_("Last contact through"), required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        regions = Counterparty.objects.exclude(region="").order_by("region").values_list("region", flat=True).distinct()
        self.fields["region"].choices = [("", _("All regions")), *[(region, region) for region in regions]]

    def clean(self):
        data = super().clean()
        start, end = data.get("contact_from"), data.get("contact_to")
        if start and end and start > end:
            data.pop("contact_from")
            data.pop("contact_to")
            raise forms.ValidationError(_("Last contact start date must not be after the end date."))
        return data


class MachineFilterForm(ListFilterForm):
    primary_filter_names = ("model", "owner", "region", "status")
    searchable_filter_names = ("model", "owner", "region", "equipment_type")
    additional_filter_groups = (
        (_("Condition and equipment"), ("issues", "equipment", "equipment_type")),
        (_("Last contact"), ("contact", "contact_from", "contact_to")),
    )

    status = forms.ChoiceField(
        label=_("Status"), required=False, choices=[("", _("All statuses")), *MachineStatus.choices],
    )
    model = forms.ModelChoiceField(
        label=_("Model"), required=False, queryset=MachineModel.objects.all(), empty_label=_("All models"),
    )
    owner = forms.ChoiceField(label=_("Owner"), required=False)
    issues = forms.ChoiceField(
        label=_("Open issues"), required=False,
        choices=[("", _("All machines")), ("yes", _("With open issues")), ("no", _("Without open issues"))],
    )
    equipment = forms.ChoiceField(
        label=_("Installed equipment"), required=False,
        choices=[("", _("All machines")), ("yes", _("With equipment")), ("no", _("Without equipment"))],
    )
    equipment_type = forms.ModelChoiceField(
        label=_("Equipment type"), required=False, queryset=EquipmentType.objects.all(), empty_label=_("All types"),
    )
    sort = forms.ChoiceField(
        label=_("Sort by"), required=False,
        choices=[
            ("machine", _("Model / factory number")), ("number", _("Factory number")),
            ("owner", _("Owner")), ("region", _("Region")),
            ("issues", _("Open issues")), ("contact", _("Last contact")),
        ],
    )
    field_order = [
        "q", "model", "owner", "region", "status", "issues", "equipment", "equipment_type",
        "contact", "contact_from", "contact_to", "sort", "direction", "per_page",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["q"].widget.attrs["placeholder"] = _("Number, model, owner, region or equipment serial number")
        self.fields["owner"].choices = [
            ("", _("All owners")), ("unassigned", _("Owner not recorded")),
            *Counterparty.objects.order_by("name", "pk").values_list("pk", "name"),
        ]


class CounterpartyFilterForm(ListFilterForm):
    primary_filter_names = ("activity", "region", "machines", "contacts")
    searchable_filter_names = ("region",)
    additional_filter_groups = (
        (_("Last contact"), ("contact", "contact_from", "contact_to")),
    )

    activity = forms.ChoiceField(
        label=_("Status"), required=False,
        choices=[("", _("All statuses")), ("active", _("Active")), ("inactive", _("Inactive"))],
    )
    machines = forms.ChoiceField(
        label=_("Machines"), required=False,
        choices=[("", _("All counterparties")), ("yes", _("With machines")), ("no", _("Without machines"))],
    )
    contacts = forms.ChoiceField(
        label=_("Active contacts"), required=False,
        choices=[("", _("All counterparties")), ("yes", _("With active contacts")), ("no", _("Without active contacts"))],
    )
    sort = forms.ChoiceField(
        label=_("Sort by"), required=False,
        choices=[
            ("name", _("Name")), ("inn", _("INN")), ("region", _("Region")),
            ("machines", _("Machine count")), ("contacts", _("Active contact count")), ("contact", _("Last contact")),
        ],
    )
    field_order = [
        "q", "activity", "region", "machines", "contacts", "contact", "contact_from", "contact_to",
        "sort", "direction", "per_page",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["q"].widget.attrs["placeholder"] = _("Name, INN, region, contact or machine")


class EquipmentFilterForm(DirectoryFilterForm):
    primary_filter_names = ("type", "state", "machine", "owner")
    searchable_filter_names = ("type", "machine", "owner")

    type = forms.ModelChoiceField(
        label=_("Equipment type"), required=False, queryset=EquipmentType.objects.all(), empty_label=_("All types"),
    )
    state = forms.ChoiceField(
        label=_("Equipment state"), required=False, choices=[("", _("All states")), *EquipmentState.choices],
    )
    machine = forms.ModelChoiceField(
        label=_("Machine"), required=False, queryset=Machine.objects.select_related("model"), empty_label=_("All machines"),
    )
    owner = forms.ModelChoiceField(
        label=_("Owner"), required=False, queryset=Counterparty.objects.all(), empty_label=_("All owners"),
    )
    sort = forms.ChoiceField(
        label=_("Sort by"), required=False,
        choices=[
            ("type", _("Equipment type")), ("serial", _("Serial number")), ("year", _("Year")),
            ("software", _("Software version")), ("state", _("Equipment state")),
            ("machine", _("Machine")), ("owner", _("Owner")),
        ],
    )
    field_order = ["q", "type", "state", "machine", "owner", "sort", "direction", "per_page"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["q"].widget.attrs["placeholder"] = _("Serial number, type, machine or owner")


class LogEntryForm(forms.Form):
    """New entry form: the set of fields depends on the kind."""

    event_date = forms.DateField(
        label=_("Event date"), initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"})
    )
    source = forms.ChoiceField(label=_("Source"), choices=LogSource.choices, initial=LogSource.PHONE)
    contact = forms.ModelChoiceField(label=_("Who reported it"), queryset=ContactPerson.objects.none(), required=False)
    title = forms.CharField(label=_("Title"), max_length=200)
    text = forms.CharField(
        label=_("Description"),
        required=False,
        max_length=TEXT_MAX_LENGTH,
        widget=forms.Textarea,
        help_text=_("Plain text or Markdown: **bold**, lists with “-”, links."),
    )

    def __init__(self, *args, machine, kind, **kwargs):
        super().__init__(*args, **kwargs)
        self.kind = kind
        self.fields["text"].initial = TEXT_SKELETONS.get(kind, "")
        contacts = ContactPerson.objects.filter(is_active=True).select_related("counterparty")
        if machine.current_owner_id:
            contacts = contacts.filter(counterparty=machine.current_owner_id)
        self.fields["contact"].queryset = contacts

        installed = Equipment.objects.filter(current_machine=machine).select_related("type")
        match kind:
            case LogKind.EQUIPMENT_INSTALL:
                self.fields["equipment"] = forms.ModelChoiceField(
                    label=_("Equipment"),
                    queryset=Equipment.objects.filter(
                        state__in=[EquipmentState.IN_STOCK, EquipmentState.REMOVED]
                    ).select_related("type"),
                )
                self.fields["software_version"] = forms.CharField(
                    label=_("Software version"),
                    max_length=64,
                    required=False,
                    help_text=_("Leave empty to keep the version recorded for this unit."),
                )
            case LogKind.EQUIPMENT_REMOVAL | LogKind.EQUIPMENT_WRITE_OFF:
                self.fields["equipment"] = forms.ModelChoiceField(label=_("Equipment"), queryset=installed)
            case LogKind.SOFTWARE_UPDATE:
                self.fields["equipment"] = forms.ModelChoiceField(label=_("Equipment"), queryset=installed)
                self.fields["software_version"] = forms.CharField(label=_("New software version"), max_length=64)
            case LogKind.OWNERSHIP_CHANGE:
                self.fields["new_owner"] = forms.ModelChoiceField(
                    label=_("New owner"),
                    queryset=Counterparty.objects.filter(is_active=True).exclude(pk=machine.current_owner_id),
                )
            case LogKind.STATUS_CHANGE:
                self.fields["new_status"] = forms.ChoiceField(
                    label=_("New status"),
                    choices=[(value, label) for value, label in MachineStatus.choices if value != machine.status],
                )
            case LogKind.MAINTENANCE:
                self.fields["resolves"] = forms.ModelMultipleChoiceField(
                    label=_("Resolved issues"),
                    queryset=machine.log_entries.filter(issue_status=LogEntry.IssueStatus.OPEN),
                    required=False,
                    widget=forms.CheckboxSelectMultiple,
                )
        self.order_fields(["event_date", "source", "contact", "equipment", "software_version",
                           "new_owner", "new_status", "resolves", "title", "text"])  # fmt: skip


class AmendLogEntryForm(forms.Form):
    title = forms.CharField(label=_("Title"), max_length=200)
    text = forms.CharField(label=_("Description"), required=False, max_length=TEXT_MAX_LENGTH, widget=forms.Textarea)
