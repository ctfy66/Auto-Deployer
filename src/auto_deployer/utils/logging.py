"""Logging helpers."""

from __future__ import annotations

import logging
from typing import Optional

_LOGGING_CONFIGURED = False


def get_logger(name: Optional[str] = None) -> logging.Logger:
    global _LOGGING_CONFIGURED
    if not _LOGGING_CONFIGURED:
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s] %(levelname)s %(name)s - %(message)s",
        )
        _LOGGING_CONFIGURED = True
    return logging.getLogger(name)
