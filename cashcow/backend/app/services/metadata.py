"""In-memory metadata resource and provider-backed AI generation service."""

import json
import logging
import re
import sys
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import AI_ENABLED, get_config_value
from app.llm.base import LLMProvider
from app.llm.factory import get_llm_provider
from app.models.job import JobLogLevel
from app.models.metadata import MetadataCreate, MetadataResponse, MetadataUpdate, VideoMetadata
from app.models.profile import DEFAULT_METADATA_PROMPT
from app.prompts.metadata import PROMPT_VERSION, SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
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

_VTT_TAG_PATTERN = re.compile(r"<[^>]+>")
_DEVANAGARI_PATTERN = re.compile(r"[\u0900-\u097F]")
_LATIN_PATTERN = re.compile(r"[a-zA-Z]")


class GeneratedMetadata(BaseModel):
    """Structured rich result returned by MetadataService AI layer."""

    model_config = ConfigDict(extra="ignore")

    title: str
    description: str
    tags: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    thumbnail_prompt: str | None = ""
    language: str | None = "en"
    prompt_version: str = PROMPT_VERSION
    model: str | None = None
    provider: str | None = None


class MetadataNotFoundError(LookupError):
    """Raised when a job has no metadata."""


class DatabasePersistenceFailure(RuntimeError):
    """Failed to write metadata to the database."""


def parse_json_response(raw_text: str) -> dict[str, Any]:
    """Parse raw AI text response into a dictionary, stripping markdown code fences if present."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        cleaned = cleaned[start_idx : end_idx + 1]

    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("AI response JSON is not a dictionary object")
    return data


def _extract_transcript_text(subtitle_paths: list[str]) -> str | None:
    """Read subtitle files (VTT or SRT) and return combined plain text."""
    all_lines: list[str] = []
    for fp in subtitle_paths:
        path = Path(fp)
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped == "WEBVTT":
                continue
            if "-->" in stripped:
                continue
            if stripped.isdigit():
                continue
            cleaned = _VTT_TAG_PATTERN.sub("", stripped)
            all_lines.append(cleaned)
    if not all_lines:
        return None
    return " ".join(all_lines)


def _detect_language(text: str | None) -> str | None:
    if not text or not text.strip():
        return None
    has_devanagari = bool(_DEVANAGARI_PATTERN.search(text))
    has_latin = bool(_LATIN_PATTERN.search(text))
    if has_devanagari:
        return "Hinglish" if has_latin else "Hindi"
    return "English"


class MetadataService:
    def __init__(self) -> None:
        self._metadata: dict[str, VideoMetadata] = {}
        self._transcripts: dict[str, str] = {}
        self._durations: dict[str, float] = {}
        self._lock = Lock()

    def store_video_context(
        self,
        job_id: str,
        *,
        transcript: str | None = None,
        video_duration: float | None = None,
    ) -> None:
        """Store video-level context (transcript, duration) for metadata enrichment."""
        with self._lock:
            if transcript and transcript.strip():
                self._transcripts[job_id] = transcript.strip()
            if video_duration is not None:
                self._durations[job_id] = video_duration

    def get(self, job_id: str) -> VideoMetadata | None:
        with self._lock:
            return self._metadata.get(job_id)

    def generate(
        self,
        job_id: str,
        request: MetadataCreate | None = None,
        log: Callable[[JobLogLevel, str], None] | None = None,
        fallback: bool = False,
        llm_provider: LLMProvider | None = None,
    ) -> VideoMetadata | None:
        job = job_store.get(job_id)
        if job is None:
            raise MetadataNotFoundError("Job not found")

        _log_job(log, "INFO", f"[Job {job_id}] Workflow transition: GENERATING_METADATA")
        logger.info("[Job %s] Workflow transition: GENERATING_METADATA", job_id)
        _log_job(log, "INFO", f"[Job {job_id}] Generating AI metadata...")
        logger.info("[Job %s] Generating metadata (fallback=%s)", job_id, fallback)

        job_store.set_metadata_status(job_id, "generating")
        job_store.set_progress(job_id, 96, "GENERATING_METADATA")

        context = self._build_generation_context(job_id, request)

        if not AI_ENABLED:
            logger.info("[Job %s] AI_ENABLED is False; using fallback metadata", job_id)
            fallback_metadata = self._generate_fallback_metadata(job_id, context, log)
            with self._lock:
                self._metadata[job_id] = fallback_metadata
            job_store.set_metadata_status(job_id, "available")
            return fallback_metadata

        if llm_provider is not None:
            try:
                user_prompt = USER_PROMPT_TEMPLATE.format(
                    profile_section=f"Profile Context: {context.creative_profile_prompt}",
                    instructions_section=f"User Instructions / Title Seed: {context.title_seed}",
                    transcript_section=f"Transcript:\n{context.transcript}",
                )
                res = llm_provider.generate(prompt=user_prompt, system_prompt=context.system_prompt)
                parsed = parse_json_response(res.content)
                title = str(parsed.get("title") or "").strip()
                description = str(parsed.get("description") or "").strip()
                if not title or not description:
                    raise ValueError("AI response missing title or description")

                metadata = VideoMetadata(
                    job_id=job_id,
                    generated_at=datetime.now(timezone.utc),
                    provider=res.model or "openai-oauth",
                    model=res.model or "gpt-5.6-sol",
                    editable=True,
                    title=title,
                    description=description,
                    tags=[str(t) for t in parsed.get("tags", []) if str(t).strip()],
                    hashtags=[str(h) for h in parsed.get("hashtags", []) if str(h).strip()],
                    thumbnail_prompt=str(parsed.get("thumbnail_prompt") or ""),
                )
                with self._lock:
                    self._metadata[job_id] = metadata
                job_store.set_metadata_status(job_id, "available")
                _log_job(log, "INFO", f"[Job {job_id}] Workflow transition: METADATA_READY")
                logger.info("[Job %s] Workflow transition: METADATA_READY", job_id)
                logger.info("[Job %s] Database write result: Successfully stored metadata for job %s", job_id, job_id)
                return metadata
            except Exception as exc:
                logger.error("[Job %s] Metadata provider error: %s", job_id, exc, exc_info=True)
                if not fallback:
                    job_store.set_metadata_status(job_id, "unavailable")
                    return None
                fallback_metadata = self._generate_fallback_metadata(job_id, context, log)
                with self._lock:
                    self._metadata[job_id] = fallback_metadata
                job_store.set_metadata_status(job_id, "available")
                return fallback_metadata

        max_retries = 2
        provider = get_metadata_provider()
        metadata = None

        for attempt in range(max_retries + 1):
            if attempt > 0:
                job_store.set_metadata_status(job_id, "generating")
                job_store.set_progress(job_id, 96, "RETRYING_METADATA")
                _log_job(log, "INFO", f"[Job {job_id}] Workflow transition: RETRYING_METADATA (Retry attempt {attempt}/{max_retries})")
                logger.info("[Job %s] Workflow transition: RETRYING_METADATA (attempt %d/%d)", job_id, attempt, max_retries)
                delay = 0.01 if "pytest" in sys.modules else 1.0 * (2 ** (attempt - 1))
                time.sleep(delay)

            try:
                _log_job(log, "INFO", f"[Job {job_id}] Using provider: {_display_provider_name(provider.name)} (Model: {provider.model})")
                logger.info("[Job %s] Provider: %s, Model: %s", job_id, provider.name, provider.model)
                response_dict = provider.generate(context)
                try:
                    response = MetadataResponse.model_validate(response_dict)
                except ValidationError as val_exc:
                    raise SchemaValidationFailure(f"Schema validation failure: {val_exc}") from val_exc

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
                _log_job(log, "INFO", f"[Job {job_id}] Workflow transition: METADATA_READY")
                logger.info("[Job %s] Workflow transition: METADATA_READY", job_id)
                logger.info("[Job %s] Database write result: Successfully stored metadata for job %s", job_id, job_id)
                _log_job(log, "INFO", f"[Job {job_id}] Database persistence: success")
                return metadata
            except Exception as exc:
                logger.warning("[Job %s] Attempt %d failed: %s", job_id, attempt, exc)
                if attempt == max_retries:
                    logger.error("[Job %s] Metadata provider error: %s", job_id, exc, exc_info=True)
                    _log_job(log, "ERROR", f"[Job {job_id}] AI metadata generation failed: {exc}")
                    job_store.set_progress(job_id, 96, "METADATA_FAILED")
                    _log_job(log, "INFO", f"[Job {job_id}] Workflow transition: METADATA_FAILED")
                    logger.info("[Job %s] Workflow transition: METADATA_FAILED", job_id)
                    if not fallback:
                        job_store.set_metadata_status(job_id, "unavailable")
                        return None

        if metadata is None:
            if fallback:
                job_store.set_progress(job_id, 96, "FALLBACK_METADATA")
                _log_job(log, "INFO", f"[Job {job_id}] Workflow transition: FALLBACK_METADATA")
                logger.info("[Job %s] Workflow transition: FALLBACK_METADATA", job_id)
                fallback_metadata = self._generate_fallback_metadata(job_id, context, log)
                with self._lock:
                    self._metadata[job_id] = fallback_metadata
                job_store.set_metadata_status(job_id, "available")
                return fallback_metadata
            else:
                job_store.set_metadata_status(job_id, "unavailable")
                return None

        return metadata

    def _generate_fallback_metadata(
        self,
        job_id: str,
        context: Any = None,
        log: Callable[[JobLogLevel, str], None] | None = None,
        original_title: str | None = None,
        title_seed: str | None = None,
        fallback_description: str = "",
    ) -> VideoMetadata:
        title = None
        if context is not None and isinstance(context, MetadataGenerationContext):
            if context.title_seed and context.title_seed.strip():
                title = context.title_seed.strip()
            elif context.original_title and context.original_title.strip():
                title = context.original_title.strip()
            elif context.output_filename:
                title = Path(context.output_filename).stem.replace("_", " ").replace("-", " ").strip()
        else:
            title = title_seed or original_title or "CashCow Video"

        if not title:
            title = "CashCow Video"

        from app.models.metadata import TITLE_MAX_LENGTH
        if len(title) > TITLE_MAX_LENGTH:
            title = title[:TITLE_MAX_LENGTH].rstrip(" .")

        fallback_metadata = VideoMetadata(
            job_id=job_id,
            generated_at=datetime.now(timezone.utc),
            provider="fallback",
            model="fallback",
            editable=True,
            title=title,
            description=fallback_description,
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
        """Manually trigger metadata regeneration for an existing job."""
        return self.generate(job_id, fallback=True)

    def _build_generation_context(
        self,
        job_id: str,
        request: MetadataCreate | None,
    ) -> MetadataGenerationContext:
        job = job_store.get(job_id)
        if job is None:
            raise MetadataNotFoundError("Job not found")

        with self._lock:
            transcript = self._transcripts.get(job_id)
            video_duration = self._durations.get(job_id)

        detected_language = _detect_language(transcript)
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
            video_duration=video_duration,
            transcript=transcript,
            detected_language=detected_language,
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
            video_duration=video_duration,
            transcript=transcript,
            detected_language=detected_language,
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
    display_names = {"openai-oauth": "OpenAI OAuth", "gemini": "Gemini", "mock": "Mock"}
    return display_names.get(name.lower(), name.capitalize())
