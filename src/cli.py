"""CLI commands and interface definitions using Typer and Rich.

Defines commands for run, config, version, and system diagnostics (doctor).
"""

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
