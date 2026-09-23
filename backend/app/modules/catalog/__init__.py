"""Marketplace catalog domain — products, pricing, inventory.

Conceptually this is the TradeBay Marketplace domain. The package name
``catalog`` is retained for stability; ``marketplace`` is an alias/stub.

Read in this order:

1. ``constants.py`` · ``models.py`` · ``schemas.py``
2. ``repository.py`` · ``storage.py`` (product images)
3. ``service.py`` — categories, products, prices, stock mutations
4. ``router.py`` — ``/catalog/*`` and ``/inventory/*``
"""

from app.modules.catalog.router import router

__all__ = ["router"]
