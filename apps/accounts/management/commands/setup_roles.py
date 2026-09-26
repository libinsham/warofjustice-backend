from django.core.management.base import BaseCommand
from apps.accounts.models import Role, Permission


class Command(BaseCommand):
    help = "Create and configure War of Justice roles and permissions."

    def handle(self, *args, **options):

        roles = {
            Role.SUPER_SUPER_ADMIN: (
                "Super Super Admin",
                "Full system control including bulk approval.",
            ),
            Role.SUPER_ADMIN: (
                "Super Admin",
                "Administrative and content management access. No bulk approval.",
            ),
            Role.SUPER_AUTHOR: (
                "Super Author",
                "Author access with bulk post creation.",
            ),
            Role.ADMIN: (
                "Admin / Editor",
                "Administrative and editorial access.",
            ),
            Role.AUTHOR: (
                "Author",
                "Normal article creation and submission.",
            ),
            Role.MEMBER: (
                "Member",
                "Member access.",
            ),
            Role.CONTRIBUTOR: (
                "Contributor",
                "Contributor access.",
            ),
            Role.SUBSCRIBER: (
                "Subscriber",
                "Subscriber access.",
            ),
        }

        role_objects = {}

        # -----------------------------------------------------
        # CREATE / UPDATE ROLES
        # -----------------------------------------------------

        for role_name, (label, description) in roles.items():

            role, created = Role.objects.get_or_create(
                name=role_name,
                defaults={
                    "label": label,
                    "description": description,
                },
            )

            if not created:
                role.label = label
                role.description = description
                role.save(
                    update_fields=[
                        "label",
                        "description",
                    ]
                )

            role_objects[role_name] = role

            action = "Created" if created else "Updated"

            self.stdout.write(
                self.style.SUCCESS(
                    f"{action} role: {role_name}"
                )
            )

        # -----------------------------------------------------
        # CREATE PERMISSIONS
        # -----------------------------------------------------

        permission_definitions = {
            "bulk_posts": (
                "Bulk Posts",
                "posts",
            ),
            "bulk_approval": (
                "Bulk Approval",
                "posts",
            ),
        }

        permission_objects = {}

        for codename, (label, group) in permission_definitions.items():

            permission, created = Permission.objects.get_or_create(
                codename=codename,
                defaults={
                    "label": label,
                    "group": group,
                },
            )

            if not created:
                permission.label = label
                permission.group = group
                permission.save(
                    update_fields=[
                        "label",
                        "group",
                    ]
                )

            permission_objects[codename] = permission

            action = "Created" if created else "Updated"

            self.stdout.write(
                self.style.SUCCESS(
                    f"{action} permission: {codename}"
                )
            )

        # -----------------------------------------------------
        # BULK POSTS
        # -----------------------------------------------------

        bulk_posts = permission_objects["bulk_posts"]

        for role_name in [
            Role.SUPER_SUPER_ADMIN,
            Role.SUPER_ADMIN,
            Role.SUPER_AUTHOR,
        ]:
            role_objects[role_name].permissions.add(
                bulk_posts
            )

        # -----------------------------------------------------
        # BULK APPROVAL
        # -----------------------------------------------------

        bulk_approval = permission_objects["bulk_approval"]

        # Remove this permission from EVERY role first.
        #
        # This guarantees that Super Admin and Super Author
        # cannot accidentally retain it from an earlier setup.
        bulk_approval.roles.clear()

        # ONLY Super Super Admin gets bulk approval.
        role_objects[
            Role.SUPER_SUPER_ADMIN
        ].permissions.add(
            bulk_approval
        )

        # -----------------------------------------------------
        # REMOVE BULK PERMISSIONS FROM NORMAL AUTHOR
        # -----------------------------------------------------

        role_objects[
            Role.AUTHOR
        ].permissions.remove(
            bulk_posts,
            bulk_approval,
        )

        # -----------------------------------------------------
        # FINAL OUTPUT
        # -----------------------------------------------------

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "War of Justice roles and permissions configured successfully."
            )
        )

        self.stdout.write("")

        self.stdout.write(
            "Bulk Posts:"
        )

        self.stdout.write(
            "  Super Super Admin  ✓"
        )

        self.stdout.write(
            "  Super Admin        ✓"
        )

        self.stdout.write(
            "  Super Author       ✓"
        )

        self.stdout.write(
            "  Author             ✗"
        )

        self.stdout.write("")

        self.stdout.write(
            "Bulk Approval:"
        )

        self.stdout.write(
            "  Super Super Admin  ✓"
        )

        self.stdout.write(
            "  Super Admin        ✗"
        )

        self.stdout.write(
            "  Super Author       ✗"
        )

        self.stdout.write(
            "  Author             ✗"
        )