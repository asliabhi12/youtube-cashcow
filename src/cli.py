"""CLI commands and interface definitions using Typer and Rich.

Defines commands for run, config, version, and system diagnostics (doctor).
"""

import json
import sys
from typing import Optional

import yaml
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.theme import Theme
from pathlib import Path

from src import constants
from src.config import load_config, Settings
from src.downloader import Downloader
from src.models import DownloadResult
from src.exceptions import CashCowError
from src.logger import get_logger, init_logger
from src.pipeline import Pipeline, PipelineRunner, default_registry
from src.performance import Benchmark, BenchmarkProfile, DecoderDetector, HardwareDetector, PerformanceEncoder
from src.processor import Processor
from src.validator import (
    initialize_directories,
    validate_dependencies,
    validate_directories,
    validate_python_version,
)

# Custom console theme for YouTube CashCow
custom_theme = Theme({
    "info": "dim cyan",
    "warning": "magenta",
    "danger": "bold red",
    "success": "bold green",
})
console = Console(theme=custom_theme)

app = typer.Typer(
    name=constants.APP_NAME.lower().replace(" ", "-"),
    help=f"[bold cyan]{constants.APP_NAME}[/bold cyan] - Automated Video Processing Platform CLI",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

pipeline_app = typer.Typer(help="Validate and run reusable media workflows.")
app.add_typer(pipeline_app, name="pipeline")


@app.command(name="hardware", help="Detect available FFmpeg hardware encoders.")
def hardware(config_file: str = typer.Option(constants.DEFAULT_SETTINGS_FILE, "--config", "-c")):
    try:
        settings = load_config(config_file)
        init_logger(settings.logging.level, settings.logging.log_dir, settings.app.debug)
        processor = Processor(settings)
        report = HardwareDetector(processor.runner).detect()
        table = Table(title="Hardware Detection")
        table.add_column("Property"); table.add_column("Value")
        table.add_row("Platform", f"{report.platform} ({report.machine})")
        table.add_row("Preferred backend", report.backend.value)
        table.add_row("Hardware available", "yes" if report.available else "no")
        table.add_row("Encoders", ", ".join(report.encoders) or "software fallback only")
        console.print(table)
    except Exception as exc:
        console.print(f"[danger]Hardware detection failed:[/danger] {exc}")
        raise typer.Exit(code=1)


@app.command(name="performance", help="Show active performance policy and detected encoder.")
def performance(config_file: str = typer.Option(constants.DEFAULT_SETTINGS_FILE, "--config", "-c")):
    try:
        settings = load_config(config_file)
        init_logger(settings.logging.level, settings.logging.log_dir, settings.app.debug)
        processor = Processor(settings)
        encoder = PerformanceEncoder.from_processor(processor)
        decision = encoder.decision()
        console.print(Panel(f"Backend: [bold]{decision.backend.value}[/bold]\nEncoder: [bold]{decision.encoder}[/bold]\nWorkers: {settings.performance.workers}\nFallback: {settings.performance.fallback}", title="Performance"))
    except Exception as exc:
        console.print(f"[danger]Performance report failed:[/danger] {exc}")
        raise typer.Exit(code=1)


def _format_duration(seconds: float | None) -> str:
    if not seconds:
        return "unknown"
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"


def _benchmark_report_table(results) -> Table:
    table = Table(title="Encoding Benchmark")
    for column in ("Encoder", "Decoder", "Preset", "Elapsed", "Avg FPS", "Speed", "Output", "CPU", "Memory", "Resolution", "Codec"):
        table.add_column(column)
    for result in results:
        metric = result.metrics
        table.add_row(
            result.codec,
            result.decoder.label if result.decoder else "-",
            result.preset or "-",
            f"{metric.duration_seconds:.2f}s",
            f"{metric.average_fps or 0:.1f}",
            f"{metric.encoding_speed or 0:.2f}x",
            f"{metric.output_size_bytes / 1_000_000:.2f} MB",
            f"{metric.cpu_percent or 0:.1f}%",
            f"{(metric.memory_bytes or 0) / 1_000_000:.1f} MB",
            result.resolution or "-",
            result.input_codec or "-",
        )
    return table


@app.command(name="benchmark", help="Benchmark encoding for a local video. Profiles: encoder (short clip), transcode (full file), quality (multi-preset).")
def benchmark(
    input_file: str = typer.Argument(..., help="Path to a local video file to benchmark."),
    profile: str = typer.Option("encoder", "--profile", "-p", help="encoder | transcode | quality"),
    duration: Optional[float] = typer.Option(None, "--duration", "-d", help="Clip length in seconds (overrides the profile default; uses FFmpeg -t)."),
    json_output: Optional[str] = typer.Option(None, "--json", help="Write a machine-readable report to this JSON file."),
    config_file: str = typer.Option(constants.DEFAULT_SETTINGS_FILE, "--config", "-c"),
):
    try:
        settings = load_config(config_file)
        if not settings.performance.benchmark:
            raise RuntimeError("Benchmarks are disabled in performance.benchmark")
        init_logger(settings.logging.level, settings.logging.log_dir, settings.app.debug)
        try:
            selected = BenchmarkProfile(profile.lower())
        except ValueError:
            raise RuntimeError(f"Unknown profile '{profile}'. Choose encoder, transcode, or quality.")

        processor = Processor(settings)
        bench = Benchmark.from_processor(processor)

        # Inspect the input and detect the decode path before encoding, so the
        # user sees what is being measured rather than a bare elapsed number.
        info = processor.inspect(input_file)
        decoder = DecoderDetector(processor.runner).detect(info.codec, settings.ffmpeg.hwaccel)
        encode_backend = bench.encoder.decision().backend.value

        console.print(Panel(
            f"[bold white]Codec:[/bold white] {info.codec or 'unknown'}\n"
            f"[bold white]Resolution:[/bold white] {info.width or '?'}x{info.height or '?'}\n"
            f"[bold white]Duration:[/bold white] {_format_duration(info.duration)}\n"
            f"[bold white]FPS:[/bold white] {info.fps or 'unknown'}\n"
            f"[bold white]Bitrate:[/bold white] {f'{info.bitrate / 1000:.0f} kb/s' if info.bitrate else 'unknown'}",
            title="[bold cyan]Input[/bold cyan]", border_style="cyan",
        ))
        clip = duration if duration else ("full file" if selected is BenchmarkProfile.TRANSCODE else "30s")
        console.print(Panel(
            f"[bold white]Profile:[/bold white] {selected.value}\n"
            f"[bold white]Clip:[/bold white] {clip}\n"
            f"[bold white]Decode:[/bold white] {decoder.label}\n"
            f"[bold white]Encode:[/bold white] {encode_backend}",
            title="[bold cyan]Benchmark[/bold cyan]", border_style="cyan",
        ))

        results = bench.run(input_file, profile=selected, duration=duration)
        console.print(_benchmark_report_table(results))

        if json_output:
            payload = {
                "input": info.model_dump(mode="json"),
                "profile": selected.value,
                "results": [result.model_dump(mode="json") for result in results],
            }
            Path(json_output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            console.print(f"[success]Report written to[/success] {json_output}")
    except Exception as exc:
        console.print(f"[danger]Benchmark failed:[/danger] {exc}")
        raise typer.Exit(code=1)


@pipeline_app.command("validate", help="Validate a workflow YAML file without executing it.")
def validate_pipeline(workflow: str = typer.Argument(...), config_file: str = typer.Option(constants.DEFAULT_SETTINGS_FILE, "--config", "-c")):
    try:
        from src.pipeline.validator import validate_workflow
        pipeline = Pipeline.from_yaml(workflow)
        validate_workflow(pipeline.workflow, default_registry())
        console.print(f"[success]Workflow '{pipeline.workflow.name}' is valid.[/success]")
    except Exception as exc:
        console.print(f"[danger]Workflow validation failed:[/danger] {exc}")
        raise typer.Exit(code=1)


@pipeline_app.command("run", help="Run a workflow YAML file.")
def run_pipeline(workflow: str = typer.Argument(...), config_file: str = typer.Option(constants.DEFAULT_SETTINGS_FILE, "--config", "-c")):
    try:
        settings = load_config(config_file)
        init_logger(settings.logging.level, settings.logging.log_dir, settings.app.debug)
        result = PipelineRunner(settings, default_registry()).run(Pipeline.from_yaml(workflow).workflow)
        console.print(f"[success]Pipeline completed:[/success] {result.output_file}")
    except Exception as exc:
        console.print(f"[danger]Pipeline failed:[/danger] {exc}")
        raise typer.Exit(code=1)


@app.command(name="run", help="Initialize and run the base system.")
def run_app(
    config_file: str = typer.Option(
        constants.DEFAULT_SETTINGS_FILE,
        "--config",
        "-c",
        help="Path to the configuration settings.yaml file.",
    )
):
    """Initializes the directories, logger, environment, and config validations.

    This command runs the Phase 1 startup sequence.
    """
    console.print("[bold cyan]--------------------------------------------------[/bold cyan]")
    console.print(f"[bold white]Initializing {constants.APP_NAME}...[/bold white]")

    try:
        # 1. Load config
        console.print("Loading configuration...")
        settings = load_config(config_file)

        # 2. Create required directories
        console.print("Creating required directories...")
        initialize_directories(settings)

        # 3. Initialize Logger
        init_logger(
            level=settings.logging.level,
            log_dir=settings.logging.log_dir,
            debug_mode=settings.app.debug,
        )
        logger = get_logger("youtube_cashcow.cli")
        logger.info("Logger initialized.")

        # 4. Run environment & system checks
        validate_python_version()
        console.print("Environment validated.")

        validate_dependencies()
        validate_directories(settings)
        console.print("Configuration validated.")

        console.print("[success]Application initialized successfully.[/success]")
        console.print("[bold green]Ready for Phase 2.[/bold green]")
        console.print("[bold cyan]--------------------------------------------------[/bold cyan]")

    except CashCowError as e:
        console.print(f"\n[danger]Initialization Error:[/danger] {e.message}")
        console.print("[bold cyan]--------------------------------------------------[/bold cyan]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"\n[danger]Unexpected System Error:[/danger] {e}")
        console.print("[bold cyan]--------------------------------------------------[/bold cyan]")
        raise typer.Exit(code=1)


@app.command(name="config", help="Print the active application configuration.")
def show_config(
    config_file: str = typer.Option(
        constants.DEFAULT_SETTINGS_FILE,
        "--config",
        "-c",
        help="Path to settings.yaml",
    )
):
    """Loads and dumps the active settings.yaml values with validation."""
    try:
        settings = load_config(config_file)
        # Dump using pydantic model_dump, convert back to yaml for syntax-highlighted output
        settings_dict = settings.model_dump()
        yaml_output = yaml.dump(settings_dict, default_flow_style=False, sort_keys=False)
        
        syntax = Syntax(yaml_output, "yaml", theme="monokai", line_numbers=True)
        console.print(
            Panel(
                syntax,
                title=f"[bold green]{constants.APP_NAME} Configuration[/bold green]",
                subtitle=f"Source: {config_file}",
            )
        )
    except CashCowError as e:
        console.print(f"[danger]Configuration Error:[/danger] {e.message}")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[danger]Error loading configuration:[/danger] {e}")
        raise typer.Exit(code=1)


@app.command(name="version", help="Print the version of the application.")
def show_version():
    """Prints the application metadata and version details."""
    console.print(
        f"[bold cyan]{constants.APP_NAME}[/bold cyan] version [bold white]{constants.VERSION}[/bold white]"
    )


@app.command(name="doctor", help="Run diagnostic health checks on the environment and folder structures.")
def run_doctor(
    config_file: str = typer.Option(
        constants.DEFAULT_SETTINGS_FILE,
        "--config",
        "-c",
        help="Path to settings.yaml",
    )
):
    """Executes environment checks, file read/write verification, and settings integrity checks."""
    console.print(Panel.fit(f"[bold yellow]Running {constants.APP_NAME} Diagnostics[/bold yellow]"))
    
    table = Table(title="Diagnostic Checks Summary", show_header=True, header_style="bold magenta")
    table.add_column("Component", style="dim", width=25)
    table.add_column("Validation Scope", width=40)
    table.add_column("Status", justify="right")

    settings: Settings = None
    doctor_failed = False

    # Check 1: Python Version
    try:
        validate_python_version()
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        table.add_row(
            "Python Runtime",
            f"Checking Python >= {'.'.join(map(str, constants.MIN_PYTHON_VERSION))} (Found {py_ver})",
            "[green]PASS[/green]",
        )
    except Exception as e:
        table.add_row("Python Runtime", "Version requirements check", f"[red]FAIL ({e})[/red]")
        doctor_failed = True

    # Check 2: Core Dependencies
    try:
        validate_dependencies()
        table.add_row(
            "Dependencies",
            "Checking importable libraries (pydantic, yaml, typer, rich, dotenv)",
            "[green]PASS[/green]",
        )
    except Exception as e:
        table.add_row("Dependencies", "Import checks of core modules", f"[red]FAIL ({e})[/red]")
        doctor_failed = True

    # Check 3: Settings.yaml Loading & Validation
    try:
        settings = load_config(config_file)
        table.add_row(
            "Configuration",
            f"Parsing settings file '{config_file}' via Pydantic",
            "[green]PASS[/green]",
        )
    except Exception as e:
        table.add_row("Configuration", f"Reading/Validating {config_file}", f"[red]FAIL ({e})[/red]")
        doctor_failed = True

    # Check 4: Workspace Directories Existence and RW Access
    if settings:
        try:
            # First ensure directories exist (doctor should attempt initialization if missing)
            initialize_directories(settings)
            validate_directories(settings)
            table.add_row(
                "Storage Directories",
                "Checking directories existence and write/read access permissions",
                "[green]PASS[/green]",
            )
        except Exception as e:
            table.add_row("Storage Directories", "Directory permissions & presence", f"[red]FAIL ({e})[/red]")
            doctor_failed = True
    else:
        table.add_row(
            "Storage Directories",
            "Checking directories (Skipped - settings.yaml invalid)",
            "[yellow]SKIP[/yellow]",
        )
        doctor_failed = True

    console.print(table)

    if doctor_failed:
        console.print("\n[danger]❌ Diagnostics found issues with the system setup. Please resolve above failures.[/danger]")
        raise typer.Exit(code=1)
    else:
        console.print("\n[success]✨ All health checks passed successfully! System is production-ready.[/success]")


@app.command(name="download", help="Download media files from a URL, a list of URLs in a file, or a playlist.")
def download(
    url: Optional[str] = typer.Argument(None, help="The URL of the video or media to download."),
    file: Optional[str] = typer.Option(
        None,
        "--file",
        "-f",
        help="Path to a text file containing target URLs (one per line).",
    ),
    playlist: bool = typer.Option(
        False,
        "--playlist",
        "-p",
        help="Treat the provided URL as a playlist URL and download all entries.",
    ),
    config_file: str = typer.Option(
        constants.DEFAULT_SETTINGS_FILE,
        "--config",
        "-c",
        help="Path to the configuration settings.yaml file.",
    ),
):
    """Downloads single videos, playlists, or batches of URLs.

    Validates parameters, registers rotating log channels, and streams real-time progress.
    """
    # 1. Load config and validate setup
    try:
        settings = load_config(config_file)
        init_logger(
            level=settings.logging.level,
            log_dir=settings.logging.log_dir,
            debug_mode=settings.app.debug,
        )
        logger = get_logger("youtube_cashcow.cli")
    except Exception as e:
        console.print(f"[danger]Failed to load configuration:[/danger] {e}")
        raise typer.Exit(code=1)

    # 2. Check input logic
    if url and file:
        console.print("[danger]Error:[/danger] Please provide either a URL argument OR a --file option, not both.")
        raise typer.Exit(code=1)
    if not url and not file:
        console.print("[danger]Error:[/danger] Missing input URL or target --file parameter. See --help.")
        raise typer.Exit(code=1)

    try:
        downloader = Downloader(settings)
    except Exception as e:
        console.print(f"[danger]Failed to initialize downloader:[/danger] {e}")
        raise typer.Exit(code=1)

    # 3. Handle batch file input
    if file:
        file_path = Path(file)
        if not file_path.exists():
            console.print(f"[danger]Error:[/danger] URL source file '{file_path}' does not exist.")
            raise typer.Exit(code=1)

        with open(file_path, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()

        urls = []
        for line in raw_lines:
            cleaned = line.strip()
            if cleaned and not cleaned.startswith("#"):
                urls.append(cleaned)

        if not urls:
            console.print("[warning]No active URLs found in target text file.[/warning]")
            raise typer.Exit(code=0)

        console.print(f"[bold cyan]Starting batch download for {len(urls)} URLs...[/bold cyan]")
        results = downloader.download_multiple(urls)
        
        # Display summary table
        table = Table(title="Batch Download Summary", show_header=True, header_style="bold magenta")
        table.add_column("URL", width=30)
        table.add_column("Status", width=10)
        table.add_column("Title / Details", width=35)
        table.add_column("Size (MB)", justify="right")

        for res in results:
            size_mb = f"{res.file_size / (1024 * 1024):.2f}" if res.file_size else "N/A"
            if res.success:
                table.add_row(res.url, "[green]SUCCESS[/green]", res.title or "", size_mb)
            else:
                table.add_row(res.url, "[red]FAILED[/red]", f"[red]{res.error}[/red]", "0.00")

        console.print(table)
        
        failures = sum(1 for r in results if not r.success)
        if failures > 0:
            console.print(f"\n[danger]❌ Completed with {failures} failures.[/danger]")
            raise typer.Exit(code=1)
        else:
            console.print("\n[success]✨ All batch downloads completed successfully![/success]")
            return

    # 4. Handle playlist URL input
    if playlist:
        console.print(f"[bold cyan]Extracting playlist items from: {url}[/bold cyan]")
        
        from rich.progress import Progress, BarColumn, TextColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            try:
                results = downloader.download_playlist(url, progress=progress)
            except Exception as e:
                console.print(f"[danger]Playlist download aborted:[/danger] {e}")
                raise typer.Exit(code=1)

        # Show playlist details summary
        table = Table(title="Playlist Download Summary", show_header=True, header_style="bold magenta")
        table.add_column("Title / URL", width=45)
        table.add_column("Status", width=10)
        table.add_column("File Size", justify="right")

        for res in results:
            size_mb = f"{res.file_size / (1024 * 1024):.2f} MB" if res.file_size else "N/A"
            if res.success:
                table.add_row(res.title or res.url, "[green]SUCCESS[/green]", size_mb)
            else:
                table.add_row(res.url, "[red]FAILED[/red]", f"[red]{res.error}[/red]")

        console.print(table)
        
        failures = sum(1 for r in results if not r.success)
        if failures > 0:
            console.print(f"\n[danger]❌ Playlist download completed with {failures} failures.[/danger]")
            raise typer.Exit(code=1)
        else:
            console.print("\n[success]✨ Playlist download completed successfully![/success]")
            return

    # 5. Handle single video URL input
    console.print(f"[bold cyan]Initializing download for URL: {url}[/bold cyan]")
    
    from rich.progress import Progress, BarColumn, TextColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task(description="Extracting metadata...", total=None)
        res = downloader.download_video(url, progress=progress, task_id=task_id)

    if res.success:
        size_mb = f"{res.file_size / (1024 * 1024):.2f} MB" if res.file_size else "Unknown"
        info_panel = (
            f"[bold white]Title:[/bold white] {res.title}\n"
            f"[bold white]Uploader:[/bold white] {res.uploader}\n"
            f"[bold white]Duration:[/bold white] {res.duration}s\n"
            f"[bold white]File Size:[/bold white] {size_mb}\n"
            f"[bold white]Output Path:[/bold white] [info]{res.file_path}[/info]\n"
            f"[bold white]Metadata Path:[/bold white] [info]{Path(res.file_path).with_suffix('.json')}[/info]\n"
        )
        if res.thumbnail_path:
            info_panel += f"[bold white]Thumbnail Path:[/bold white] [info]{res.thumbnail_path}[/info]\n"
        if res.description_path:
            info_panel += f"[bold white]Description Path:[/bold white] [info]{res.description_path}[/info]\n"
        if res.subtitles:
            info_panel += f"[bold white]Subtitles (Languages):[/bold white] {', '.join(res.subtitles.keys())}\n"

        console.print(
            Panel(
                info_panel.strip(),
                title="[success]✓ Media Download Success[/success]",
                border_style="success",
            )
        )
    else:
        console.print(f"[danger]❌ Download failed:[/danger] {res.error}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
