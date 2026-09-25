
from __future__ import annotations

from app.modules.catalog.constants import ProductStatus
from app.modules.identity.constants import SupplierVerificationStatus


def test_buyer_visible_statuses_exclude_inactive() -> None:
    from app.modules.catalog.constants import BUYER_VISIBLE_PRODUCT_STATUSES

    assert ProductStatus.ACTIVE in BUYER_VISIBLE_PRODUCT_STATUSES
    assert ProductStatus.INACTIVE not in BUYER_VISIBLE_PRODUCT_STATUSES
    assert ProductStatus.DRAFT not in BUYER_VISIBLE_PRODUCT_STATUSES

def test_verification_transition_allows_revoke_from_verified() -> None:
    from app.modules.identity.constants import VERIFICATION_TRANSITIONS

    assert (
        SupplierVerificationStatus.REVOKED
        in VERIFICATION_TRANSITIONS[SupplierVerificationStatus.VERIFIED]
    )
    assert (
        SupplierVerificationStatus.PENDING
        in VERIFICATION_TRANSITIONS[SupplierVerificationStatus.REVOKED]
    )
