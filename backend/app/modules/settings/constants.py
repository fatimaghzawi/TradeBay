from enum import StrEnum

# `platform_settings` and `business_settings` are singletons keyed on this value.
SINGLETON_KEY = "default"


class TaxType(StrEnum):
    VAT = "VAT"
