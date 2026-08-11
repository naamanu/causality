"""Stable, optional boundary for privately distributed product extensions."""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass, field
from typing import Protocol

from fastapi import APIRouter


class Extension(Protocol):
    routers: list[APIRouter]

    def validate(self) -> None: ...

    def startup(self) -> None: ...


@dataclass
class CommunityExtension:
    routers: list[APIRouter] = field(default_factory=list)

    def validate(self) -> None:
        return None

    def startup(self) -> None:
        return None


def load_extension() -> Extension:
    module_name = os.environ.get("CAUSALITY_EXTENSION_MODULE", "").strip()
    if not module_name:
        return CommunityExtension()
    module = importlib.import_module(module_name)
    factory = getattr(module, "create_extension", None)
    if not callable(factory):
        raise RuntimeError(f"{module_name} must export create_extension()")
    extension = factory()
    for attribute in ("routers", "validate", "startup"):
        if not hasattr(extension, attribute):
            raise RuntimeError(f"{module_name} extension is missing {attribute}")
    return extension
