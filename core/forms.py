from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import (
    TEXT_MAX_LENGTH,
    ContactPerson,
    Counterparty,
    Equipment,
    EquipmentState,
    LogEntry,
    LogKind,
    LogSource,
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
