"""Shared AI infrastructure (provider abstraction + stubs).

Authoritative AI *domain entities* live in:
- `app.modules.ai_sourcing` (SourcingRequest, recommendations)
- `app.modules.business_planner` (BusinessPlan, PriceEstimate)

This package must never mutate orders, payments, inventory, or permissions.
"""
