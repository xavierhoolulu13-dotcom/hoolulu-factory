"""Typed boundaries between stages. See ``core/contracts/``."""

from __future__ import annotations

import json

from .. import config
from .validator import validate

__all__ = ["load", "validate_contract", "check", "ContractError", "validator"]

_CACHE: dict[str, dict] = {}


class ContractError(ValueError):
    """Raised when a stage tries to hand over data that breaks its contract."""


def load(name: str) -> dict:
    """Load a contract schema by short name (``product``, ``build``, ...)."""
    if name not in _CACHE:
        path = config.CONTRACTS_DIR / f"{name}.schema.json"
        if not path.exists():
            raise ContractError(f"unknown contract '{name}' (looked in {path})")
        _CACHE[name] = json.loads(path.read_text())
    return _CACHE[name]


def validate_contract(name: str, instance) -> list[str]:
    """Validate ``instance`` against contract ``name``. Returns error strings."""
    return validate(instance, load(name))


def check(name: str, instance, *, strict: bool = True) -> list[str]:
    """Validate and, unless ``strict`` is False, raise on the first problem."""
    errors = validate_contract(name, instance)
    if errors and strict:
        raise ContractError(f"{name} contract failed: " + "; ".join(errors[:5]))
    return errors
