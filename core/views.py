from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, OuterRef, Q, Subquery, Value
from django.db.models.functions import Concat, Trim
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from .forms import FORM_KINDS, AmendLogEntryForm, LogEntryForm
from .models import IssueStatus, LogEntry, LogKind, Machine
from .services import amend_log_entry, can_amend, create_log_entry


@login_required
def machine_list(request):
    query = request.GET.get("q", "").strip()
    machines = Machine.objects.select_related("model", "current_owner").annotate(
        open_issues=Count("log_entries", filter=Q(log_entries__issue_status=IssueStatus.OPEN))
    )
    if query:
        machines = machines.filter(
            Q(factory_number__icontains=query)
            | Q(model__name__icontains=query)
            | Q(current_owner__name__icontains=query)
            | Q(current_owner__region__icontains=query)
        )
    return render(request, "core/machine_list.html", {"machines": machines, "query": query})


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
