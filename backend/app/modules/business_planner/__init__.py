"""Business Planner — guided discovery → catalog-backed plan → sourcing handoff.

Plans may be user- or guest-scoped. Marketplace stats come from catalog
aggregates; financial arithmetic is deterministic Decimal code.

Read in this order:

1. ``constants.py`` · ``models.py`` · ``schemas.py`` · ``exceptions.py``
2. ``guest.py`` · ``market.py`` · ``finance.py`` · ``planner_ai.py``
3. ``repository.py`` · ``service.py``
4. ``router.py`` (sessions + plans routers)
"""
