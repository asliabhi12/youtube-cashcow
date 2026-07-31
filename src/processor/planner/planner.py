"""High-level render planner.

Consumes a RenderPlan, applies optimization passes, generates filter graphs,
and prepares the final single-pass execution plan.
"""

from dataclasses import dataclass
from pathlib import Path
from src.config import Settings
from .command_builder import FFmpegCommandBuilder
from .filter_graph import FilterGraphBuilder, FilterGraphResult
from .plan import RenderPlan


@dataclass
class ExecutionPlan:
    """The fully prepared single-pass execution plan ready for media execution."""

    optimized_plan: RenderPlan
    graph_result: FilterGraphResult
    command_args: list[str]
    input_file: Path
    output_file: Path


class RenderPlanner:
    """Consumes RenderPlan and orchestrates optimization and command generation."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.filter_builder = FilterGraphBuilder()
        self.command_builder = FFmpegCommandBuilder(settings)

    def create_execution_plan(
        self,
        plan: RenderPlan,
        input_file: Path,
        output_file: Path,
        encode_args_fn=None,
    ) -> ExecutionPlan:
        """Analyze, optimize, and compile a RenderPlan into an ExecutionPlan."""
        optimized = plan.optimize()
        graph_result = self.filter_builder.build(optimized, input_file)
        command_args = self.command_builder.build_command(
            input_file=input_file,
            output_file=output_file,
            plan=optimized,
            graph=graph_result,
            encode_args_fn=encode_args_fn,
        )
        return ExecutionPlan(
            optimized_plan=optimized,
            graph_result=graph_result,
            command_args=command_args,
            input_file=input_file,
            output_file=output_file,
        )
