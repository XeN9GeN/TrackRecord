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
APPEND_DATA_FILE = DATA_FILE.with_name("demo_data_extra.json")


class Command(BaseCommand):
    help = "Fill an empty demo database or append the extended demo dataset."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="demo-pass-2026", help="Password for all demo users.")
        parser.add_argument("--append", action="store_true", help="Add the extended dataset to a demo database.")
        parser.add_argument("--author", help="Existing active username to credit for entries added with --append.")

    @transaction.atomic
    def handle(self, *args, password, append, author, **options):
        if append != bool(author):
            raise CommandError("--append and --author must be used together.")
        if not append and Machine.objects.exists():
            raise CommandError("The database already has machines; demo data is loaded only into an empty one.")
        data_file = APPEND_DATA_FILE if append else DATA_FILE
        data = json.loads(data_file.read_text(encoding="utf-8"))
        today = timezone.localdate()

        models = {
            item["name"]: MachineModel.objects.get_or_create(
                name=item["name"], defaults={"manufacturer": item["manufacturer"]}
            )[0]
            for item in data["machine_models"]
        }
        first_machine = None
        if append:
            user = User.objects.filter(username=author, is_active=True).first()
            if user is None or not user.has_perm("core.add_logentry"):
                raise CommandError("--author must identify an active user who can add log entries.")
            users = {"demo": user}
            first, *remaining = data["machines"]
            # The machine's unique key serializes concurrent attempts to import this batch.
            first_machine, created = Machine.objects.get_or_create(
                model=models[first["model"]], factory_number=first["factory_number"]
            )
            if not created:
                numbers = [item["factory_number"] for item in remaining]
                existing_keys = set(
                    Machine.objects.filter(factory_number__in=numbers).values_list("model_id", "factory_number")
                )
                expected_keys = {(models[item["model"]].pk, item["factory_number"]) for item in remaining}
                if not expected_keys <= existing_keys:
                    raise CommandError("The extended demo dataset has conflicting machine numbers.")
                self.stdout.write("The extended demo dataset is already present.")
                return
        else:
            users = self.create_demo_users(data["users"], password)

        counterparties, contacts = {}, {}
        for item in data["counterparties"]:
            counterparty = Counterparty.objects.create(name=item["name"], inn=item["inn"], region=item["region"])
            counterparties[counterparty.name] = counterparty
            for contact in item["contacts"]:
                contacts[contact["full_name"]] = ContactPerson.objects.create(counterparty=counterparty, **contact)

        equipment = {}
        for item in data["equipment"]:
            unit_type, _ = EquipmentType.objects.get_or_create(name=item["type"])
            fields = {key: value for key, value in item.items() if key != "type"}
            unit = Equipment.objects.create(type=unit_type, **fields)
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

        entries = len(data["written_off_from_stock"])
        for item in data["machines"]:
            machine = first_machine or Machine.objects.create(
                model=models[item["model"]], factory_number=item["factory_number"]
            )
            first_machine = None
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

        summary = (
            f"Created {len(counterparties)} counterparties, {len(contacts)} contacts, "
            f"{len(data['machines'])} machines, {len(equipment)} equipment units and {entries} log entries."
        )
        if not append:
            summary = f"Created {len(users)} users. {summary} Users: {', '.join(users)}; password: {password}"
        self.stdout.write(self.style.SUCCESS(summary))

    def create_demo_users(self, items, password):
        users = {}
        for item in items:
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
        return users
