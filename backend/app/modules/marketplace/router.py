"""Marketplace API aliases — same routes as catalog (products, categories, inventory)."""

from app.modules.catalog.router import router

__all__ = ["router"]
