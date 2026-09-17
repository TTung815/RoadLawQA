"""Legal support states and the current production provenance boundary."""

from typing import Literal

SupportState = Literal["positive_support", "negative_support", "unknown"]


def publishable_support(state: SupportState) -> bool:
    """No production source currently proves exhaustive negative applicability.

    Clause membership metadata and model confidence cannot authorize a negative
    conclusion. Keep negatives blocked until trusted rule-scope provenance exists.
    """
    return state == "positive_support"
