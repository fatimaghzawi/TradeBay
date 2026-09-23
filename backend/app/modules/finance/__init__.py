"""Customer Finance (AR) — invoices, payments, credit notes, refunds.

Independent from Platform Money (commissions/payouts). Persistence is currently
inline in the service (no separate repository module yet).

Read in this order:

1. ``constants.py`` · ``models.py`` · ``schemas.py`` · ``balance.py``
2. ``exceptions.py``
3. ``service.py`` — AR use-cases
4. ``router.py``
"""
