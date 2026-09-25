"""AI Sourcing — requirement extraction and catalog recommendations.

Uses shared ``AIProvider`` for language understanding and ``MongoHybridRetriever``
for catalog matching. Marketplace facts (prices, stock, verification)
come from catalog + identity only. Never invents suppliers, prices, or verification.

Read in this order:

1. ``constants.py`` · ``models.py`` · ``schemas.py`` · ``exceptions.py``
2. ``recommendation.py`` — scoring / matching
3. ``repository.py`` · ``service.py``
4. ``router.py``
"""
