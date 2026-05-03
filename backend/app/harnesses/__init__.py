"""Auto-import every harness module so each register(definition) call runs at startup.

Gated on settings.harness_enabled — when off, the registry stays empty and the
codebase is byte-identical to pre-Phase-20 (D-16 invariant).

Import order is alphabetical (deterministic). Module names starting with '_'
are skipped (allows _internal helpers).
"""
from __future__ import annotations

import importlib
import logging
import pkgutil
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)

if get_settings().harness_enabled:
    _pkg_dir = Path(__file__).parent
    for _info in pkgutil.iter_modules([str(_pkg_dir)]):
        if _info.name.startswith("_"):
            continue
        try:
            importlib.import_module(f"{__name__}.{_info.name}")
            logger.info("harnesses: auto-imported %s", _info.name)
        except Exception as exc:
            logger.error(
                "harnesses: failed to import %s: %s",
                _info.name,
                exc,
                exc_info=True,
            )
else:
    logger.info(
        "harnesses: HARNESS_ENABLED=False — registry stays empty (byte-identical mode)"
    )
