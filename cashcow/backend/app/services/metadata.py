"""In-memory metadata resource and provider-backed generation service."""

from datetime import datetime, timezone
import logging
from pathlib import Path
from threading import Lock
from collections.abc import Callable

from pydantic import ValidationError

from app.models.job import JobLogLevel
from app.models.metadata import MetadataCreate, MetadataResponse, MetadataUpdate, VideoMetadata
from app.models.profile import DEFAULT_METADATA_PROMPT
from app.services import profiles
from app.services.ai.metadata_provider import MetadataGenerationContext, MetadataProviderError
from app.services.ai.provider_factory import get_metadata_provider
from app.services.jobs import job_store

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert YouTube metadata generator.
Generate polished, accurate, SEO-friendly YouTube metadata from the provided context.
The user's Title Seed is the highest-priority signal of intent. Refine it into a
finished YouTube title instead of ignoring or replacing it.

Return ONLY a valid JSON object with exactly these fields:
{
  "title": "...",
  "description": "...",
  "tags": ["...", "...", "..."]
}

Do not include markdown, explanations, or any additional fields."""


class MetadataNotFoundError(LookupError):
    """Raised when a job has no metadata."""


class MetadataService:
    def __init__(self) -> None:
        self._metadata: dict[str, VideoMetadata] = {}
        self._lock = Lock()

    def get(self, job_id: str) -> VideoMetadata | None:
        with self._lock:
            return self._metadata.get(job_id)

    def generate(
        self,
        job_id: str,
        request: MetadataCreate | None = None,
        log: Callable[[JobLogLevel, str], None] | None = None,
    ) -> VideoMetadata | None:
        job = job_store.get(job_id)
        if job is None:
            raise MetadataNotFoundError("Job not found")
        job_store.set_metadata_status(job_id, "generating")
        _log_job(log, "INFO", "Generating AI metadata...")
        try:
            provider = get_metadata_provider()
            _log_job(log, "INFO", f"Using provider: {_display_provider_name(provider.name)}")
            context = self._build_generation_context(job_id, request)
            response = MetadataResponse.model_validate(provider.generate(context))
        except MetadataProviderError as exc:
            logger.warning("Metadata provider error for job %s: %s", job_id, exc)
            job_store.set_metadata_status(job_id, "unavailable")
            _log_job(log, "WARNING", "Metadata generation unavailable.")
            return None
        except ValidationError as exc:
            logger.warning("Metadata validation failed for job %s: %s", job_id, exc)
            job_store.set_metadata_status(job_id, "unavailable")
            _log_job(log, "WARNING", "Metadata validation failed.")
            return None
        except Exception as exc:  # noqa: BLE001 - metadata generation is optional.
            logger.warning("Metadata generation failed for job %s: %s", job_id, exc)
            job_store.set_metadata_status(job_id, "unavailable")
            _log_job(log, "WARNING", "Metadata generation unavailable.")
            return None

        metadata = VideoMetadata(
            job_id=job_id,
            generated_at=datetime.now(timezone.utc),
            provider=provider.name,
            model=provider.model,
            editable=True,
            **response.model_dump(),
        )
        with self._lock:
            self._metadata[job_id] = metadata
        job_store.set_metadata_status(job_id, "available")
        _log_job(log, "INFO", "Metadata generated successfully.")
        return metadata

    def update(self, job_id: str, request: MetadataUpdate) -> VideoMetadata:
        current = self.get(job_id)
        if current is None:
            raise MetadataNotFoundError("Metadata not found")
        values = current.model_dump()
        values.update(request.model_dump(exclude_none=True, exclude={"title_seed"}))
        values["generated_at"] = current.generated_at
        metadata = VideoMetadata(**values)
        with self._lock:
            self._metadata[job_id] = metadata
        return metadata

    def delete(self, job_id: str) -> bool:
        with self._lock:
            deleted = self._metadata.pop(job_id, None) is not None
        if deleted:
            job_store.set_metadata_status(job_id, "idle")
        return deleted

    def regenerate(self, job_id: str) -> VideoMetadata | None:
        return self.generate(job_id)

    def _build_generation_context(
        self,
        job_id: str,
        request: MetadataCreate | None,
    ) -> MetadataGenerationContext:
        job = job_store.get(job_id)
        if job is None:
            raise MetadataNotFoundError("Job not found")

        profile = profiles.get_profile(job.profile_id)
        creative_prompt = (
            profile.metadata_prompt
            if profile is not None and profile.metadata_prompt.strip()
            else DEFAULT_METADATA_PROMPT
        )
        title_seed = _title_seed_from_request(request) or job.title_seed
        original_title = _title_from_output_name(job.output_name)
        final_prompt = _compose_final_prompt(
            system_prompt=SYSTEM_PROMPT,
            creative_profile_prompt=creative_prompt,
            title_seed=title_seed,
            original_title=original_title,
            video_duration=None,
            transcript=None,
            detected_language=None,
            output_filename=job.output_name,
            topics=[],
            keywords=[],
        )
        return MetadataGenerationContext(
            system_prompt=SYSTEM_PROMPT,
            creative_profile_prompt=creative_prompt,
            title_seed=title_seed,
            original_title=original_title,
            video_duration=None,
            transcript=None,
            detected_language=None,
            output_filename=job.output_name,
            topics=[],
            keywords=[],
            final_prompt=final_prompt,
        )


metadata_service = MetadataService()


def _title_seed_from_request(request: MetadataCreate | None) -> str | None:
    if request is None:
        return None
    return request.title_seed or request.title


def _title_from_output_name(output_name: str | None) -> str | None:
    if output_name is None:
        return None
    stem = Path(output_name).stem.replace("_", " ").replace("-", " ").strip()
    return stem or None


def _compose_final_prompt(
    *,
    system_prompt: str,
    creative_profile_prompt: str,
    title_seed: str | None,
    original_title: str | None,
    video_duration: float | None,
    transcript: str | None,
    detected_language: str | None,
    output_filename: str | None,
    topics: list[str],
    keywords: list[str],
) -> str:
    context_lines = [
        _optional_line("Title Seed", title_seed),
        _optional_line("Original YouTube title", original_title),
        _optional_line(
            "Video duration",
            f"{video_duration:g} seconds" if video_duration is not None else None,
        ),
        _optional_line("Transcript", transcript),
        _optional_line("Detected language", detected_language),
        _optional_line("Output filename", output_filename),
        _optional_line("Extracted topics", ", ".join(topics) if topics else None),
        _optional_line("Extracted keywords", ", ".join(keywords) if keywords else None),
    ]
    available_context = "\n".join(line for line in context_lines if line is not None)
    if not available_context:
        available_context = "No additional video context is available."
    return "\n\n".join(
        [
            system_prompt,
            "Creative Profile Metadata Prompt:\n" + creative_profile_prompt,
            "Available Video Context:\n" + available_context,
        ]
    )


def _optional_line(label: str, value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    return f"{label}: {value}"


def _log_job(
    callback: Callable[[JobLogLevel, str], None] | None,
    level: JobLogLevel,
    message: str,
) -> None:
    if callback is not None:
        callback(level, message)


def _display_provider_name(name: str) -> str:
    display_names = {"gemini": "Gemini"}
    return display_names.get(name.lower(), name)
