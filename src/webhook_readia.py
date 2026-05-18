"""Webhook entry points for future Read IA integrations."""

from collections.abc import Mapping
from typing import Any


def handle_readia_webhook(payload: Mapping[str, Any]) -> dict[str, str]:
    """Handle a Read IA webhook payload.

    Args:
        payload: Raw webhook payload received from Read IA.
    """
    raise NotImplementedError("Read IA webhook handling is not implemented yet.")
