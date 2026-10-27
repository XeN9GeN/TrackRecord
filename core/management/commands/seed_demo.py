import datetime
import json
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import (
    ContactPerson,
    Counterparty,
    Equipment,
    EquipmentType,
    LogKind,
    Machine,
    MachineModel,
)
from core.services import create_log_entry

DATA_FILE = Path(__file__).resolve().parents[2] / "demo_data.json"


class Command(BaseCommand):
    help = "Fill an empty database with demo machines, counterparties, equipment and history."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="demo-pass-2026", help="Password for all demo users.")

    @transaction.atomic
    def handle(self, *args, password, **options):
        if Machine.objects.exists():
            raise CommandError("The database already has machines; demo data is loaded only into an empty one.")
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        today = timezone.localdate()

        users = {}
        for item in data["users"]:
            user = User.objects.create_user(
                item["username"],
                password=password,
                first_name=item["first_name"],
                last_name=item["last_name"],
                is_staff=item.get("superuser", False) or item["group"] == "Administrator",
                is_superuser=item.get("superuser", False),
            )
            user.groups.add(Group.objects.get(name=item["group"]))
            users[user.username] = user

        counterparties, contacts = {}, {}
        for item in data["counterparties"]:
            counterparty = Counterparty.objects.create(name=item["name"], inn=item["inn"], region=item["region"])
            counterparties[counterparty.name] = counterparty
            for contact in item["contacts"]:
                contacts[contact["full_name"]] = ContactPerson.objects.create(counterparty=counterparty, **contact)

        models = {item["name"]: MachineModel.objects.create(**item) for item in data["machine_models"]}
        equipment = {}
        for item in data["equipment"]:
            unit_type, _ = EquipmentType.objects.get_or_create(name=item.pop("type"))
            unit = Equipment.objects.create(type=unit_type, **item)
            equipment[unit.serial_number] = unit

        for item in data["written_off_from_stock"]:
            create_log_entry(
                author=users[item["author"]],
                kind=LogKind.EQUIPMENT_WRITE_OFF,
                equipment=equipment[item["serial_number"]],
                event_date=today - datetime.timedelta(days=item["days_ago"]),
                title=item["title"],
                text=item.get("text", ""),
            )

        entries = 0
        for item in data["machines"]:
            machine = Machine.objects.create(model=models[item["model"]], factory_number=item["factory_number"])
            refs = {}
            for event in item["history"]:
                entry = create_log_entry(
                    author=users[event["author"]],
                    machine=machine,
                    kind=event["kind"],
                    source=event["source"],
                    event_date=today - datetime.timedelta(days=event["days_ago"]),
                    title=event["title"],
                    text=event.get("text", ""),
                    contact=contacts.get(event.get("contact")),
                    equipment=equipment.get(event.get("equipment")),
                    software_version=event.get("software_version"),
                    new_owner=counterparties.get(event.get("new_owner")),
                    new_status=event.get("new_status"),
                    resolves=[refs[ref] for ref in event.get("resolves", [])],
                )
                if "ref" in event:
                    refs[event["ref"]] = entry
                entries += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(users)} users, {len(counterparties)} counterparties, "
                f"{len(data['machines'])} machines and {entries} log entries. "
                f"Users: {', '.join(users)}; password: {password}"
            )
        )
