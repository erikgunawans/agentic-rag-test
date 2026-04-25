"""Redaction sub-package.

Phase 1 milestone v1.0 — Detection & Anonymization Foundation.
See .planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md for the
locked architectural decisions (D-01..D-20) that shape this module.

Public surface (after all Phase 1 plans land):
    from app.services.redaction import RedactionError
    from app.services.redaction_service import (
        RedactionResult, RedactionService, get_redaction_service,
    )

Note: To avoid the circular import chain
    __init__.py -> redaction_service.py -> anonymization.py -> detection.py ->
    uuid_filter.py -> __init__.py
this package's `__init__.py` re-exports ONLY `RedactionError`. The service
classes live in `app.services.redaction_service` and must be imported from
that module directly.
"""

from __future__ import annotations

# Re-exports populated as Wave 2 / Wave 3 plans land. Keep this minimal.
# Plan 04 will create errors.py and re-export RedactionError below.

__all__: list[str] = []
