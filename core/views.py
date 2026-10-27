from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, OuterRef, Q, Subquery, Value
from django.db.models.functions import Concat, Trim
from django.shortcuts import get_object_or_404, render

from .forms import FORM_KINDS
from .models import IssueStatus, LogEntry, LogKind, Machine


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
        "form_kinds": FORM_KINDS,
    }
    return render(request, "core/machine_detail.html", context)
