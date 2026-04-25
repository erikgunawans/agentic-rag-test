"""Redaction sub-package — Phase 1 milestone v1.0.

Public surface:

- ``RedactionError`` is re-exported here for ``from app.services.redaction
  import RedactionError`` style imports.
- ``RedactionResult``, ``RedactionService``, and ``get_redaction_service``
  must be imported from the leaf module ``app.services.redaction_service``
  directly. They are NOT re-exported here.

NOTE (B2 option B): this package deliberately re-exports ONLY
``RedactionError``. Re-exporting the service classes here would re-enter
the package mid-load through the chain
``__init__ → redaction_service → anonymization → detection → uuid_filter →
__init__`` and Python would raise
``ImportError: cannot import name 'RedactionError'``.

``errors.py`` is the leaf module of the package's import graph; every
internal redaction module imports ``RedactionError`` directly from
``app.services.redaction.errors``. The re-export here is purely a
convenience for external consumers.

See ``.planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md``
(D-01..D-20) for the locked architectural decisions that shape this module.
"""

from __future__ import annotations

from app.services.redaction.errors import RedactionError

__all__ = ["RedactionError"]
