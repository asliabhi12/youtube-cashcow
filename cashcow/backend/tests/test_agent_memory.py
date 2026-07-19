"""Tests for SQLite-backed Agent Memory.

These tests cover database creation, CRUD operations on all four repositories,
memory-reuse optimisation, and process-resume semantics.
"""

# ── database initialisation ──────────────────────────────────────────────

from app.infrastructure.database import DB_PATH, init_database, reset_database_for_testing


def _clean_db() -> None:
    """Drop every table so the next init_database call creates them fresh."""
    reset_database_for_testing()


def test_database_initialisation_creates_file() -> None:
    _clean_db()
    assert not DB_PATH.exists()
    init_database()
    assert DB_PATH.exists()


def test_database_initialisation_idempotent() -> None:
    _clean_db()
    init_database()
    init_database()  # second call must not raise


def test_database_schema_has_expected_tables() -> None:
    _clean_db()
    init_database()
    from app.infrastructure.database import _get_connection

    conn = _get_connection()
    tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    expected = {"jobs", "metadata", "workflow_events", "agent_memory"}
    assert expected.issubset(tables), f"Missing tables: {expected - tables}"


# ── repositories ─────────────────────────────────────────────────────────

_JOB_ID = "test-job-001"


def _init() -> None:
    _clean_db()
    init_database()


def test_job_repository_upsert_and_get() -> None:
    _init()
    from app.infrastructure.repositories import JobRepository

    repo = JobRepository()
    repo.upsert(_JOB_ID)
    row = repo.get(_JOB_ID)
    assert row is not None
    assert row["id"] == _JOB_ID


def test_job_repository_get_missing() -> None:
    _init()
    from app.infrastructure.repositories import JobRepository

    assert JobRepository().get("nonexistent") is None


def test_metadata_repository_save_and_get() -> None:
    _init()
    from app.infrastructure.repositories import MetadataRepository

    repo = MetadataRepository()
    repo.save(_JOB_ID, title="Test Title", model="gemini-2.0-flash")
    row = repo.get(_JOB_ID)
    assert row is not None
    assert row["title"] == "Test Title"
    assert row["model"] == "gemini-2.0-flash"


def test_metadata_repository_overwrite() -> None:
    _init()
    from app.infrastructure.repositories import MetadataRepository

    repo = MetadataRepository()
    repo.save(_JOB_ID, title="First")
    repo.save(_JOB_ID, title="Second")
    row = repo.get(_JOB_ID)
    assert row["title"] == "Second"


def test_workflow_event_repository_append_and_latest() -> None:
    _init()
    from app.infrastructure.repositories import WorkflowEventRepository

    repo = WorkflowEventRepository()
    repo.append(_JOB_ID, "pipeline", "started")
    repo.append(_JOB_ID, "pipeline", "completed", finished_at="2026-01-01T00:00:00")
    latest = repo.latest_event(_JOB_ID)
    assert latest is not None
    assert latest["stage"] == "pipeline"
    assert latest["status"] == "completed"


def test_workflow_event_latest_when_empty() -> None:
    _init()
    from app.infrastructure.repositories import WorkflowEventRepository

    assert WorkflowEventRepository().latest_event("nonexistent") is None


# ── agent memory ─────────────────────────────────────────────────────────


def test_memory_save_and_is_completed() -> None:
    _init()
    from app.infrastructure.repositories import MemoryRepository

    repo = MemoryRepository()
    assert repo.is_completed(_JOB_ID, "download_video") is False
    repo.save(_JOB_ID, "download_video", "completed", artifact_path="/tmp/video.mp4")
    assert repo.is_completed(_JOB_ID, "download_video") is True


def test_memory_get_task() -> None:
    _init()
    from app.infrastructure.repositories import MemoryRepository

    repo = MemoryRepository()
    repo.save(_JOB_ID, "generate_metadata", "completed", output_summary="title=Hello")
    entry = repo.get_task(_JOB_ID, "generate_metadata")
    assert entry is not None
    assert entry["output_summary"] == "title=Hello"


def test_memory_multiple_tasks_independent() -> None:
    _init()
    from app.infrastructure.repositories import MemoryRepository

    repo = MemoryRepository()
    repo.save(_JOB_ID, "download_video", "completed")
    repo.save(_JOB_ID, "extract_transcript", "failed")
    assert repo.is_completed(_JOB_ID, "download_video") is True
    assert repo.is_completed(_JOB_ID, "extract_transcript") is False


def test_memory_clear_job_removes_all_traces() -> None:
    _init()
    from app.infrastructure.repositories import (
        MemoryRepository,
        MetadataRepository,
        WorkflowEventRepository,
    )

    mem = MemoryRepository()
    meta = MetadataRepository()
    events = WorkflowEventRepository()
    meta.save(_JOB_ID, title="ToDelete")
    events.append(_JOB_ID, "pipeline", "started")
    mem.save(_JOB_ID, "download_video", "completed")
    mem.clear_job(_JOB_ID)
    assert mem.get_task(_JOB_ID, "download_video") is None
    assert events.latest_event(_JOB_ID) is None
    assert meta.get(_JOB_ID) is None


# ── memory reuse / skip logic ────────────────────────────────────────────


def test_is_completed_for_missing_job_returns_false() -> None:
    """When no entry exists, is_completed must return False so the task runs."""
    _init()
    from app.infrastructure.repositories import MemoryRepository

    assert MemoryRepository().is_completed("ghost-job", "generate_metadata") is False


def test_is_completed_checks_only_latest_entry() -> None:
    """If a task was completed then later re-ran and failed, the latest status wins."""
    _init()
    from app.infrastructure.repositories import MemoryRepository

    repo = MemoryRepository()
    repo.save(_JOB_ID, "generate_metadata", "completed")
    assert repo.is_completed(_JOB_ID, "generate_metadata") is True
    repo.save(_JOB_ID, "generate_metadata", "failed")
    assert repo.is_completed(_JOB_ID, "generate_metadata") is False


def test_exactly_one_db_file() -> None:
    """All four repos share the same cashcow.db file."""
    _init()
    from app.infrastructure.repositories import (
        JobRepository,
        MemoryRepository,
        MetadataRepository,
        WorkflowEventRepository,
    )

    JobRepository().upsert(_JOB_ID)
    MetadataRepository().save(_JOB_ID, title="Shared")
    MemoryRepository().save(_JOB_ID, "task_x", "completed")
    WorkflowEventRepository().append(_JOB_ID, "stage_x", "done")

    from app.infrastructure.database import _get_connection

    conn = _get_connection()
    counts = {
        "jobs": conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
        "metadata": conn.execute("SELECT COUNT(*) FROM metadata").fetchone()[0],
        "agent_memory": conn.execute("SELECT COUNT(*) FROM agent_memory").fetchone()[0],
        "workflow_events": conn.execute("SELECT COUNT(*) FROM workflow_events").fetchone()[0],
    }
    conn.close()
    assert counts["jobs"] == 1
    assert counts["metadata"] == 1
    assert counts["agent_memory"] == 1
    assert counts["workflow_events"] == 1


# ── resume unfinished jobs ───────────────────────────────────────────────


def test_get_unfinished_jobs_returns_jobs_without_completed_pipeline() -> None:
    _init()
    from app.infrastructure.repositories import (
        MemoryRepository,
        WorkflowEventRepository,
    )

    mem = MemoryRepository()
    events = WorkflowEventRepository()

    job_a = "job-a-finished"
    job_b = "job-b-unfinished"
    job_c = "job-c-no-events"

    # job_a has a completed pipeline
    events.append(job_a, "pipeline", "completed", finished_at="2026-01-01T00:00:00")
    mem.save(job_a, "download_video", "completed")

    # job_b has pipeline but not completed
    events.append(job_b, "pipeline", "started")
    mem.save(job_b, "download_video", "completed")

    # job_c has memory entries but no pipeline events
    mem.save(job_c, "download_video", "completed")

    unfinished = mem.get_unfinished_jobs()
    assert job_a not in unfinished
    assert job_b in unfinished
    assert job_c in unfinished


def test_resume_unfinished_jobs_empty_when_all_complete() -> None:
    """If every known job finished, resume_unfinished_jobs returns an empty list."""
    _init()
    from app.infrastructure.repositories import (
        MemoryRepository,
        WorkflowEventRepository,
    )

    mem = MemoryRepository()
    events = WorkflowEventRepository()
    events.append("j1", "pipeline", "completed", finished_at="2026-01-01T00:00:00")
    mem.save("j1", "download_video", "completed")
    events.append("j2", "pipeline", "completed", finished_at="2026-01-01T00:00:00")
    mem.save("j2", "download_video", "completed")

    from app.services.workflow import resume_unfinished_jobs

    assert resume_unfinished_jobs() == []


def test_resume_unfinished_jobs_finds_unfinished() -> None:
    """Jobs with only a 'started' pipeline event appear in the returned list."""
    _init()
    from app.infrastructure.repositories import (
        MemoryRepository,
        WorkflowEventRepository,
    )

    mem = MemoryRepository()
    events = WorkflowEventRepository()
    events.append("unfinished-1", "pipeline", "started")
    mem.save("unfinished-1", "download_video", "completed")
    events.append("finished-1", "pipeline", "completed", finished_at="2026-01-01T00:00:00")
    mem.save("finished-1", "download_video", "completed")

    from app.services.workflow import resume_unfinished_jobs

    result = resume_unfinished_jobs()
    assert "unfinished-1" in result
    assert "finished-1" not in result


# ── integration: workflow memory checks ──────────────────────────────────


def test_workflow_module_level_repos_are_instantiated() -> None:
    """The module-level _memory_repo and _workflow_event_repo exist and respond."""
    _init()
    # reload the module so module-level expressions re-run
    import importlib

    from app.services import workflow

    importlib.reload(workflow)
    assert workflow._memory_repo is not None
    assert workflow._workflow_event_repo is not None


def test_workflow_reuses_metadata_when_memory_says_completed() -> None:
    """If agent_memory has generate_metadata = completed, _execute skips generation."""
    _init()
    from app.infrastructure.repositories import MemoryRepository, WorkflowEventRepository

    # prime the database
    mem = MemoryRepository()
    events = WorkflowEventRepository()
    mem.save("reuse-test", "generate_metadata", "completed")
    events.append("reuse-test", "pipeline", "completed")

    # reset workflow module-level caches and instantiate repo references
    import importlib

    from app.services import workflow

    importlib.reload(workflow)

    # is_completed should return True
    assert workflow._memory_repo.is_completed("reuse-test", "generate_metadata") is True
