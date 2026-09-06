from django.core.management.base import BaseCommand

from apps.accounts.models import Permission, Role


PERMISSIONS = [
    "posts.create", "posts.edit_own", "posts.edit_any", "posts.delete_own",
    "posts.delete_any", "posts.submit", "posts.approve", "posts.reject",
    "posts.request_changes", "posts.publish", "posts.archive",
    "categories.manage", "tags.manage",
    "media.upload", "media.manage_any",
    "users.manage", "authors.manage",
    "comments.moderate", "settings.manage", "logs.view", "analytics.view",
]

ROLE_PERMS = {
    Role.SUPER_ADMIN: PERMISSIONS,  # redundant (is_super_admin() already bypasses checks)
    Role.ADMIN: [
        "posts.edit_any", "posts.delete_any", "posts.approve", "posts.reject",
        "posts.request_changes", "posts.publish", "posts.archive",
        "categories.manage", "tags.manage", "media.manage_any",
        "authors.manage", "comments.moderate", "analytics.view",
    ],
    Role.AUTHOR: ["posts.create", "posts.edit_own", "posts.delete_own", "posts.submit", "media.upload"],
    Role.READER: [],
}

ROLE_LABELS = {
    Role.SUPER_ADMIN: "Super Admin",
    Role.ADMIN: "Admin / Editor",
    Role.AUTHOR: "Author / User",
    Role.READER: "Reader",
}


class Command(BaseCommand):
    help = "Seed War of Justice roles and permissions (idempotent)."

    def handle(self, *args, **options):
        perm_objs = {}
        for codename in PERMISSIONS:
            perm, _ = Permission.objects.get_or_create(
                codename=codename,
                defaults={"label": codename.replace(".", " - ").replace("_", " ").title(),
                          "group": codename.split(".")[0]},
            )
            perm_objs[codename] = perm

        for role_name, label in ROLE_LABELS.items():
            role, _ = Role.objects.get_or_create(name=role_name, defaults={"label": label})
            role.permissions.set([perm_objs[c] for c in ROLE_PERMS[role_name]])

        self.stdout.write(self.style.SUCCESS("Roles and permissions seeded."))
