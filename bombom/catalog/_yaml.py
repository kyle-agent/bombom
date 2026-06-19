"""Decimal-safe YAML loading.

The upstream devicetype-library validates with floats parsed as ``decimal.Decimal`` so that
JSON-Schema ``multipleOf`` constraints (e.g. weight is a multiple of 0.01) are checked with
exact arithmetic instead of binary-float approximations. We mirror that exactly to avoid
falsely quarantining valid specs.

Loader adapted from netbox-community/devicetype-library tests/yaml_loader.py.
"""

from __future__ import annotations

import decimal

from yaml.composer import Composer
from yaml.constructor import SafeConstructor
from yaml.parser import Parser
from yaml.reader import Reader
from yaml.resolver import Resolver
from yaml.scanner import Scanner


class _DecimalSafeConstructor(SafeConstructor):
    def construct_yaml_float(self, node):
        value = super().construct_yaml_float(node)
        # Force the string repr so 10.11 -> Decimal("10.11"), not the long binary expansion.
        return decimal.Decimal(f"{value}")


_DecimalSafeConstructor.add_constructor(
    "tag:yaml.org,2002:float", _DecimalSafeConstructor.construct_yaml_float
)


class DecimalSafeLoader(
    Reader, Scanner, Parser, Composer, _DecimalSafeConstructor, Resolver
):
    def __init__(self, stream):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        _DecimalSafeConstructor.__init__(self)
        Resolver.__init__(self)


def to_plain(obj):
    """Convert Decimals back to int/float for typed models and JSON storage."""
    if isinstance(obj, decimal.Decimal):
        as_int = int(obj)
        return as_int if obj == as_int else float(obj)
    if isinstance(obj, dict):
        return {key: to_plain(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [to_plain(item) for item in obj]
    return obj
