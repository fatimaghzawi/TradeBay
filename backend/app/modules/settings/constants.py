from enum import StrEnum

SINGLETON_KEY = "default"


class TaxType(StrEnum):
    VAT = "VAT"
    OTHER = "OTHER"
