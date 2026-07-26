"""Container for accumulated render operations.

RenderPlan manages the sequence of operations for a pipeline execution,
providing methods to add operations, inspect plans, and optimize sequences.
"""

from typing import Iterator
from .operations import EncodeOperation, RenderOperation, ResizeOperation


class RenderPlan:
    """Accumulates and optimizes render operations for single-pass processing."""

    def __init__(self) -> None:
        self._operations: list[RenderOperation] = []

    def add(self, operation: RenderOperation) -> None:
        """Add a render operation to the plan."""
        self._operations.append(operation)

    def is_empty(self) -> bool:
        """Return True if no operations have been added."""
        return len(self._operations) == 0

    def __len__(self) -> int:
        return len(self._operations)

    def __iter__(self) -> Iterator[RenderOperation]:
        return iter(self._operations)

    def clear(self) -> None:
        """Clear all operations from the plan."""
        self._operations.clear()

    def optimize(self) -> "RenderPlan":
        """Return an optimized copy of the render plan.

        Optimizations:
        1. Keep only the final ResizeOperation if multiple are present, preserving order.
        2. Keep only the final EncodeOperation if multiple are present, preserving order.
        """
        optimized = RenderPlan()
        resizes = [i for i, op in enumerate(self._operations) if isinstance(op, ResizeOperation)]
        encodes = [i for i, op in enumerate(self._operations) if isinstance(op, EncodeOperation)]

        skip_indices = set()
        if len(resizes) > 1:
            skip_indices.update(resizes[:-1])
        if len(encodes) > 1:
            skip_indices.update(encodes[:-1])

        for i, op in enumerate(self._operations):
            if i not in skip_indices:
                optimized.add(op)

        return optimized
