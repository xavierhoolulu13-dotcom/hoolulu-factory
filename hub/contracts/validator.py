"""A small, dependency-free JSON Schema checker.

Supports the subset the hub's contracts actually use: ``type``, ``required``,
``properties``, ``items``, ``enum``, ``pattern``, ``minimum``, ``maximum``,
``minLength``, ``minItems``. Deliberately not a full implementation — the point
is that contract validation works on a phone with no pip, so it is ~90 lines
instead of a dependency.
"""

from __future__ import annotations

import re

_RANGE = {
    "integer": int,
    "number": (int, float),
    "string": str,
    "object": dict,
    "array": list,
    "boolean": bool,
    "null": type(None),
}


def validate(instance, schema, path="$"):
    """Return a list of human-readable errors. Empty list means valid."""
    errors: list[str] = []

    types = schema.get("type")
    if types is not None:
        wanted = types if isinstance(types, list) else [types]
        if "null" in wanted and instance is None:
            return errors
        ok = any(_is_type(instance, t) for t in wanted)
        if not ok:
            errors.append(f"{path}: expected {'|'.join(wanted)}, got {_name(instance)}")
            return errors  # no point checking deeper on a type mismatch

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in {schema['enum']}")

    if isinstance(instance, str):
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: {instance!r} does not match {schema['pattern']}")
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: shorter than {schema['minLength']} chars")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance} < minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: {instance} > maximum {schema['maximum']}")

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}.{key}: required")
        props = schema.get("properties", {})
        for key, value in instance.items():
            if key in props:
                errors.extend(validate(value, props[key], f"{path}.{key}"))

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: needs at least {schema['minItems']} item(s)")
        item_schema = schema.get("items")
        if item_schema:
            for index, value in enumerate(instance):
                errors.extend(validate(value, item_schema, f"{path}[{index}]"))

    return errors


def _is_type(instance, type_name: str) -> bool:
    expected = _RANGE.get(type_name)
    if expected is None:
        return True
    if type_name in ("integer", "number") and isinstance(instance, bool):
        return False
    return isinstance(instance, expected)


def _name(instance) -> str:
    return "null" if instance is None else type(instance).__name__
