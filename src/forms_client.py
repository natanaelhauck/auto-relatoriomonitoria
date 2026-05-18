"""Google Forms submission client."""

from collections.abc import Mapping
from typing import Any


def submit_form_payload(form_url: str, payload: Mapping[str, Any]) -> None:
    """Submit a normalized payload to Google Forms.

    Args:
        form_url: Target Google Forms URL.
        payload: Field mapping expected by the form.
    """
    raise NotImplementedError("Google Forms submission is not implemented yet.")
