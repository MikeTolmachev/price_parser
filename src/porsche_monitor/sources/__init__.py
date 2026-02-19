from __future__ import annotations

from typing import Type

from .base import Source
from .porsche_finder import PorscheFinderSource
from .mobile_de import MobileDeSource
from .autoscout24 import AutoScout24Source
from .porsche_de import PorscheDeSource

SOURCE_REGISTRY: dict[str, Type[Source]] = {
    "porsche_finder": PorscheFinderSource,
    "mobile_de": MobileDeSource,
    "autoscout24": AutoScout24Source,
    "porsche_de": PorscheDeSource,
}


def get_source(name: str) -> Type[Source]:
    if name not in SOURCE_REGISTRY:
        raise ValueError(
            f"Unknown source '{name}'. Available: {', '.join(SOURCE_REGISTRY)}"
        )
    return SOURCE_REGISTRY[name]
