"""Re-export Trust notifier so procurement call sites stay stable."""

from app.modules.trust.notify import notify

__all__ = ["notify"]
