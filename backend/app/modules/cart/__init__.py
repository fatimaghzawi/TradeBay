
from __future__ import annotations

__all__ = ["router"]

def __getattr__(name: str):
    if name == "router":
        from app.modules.cart.router import router

        return router
    raise AttributeError(name)
