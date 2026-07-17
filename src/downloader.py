"""Production-grade media downloader engine powered by yt-dlp.

Implements single video, playlist, and batch concurrent download pipelines
with automated file collision safety, daily log tracking, and Rich progress bars.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import time
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlparse

import yt_dlp
from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn, TimeRemainingColumn, TransferSpeedColumn

from src.config import Settings
from src.exceptions import DownloadError, FolderError, InvalidUrlError
from src.logger import get_logger
from src.models import DownloadResult
from src.utils import check_write_permission, ensure_directory, get_current_timestamp


class Downloader:
    """Core media downloader utilizing yt-dlp API and ThreadPoolExecutor.

    Maintains safe writes, metadata preservation, connection retries, and batching.
    """

    _SOCKET_TIMEOUT: int = 30

    def __init__(self, settings: Settings) -> None:
        """Initialize the downloader.

        Args:
            settings: Loaded Pydantic configuration settings.

        Raises:
            FolderError: If the output directory is invalid or not writable.
        """
        self.settings = settings
        self.logger = get_logger("youtube_cashcow.downloader")
        self.output_dir = Path(settings.download.output_directory)

        try:
            ensure_directory(self.output_dir)
        except FolderError as e:
            raise FolderError(f"Could not access output directory: {e}") from e

        if not check_write_permission(self.output_dir):
            raise FolderError(
                f"Write permission denied for configured output directory: '{self.output_dir}'"
            )

    def validate_url(self, url: str) -> None:
        """Validate that the given URL is supported and well-formed.

        Args:
            url: The media URL to validate.

        Raises:
            InvalidUrlError: If the URL is empty or malformed.
        """
        if not url:
            raise InvalidUrlError("URL cannot be empty.")

        parsed = urlparse(url)
        if not parsed.scheme or parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise InvalidUrlError(
                f"Invalid URL: '{url}'. The URL must be a fully formed HTTP or HTTPS address."
            )

    def _build_ydl_options(
        self, progress_hook: Optional[Callable[[dict[str, Any]], None]] = None
    ) -> dict[str, Any]:
        """Construct the configuration dictionary for YoutubeDL.

        Args:
            progress_hook: Callback hook to intercept download updates.

        Returns:
            dict: Config parameters dictionary ready for yt-dlp YoutubeDL.
        """
        # The extension is deliberately left to yt-dlp.  The selected stream or
        # merger may produce webm, mkv, mp4, or an audio-only extension.
        outtmpl = str(self.output_dir / "%(title)s.%(ext)s")

        log_dir = Path(self.settings.logging.log_dir)
        archive_file = log_dir / "download_archive.txt"

        opts = {
            "format": self.settings.download.quality,
            "outtmpl": outtmpl,
            "merge_output_format": self.settings.download.format,
            "retries": self.settings.download.retries,
            "writethumbnail": self.settings.download.write_thumbnail,
            "writedescription": self.settings.download.write_description,
            "writesubtitles": self.settings.download.write_subtitles,
            "download_archive": str(archive_file),
            "overwrites": self.settings.download.overwrite,
            "noplaylist": True,
            "nocheckcertificate": True,
            "ignoreerrors": False,
            "logtostderr": False,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": self._SOCKET_TIMEOUT,
        }

        if progress_hook:
            opts["progress_hooks"] = [progress_hook]

        return opts

    def _extract_info(self, url: str, **extra_opts: Any) -> dict[str, Any]:
        """Extract metadata from a URL using yt-dlp.

        Args:
            url: The media URL.
            extra_opts: Additional yt-dlp options.

        Returns:
            dict: Extracted metadata.

        Raises:
            DownloadError: If metadata extraction fails.
        """
        ydl_opts: dict[str, Any] = {
            "nocheckcertificate": True,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": self._SOCKET_TIMEOUT,
        }
        ydl_opts.update(extra_opts)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            raise DownloadError(f"Failed to retrieve video information for: '{url}'")

        return info

    def _resolve_downloaded_path(self, ydl: yt_dlp.YoutubeDL, info: dict[str, Any]) -> Path:
        """Return the media path reported by yt-dlp after post-processing.

        ``filepath`` is updated by yt-dlp post-processors and is therefore the
        authoritative result for merged downloads.  Older yt-dlp versions may
        only expose a requested download path, so those values are retained as
        compatibility candidates.  The final stem fallback covers archive and
        no-overwrite skips where yt-dlp reports a proposed extension instead of
        the already-present container.
        """
        candidates: list[Path] = []

        for filepath in (info.get("filepath"), info.get("_filename")):
            if filepath:
                candidates.append(Path(filepath))

        for requested_download in info.get("requested_downloads") or []:
            filepath = requested_download.get("filepath")
            if filepath:
                candidates.append(Path(filepath))

        try:
            candidates.append(Path(ydl.prepare_filename(info)))
        except (KeyError, TypeError, ValueError):
            # Requested-download paths above are sufficient for yt-dlp versions
            # that cannot prepare a filename for post-processed metadata.
            pass

        for candidate in candidates:
            if candidate.is_file() and candidate.stat().st_size > 0:
                return candidate

        # A merger can change only the extension.  This fallback is intentionally
        # stem-based (never ``name.*``) and only follows a yt-dlp-reported path.
        for candidate in candidates:
            if not candidate.parent.is_dir():
                continue
            matches = [
                path for path in candidate.parent.glob(f"{candidate.stem}.*")
                if path.is_file() and path.stat().st_size > 0
                and path.suffix not in {".json", ".description", ".vtt", ".srt", ".part"}
            ]
            if matches:
                return max(matches, key=lambda path: path.stat().st_mtime)

        reported_path = candidates[0] if candidates else self.output_dir
        raise DownloadError(
            f"Download finalized but could not find a non-empty media file reported by yt-dlp: "
            f"'{reported_path}'"
        )

    def _create_progress_hook(
        self,
        progress: Optional[Progress],
        task_id: Optional[Any],
        title: str,
    ) -> Callable[[dict[str, Any]], None]:
        """Build a progress hook callback bound to the given task.

        Args:
            progress: Rich Progress object.
            task_id: ID of the associated progress bar.
            title: Video title for display.

        Returns:
            Callable: Progress hook function for yt-dlp.
        """
        def progress_hook(d: dict[str, Any]) -> None:
            if not progress or task_id is None:
                return
            display_title = d.get("info_dict", {}).get("title") or title
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                completed = d.get("downloaded_bytes", 0)
                progress.update(
                    task_id,
                    total=total,
                    completed=completed,
                    description=f"[cyan]Downloading: {display_title[:20]}...[/cyan]",
                )
            elif d["status"] == "finished":
                progress.update(
                    task_id, description=f"[green]Finalizing: {display_title[:20]}...[/green]"
                )

        return progress_hook

    def _save_metadata(self, info: dict[str, Any], url: str, target_file_path: Path, file_size: int) -> Path:
        """Persist download metadata as a JSON sidecar file.

        Args:
            info: Extracted media metadata.
            url: Original media URL.
            target_file_path: Path to the downloaded media file.
            file_size: Size of the downloaded file in bytes.

        Returns:
            Path: Path to the saved metadata file.
        """
        metadata_path = target_file_path.with_suffix(".json")
        metadata = {
            "title": info.get("title"),
            "uploader": info.get("uploader"),
            "duration": info.get("duration"),
            "resolution": f"{info.get('width')}x{info.get('height')}" if info.get("width") else None,
            "original_url": url,
            "downloaded_at": get_current_timestamp(format_str="%Y-%m-%d %H:%M:%S"),
            "format": info.get("format"),
            "extension": target_file_path.suffix.lstrip("."),
            "file_size": file_size,
        }

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4)

        self.logger.info(f"Metadata Saved: '{metadata_path}'")
        return metadata_path

    def _find_companion_files(
        self, target_file_path: Path, info: dict[str, Any]
    ) -> tuple[Optional[str], Optional[str], dict[str, str]]:
        """Locate companion files written by yt-dlp (description, thumbnail, subtitles).

        Args:
            target_file_path: Path to the downloaded media file.
            info: Extracted media metadata.

        Returns:
            tuple: (description_path, thumbnail_path, subtitles_dict)
        """
        description_path = target_file_path.with_suffix(".description")
        description_file = str(description_path) if description_path.exists() else None

        thumbnail_file: Optional[str] = None
        for thumb_ext in [".jpg", ".webp", ".png", ".jpeg"]:
            thumb_path = target_file_path.with_suffix(thumb_ext)
            if thumb_path.exists():
                thumbnail_file = str(thumb_path)
                break

        subtitles: dict[str, str] = {}
        requested_subtitles = info.get("requested_subtitles")
        if requested_subtitles:
            for lang, sub_info in requested_subtitles.items():
                sub_path = sub_info.get("filepath")
                if sub_path and Path(sub_path).exists():
                    subtitles[lang] = str(Path(sub_path).resolve())

        if not subtitles:
            for child in target_file_path.parent.iterdir():
                if child.name.startswith(target_file_path.stem) and child.suffix in (".vtt", ".srt"):
                    parts = child.name.split(".")
                    if len(parts) >= 3:
                        lang = parts[-2]
                        subtitles[lang] = str(child)

        return description_file, thumbnail_file, subtitles

    def download_video(
        self,
        url: str,
        progress: Optional[Progress] = None,
        task_id: Optional[Any] = None,
    ) -> DownloadResult:
        """Download a single video, preserve its metadata, and return structured info.

        Args:
            url: The media URL to download.
            progress: Rich Progress object for reporting status.
            task_id: ID of the progress bar associated with this task.

        Returns:
            DownloadResult: Pydantic model representing success or failure metadata.
        """
        start_time = time.time()
        self.logger.info(f"Download Started: {url}")

        try:
            self.validate_url(url)

            # extract_info(download=True) performs one network request and returns
            # the post-processed metadata needed to identify the actual file.
            progress_hook = self._create_progress_hook(progress, task_id, "media")
            ydl_opts = self._build_ydl_options(progress_hook)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info:
                    target_file_path = self._resolve_downloaded_path(ydl, info)

            if not info:
                # yt-dlp returns None for a download-archive skip, which gives
                # us no metadata or filepath to validate. Retry once without the
                # archive: this is necessary to distinguish a valid existing file
                # from a stale archive entry whose output was deleted or moved.
                self.logger.warning(
                    "yt-dlp skipped the URL via the download archive; retrying once "
                    "to locate or restore the media file."
                )
                retry_opts = dict(ydl_opts)
                retry_opts.pop("download_archive", None)
                with yt_dlp.YoutubeDL(retry_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if not info:
                        raise DownloadError(
                            "yt-dlp did not return metadata or a file path after an archive-skip retry."
                        )
                    target_file_path = self._resolve_downloaded_path(ydl, info)

            if info.get("_type") == "playlist" or "entries" in info:
                raise DownloadError(
                    "The URL points to a playlist. Please use playlist download features."
                )

            title = info.get("title", "untitled")
            self.logger.info(f"yt-dlp finalized destination path: '{target_file_path}'")

            download_duration = time.time() - start_time
            file_size = target_file_path.stat().st_size
            if file_size <= 0:
                raise DownloadError(f"Downloaded media file is empty: '{target_file_path}'")

            self._save_metadata(info, url, target_file_path, file_size)

            description_file, thumbnail_file, subtitles = self._find_companion_files(target_file_path, info)

            self.logger.info(f"Download Finished: '{target_file_path.name}' (Success)")

            return DownloadResult(
                success=True,
                url=url,
                title=title,
                duration=info.get("duration"),
                uploader=info.get("uploader"),
                file_path=str(target_file_path),
                thumbnail_path=thumbnail_file,
                description_path=description_file,
                subtitles=subtitles,
                download_time=download_duration,
                file_size=file_size,
            )

        except yt_dlp.utils.DownloadError as e:
            download_duration = time.time() - start_time
            err_msg = str(e)
            self.logger.error(f"Failure downloading '{url}': {err_msg}")

            clean_err = err_msg
            if "private" in err_msg.lower():
                clean_err = "The video is private and cannot be accessed."
            elif "confirm your age" in err_msg.lower() or "age-restricted" in err_msg.lower():
                clean_err = "The video is age-restricted and requires authorization."
            elif "unavailable" in err_msg.lower() or "not found" in err_msg.lower():
                clean_err = "The video is unavailable or has been removed."
            elif "space left on device" in err_msg.lower():
                clean_err = "Out of disk space on target output directory."
            elif "permission" in err_msg.lower():
                clean_err = "Permission denied while writing output files."

            return DownloadResult(
                success=False,
                url=url,
                download_time=download_duration,
                error=clean_err,
            )
        except Exception as e:
            download_duration = time.time() - start_time
            self.logger.error(f"Unexpected error downloading '{url}': {e}")
            return DownloadResult(
                success=False,
                url=url,
                download_time=download_duration,
                error=str(e),
            )

    def download_playlist(
        self, url: str, progress: Optional[Progress] = None
    ) -> list[DownloadResult]:
        """Download all entry videos listed within a playlist.

        Args:
            url: The playlist URL.
            progress: Rich Progress object for tracking downloads.

        Returns:
            list[DownloadResult]: List of individual download results.
        """
        self.validate_url(url)
        self.logger.info(f"Starting playlist download: {url}")

        playlist_info = self._extract_info(url, extract_flat="in_playlist")

        if "entries" not in playlist_info:
            raise DownloadError(f"URL is not recognized as a playlist: '{url}'")

        entries = list(playlist_info["entries"])
        self.logger.info(f"Playlist contains {len(entries)} items queued for download.")

        results = []
        for idx, entry in enumerate(entries, start=1):
            entry_url = entry.get("url") or entry.get("webpage_url")
            if not entry_url:
                video_id = entry.get("id")
                if video_id:
                    entry_url = f"https://www.youtube.com/watch?v={video_id}"

            if not entry_url:
                self.logger.warning(f"Could not resolve entry URL for index {idx}. Skipping.")
                results.append(
                    DownloadResult(
                        success=False,
                        url=url,
                        error=f"Could not extract entry URL at index {idx}",
                    )
                )
                continue

            title = entry.get("title", f"Playlist Entry {idx}")
            self.logger.info(f"Downloading playlist item {idx}/{len(entries)}: '{title}'")

            task_id = None
            if progress:
                task_id = progress.add_task(
                    description=f"[cyan]Queueing: {title[:20]}...[/cyan]", total=None
                )

            res = self.download_video(entry_url, progress=progress, task_id=task_id)
            results.append(res)

        return results

    def download_multiple(self, urls: list[str]) -> list[DownloadResult]:
        """Download multiple media URLs concurrently using a ThreadPoolExecutor.

        Args:
            urls: A list of media URLs to download.

        Returns:
            list[DownloadResult]: List of download results.
        """
        self.logger.info(f"Batch downloading started for {len(urls)} target URLs.")
        max_workers = self.settings.download.concurrent_downloads
        results: list[Optional[DownloadResult]] = [None] * len(urls)

        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_index = {}
                for idx, url in enumerate(urls):
                    task_id = progress.add_task(
                        description=f"[cyan]Queueing: {url[:20]}[/cyan]", total=None
                    )
                    future = executor.submit(
                        self.download_video,
                        url=url,
                        progress=progress,
                        task_id=task_id,
                    )
                    future_to_index[future] = idx

                for future in as_completed(future_to_index):
                    idx = future_to_index[future]
                    try:
                        res = future.result()
                        results[idx] = res
                    except Exception as e:
                        self.logger.exception(f"Unhandled thread error downloading {urls[idx]}: {e}")
                        results[idx] = DownloadResult(
                            success=False,
                            url=urls[idx],
                            error=f"Thread execution failed: {e}",
                        )

        return results
