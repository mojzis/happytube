# Phase 3: CLI & Commands

**Timeline:** Day 5

## Overview

This phase creates a user-friendly command-line interface using **Typer** that allows users to run individual stages or the complete pipeline. The CLI will provide rich console output and progress tracking.

## Goals

- Set up Typer-based CLI framework
- Implement individual stage commands (fetch, assess, enhance)
- Implement run-all pipeline command
- Add status command to check progress
- Integrate Rich console for beautiful output
- Add progress bars and status indicators
- Enable configuration via CLI options

## CLI Design

### Command Structure

```bash
happytube fetch --category Music --max-videos 50
happytube assess --date 2025-11-09
happytube enhance --threshold 3
happytube run-all --category Music
happytube status --date 2025-11-09
```

### Why Typer?

- Built on top of Click with modern Python features
- Excellent type hints support
- Automatic help generation
- Better integration with Pydantic
- Cleaner, more Pythonic syntax
- Rich integration out of the box

## Tasks

### 1. Add Typer Dependency

```bash
poetry add typer[all]  # Includes rich integration
```

### 2. Set Up Poetry Script Entry Point

**File:** `pyproject.toml`

Add this to the `[tool.poetry.scripts]` section:

```toml
[tool.poetry.scripts]
happytube = "happytube.cli.commands:app"
```

### 3. Implement Main CLI Module

**File:** `happytube/cli/commands.py`

**Purpose:** Main entry point for all CLI commands.

**Implementation:**
```python
import typer
from rich.console import Console
from rich.panel import Panel
from datetime import date, datetime
from pathlib import Path

from happytube.config.settings import get_settings
from happytube.config.config_manager import ConfigManager
from happytube.utils.logging import setup_logging, get_logger

app = typer.Typer(
    name="happytube",
    help="🎥 HappyTube - YouTube happiness analyzer",
    add_completion=False,
)

console = Console()

@app.callback()
def main(
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        "-l",
        help="Set logging level (DEBUG, INFO, WARNING, ERROR)"
    )
):
    """
    HappyTube - YouTube happiness analyzer

    Fetches videos from YouTube, assesses their happiness level,
    enhances descriptions for happy content, and generates reports.
    """
    # Setup logging
    setup_logging(log_level.upper())
    logger = get_logger()

    # Validate settings
    try:
        settings = get_settings()
        if not settings.has_all_credentials:
            console.print("[red]Error: Missing API credentials in .env file[/red]")
            console.print("Required: YTKEY (YouTube API) and ANTHROPIC_API_KEY")
            raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def fetch(
    category: str = typer.Option(
        "Music",
        "--category",
        "-c",
        help="YouTube search config name (from youtube.yaml)"
    ),
    max_videos: int = typer.Option(
        50,
        "--max-videos",
        "-m",
        help="Maximum number of videos to fetch"
    ),
    target_date: str = typer.Option(
        None,
        "--date",
        "-d",
        help="Target date (YYYY-MM-DD), defaults to today"
    )
):
    """
    Fetch videos from YouTube and save as markdown files.

    Example:
        happytube fetch --category Music --max-videos 50
    """
    import asyncio
    from happytube.stages.fetch import FetchStage

    logger = get_logger()

    # Parse date
    run_date = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else date.today()

    console.print(Panel(
        f"[bold blue]🔍 Fetching videos for {run_date}[/bold blue]\n"
        f"Category: {category}\n"
        f"Max videos: {max_videos}",
        title="Fetch Stage"
    ))

    # Load config
    cm = ConfigManager()
    youtube_config_name = f"{category.lower()}_search"
    youtube_configs = cm.load_base_config('youtube')

    if youtube_config_name not in youtube_configs.get('searches', {}):
        console.print(f"[red]Error: Unknown category '{category}'[/red]")
        console.print(f"Available: {list(youtube_configs.get('searches', {}).keys())}")
        raise typer.Exit(code=1)

    youtube_config = youtube_configs['searches'][youtube_config_name]['params']

    # Run stage
    stage = FetchStage(youtube_config, max_videos)
    result = asyncio.run(stage.run(run_date))

    # Display results
    if result.get("status") == "success":
        console.print(f"[green]✓ Successfully fetched {result['new_videos']} videos[/green]")
    else:
        console.print(f"[yellow]⚠ {result.get('status', 'Unknown status')}[/yellow]")

    if result.get("errors", 0) > 0:
        console.print(f"[yellow]⚠ {result['errors']} errors occurred[/yellow]")


@app.command()
def assess(
    target_date: str = typer.Option(
        None,
        "--date",
        "-d",
        help="Target date (YYYY-MM-DD), defaults to today"
    ),
    prompt_version: str = typer.Option(
        "happiness_v2",
        "--prompt",
        "-p",
        help="Prompt version to use (from prompts.yaml)"
    ),
    batch_size: int = typer.Option(
        20,
        "--batch-size",
        "-b",
        help="Number of videos to process per API call"
    )
):
    """
    Assess happiness scores for fetched videos using Claude API.

    Example:
        happytube assess --date 2025-11-09
    """
    import asyncio
    from happytube.stages.assess import AssessStage

    # Parse date
    run_date = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else date.today()

    console.print(Panel(
        f"[bold yellow]🎯 Assessing happiness for {run_date}[/bold yellow]\n"
        f"Prompt version: {prompt_version}\n"
        f"Batch size: {batch_size}",
        title="Assess Stage"
    ))

    # Load config
    cm = ConfigManager()
    prompts_config = cm.load_base_config('prompts')

    if prompt_version not in prompts_config.get('prompts', {}):
        console.print(f"[red]Error: Unknown prompt version '{prompt_version}'[/red]")
        raise typer.Exit(code=1)

    prompt_config = prompts_config['prompts'][prompt_version]

    # Run stage
    stage = AssessStage(prompt_config, batch_size)
    result = asyncio.run(stage.run(run_date))

    # Display results
    if result.get("status") == "success":
        console.print(f"[green]✓ Successfully assessed {result['assessed_videos']} videos[/green]")
    else:
        console.print(f"[yellow]⚠ {result.get('status', 'Unknown status')}[/yellow]")


@app.command()
def enhance(
    target_date: str = typer.Option(
        None,
        "--date",
        "-d",
        help="Target date (YYYY-MM-DD), defaults to today"
    ),
    threshold: int = typer.Option(
        3,
        "--threshold",
        "-t",
        help="Minimum happiness score for enhancement"
    ),
    prompt_version: str = typer.Option(
        "enhance_description_v1",
        "--prompt",
        "-p",
        help="Prompt version to use (from prompts.yaml)"
    )
):
    """
    Enhance descriptions for videos with high happiness scores.

    Example:
        happytube enhance --threshold 3
    """
    import asyncio
    from happytube.stages.enhance import EnhanceStage

    # Parse date
    run_date = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else date.today()

    console.print(Panel(
        f"[bold magenta]✨ Enhancing descriptions for {run_date}[/bold magenta]\n"
        f"Threshold: {threshold}\n"
        f"Prompt version: {prompt_version}",
        title="Enhance Stage"
    ))

    # Load config
    cm = ConfigManager()
    prompts_config = cm.load_base_config('prompts')

    if prompt_version not in prompts_config.get('prompts', {}):
        console.print(f"[red]Error: Unknown prompt version '{prompt_version}'[/red]")
        raise typer.Exit(code=1)

    prompt_config = prompts_config['prompts'][prompt_version]

    # Run stage
    stage = EnhanceStage(prompt_config, threshold)
    result = asyncio.run(stage.run(run_date))

    # Display results
    if result.get("status") == "success":
        console.print(f"[green]✓ Successfully enhanced {result['enhanced_videos']} videos[/green]")
    else:
        console.print(f"[yellow]⚠ {result.get('status', 'Unknown status')}[/yellow]")


@app.command(name="run-all")
def run_all(
    category: str = typer.Option(
        "Music",
        "--category",
        "-c",
        help="YouTube search config name"
    ),
    max_videos: int = typer.Option(
        50,
        "--max-videos",
        "-m",
        help="Maximum number of videos to fetch"
    ),
    target_date: str = typer.Option(
        None,
        "--date",
        "-d",
        help="Target date (YYYY-MM-DD), defaults to today"
    ),
    threshold: int = typer.Option(
        3,
        "--threshold",
        "-t",
        help="Minimum happiness score for enhancement"
    )
):
    """
    Run complete pipeline: fetch → assess → enhance → report

    Example:
        happytube run-all --category Music --max-videos 50
    """
    import asyncio
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from happytube.stages.fetch import FetchStage
    from happytube.stages.assess import AssessStage
    from happytube.stages.enhance import EnhanceStage
    from happytube.stages.report import ReportStage

    # Parse date
    run_date = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else date.today()

    console.print(Panel(
        f"[bold green]🚀 Starting HappyTube pipeline for {run_date}[/bold green]\n"
        f"Category: {category}\n"
        f"Max videos: {max_videos}\n"
        f"Happiness threshold: {threshold}",
        title="Full Pipeline"
    ))

    # Load configs
    cm = ConfigManager()
    youtube_configs = cm.load_base_config('youtube')
    prompts_config = cm.load_base_config('prompts')

    youtube_config_name = f"{category.lower()}_search"
    if youtube_config_name not in youtube_configs.get('searches', {}):
        console.print(f"[red]Error: Unknown category '{category}'[/red]")
        raise typer.Exit(code=1)

    youtube_config = youtube_configs['searches'][youtube_config_name]['params']
    happiness_prompt = prompts_config['prompts']['happiness_v2']
    enhance_prompt = prompts_config['prompts']['enhance_description_v1']

    # Run pipeline with progress tracking
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console
    ) as progress:

        # Stage 1: Fetch
        task = progress.add_task("[blue]Fetching videos...", total=1)
        fetch_stage = FetchStage(youtube_config, max_videos)
        fetch_result = asyncio.run(fetch_stage.run(run_date))
        progress.update(task, completed=1)
        console.print(f"[green]✓ Fetch: {fetch_result.get('new_videos', 0)} videos[/green]")

        if fetch_result.get('new_videos', 0) == 0:
            console.print("[yellow]No videos fetched, stopping pipeline[/yellow]")
            raise typer.Exit(code=0)

        # Stage 2: Assess
        task = progress.add_task("[yellow]Assessing happiness...", total=1)
        assess_stage = AssessStage(happiness_prompt)
        assess_result = asyncio.run(assess_stage.run(run_date))
        progress.update(task, completed=1)
        console.print(f"[green]✓ Assess: {assess_result.get('assessed_videos', 0)} videos[/green]")

        # Stage 3: Enhance
        task = progress.add_task("[magenta]Enhancing descriptions...", total=1)
        enhance_stage = EnhanceStage(enhance_prompt, threshold)
        enhance_result = asyncio.run(enhance_stage.run(run_date))
        progress.update(task, completed=1)
        console.print(f"[green]✓ Enhance: {enhance_result.get('enhanced_videos', 0)} videos[/green]")

        # Stage 4: Report
        task = progress.add_task("[cyan]Generating report...", total=1)
        report_stage = ReportStage()
        report_result = asyncio.run(report_stage.run(run_date))
        progress.update(task, completed=1)
        console.print(f"[green]✓ Report: {report_result.get('videos_reported', 0)} videos[/green]")

    # Final summary
    console.print(Panel(
        f"[bold green]✓ Pipeline completed successfully![/bold green]\n\n"
        f"Fetched: {fetch_result.get('new_videos', 0)}\n"
        f"Assessed: {assess_result.get('assessed_videos', 0)}\n"
        f"Enhanced: {enhance_result.get('enhanced_videos', 0)}\n"
        f"Reported: {report_result.get('videos_reported', 0)}\n"
        f"Average Happiness: {report_result.get('avg_happiness', 0)}/5\n\n"
        f"Report: {report_result.get('report_path', 'N/A')}",
        title="Pipeline Summary"
    ))


@app.command()
def status(
    target_date: str = typer.Option(
        None,
        "--date",
        "-d",
        help="Target date (YYYY-MM-DD), defaults to today"
    )
):
    """
    Check processing status for a specific date.

    Example:
        happytube status --date 2025-11-09
    """
    from rich.table import Table

    # Parse date
    run_date = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else date.today()

    console.print(f"\n[bold]Status for {run_date}[/bold]\n")

    # Create table
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Stage", style="dim")
    table.add_column("Status", justify="center")
    table.add_column("Files", justify="right")

    # Check each stage
    stages = ["fetch", "assess", "enhance", "report"]

    for stage_name in stages:
        stage_dir = Path("stages") / stage_name / run_date.strftime("%Y-%m-%d")

        if stage_name == "report":
            report_file = Path("stages") / "report" / f"{run_date.strftime('%Y-%m-%d')}.html"
            status_icon = "✓" if report_file.exists() else "✗"
            status_text = "[green]Complete[/green]" if report_file.exists() else "[dim]Not started[/dim]"
            file_count = "1" if report_file.exists() else "0"
        else:
            if stage_dir.exists():
                files = list(stage_dir.glob("*.md"))
                status_icon = "✓"
                status_text = "[green]Complete[/green]"
                file_count = str(len(files))
            else:
                status_icon = "✗"
                status_text = "[dim]Not started[/dim]"
                file_count = "0"

        table.add_row(
            f"{status_icon} {stage_name.capitalize()}",
            status_text,
            file_count
        )

    console.print(table)
    console.print()


if __name__ == "__main__":
    app()
```

### 4. Create __init__.py Files

**File:** `happytube/cli/__init__.py`

```python
"""CLI module for HappyTube."""

from happytube.cli.commands import app

__all__ = ["app"]
```

### 5. Update Main Module

**File:** `happytube/__init__.py`

```python
"""HappyTube - YouTube happiness analyzer."""

__version__ = "1.0.0"
```

## Testing Phase 3

After completing this phase, test the CLI:

```bash
# Test help
happytube --help
happytube fetch --help
happytube assess --help

# Test individual commands
happytube fetch --category Music --max-videos 5
happytube assess
happytube enhance --threshold 3

# Test full pipeline
happytube run-all --category Music --max-videos 5

# Test status
happytube status
happytube status --date 2025-11-09

# Test with different log levels
happytube --log-level DEBUG fetch --max-videos 5
```

## CLI Features Summary

### Individual Stage Commands

1. **fetch** - Retrieve videos from YouTube
   - Configurable category
   - Max videos limit
   - Custom date support

2. **assess** - Score happiness with Claude
   - Custom prompt versions
   - Batch size control
   - Date-specific processing

3. **enhance** - Improve descriptions
   - Happiness threshold
   - Custom prompts
   - Date-specific processing

4. **run-all** - Complete pipeline
   - All fetch options
   - Automatic stage progression
   - Progress tracking with Rich
   - Summary output

5. **status** - Check progress
   - Stage completion status
   - File counts
   - Pretty table output

### Global Options

- `--log-level`: Control logging verbosity
- Automatic credential validation
- Rich console output
- Error handling with exit codes

## Dependencies Summary

Dependencies for this phase:

```bash
poetry add "typer[all]"  # Includes rich integration
```

## Success Criteria

- ✅ CLI accessible via `happytube` command
- ✅ All commands work with type hints
- ✅ Help text is clear and informative
- ✅ Rich console output looks good
- ✅ Progress bars work in run-all
- ✅ Status command shows table correctly
- ✅ Error handling provides useful messages
- ✅ Configuration validation on startup

## Typer vs Click Comparison

### Typer Advantages Used

1. **Type Hints**: Native Python type hints for options
2. **Automatic Validation**: Pydantic-style validation
3. **Better Defaults**: Sensible defaults without decorators
4. **Rich Integration**: Built-in rich support
5. **Modern Syntax**: More Pythonic code

### Example Comparison

**Click:**
```python
@click.command()
@click.option("--category", default="Music", help="YouTube category")
def fetch(category):
    pass
```

**Typer:**
```python
@app.command()
def fetch(
    category: str = typer.Option("Music", help="YouTube category")
):
    pass
```

## Next Phase

Phase 4 will focus on analytics and reporting enhancements, including better HTML templates and analytics dashboards.
