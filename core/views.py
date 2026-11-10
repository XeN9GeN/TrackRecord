from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Exists, F, Max, OuterRef, Q, Subquery, Value
from django.db.models.functions import Concat, Trim
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from .forms import (
    FORM_KINDS,
    AmendLogEntryForm,
    CounterpartyFilterForm,
    EquipmentFilterForm,
    LogEntryForm,
    MachineFilterForm,
)
from .models import ContactPerson, Counterparty, Equipment, IssueStatus, LogEntry, LogKind, Machine
from .services import amend_log_entry, can_amend, create_log_entry


def _filter_last_contact(objects, filters):
    if filters.get("contact") == "never":
        objects = objects.filter(last_contact_at__isnull=True)
    elif filters.get("contact") == "overdue":
        cutoff = timezone.localdate() - timedelta(days=90)
        objects = objects.filter(Q(last_contact_at__date__lte=cutoff) | Q(last_contact_at__isnull=True))
    if filters.get("contact_from"):
        objects = objects.filter(last_contact_at__date__gte=filters["contact_from"])
    if filters.get("contact_to"):
        objects = objects.filter(last_contact_at__date__lte=filters["contact_to"])
    return objects


def _list_context(request, objects, form, name, sort_fields, default_sort):
    filters = form.cleaned_data
    fields = sort_fields[filters.get("sort") or default_sort]
    descending = filters.get("direction") == "desc"
    ordering = [F(field).desc(nulls_last=True) if descending else F(field).asc(nulls_last=True) for field in fields]
    page = Paginator(objects.order_by(*ordering, "pk"), filters.get("per_page") or 25).get_page(request.GET.get("page"))
    active_filters = []
    for field in form:
        value = filters.get(field.name)
        if field.name in {"sort", "direction", "per_page"} or value in (None, ""):
            continue
        if hasattr(field.field, "queryset"):
            label = str(value)
        else:
            choices = {str(key): label for key, label in getattr(field.field, "choices", ())}
            label = choices.get(str(value), value)
        params = request.GET.copy()
        params.pop(field.name, None)
        params.pop("page", None)
        active_filters.append({"name": field.name, "label": field.label, "value": label, "url": "?" + params.urlencode()})
    additional_names = {field for _, names in form.additional_filter_groups for field in names}
    return {
        "filter_form": form, name: page.object_list, "query": filters.get("q", ""), "page": page,
        "active_filters": active_filters,
        "additional_filter_count": sum(item["name"] in additional_names for item in active_filters),
    }


@login_required
def equipment_list(request):
    form = EquipmentFilterForm(request.GET)
    form.is_valid()
    filters = form.cleaned_data
    equipment = Equipment.objects.select_related("type", "current_machine__model", "current_machine__current_owner")
    for term in filters.get("q", "").split():
        equipment = equipment.filter(
            Q(serial_number__icontains=term)
            | Q(type__name__icontains=term)
            | Q(current_machine__factory_number__icontains=term)
            | Q(current_machine__model__name__icontains=term)
            | Q(current_machine__current_owner__name__icontains=term)
        )
    if filters.get("state"):
        equipment = equipment.filter(state=filters["state"])
    if filters.get("type"):
        equipment = equipment.filter(type=filters["type"])
    if filters.get("machine"):
        equipment = equipment.filter(current_machine=filters["machine"])
    if filters.get("owner"):
        equipment = equipment.filter(current_machine__current_owner=filters["owner"])
    context = _list_context(request, equipment, form, "equipment", {
        "type": ("type__name", "serial_number"), "serial": ("serial_number", "type__name"),
        "year": ("production_year", "type__name", "serial_number"),
        "software": ("software_version", "type__name", "serial_number"),
        "state": ("state", "type__name", "serial_number"),
        "machine": ("current_machine__model__name", "current_machine__factory_number", "serial_number"),
        "owner": ("current_machine__current_owner__name", "type__name", "serial_number"),
    }, "type")
    return render(request, "core/equipment_list.html", context)


@login_required
def equipment_detail(request, pk):
    equipment = get_object_or_404(
        Equipment.objects.select_related("type", "current_machine__model", "current_machine__current_owner"), pk=pk
    )
    kind = request.GET.get("kind", "")
    if kind not in LogEntry.EQUIPMENT_KINDS:
        kind = ""
    entries = equipment.log_entries.select_related(
        "machine__model", "author", "contact", "equipment__type", "new_owner", "resolved_by"
    ).prefetch_related("resolved_issues").order_by("-event_date", "-created_at", "-pk")
    present_kinds = set(equipment.log_entries.values_list("kind", flat=True).distinct())
    if kind:
        entries = entries.filter(kind=kind)
    context = {
        "equipment": equipment,
        "page": Paginator(entries, 30).get_page(request.GET.get("page")),
        "kind_filter": [(value, label) for value, label in LogKind.choices if value in present_kinds],
        "selected_kind": kind,
    }
    return render(request, "core/equipment_detail.html", context)


@login_required
def counterparty_list(request):
    form = CounterpartyFilterForm(request.GET)
    form.is_valid()
    filters = form.cleaned_data
    counterparties = Counterparty.objects.defer("notes").annotate(
        machine_count=Count("machines", distinct=True),
        active_contact_count=Count("contacts", filter=Q(contacts__is_active=True), distinct=True),
        last_contact_at=Max("machines__last_contact_at"),
    )
    for term in filters.get("q", "").split():
        contacts = ContactPerson.objects.filter(counterparty=OuterRef("pk"), is_active=True).filter(
            Q(full_name__icontains=term) | Q(phones__icontains=term) | Q(email__icontains=term)
        )
        machines = Machine.objects.filter(current_owner=OuterRef("pk")).filter(
            Q(factory_number__icontains=term) | Q(model__name__icontains=term)
        )
        counterparties = counterparties.filter(
            Q(name__icontains=term) | Q(inn__icontains=term) | Q(region__icontains=term)
            | Q(Exists(contacts)) | Q(Exists(machines))
        )
    if filters.get("activity"):
        counterparties = counterparties.filter(is_active=filters["activity"] == "active")
    if filters.get("region"):
        counterparties = counterparties.filter(region=filters["region"])
    if filters.get("machines"):
        if filters["machines"] == "yes":
            counterparties = counterparties.filter(machine_count__gt=0)
        else:
            counterparties = counterparties.filter(machine_count=0)
    if filters.get("contacts"):
        if filters["contacts"] == "yes":
            counterparties = counterparties.filter(active_contact_count__gt=0)
        else:
            counterparties = counterparties.filter(active_contact_count=0)
    counterparties = _filter_last_contact(counterparties, filters)
    context = _list_context(request, counterparties, form, "counterparties", {
        "name": ("name",), "inn": ("inn", "name"), "region": ("region", "name"),
        "machines": ("machine_count", "name"), "contacts": ("active_contact_count", "name"),
        "contact": ("last_contact_at", "name"),
    }, "name")
    return render(request, "core/counterparty_list.html", context)


@login_required
def counterparty_detail(request, pk):
    counterparty = get_object_or_404(Counterparty, pk=pk)
    machines = (
        counterparty.machines.select_related("model")
        .annotate(open_issues=Count("log_entries", filter=Q(log_entries__issue_status=IssueStatus.OPEN)))
        .order_by("model__name", "factory_number")
    )
    context = {
        "counterparty": counterparty,
        "contacts": counterparty.contacts.filter(is_active=True),
        "machines": machines,
    }
    return render(request, "core/counterparty_detail.html", context)


@login_required
def machine_list(request):
    form = MachineFilterForm(request.GET)
    form.is_valid()
    filters = form.cleaned_data
    machines = Machine.objects.select_related("model", "current_owner").annotate(
        open_issues=Count("log_entries", filter=Q(log_entries__issue_status=IssueStatus.OPEN))
    )
    for term in filters.get("q", "").split():
        equipment = Equipment.objects.filter(current_machine=OuterRef("pk")).filter(
            Q(serial_number__icontains=term) | Q(type__name__icontains=term)
        )
        machines = machines.filter(
            Q(factory_number__icontains=term)
            | Q(model__name__icontains=term)
            | Q(current_owner__name__icontains=term)
            | Q(current_owner__region__icontains=term)
            | Q(Exists(equipment))
        )
    if filters.get("status"):
        machines = machines.filter(status=filters["status"])
    if filters.get("model"):
        machines = machines.filter(model=filters["model"])
    if filters.get("owner") == "unassigned":
        machines = machines.filter(current_owner__isnull=True)
    elif filters.get("owner"):
        machines = machines.filter(current_owner_id=filters["owner"])
    if filters.get("region"):
        machines = machines.filter(current_owner__region=filters["region"])
    if filters.get("issues"):
        if filters["issues"] == "yes":
            machines = machines.filter(open_issues__gt=0)
        else:
            machines = machines.filter(open_issues=0)
    installed = Equipment.objects.filter(current_machine=OuterRef("pk"))
    if filters.get("equipment") == "yes":
        machines = machines.filter(Exists(installed))
    elif filters.get("equipment") == "no":
        machines = machines.filter(~Exists(installed))
    if filters.get("equipment_type"):
        machines = machines.filter(Exists(installed.filter(type=filters["equipment_type"])))
    machines = _filter_last_contact(machines, filters)
    context = _list_context(request, machines, form, "machines", {
        "machine": ("model__name", "factory_number"), "number": ("factory_number", "model__name"),
        "owner": ("current_owner__name", "model__name", "factory_number"),
        "region": ("current_owner__region", "model__name", "factory_number"),
        "issues": ("open_issues", "model__name", "factory_number"),
        "contact": ("last_contact_at", "model__name", "factory_number"),
    }, "machine")
    return render(request, "core/machine_list.html", context)


@login_required
def machine_detail(request, pk):
    machine = get_object_or_404(Machine.objects.select_related("model", "current_owner"), pk=pk)
    kind = request.GET.get("kind", "")
    entries = machine.log_entries.select_related(
        "author", "contact", "equipment__type", "new_owner", "resolved_by"
    ).prefetch_related("resolved_issues")
    if kind in LogKind.values:
        entries = entries.filter(kind=kind)
    installations = LogEntry.objects.filter(
        equipment=OuterRef("pk"), machine=machine, kind=LogKind.EQUIPMENT_INSTALL
    ).order_by("-event_date", "-created_at")
    installed = machine.installed_equipment.select_related("type").annotate(
        installed_on=Subquery(installations.values("event_date")[:1]),
        installed_by=Subquery(
            installations.annotate(
                name=Trim(Concat("author__first_name", Value(" "), "author__last_name"))
            ).values("name")[:1]
        ),
    )
    present_kinds = set(machine.log_entries.values_list("kind", flat=True).distinct())
    context = {
        "machine": machine,
        "contacts": machine.current_owner.contacts.filter(is_active=True) if machine.current_owner else [],
        "installed": installed,
        "open_issues": machine.log_entries.filter(issue_status=IssueStatus.OPEN).defer("text"),
        "page": Paginator(entries, 30).get_page(request.GET.get("page")),
        "kind_filter": [(value, label) for value, label in LogKind.choices if value in present_kinds],
        "selected_kind": kind,
    }
    return render(request, "core/machine_detail.html", context)


@login_required
@permission_required("core.add_logentry", raise_exception=True)
def log_entry_create(request, machine_pk):
    machine = get_object_or_404(Machine.objects.select_related("model", "current_owner"), pk=machine_pk)
    kind = request.GET.get("kind", "")
    if kind not in FORM_KINDS:
        return render(request, "core/log_entry_kind.html", {"machine": machine, "form_kinds": FORM_KINDS})
    kind = LogKind(kind)
    form = LogEntryForm(request.POST or None, machine=machine, kind=kind)
    if request.method == "POST" and form.is_valid():
        try:
            create_log_entry(author=request.user, machine=machine, kind=kind, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, _("Entry added."))
            return redirect("core:machine_detail", pk=machine.pk)
    return render(request, "core/log_entry_form.html", {"machine": machine, "form": form, "kind": kind})


@login_required
def log_entry_detail(request, pk):
    entry = get_object_or_404(
        LogEntry.objects.select_related("machine__model", "author", "contact", "equipment__type", "new_owner"),
        pk=pk,
    )
    context = {
        "entry": entry,
        "revisions": entry.revisions.select_related("edited_by"),
        "can_amend": can_amend(request.user, entry),
    }
    return render(request, "core/log_entry_detail.html", context)


@login_required
def log_entry_amend(request, pk):
    entry = get_object_or_404(LogEntry.objects.select_related("machine__model"), pk=pk)
    if not can_amend(request.user, entry):
        raise PermissionDenied
    form = AmendLogEntryForm(request.POST or None, initial={"title": entry.title, "text": entry.text})
    if request.method == "POST" and form.is_valid():
        try:
            changed = amend_log_entry(entry, editor=request.user, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            if changed:
                messages.success(request, _("Entry updated, the previous version is kept."))
            return redirect("core:log_entry_detail", pk=entry.pk)
    return render(request, "core/log_entry_amend.html", {"entry": entry, "form": form})
