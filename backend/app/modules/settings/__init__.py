"""System settings — platform configuration, VAT, and invoice letterhead.

ERD §10. Owned by the platform. ``business_settings`` is TradeBay letterhead
(not a trading company's Identity business account). Historical invoices and
commission records snapshot rates — changing settings never rewrites money docs.

Read in this order:

1. ``constants.py`` · ``models.py`` · ``schemas.py``
2. ``tax.py`` · ``numbering.py``
3. ``repository.py`` · ``service.py``
4. ``router.py``
"""

from app.modules.settings.service import SettingsService

__all__ = ["SettingsService"]
