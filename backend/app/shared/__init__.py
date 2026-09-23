"""Shared cross-domain building blocks (not business rules).

Read in this order:

1. ``schemas/response.py`` / ``schemas/pagination.py`` — API envelopes
2. ``repositories/base.py`` — Motor CRUD primitives
3. ``services/audit.py`` — centralized audit writes
4. ``events/bus.py`` — in-process domain events
5. ``types/`` · ``utils/`` — money, ids, datetime, ObjectId helpers
6. ``http/skeleton.py`` — shared 501 stub for unfinished domains
"""
