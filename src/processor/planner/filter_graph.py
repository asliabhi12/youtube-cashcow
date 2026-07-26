"""Builder for FFmpeg filter graph expressions.

Constructs unified video and audio filter chains or -filter_complex graphs
from a RenderPlan, correctly mapping input stream specifiers and node labels.
"""

from pathlib import Path
from typing import NamedTuple

from src.processor.compositor import _effects_chain, _overlay_chain
from src.processor.models import OverlayConfig
from src.processor.overlay import cover_scale2ref, resolve_position
from .operations import OverlayOperation, RenderOperation
from .plan import RenderPlan


class FilterGraphResult(NamedTuple):
    filter_complex: str | None
    video_filters: list[str]
    audio_filters: list[str]
    video_map: str | None
    audio_map: str | None
    extra_inputs: list[Path]


class FilterGraphBuilder:
    """Builds single-pass FFmpeg filter expressions from a RenderPlan."""

    def build(self, plan: RenderPlan, input_file: Path) -> FilterGraphResult:
        """Construct the filter graph for the given plan."""
        extra_inputs: list[Path] = []
        v_filters: list[str] = []
        a_filters: list[str] = []

        # Collect simple linear filters and extra input media
        overlay_ops: list[OverlayOperation] = []

        for op in plan:
            for extra in op.get_extra_inputs():
                if extra not in extra_inputs and extra.resolve() != input_file.resolve():
                    extra_inputs.append(extra)

            if isinstance(op, OverlayOperation):
                overlay_ops.append(op)
            else:
                v_filters.extend(op.to_video_filters())
                a_filters.extend(op.to_audio_filters())

        # If we have complex inputs like overlay assets, build a -filter_complex graph
        if overlay_ops:
            complex_nodes = []
            curr_v_stream = "0:v"

            # Apply initial linear video filters if present
            if v_filters:
                linear_v = ",".join(v_filters)
                complex_nodes.append(f"[{curr_v_stream}]{linear_v}[v_init]")
                curr_v_stream = "v_init"

            # Chain overlay operations
            for idx, op in enumerate(overlay_ops):
                overlay_input_idx = extra_inputs.index(Path(op.source)) + 1

                # Build OverlayConfig from OverlayOperation
                if isinstance(op.raw_config, OverlayConfig):
                    config = op.raw_config
                elif isinstance(op.raw_config, dict):
                    config = OverlayConfig(**op.raw_config)
                else:
                    cfg_kwargs = {
                        "source": op.source,
                        "x": op.x,
                        "y": op.y,
                        "opacity": op.opacity,
                    }
                    if op.scale is not None:
                        cfg_kwargs["scale"] = op.scale
                    if getattr(op, "width", None) is not None:
                        cfg_kwargs["width"] = op.width
                    if getattr(op, "height", None) is not None:
                        cfg_kwargs["height"] = op.height
                    if getattr(op, "rotation", 0):
                        cfg_kwargs["rotation"] = op.rotation
                    if op.mask is not None:
                        cfg_kwargs["mask"] = op.mask
                    if getattr(op, "color", None) is not None:
                        cfg_kwargs["color"] = op.color

                    if op.is_legacy and op.legacy_options:
                        for k in ("scale", "width", "height", "opacity", "rotation", "mask", "color"):
                            if k in op.legacy_options and k not in cfg_kwargs:
                                cfg_kwargs[k] = op.legacy_options[k]

                    config = OverlayConfig(**cfg_kwargs)

                x_pos, y_pos = resolve_position(config.x, config.y)
                overlay_str = f"x={x_pos}:y={y_pos}"
                next_v_stream = f"v_ov_{idx}"

                if config.scale is not None:
                    # Fractional scale: scale2ref onto main video stream
                    scale_node = cover_scale2ref(config.scale)
                    effects_chain = _effects_chain(config)
                    ovs_stream = f"ovs_{idx}"
                    base_stream = f"base_ref_{idx}"
                    ov_final = f"ov_final_{idx}"

                    complex_nodes.append(
                        f"[{overlay_input_idx}:v][{curr_v_stream}]{scale_node}[{ovs_stream}][{base_stream}]"
                    )
                    complex_nodes.append(
                        f"[{ovs_stream}]{effects_chain}[{ov_final}]"
                    )
                    complex_nodes.append(
                        f"[{base_stream}][{ov_final}]overlay={overlay_str}[{next_v_stream}]"
                    )
                else:
                    chain = _overlay_chain(config)
                    ov_final = f"ov_final_{idx}"
                    complex_nodes.append(
                        f"[{overlay_input_idx}:v]{chain}[{ov_final}]"
                    )
                    complex_nodes.append(
                        f"[{curr_v_stream}][{ov_final}]overlay={overlay_str}[{next_v_stream}]"
                    )

                curr_v_stream = next_v_stream

            # Handle audio filters in filter_complex if present
            if a_filters:
                linear_a = ",".join(a_filters)
                complex_nodes.append(f"[0:a]{linear_a}[aout]")
                a_map = "[aout]"
            else:
                a_map = "0:a"

            filter_complex = ";".join(complex_nodes)
            return FilterGraphResult(
                filter_complex=filter_complex,
                video_filters=[],
                audio_filters=[],
                video_map=f"[{curr_v_stream}]",
                audio_map=a_map,
                extra_inputs=extra_inputs,
            )

        # Simple linear graph without multi-input overlays
        return FilterGraphResult(
            filter_complex=None,
            video_filters=v_filters,
            audio_filters=a_filters,
            video_map=None,
            audio_map=None,
            extra_inputs=extra_inputs,
        )
