"""Store translated labels for the permissions Django creates in English.

``django.contrib.auth`` builds permission names as ``"Can <action> <model>"``
from the model's untranslated verbose name and stores them in the database.
The admin renders that stored string as-is, so a Russian UI shows a mix such as
``Can add historical contact person``. This command regenerates the names from
the translated model labels and the Russian action verbs.

It is idempotent and runs after ``migrate`` so permissions for new models are
localised as well.
"""

from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override

ACTION_TEMPLATES = {
    "add": _("Can add %(model)s"),
    "change": _("Can change %(model)s"),
    "delete": _("Can delete %(model)s"),
    "view": _("Can view %(model)s"),
}


class Command(BaseCommand):
    help = "Replace Django's English permission names with translated ones."

    def handle(self, *args, **options):
        changed = []
        with override("ru"):
            for permission in Permission.objects.select_related("content_type"):
                model = permission.content_type.model_class()
                if model is None:
                    continue
                action = permission.codename.split("_", 1)[0]
                template = ACTION_TEMPLATES.get(action)
                if template is None:
                    continue
                name = str(template) % {"model": model._meta.verbose_name}
                if permission.name != name:
                    permission.name = name
                    changed.append(permission)
        if changed:
            Permission.objects.bulk_update(changed, ["name"])
        self.stdout.write(f"Localised {len(changed)} permission names.")
