"""
Legacy import path: configuration lives in ``config.py`` as ``CONFIG`` (dict) and ``config`` (view).

Prefer: ``from src.config.config import CONFIG``
"""
from src.config.config import CONFIG, ConfigView, config

__all__ = ["CONFIG", "ConfigView", "config"]
