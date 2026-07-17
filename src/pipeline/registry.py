"""Extensible name-to-step registry."""

from typing import Type

from .exceptions import StepNotFoundError
from .steps.base import PipelineStep


class StepRegistry:
    def __init__(self) -> None:
        self._steps: dict[str, Type[PipelineStep]] = {}

    def register(self, name: str, step_class: Type[PipelineStep]) -> None:
        self._steps[name.lower()] = step_class

    def create(self, name: str, options: dict) -> PipelineStep:
        try:
            return self._steps[name.lower()](options)
        except KeyError as exc:
            raise StepNotFoundError(f"No step is registered as '{name}'.") from exc

    def contains(self, name: str) -> bool:
        return name.lower() in self._steps
