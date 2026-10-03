from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.documents.models import Membership
from apps.documents.services.numbering import assign_membership_number


@transaction.atomic
def create_or_get_membership(
    *,
    user,
    application=None,
    membership_type: str,
    approved_by=None,
    designation: str = "",
    expiry_date=None,
) -> Membership:
    """
    Create or return the membership associated with a user.

    This function is intentionally reusable by:
    - Contributor approval
    - Member approval
    - Subscriber approval
    - Future admin workflows
    """

    membership = Membership.objects.filter(
        user=user
    ).first()

    if membership:
        changed_fields = []

        if approved_by and membership.approved_by_id != approved_by.id:
            membership.approved_by = approved_by
            changed_fields.append("approved_by")

        if membership.status != Membership.ACTIVE:
            membership.status = Membership.ACTIVE
            changed_fields.append("status")

        if membership.approved_at is None:
            membership.approved_at = timezone.now()
            changed_fields.append("approved_at")

        if designation and membership.designation != designation:
            membership.designation = designation
            changed_fields.append("designation")

        if expiry_date and membership.expiry_date != expiry_date:
            membership.expiry_date = expiry_date
            changed_fields.append("expiry_date")

        if changed_fields:
            changed_fields.append("updated_at")
            membership.save(update_fields=changed_fields)

        if not membership.membership_id:
            assign_membership_number(membership)

        return membership

    membership = Membership.objects.create(
        user=user,
        member_contributor_application=application,
        membership_type=membership_type,
        designation=designation,
        issue_date=timezone.localdate(),
        expiry_date=expiry_date,
        status=Membership.ACTIVE,
        approved_by=approved_by,
        approved_at=timezone.now(),
    )

    assign_membership_number(membership)

    return membership