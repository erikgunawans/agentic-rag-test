"""Redaction error types.

Lives in its own leaf module so that other redaction modules can import
`RedactionError` without triggering package initialisation. This breaks the
otherwise-cyclic import chain:

    __init__.py
      └─ redaction_service.py (Plan 06)
          └─ anonymization.py
              └─ detection.py
                  └─ uuid_filter.py
                      └─ RedactionError  (← would re-enter __init__ if hosted there)

Plan 06's `__init__.py` may re-export this symbol (only this symbol) for
external consumers; internal modules MUST import directly from
`app.services.redaction.errors`.
"""

from __future__ import annotations


class RedactionError(Exception):
    """Raised on unrecoverable redaction state.

    Concrete cases (Phase 1):
    - D-11 sentinel collision: input already contains literal `<<UUID_`
      substring before pre-masking.
    """
