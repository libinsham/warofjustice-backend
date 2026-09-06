from django.contrib.auth.base_user import BaseUserManager


class CustomUserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):

        if not email:
            raise ValueError("The Email field must be set")

        email = self.normalize_email(email)

        # Get Role model dynamically
        Role = self.model._meta.get_field("role").remote_field.model

        # Assign Reader role by default
        if "role" not in extra_fields:
            role, _ = Role.objects.get_or_create(
                name=Role.READER,
                defaults={
                    "label": "Reader",
                    "description": "Default reader role",
                }
            )
            extra_fields["role"] = role

        user = self.model(
            email=email,
            **extra_fields
        )

        user.set_password(password)
        user.save(using=self._db)

        return user


    def create_superuser(self, email, password=None, **extra_fields):

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("status", "active")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        # Get Role model dynamically
        Role = self.model._meta.get_field("role").remote_field.model

        # Automatically create/get Super Admin role
        role, _ = Role.objects.get_or_create(
            name=Role.SUPER_ADMIN,
            defaults={
                "label": "Super Admin",
                "description": "Full system administrator access",
            }
        )

        extra_fields["role"] = role

        return self.create_user(
            email,
            password,
            **extra_fields
        )