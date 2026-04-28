"""ADR-0008: effective web search toggle = L1 AND (L3 if provided else L2)."""
import pytest

from app.routers.chat import compute_web_search_effective


@pytest.mark.parametrize(
    "system, user_default, message_override, expected",
    [
        # System off: always false
        (False, False, None,  False),
        (False, True,  None,  False),
        (False, False, True,  False),
        (False, True,  True,  False),
        # System on, no override: user default decides
        (True,  False, None,  False),
        (True,  True,  None,  True),
        # System on, override provided: override wins
        (True,  False, True,  True),
        (True,  True,  False, False),
        (True,  False, False, False),
        (True,  True,  True,  True),
    ],
)
def test_compute_web_search_effective(system, user_default, message_override, expected):
    assert compute_web_search_effective(system, user_default, message_override) is expected
