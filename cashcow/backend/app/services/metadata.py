"""In-memory metadata resource and provider-backed generation service."""

import time
from datetime import datetime, timezone
import logging
from pathlib import Path
from threading import Lock
from collections.abc import Callable
import sys

from pydantic import ValidationError

from app.models.job import JobLogLevel
from app.models.metadata import MetadataCreate, MetadataResponse, MetadataUpdate, VideoMetadata
from app.models.profile import DEFAULT_METADATA_PROMPT
from app.services import profiles
from app.services.ai.metadata_provider import (
    GeminiAPIError,
    GeminiAuthenticationError,
    GeminiEmptyResponseError,
    GeminiInvalidJSONError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    MetadataGenerationContext,
    MetadataProviderError,
    SchemaValidationFailure,
)
from app.services.ai.provider_factory import get_metadata_provider
from app.services.jobs import job_store

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert YouTube metadata generator.

Generate polished, accurate, SEO-friendly YouTube metadata from the provided context.

LANGUAGE HANDLING:
- Accept English, Hindi, and Hinglish inputs
- If the Title Seed is in Hinglish (Hindi + English mix):
  - Correct grammar and spelling
  - Preserve the language mix as-is
  - Do NOT translate to English
- If the Title Seed is in Hindi:
  - Correct grammar only
  - Do NOT translate to English
- If the Title Seed is in English:
  - Improve readability and clickability only
  - Do not change the core meaning

RULES:
- Never hallucinate facts or claims not present in the context
- Use transcript and context only for factual content
- The Title Seed is the highest-priority signal of intent
- Generate clickable, SEO-optimized titles within YouTube's 100-character limit
- Descriptions should be 2-3 paragraphs covering what the viewer will learn/see

Return ONLY a valid JSON object with exactly these fields:
{
  "title": "...",
  "description": "...",
  "tags": ["...", "...", "..."]
}

Do not include markdown, explanations, or any additional fields."""


class MetadataNotFoundError(LookupError):
    """Raised when a job has no metadata."""


class DatabasePersistenceFailure(RuntimeError):
    """Failed to write metadata to the database."""


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
        fallback: bool = False,
    ) -> VideoMetadata | None:
        job = job_store.get(job_id)
        if job is None:
            raise MetadataNotFoundError("Job not found")

        _log_job(log, "INFO", f"[Job {job_id}] Workflow transition: GENERATING_METADATA")
        logger.info("[Job %s] Workflow transition: GENERATING_METADATA", job_id)
        _log_job(log, "INFO", f"[Job {job_id}] Generating AI metadata...")
        logger.info("[Job %s] Generating metadata (fallback=%s)", job_id, fallback)

        # 1. State transition to GENERATING_METADATA
        job_store.set_metadata_status(job_id, "generating")
        job_store.set_progress(job_id, 96, "GENERATING_METADATA")

        generation_start = time.monotonic()
        context = self._build_generation_context(job_id, request)
        logger.info("[Job %s] Prompt length: %d characters", job_id, len(context.final_prompt))
        logger.info("[Job %s] Title Seed: %s", job_id, context.title_seed)
        logger.info("[Job %s] Creative Profile: %s", job_id, context.creative_profile_prompt[:80] if context.creative_profile_prompt else "None")
        logger.info("[Job %s] Transcript length: %d characters", job_id, len(context.transcript or ""))

        max_retries = 2
        provider = get_metadata_provider()
        last_exc = None
        metadata = None

        for attempt in range(max_retries + 1):
            if attempt > 0:
                # Transition to RETRYING_METADATA
                job_store.set_metadata_status(job_id, "generating")
                job_store.set_progress(job_id, 96, "RETRYING_METADATA")
                _log_job(log, "INFO", f"[Job {job_id}] Workflow transition: RETRYING_METADATA (Retry attempt {attempt}/{max_retries})")
                logger.info("[Job %s] Workflow transition: RETRYING_METADATA (attempt %d/%d)", job_id, attempt, max_retries)

                # Exponential backoff
                delay = 1.0 * (2 ** (attempt - 1))
                if "pytest" in sys.modules:
                    delay = 0.01
                logger.info("[Job %s] Backoff delay: %.2fs", job_id, delay)
                import time as _time
                _time.sleep(delay)

            try:
                attempt_start = time.monotonic()
                _log_job(log, "INFO", f"[Job {job_id}] Using provider: {_display_provider_name(provider.name)} (Model: {provider.model})")
                logger.info("[Job %s] Provider: %s, Model: %s", job_id, provider.name, provider.model)
                response_dict = provider.generate(context)
                attempt_duration = time.monotonic() - attempt_start
                logger.info("[Job %s] Provider request duration: %.2fs", job_id, attempt_duration)

                # Validate schema
                try:
                    response = MetadataResponse.model_validate(response_dict)
                    logger.info("[Job %s] Validation result: passed", job_id)
                    logger.info("[Job %s] Validated title: %s", job_id, response.title)
                    logger.info("[Job %s] Validated description length: %d", job_id, len(response.description))
                    logger.info("[Job %s] Validated tags: %s", job_id, response.tags)
                except ValidationError as val_exc:
                    logger.warning("[Job %s] Schema validation failure: %s", job_id, val_exc)
                    logger.info("[Job %s] Validation errors: %s", job_id, str(val_exc))
                    _log_job(log, "ERROR", f"[Job {job_id}] Schema validation failure: {val_exc}")
                    raise SchemaValidationFailure(f"Schema validation failure: {val_exc}") from val_exc

                metadata = VideoMetadata(
                    job_id=job_id,
                    generated_at=datetime.now(timezone.utc),
                    provider=provider.name,
                    model=provider.model,
                    editable=True,
                    **response.model_dump(),
                )
                logger.info("[Job %s] Parsed metadata: title=%s, description_len=%d, tags_count=%d",
                            job_id, metadata.title, len(metadata.description), len(metadata.tags))

                # Persist metadata
                try:
                    with self._lock:
                        self._metadata[job_id] = metadata
                    job_store.set_metadata_status(job_id, "available")
                    logger.info("[Job %s] Database write result: Successfully stored metadata for job %s", job_id, job_id)
                    _log_job(log, "INFO", f"[Job {job_id}] Database persistence: success")
                except Exception as db_exc:
                    logger.error("[Job %s] Database persistence failure: %s", job_id, db_exc)
                    _log_job(log, "ERROR", f"[Job {job_id}] Database persistence failure: {db_exc}")
                    raise DatabasePersistenceFailure(f"Database persistence failure: {db_exc}") from db_exc

                # Transition to METADATA_READY
                job_store.set_progress(job_id, 96, "METADATA_READY")
                _log_job(log, "INFO", f"[Job {job_id}] Workflow transition: METADATA_READY")
                logger.info("[Job %s] Workflow transition: METADATA_READY", job_id)
                _log_job(log, "INFO", f"[Job {job_id}] Metadata generated successfully.")
                total_duration = time.monotonic() - generation_start
                logger.info("[Job %s] Metadata generation total duration: %.2fs", job_id, total_duration)
                break

            except (GeminiAuthenticationError, DatabasePersistenceFailure) as exc:
                last_exc = exc
                if isinstance(exc, MetadataProviderError):
                    logger.warning("[Job %s] Non-retryable metadata provider error: %s", job_id, exc)
                break
            except Exception as exc:
                last_exc = exc
                if isinstance(exc, MetadataProviderError):
                    logger.warning("[Job %s] Metadata provider error: %s", job_id, exc)
                logger.warning("[Job %s] Metadata generation attempt %d/%d failed: %s", job_id, attempt + 1, max_retries + 1, exc)
                _log_job(log, "WARNING", f"[Job {job_id}] Metadata generation attempt {attempt + 1} failed: {exc}")

        if metadata is None:
            err_msg = str(last_exc)
            if isinstance(last_exc, GeminiAuthenticationError):
                category = "Authentication failed"
            elif isinstance(last_exc, GeminiRateLimitError):
                category = "Rate limited"
            elif isinstance(last_exc, GeminiTimeoutError):
                category = "Timeout"
            elif isinstance(last_exc, GeminiEmptyResponseError):
                category = "Empty response"
            elif isinstance(last_exc, GeminiInvalidJSONError):
                category = "Invalid JSON"
            elif isinstance(last_exc, SchemaValidationFailure):
                category = "Schema validation failed"
            elif isinstance(last_exc, DatabasePersistenceFailure):
                category = "Metadata persistence failed"
            elif isinstance(last_exc, GeminiAPIError):
                category = "API error"
            else:
                category = "API error"

            logger.error("[Job %s] %s: %s", job_id, category, err_msg)
            _log_job(log, "ERROR", f"[Job {job_id}] {category}: {err_msg}")

            if not fallback:
                job_store.set_metadata_status(job_id, "unavailable")
                _log_job(log, "WARNING", f"[Job {job_id}] Metadata generation unavailable.")
                total_duration = time.monotonic() - generation_start
                logger.info("[Job %s] Metadata generation failed (no fallback). Total duration: %.2fs", job_id, total_duration)
                return None

            # Transition to METADATA_FAILED
            job_store.set_progress(job_id, 96, "METADATA_FAILED")
            _log_job(log, "INFO", f"[Job {job_id}] Workflow transition: METADATA_FAILED")
            logger.info("[Job %s] Workflow transition: METADATA_FAILED", job_id)

            # Transition to FALLBACK_METADATA
            job_store.set_progress(job_id, 96, "FALLBACK_METADATA")
            _log_job(log, "INFO", f"[Job {job_id}] Workflow transition: FALLBACK_METADATA")
            logger.info("[Job %s] Workflow transition: FALLBACK_METADATA", job_id)

            metadata = self._generate_fallback_metadata(job_id, context, log)

            try:
                with self._lock:
                    self._metadata[job_id] = metadata
                job_store.set_metadata_status(job_id, "available")
                logger.info("[Job %s] Database write result: Successfully stored fallback metadata", job_id)
                _log_job(log, "INFO", f"[Job {job_id}] Database persistence: success (fallback)")
            except Exception as db_exc:
                logger.error("[Job %s] Database persistence failure (fallback): %s", job_id, db_exc)
                _log_job(log, "ERROR", f"[Job {job_id}] Database persistence failure (fallback): {db_exc}")
                raise DatabasePersistenceFailure(f"Database persistence failure: {db_exc}") from db_exc

            _log_job(log, "INFO", f"[Job {job_id}] Fallback metadata generated and saved successfully.")
            total_duration = time.monotonic() - generation_start
            logger.info("[Job %s] Metadata generation completed (fallback). Total duration: %.2fs", job_id, total_duration)

        return metadata

    def _generate_fallback_metadata(
        self,
        job_id: str,
        context: MetadataGenerationContext,
        log: Callable[[JobLogLevel, str], None] | None = None,
    ) -> VideoMetadata:
        title = None
        if context.title_seed and context.title_seed.strip():
            title = context.title_seed.strip()
        elif context.original_title and context.original_title.strip():
            title = context.original_title.strip()
        elif context.output_filename:
            title = Path(context.output_filename).stem.replace("_", " ").replace("-", " ").strip()

        if not title:
            title = "CashCow Video"

        from app.models.metadata import TITLE_MAX_LENGTH
        if len(title) > TITLE_MAX_LENGTH:
            title = title[:TITLE_MAX_LENGTH].rstrip(" .")

        logger.info("[Job %s] Fallback metadata: title=%s, source=%s", job_id, title, "title_seed" if context.title_seed else "original_title" if context.original_title else "output_filename")

        fallback_metadata = VideoMetadata(
            job_id=job_id,
            generated_at=datetime.now(timezone.utc),
            provider="fallback",
            model="fallback",
            editable=True,
            title=title,
            description="",
            tags=[],
            hashtags=[],
            category="",
            thumbnail_prompt="",
        )
        return fallback_metadata

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
            job_id=job_id,
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
    display_names = {"gemini": "Gemini", "mock": "Mock"}
    return display_names.get(name.lower(), name)
