
from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.modules.settings.constants import SINGLETON_KEY
from app.shared.types.address import AddressEmbedded
from app.shared.types.document import MongoDocument
from app.shared.types.ids import OptionalDocumentId
from app.shared.types.money import Money, OptionalMoney


class PlatformSettingsDocument(MongoDocument):

    key: str = Field(default=SINGLETON_KEY)
    platform_name: str
    default_currency: str = "USD"
    commission_rate: Money
    commission_type: str
    commission_base: str
    minimum_order_value: OptionalMoney = None
    payment_provider: str | None = None
    payment_provider_active: bool = False
    updated_by: OptionalDocumentId = None
    created_at: datetime
    updated_at: datetime

class TaxSettingsDocument(MongoDocument):

    name: str
    rate: Money
    type: str = "VAT"
    is_active: bool = True
    effective_from: datetime
    effective_until: datetime | None = None
    updated_by: OptionalDocumentId = None
    created_at: datetime
    updated_at: datetime

class BusinessSettingsDocument(MongoDocument):

    key: str = Field(default=SINGLETON_KEY)
    business_name: str
    business_email: str | None = None
    business_phone: str | None = None
    address: AddressEmbedded | None = None
    tax_registration_number: str | None = None
    invoice_prefix: str = "TB-INV"
    updated_by: OptionalDocumentId = None
    created_at: datetime
    updated_at: datetime
