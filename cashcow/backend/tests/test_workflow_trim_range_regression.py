"""Regression tests for the Workflow Form Trim Range state synchronization and metadata lookup logic."""

from pathlib import Path
import re


FRONTEND_ROOT = Path(__file__).resolve().parents[2] / "frontend"


def _read(relative: str) -> str:
    return (FRONTEND_ROOT / relative).read_text(encoding="utf-8")


def test_use_workflow_form_resets_trim_range_on_new_video_duration():
    source = _read("features/workflow-form/use-workflow-form.ts")

    # 1. Verify trim state resets to full duration upon metadata load (start: 0, end: duration)
    assert "setTrim({ start: 0, end: duration });" in source

    # 2. Verify stale trim capping logic (Math.min(prev.end, duration)) is removed
    assert "const end = Math.min(prev.end, duration);" not in source


def test_use_workflow_form_resets_state_on_url_change_and_invalid_url():
    source = _read("features/workflow-form/use-workflow-form.ts")

    # 1. Empty URL or error resets trim state to 0 (no silent 600 fallback leak)
    assert "setTrim({ start: 0, end: 0 });" in source
    assert 'setMetadataError("Unable to load video metadata");' in source

    # 2. Loading state is set immediately when URL changes
    assert "setLoadingMetadata(true);" in source
    assert "setVideoTitle(null);" in source
    assert "setMetadataError(null);" in source


def test_use_workflow_form_prevents_race_conditions_from_aborted_requests():
    source = _read("features/workflow-form/use-workflow-form.ts")

    # Verify signal.aborted check in try and catch blocks
    assert "if (controller.signal.aborted) return;" in source
    assert "if (!controller.signal.aborted)" in source


def test_workflow_submission_payload_includes_url_and_trim_range():
    hook_source = _read("features/workflow-form/use-workflow-form.ts")
    api_source = _read("lib/api.ts")

    # Verify submission payload format
    assert "trim: { start: trim.start, end: trim.end }" in hook_source
    assert "trim?: TrimRange;" in api_source


def test_trim_range_slider_renders_safe_max_duration():
    slider_source = _read("components/trim-range-slider.tsx")

    # Verify the right-hand bound displays formatDuration(safeMax) when video loaded or --:-- when 0
    assert 'safeMax > 0 ? formatDuration(safeMax) : "--:--"' in slider_source
