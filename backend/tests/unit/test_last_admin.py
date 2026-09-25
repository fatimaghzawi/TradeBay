
from app.modules.identity.guards import would_remove_last_admin
from bson import ObjectId


def test_last_admin_blocked_when_only_one_remains() -> None:
    admin = ObjectId()
    assert would_remove_last_admin(
        membership_role_id=admin,
        admin_role_id=admin,
        active_admin_count=1,
    )

def test_last_admin_allows_non_admin_or_multiple_admins() -> None:
    admin = ObjectId()
    other = ObjectId()
    assert not would_remove_last_admin(
        membership_role_id=other,
        admin_role_id=admin,
        active_admin_count=1,
    )
    assert not would_remove_last_admin(
        membership_role_id=admin,
        admin_role_id=admin,
        active_admin_count=2,
    )
