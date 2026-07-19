"""Source-level checks for the Home page Title Seed field."""

from pathlib import Path


FRONTEND_ROOT = Path(__file__).resolve().parents[2] / "frontend"


def _read(relative: str) -> str:
    return (FRONTEND_ROOT / relative).read_text(encoding="utf-8")


def test_home_workflow_form_renders_title_seed_below_url_field():
    source = _read("features/workflow-form/workflow-form.tsx")

    url_index = source.index('htmlFor="youtube-url"')
    seed_index = source.index('htmlFor="title-seed"')
    trim_index = source.index("{/* Trim */}")

    assert url_index < seed_index < trim_index
    assert "Title Seed" in source
    assert "e.g. Epic Ride Through Mumbai" in source
    assert "This is the starting idea for the AI-generated YouTube title." in source


def test_home_workflow_form_sends_title_seed_in_create_job_request():
    hook_source = _read("features/workflow-form/use-workflow-form.ts")
    api_source = _read("lib/api.ts")

    assert "titleSeed: string;" in hook_source
    assert "setTitleSeed" in hook_source
    assert "title_seed: titleSeed.trim() || undefined" in hook_source
    assert "title_seed?: string;" in api_source
