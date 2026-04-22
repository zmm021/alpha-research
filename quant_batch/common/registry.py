from __future__ import annotations

from collections.abc import Callable
from typing import Any


INDICATOR_REGISTRY: dict[str, Callable[..., Any]] = {}
FACTOR_REGISTRY: dict[str, Callable[..., Any]] = {}
STATE_REGISTRY: dict[str, Callable[..., Any]] = {}


def register_indicator(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if name in INDICATOR_REGISTRY:
            raise ValueError(f"Indicator already registered: {name}")
        INDICATOR_REGISTRY[name] = func
        return func

    return decorator


def register_factor(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if name in FACTOR_REGISTRY:
            raise ValueError(f"Factor already registered: {name}")
        FACTOR_REGISTRY[name] = func
        return func

    return decorator


def register_state(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if name in STATE_REGISTRY:
            raise ValueError(f"State already registered: {name}")
        STATE_REGISTRY[name] = func
        return func

    return decorator


def get_indicator(name: str) -> Callable[..., Any]:
    if name not in INDICATOR_REGISTRY:
        raise KeyError(f"Indicator not found: {name}")
    return INDICATOR_REGISTRY[name]


def get_factor(name: str) -> Callable[..., Any]:
    if name not in FACTOR_REGISTRY:
        raise KeyError(f"Factor not found: {name}")
    return FACTOR_REGISTRY[name]


def get_state(name: str) -> Callable[..., Any]:
    if name not in STATE_REGISTRY:
        raise KeyError(f"State not found: {name}")
    return STATE_REGISTRY[name]